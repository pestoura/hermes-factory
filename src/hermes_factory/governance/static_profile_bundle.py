from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml

from hermes_factory.agents import compile_profile_distribution
from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlanBuilder
from hermes_factory.governance.eval_inventory import (
    EvalInventoryBuilder,
    discover_skill_artifacts,
)
from hermes_factory.governance.static_profile_evals import (
    StaticProfileEvalReport,
    execute_static_profile_evals,
)
from hermes_factory.traceability.registry import SemanticRegistry

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class StaticProfileEvalBundle:
    manifest_path: Path
    registry_path: Path
    report: StaticProfileEvalReport
    remaining_work_items: int


def _load_yaml(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"{path} must contain a mapping")
    return document


def build_static_profile_eval_bundle(
    *,
    repo_root: Path,
    output_dir: Path,
    candidate_sha: str,
) -> StaticProfileEvalBundle:
    if not _SHA_RE.fullmatch(candidate_sha):
        raise ValueError("candidate_sha must be an exact 40-character Git SHA")

    root = Path(repo_root)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    registry_path = destination / "static-profile-evals.db"
    manifest_path = destination / "static-profile-evals.json"
    if registry_path.exists() or manifest_path.exists():
        raise FileExistsError("static Profile eval bundle output already exists")

    catalog_document = _load_yaml(root / "agents/catalog-v1.2.yaml")
    catalog = catalog_document.get("catalog")
    if not isinstance(catalog, dict):
        raise TypeError("agent catalog must contain catalog mapping")
    active_candidates = catalog.get("active_candidates")
    if not isinstance(active_candidates, list) or not all(
        isinstance(agent_id, str) and agent_id.strip() for agent_id in active_candidates
    ):
        raise TypeError("agent catalog active_candidates must be a list of IDs")

    registry_document = _load_yaml(root / "skills/registry.yaml")
    skill_registry = registry_document.get("registry")
    if not isinstance(skill_registry, dict):
        raise TypeError("Skill registry must contain registry mapping")
    runtime_policies = _load_yaml(root / "agents/_shared/runtime-policies.yaml")
    skill_artifacts = discover_skill_artifacts(root / "skills", skill_registry)
    evidence_ref = f"ci:{candidate_sha}:static-profile-evals"

    semantic_registry = SemanticRegistry(registry_path)
    store = EvalEvidenceStore(semantic_registry)
    profile_digests: dict[str, str] = {}
    profile_states: dict[str, dict[str, str]] = {}

    with TemporaryDirectory(prefix="factory-static-profile-evals-") as temp_dir:
        profile_artifacts: dict[str, Path] = {}
        agent_documents: dict[str, dict[str, Any]] = {}
        profiles_root = Path(temp_dir) / "profiles"

        for agent_id in active_candidates:
            agent_document = _load_yaml(root / "agents" / agent_id / "agent.yaml")
            agent_documents[agent_id] = agent_document
            distribution = profiles_root / agent_id
            compile_profile_distribution(
                agent_document,
                (root / "agents" / agent_id / "SOUL.md").read_text(encoding="utf-8"),
                registry_document,
                distribution,
                cron_jobs=[],
                skill_artifacts=skill_artifacts,
                runtime_policies=runtime_policies,
            )
            profile_artifacts[agent_id] = distribution

        report = execute_static_profile_evals(
            store,
            profile_artifacts=profile_artifacts,
            agent_documents=agent_documents,
            skill_registry=registry_document,
            runtime_policies=runtime_policies,
            evidence_ref=evidence_ref,
        )

        for agent_id, distribution in sorted(profile_artifacts.items()):
            digest = digest_artifact(distribution)
            profile_digests[agent_id] = digest
            rows = semantic_registry.list_evidence(
                candidate=f"profile:{agent_id}:{digest}"
            )
            profile_states[agent_id] = {
                str(row["payload"]["dimension"]): str(row["state"])
                for row in rows
                if row["kind"] == "PROFILE_EVAL"
            }

        inventory = EvalInventoryBuilder(store).build(
            profile_artifacts=profile_artifacts,
            skill_artifacts=skill_artifacts,
            scheduled_profile_ids=(),
        )
        execution_plan = EvalExecutionPlanBuilder(store).build(
            inventory,
            scheduled_profile_ids=(),
        )
        remaining_work_items = len(execution_plan.items)

    manifest = {
        "schema": "hermes.factory/static-profile-eval-bundle/v1",
        "candidate_sha": candidate_sha.lower(),
        "evidence_ref": evidence_ref,
        "report": {
            "candidate_count": report.candidate_count,
            "evidence_count": report.evidence_count,
            "passed_count": report.passed_count,
            "failed_count": report.failed_count,
            "state": report.state,
        },
        "remaining_work_items": remaining_work_items,
        "profiles": {
            agent_id: {
                "digest": profile_digests[agent_id],
                "states": profile_states[agent_id],
            }
            for agent_id in sorted(profile_digests)
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return StaticProfileEvalBundle(
        manifest_path=manifest_path,
        registry_path=registry_path,
        report=report,
        remaining_work_items=remaining_work_items,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build exact-head static Profile eval evidence")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args(argv)

    bundle = build_static_profile_eval_bundle(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        candidate_sha=args.candidate_sha,
    )
    print(
        json.dumps(
            {
                "candidate_sha": args.candidate_sha.lower(),
                "evidence_count": bundle.report.evidence_count,
                "remaining_work_items": bundle.remaining_work_items,
                "state": bundle.report.state,
            },
            sort_keys=True,
        )
    )
    return 0 if bundle.report.state == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

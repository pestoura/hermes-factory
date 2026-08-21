from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import yaml

from hermes_factory.agents import compile_profile_distribution
from hermes_factory.governance.behavioral_eval_execution import (
    BehavioralEvalExecutionReport,
    BehavioralEvalExecutor,
    BehavioralEvalRuntime,
    CompositeBehavioralEvalRuntime,
    select_automated_eval_plan,
)
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import (
    EvalExecutionPlan,
    EvalExecutionPlanBuilder,
    EvalWorkItem,
)
from hermes_factory.governance.eval_inventory import (
    EvalInventoryBuilder,
    discover_skill_artifacts,
)
from hermes_factory.governance.hermes_behavioral_eval_runtime import (
    HermesBehavioralEvalRuntime,
    load_profile_behavioral_case_registry,
)
from hermes_factory.governance.hermes_behavioral_eval_runtime import (
    SubprocessEvalCommandRunner as ProfileEvalCommandRunner,
)
from hermes_factory.governance.hermes_skill_eval_runtime import (
    HermesSkillEvalRuntime,
    load_skill_behavioral_case_registry,
)
from hermes_factory.governance.hermes_skill_eval_runtime import (
    SubprocessEvalCommandRunner as SkillEvalCommandRunner,
)
from hermes_factory.traceability.registry import SemanticRegistry

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
_PLAN_SCHEMA = "hermes.factory/eval-execution-plan/v1"
_HANDOFF_SCHEMA = "hermes.factory/behavioral-eval-handoff/v1"
_BUNDLE_SCHEMA = "hermes.factory/automated-behavioral-eval-bundle/v1"


class AutomatedEvalBundleError(ValueError):
    pass


@dataclass(frozen=True)
class BehavioralEvalHandoff:
    candidate_sha: str
    static_evidence_ref: str
    work_item_count: int
    profile_work_item_count: int
    skill_work_item_count: int
    independent_review_count: int
    plan_digest: str
    plan: EvalExecutionPlan


@dataclass(frozen=True)
class AutomatedBehavioralEvalBundle:
    registry_path: Path
    report_path: Path
    residual_plan_path: Path
    execution_report: BehavioralEvalExecutionReport
    residual_plan: EvalExecutionPlan
    independent_review_count: int
    state: str


def _require_mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise AutomatedEvalBundleError(f"{label} must be a string-keyed mapping")
    return cast(dict[str, Any], value)


def _load_yaml(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AutomatedEvalBundleError(f"{label} must be a regular file")
    try:
        document: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AutomatedEvalBundleError(f"{label} could not be loaded") from exc
    return _require_mapping(document, label=label)


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AutomatedEvalBundleError(f"{label} must be a regular file")
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AutomatedEvalBundleError(f"{label} could not be loaded") from exc
    return _require_mapping(document, label=label)


def _nonnegative_int(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AutomatedEvalBundleError(f"{label} must be a non-negative integer")
    return value


def _plan_from_mapping(value: object) -> EvalExecutionPlan:
    payload = _require_mapping(value, label="behavioral eval plan")
    if payload.get("schema") != _PLAN_SCHEMA:
        raise AutomatedEvalBundleError("unsupported behavioral eval plan schema")
    raw_items = payload.get("items")
    raw_blockers = payload.get("blockers")
    state = payload.get("execution_state")
    execute = payload.get("execute")
    if not isinstance(raw_items, list):
        raise AutomatedEvalBundleError("behavioral eval plan items must be a list")
    if not isinstance(raw_blockers, list) or any(
        not isinstance(blocker, str) for blocker in raw_blockers
    ):
        raise AutomatedEvalBundleError("behavioral eval plan blockers must be strings")
    if not isinstance(state, str):
        raise AutomatedEvalBundleError("behavioral eval plan execution_state is required")
    if not isinstance(execute, bool):
        raise AutomatedEvalBundleError("behavioral eval plan execute must be boolean")
    if execute:
        raise AutomatedEvalBundleError("input behavioral eval plan must not request execution")

    items: list[EvalWorkItem] = []
    for index, raw_item in enumerate(raw_items):
        item = _require_mapping(raw_item, label=f"behavioral eval item {index}")
        kind = item.get("candidate_kind")
        candidate_id = item.get("candidate_id")
        candidate_digest = item.get("candidate_digest")
        check = item.get("check")
        independent = item.get("requires_independent_reviewer")
        if kind not in {"PROFILE", "SKILL"}:
            raise AutomatedEvalBundleError(f"behavioral eval item {index} candidate kind is invalid")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise AutomatedEvalBundleError(f"behavioral eval item {index} candidate id is invalid")
        if not isinstance(candidate_digest, str) or not _DIGEST_RE.fullmatch(candidate_digest):
            raise AutomatedEvalBundleError(
                f"behavioral eval item {index} candidate digest is invalid"
            )
        if not isinstance(check, str) or not check.strip():
            raise AutomatedEvalBundleError(f"behavioral eval item {index} check is invalid")
        if not isinstance(independent, bool):
            raise AutomatedEvalBundleError(
                f"behavioral eval item {index} independent-review marker is invalid"
            )
        items.append(
            EvalWorkItem(
                candidate_kind=kind,
                candidate_id=candidate_id,
                candidate_digest=candidate_digest.lower(),
                check=check,
                requires_independent_reviewer=independent,
            )
        )

    return EvalExecutionPlan(
        items=tuple(items),
        blockers=tuple(raw_blockers),
        execution_state=state,
        execute=False,
    )


def load_behavioral_eval_handoff(
    path: Path,
    *,
    expected_candidate_sha: str,
) -> BehavioralEvalHandoff:
    if not _SHA_RE.fullmatch(expected_candidate_sha):
        raise AutomatedEvalBundleError("expected candidate SHA must be an exact 40-character Git SHA")
    document = _load_json(Path(path), label="behavioral eval handoff")
    if document.get("schema") != _HANDOFF_SCHEMA:
        raise AutomatedEvalBundleError("unsupported behavioral eval handoff schema")

    candidate_sha = document.get("candidate_sha")
    if not isinstance(candidate_sha, str) or candidate_sha.lower() != expected_candidate_sha.lower():
        raise AutomatedEvalBundleError("behavioral eval handoff candidate does not match expected SHA")
    static_evidence_ref = document.get("static_evidence_ref")
    if not isinstance(static_evidence_ref, str) or not static_evidence_ref.strip():
        raise AutomatedEvalBundleError("behavioral eval handoff static evidence reference is required")

    plan = _plan_from_mapping(document.get("plan"))
    plan_digest = document.get("plan_digest")
    if not isinstance(plan_digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", plan_digest):
        raise AutomatedEvalBundleError("behavioral eval handoff plan digest is invalid")
    if plan.digest != plan_digest.lower():
        raise AutomatedEvalBundleError("behavioral eval handoff plan digest does not match plan")

    work_item_count = _nonnegative_int(document.get("work_item_count"), label="work_item_count")
    profile_count = _nonnegative_int(
        document.get("profile_work_item_count"), label="profile_work_item_count"
    )
    skill_count = _nonnegative_int(
        document.get("skill_work_item_count"), label="skill_work_item_count"
    )
    review_count = _nonnegative_int(
        document.get("independent_review_count"), label="independent_review_count"
    )
    observed_profile_count = sum(item.candidate_kind == "PROFILE" for item in plan.items)
    observed_skill_count = sum(item.candidate_kind == "SKILL" for item in plan.items)
    observed_review_count = sum(item.requires_independent_reviewer for item in plan.items)
    if (
        work_item_count != len(plan.items)
        or profile_count != observed_profile_count
        or skill_count != observed_skill_count
        or review_count != observed_review_count
    ):
        raise AutomatedEvalBundleError("behavioral eval handoff counts do not match plan")

    return BehavioralEvalHandoff(
        candidate_sha=candidate_sha.lower(),
        static_evidence_ref=static_evidence_ref,
        work_item_count=work_item_count,
        profile_work_item_count=profile_count,
        skill_work_item_count=skill_count,
        independent_review_count=review_count,
        plan_digest=plan_digest.lower(),
        plan=plan,
    )


def _verify_repo_head(repo_root: Path, candidate_sha: str) -> None:
    try:
        completed = subprocess.run(
            ("git", "-C", str(repo_root), "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AutomatedEvalBundleError("repository HEAD could not be verified") from exc
    if completed.returncode != 0:
        raise AutomatedEvalBundleError("repository HEAD could not be verified")
    observed = completed.stdout.strip().lower()
    if observed != candidate_sha.lower():
        raise AutomatedEvalBundleError(
            f"repository HEAD does not match candidate SHA: expected={candidate_sha.lower()} "
            f"observed={observed or 'UNKNOWN'}"
        )


def _candidate_sources(
    repo_root: Path,
    *,
    profiles_root: Path,
) -> tuple[dict[str, Path], dict[str, Path]]:
    catalog_document = _load_yaml(repo_root / "agents/catalog-v1.2.yaml", label="agent catalog")
    catalog = _require_mapping(catalog_document.get("catalog"), label="agent catalog mapping")
    active_candidates = catalog.get("active_candidates")
    if not isinstance(active_candidates, list) or not all(
        isinstance(agent_id, str) and agent_id.strip() for agent_id in active_candidates
    ):
        raise AutomatedEvalBundleError("agent catalog active_candidates must be a list of IDs")

    registry_document = _load_yaml(repo_root / "skills/registry.yaml", label="Skill registry")
    skill_registry = _require_mapping(
        registry_document.get("registry"), label="Skill registry mapping"
    )
    runtime_policies = _load_yaml(
        repo_root / "agents/_shared/runtime-policies.yaml",
        label="runtime policies",
    )
    skill_artifacts = discover_skill_artifacts(repo_root / "skills", skill_registry)
    profile_artifacts: dict[str, Path] = {}
    for agent_id in active_candidates:
        agent_document = _load_yaml(
            repo_root / "agents" / agent_id / "agent.yaml",
            label=f"Agent DNA for {agent_id}",
        )
        distribution = profiles_root / agent_id
        compile_profile_distribution(
            agent_document,
            (repo_root / "agents" / agent_id / "SOUL.md").read_text(encoding="utf-8"),
            registry_document,
            distribution,
            cron_jobs=[],
            skill_artifacts=skill_artifacts,
            runtime_policies=runtime_policies,
        )
        profile_artifacts[agent_id] = distribution
    return profile_artifacts, skill_artifacts


def _native_runtime(
    *,
    repo_root: Path,
    profile_artifacts: Mapping[str, Path],
    skill_artifacts: Mapping[str, Path],
    model: str,
    base_environment: Mapping[str, str],
    hermes_executable: str,
) -> BehavioralEvalRuntime:
    profile_cases = load_profile_behavioral_case_registry(
        repo_root / "evals/profile-behavioral-cases-v1.2.yaml",
        agents_root=repo_root / "agents",
    )
    skill_cases = load_skill_behavioral_case_registry(
        repo_root / "evals/skill-behavioral-cases-v1.2.yaml",
        skill_sources=skill_artifacts,
    )
    profile_runtime = HermesBehavioralEvalRuntime(
        runner=ProfileEvalCommandRunner(),
        profile_artifacts=profile_artifacts,
        cases=profile_cases,
        model=model,
        base_environment=base_environment,
        hermes_executable=hermes_executable,
    )
    skill_runtime = HermesSkillEvalRuntime(
        runner=SkillEvalCommandRunner(),
        skill_sources=skill_artifacts,
        cases=skill_cases,
        model=model,
        base_environment=base_environment,
        hermes_executable=hermes_executable,
    )
    return CompositeBehavioralEvalRuntime(
        profile_runtime=profile_runtime,
        skill_runtime=skill_runtime,
    )


def build_automated_behavioral_eval_bundle(
    *,
    repo_root: Path,
    static_bundle_dir: Path,
    output_dir: Path,
    candidate_sha: str,
    model: str,
    base_environment: Mapping[str, str],
    hermes_executable: str = "hermes",
    runtime: BehavioralEvalRuntime | None = None,
    verify_repo_head: bool = True,
) -> AutomatedBehavioralEvalBundle:
    if not _SHA_RE.fullmatch(candidate_sha):
        raise AutomatedEvalBundleError("candidate SHA must be an exact 40-character Git SHA")
    if not model.strip():
        raise AutomatedEvalBundleError("behavioral eval model is required")
    if not hermes_executable.strip():
        raise AutomatedEvalBundleError("Hermes executable is required")

    root = Path(repo_root).resolve()
    source = Path(static_bundle_dir).resolve()
    destination = Path(output_dir).resolve()
    if source.is_symlink() or not source.is_dir():
        raise AutomatedEvalBundleError("static bundle directory must be a regular directory")
    if destination.exists():
        raise AutomatedEvalBundleError("automated eval output directory already exists")
    if verify_repo_head:
        _verify_repo_head(root, candidate_sha)

    source_db = source / "static-profile-evals.db"
    handoff_path = source / "behavioral-eval-plan.json"
    if source_db.is_symlink() or not source_db.is_file():
        raise AutomatedEvalBundleError("static evidence database must be a regular file")
    handoff = load_behavioral_eval_handoff(
        handoff_path,
        expected_candidate_sha=candidate_sha,
    )
    selection = select_automated_eval_plan(handoff.plan)
    if selection.independent_review_count != handoff.independent_review_count:
        raise AutomatedEvalBundleError("independent review count does not match handoff")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    registry_path = destination / "automated-behavioral-evals.db"
    report_path = destination / "automated-behavioral-evals.json"
    residual_plan_path = destination / "residual-eval-plan.json"
    shutil.copy2(source_db, registry_path)

    store = EvalEvidenceStore(SemanticRegistry(registry_path))
    with TemporaryDirectory(prefix="factory-automated-eval-sources-") as temporary:
        profile_artifacts, skill_artifacts = _candidate_sources(
            root,
            profiles_root=Path(temporary) / "profiles",
        )
        selected_runtime = runtime or _native_runtime(
            repo_root=root,
            profile_artifacts=profile_artifacts,
            skill_artifacts=skill_artifacts,
            model=model,
            base_environment=base_environment,
            hermes_executable=hermes_executable,
        )
        execution_report = BehavioralEvalExecutor(store, selected_runtime).execute(
            selection.automated_plan
        )
        residual_inventory = EvalInventoryBuilder(store).build(
            profile_artifacts=profile_artifacts,
            skill_artifacts=skill_artifacts,
            scheduled_profile_ids=(),
        )
        residual_plan = EvalExecutionPlanBuilder(store).build(
            residual_inventory,
            scheduled_profile_ids=(),
        )

    residual_automated = tuple(
        item for item in residual_plan.items if not item.requires_independent_reviewer
    )
    residual_reviews = tuple(
        item for item in residual_plan.items if item.requires_independent_reviewer
    )
    if residual_automated:
        raise AutomatedEvalBundleError(
            "automated execution completed with non-independent NOT_RUN work remaining"
        )
    if len(residual_reviews) != selection.independent_review_count:
        raise AutomatedEvalBundleError("residual independent review set does not match source plan")

    if execution_report.state != "PASS" or residual_plan.blockers:
        state = "AUTOMATED_FAIL"
    elif residual_reviews:
        state = "AUTOMATED_PASS_REVIEW_REQUIRED"
    else:
        state = "PASS"

    residual_plan_path.write_text(
        json.dumps(residual_plan.to_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": _BUNDLE_SCHEMA,
        "candidate_sha": candidate_sha.lower(),
        "static_evidence_ref": handoff.static_evidence_ref,
        "source_plan_digest": handoff.plan_digest,
        "source_item_count": selection.source_item_count,
        "automated_item_count": selection.automated_item_count,
        "independent_review_count": len(residual_reviews),
        "execution": {
            "attempted_count": execution_report.attempted_count,
            "recorded_count": execution_report.recorded_count,
            "passed_count": execution_report.passed_count,
            "failed_count": execution_report.failed_count,
            "state": execution_report.state,
        },
        "residual_plan_digest": residual_plan.digest,
        "residual_blocker_count": len(residual_plan.blockers),
        "residual_item_count": len(residual_plan.items),
        "state": state,
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return AutomatedBehavioralEvalBundle(
        registry_path=registry_path,
        report_path=report_path,
        residual_plan_path=residual_plan_path,
        execution_report=execution_report,
        residual_plan=residual_plan,
        independent_review_count=len(residual_reviews),
        state=state,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute exact-SHA automated Factory behavioral evaluations"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--static-bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--hermes-executable", default="hermes")
    args = parser.parse_args(argv)

    bundle = build_automated_behavioral_eval_bundle(
        repo_root=args.repo_root,
        static_bundle_dir=args.static_bundle_dir,
        output_dir=args.output_dir,
        candidate_sha=args.candidate_sha,
        model=args.model,
        base_environment=os.environ,
        hermes_executable=args.hermes_executable,
        verify_repo_head=True,
    )
    print(
        json.dumps(
            {
                "candidate_sha": args.candidate_sha.lower(),
                "automated_attempted": bundle.execution_report.attempted_count,
                "automated_passed": bundle.execution_report.passed_count,
                "automated_failed": bundle.execution_report.failed_count,
                "independent_review_count": bundle.independent_review_count,
                "state": bundle.state,
            },
            sort_keys=True,
        )
    )
    return 0 if bundle.state in {"PASS", "AUTOMATED_PASS_REVIEW_REQUIRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

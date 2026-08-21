from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from hermes_factory.agents import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlan, EvalWorkItem
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState
from hermes_factory.traceability.registry import SemanticRegistry

_PACKET_SCHEMA = "hermes.factory/independent-review-packet/v1"
_DECISIONS_SCHEMA = "hermes.factory/independent-review-decisions/v1"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
_PROFILE_PRIOR = frozenset(
    {
        "routing_correctness",
        "refusal_authority_boundary",
        "tool_policy_projection",
        "skill_allowlist",
        "separation_of_duties",
        "handoff_evidence_quality",
        "escalation_correctness",
        "no_internal_mcp_dependency",
    }
)
_SKILL_PRIOR = frozenset(
    {"baseline_red", "skill_green", "variation_eval", "pressure_eval"}
)


class IndependentReviewBundleError(ValueError):
    pass


@dataclass(frozen=True)
class IndependentReviewPacket:
    output_path: Path
    candidate_sha: str
    packet_digest: str
    item_count: int


@dataclass(frozen=True)
class IndependentReviewImportResult:
    output_registry_path: Path
    recorded_count: int
    passed_count: int
    failed_count: int
    state: str


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    raw = Path(path)
    if raw.is_symlink() or not raw.is_file():
        raise IndependentReviewBundleError(f"{label} must be a regular file")
    try:
        document: object = json.loads(raw.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndependentReviewBundleError(f"{label} could not be loaded") from exc
    if not isinstance(document, dict) or any(not isinstance(key, str) for key in document):
        raise IndependentReviewBundleError(f"{label} must be a string-keyed mapping")
    return cast(dict[str, Any], document)


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _candidate_key(item: EvalWorkItem) -> str:
    prefix = "profile" if item.candidate_kind == "PROFILE" else "skill"
    return f"{prefix}:{item.candidate_id}:{item.candidate_digest}"


def _review_key(kind: str, candidate_id: str, candidate_digest: str) -> tuple[str, str, str]:
    return kind, candidate_id, candidate_digest


def _prior_evidence(
    registry: SemanticRegistry,
    item: EvalWorkItem,
) -> list[dict[str, str]]:
    expected = _PROFILE_PRIOR if item.candidate_kind == "PROFILE" else _SKILL_PRIOR
    observed: dict[str, dict[str, str]] = {}
    for row in registry.list_evidence(candidate=_candidate_key(item)):
        payload = row["payload"]
        if not isinstance(payload, dict):
            continue
        gate = payload.get("dimension") if item.candidate_kind == "PROFILE" else payload.get("gate")
        if not isinstance(gate, str) or gate not in expected:
            continue
        observed[gate] = {
            "check": gate,
            "state": str(row["state"]),
            "evidence_ref": str(payload.get("evidence_ref", "")),
            "evaluator": str(payload.get("evaluator", "")),
        }

    if set(observed) != expected:
        missing = sorted(expected - set(observed))
        raise IndependentReviewBundleError(
            f"prior evidence is incomplete for {item.candidate_id}: missing={missing!r}"
        )
    if any(record["state"] != "PASS" for record in observed.values()):
        raise IndependentReviewBundleError(
            f"prior evidence is not PASS for {item.candidate_id}"
        )
    if any(
        not record["evidence_ref"].strip() or not record["evaluator"].strip()
        for record in observed.values()
    ):
        raise IndependentReviewBundleError(
            f"prior evidence provenance is incomplete for {item.candidate_id}"
        )
    return [observed[key] for key in sorted(observed)]


def prepare_independent_review_bundle(
    *,
    registry_path: Path,
    residual_plan: EvalExecutionPlan,
    output_path: Path,
    candidate_sha: str,
) -> IndependentReviewPacket:
    if not _SHA_RE.fullmatch(candidate_sha):
        raise IndependentReviewBundleError("candidate SHA must be an exact 40-character Git SHA")
    raw_registry = Path(registry_path)
    raw_output = Path(output_path)
    if raw_registry.is_symlink() or not raw_registry.is_file():
        raise IndependentReviewBundleError("evaluation registry must be a regular file")
    if raw_output.is_symlink() or raw_output.exists():
        raise IndependentReviewBundleError("review packet output already exists")
    if residual_plan.blockers or residual_plan.execution_state != "NOT_RUN":
        raise IndependentReviewBundleError("review packet requires an unblocked NOT_RUN residual plan")
    if not residual_plan.items:
        raise IndependentReviewBundleError("review packet requires independent review items")
    if any(
        not item.requires_independent_reviewer or item.check != "independent_review"
        for item in residual_plan.items
    ):
        raise IndependentReviewBundleError("review packet may contain only independent review items")

    registry = SemanticRegistry(raw_registry)
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in residual_plan.items:
        if item.candidate_kind not in {"PROFILE", "SKILL"}:
            raise IndependentReviewBundleError("review item candidate kind is invalid")
        if not _DIGEST_RE.fullmatch(item.candidate_digest):
            raise IndependentReviewBundleError("review item candidate digest is invalid")
        key = _review_key(item.candidate_kind, item.candidate_id, item.candidate_digest)
        if key in seen:
            raise IndependentReviewBundleError("duplicate independent review item")
        seen.add(key)
        items.append(
            {
                "candidate_kind": item.candidate_kind,
                "candidate_id": item.candidate_id,
                "candidate_digest": item.candidate_digest,
                "check": "independent_review",
                "prior_evidence": _prior_evidence(registry, item),
                "required_decision": "PASS_OR_FAIL",
                "required_fields": ["state", "evidence_ref", "rationale"],
            }
        )

    body = {
        "schema": _PACKET_SCHEMA,
        "candidate_sha": candidate_sha.lower(),
        "item_count": len(items),
        "items": items,
    }
    packet_digest = _canonical_digest(body)
    document = {**body, "packet_digest": packet_digest}
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return IndependentReviewPacket(
        output_path=raw_output,
        candidate_sha=candidate_sha.lower(),
        packet_digest=packet_digest,
        item_count=len(items),
    )


def _load_and_verify_packet(path: Path) -> dict[str, Any]:
    packet = _load_json(path, label="independent review packet")
    if packet.get("schema") != _PACKET_SCHEMA:
        raise IndependentReviewBundleError("unsupported independent review packet schema")
    digest = packet.get("packet_digest")
    if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
        raise IndependentReviewBundleError("independent review packet digest is invalid")
    body = dict(packet)
    body.pop("packet_digest", None)
    if _canonical_digest(body) != digest.lower():
        raise IndependentReviewBundleError("independent review packet digest does not match content")
    return packet


def import_independent_review_decisions(
    *,
    registry_path: Path,
    packet_path: Path,
    decisions_path: Path,
    output_registry_path: Path,
) -> IndependentReviewImportResult:
    raw_registry = Path(registry_path)
    raw_output = Path(output_registry_path)
    if raw_registry.is_symlink() or not raw_registry.is_file():
        raise IndependentReviewBundleError("evaluation registry must be a regular file")
    if raw_output.is_symlink() or raw_output.exists():
        raise IndependentReviewBundleError("reviewed registry output already exists")

    packet = _load_and_verify_packet(Path(packet_path))
    decisions = _load_json(Path(decisions_path), label="independent review decisions")
    if decisions.get("schema") != _DECISIONS_SCHEMA:
        raise IndependentReviewBundleError("unsupported independent review decisions schema")
    if decisions.get("candidate_sha") != packet.get("candidate_sha"):
        raise IndependentReviewBundleError("review decisions candidate SHA does not match packet")
    if decisions.get("packet_digest") != packet.get("packet_digest"):
        raise IndependentReviewBundleError("review decisions packet digest does not match packet")
    reviewer_id = decisions.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise IndependentReviewBundleError("independent reviewer identity is required")

    packet_items = packet.get("items")
    decision_items = decisions.get("decisions")
    if not isinstance(packet_items, list) or not isinstance(decision_items, list):
        raise IndependentReviewBundleError("review packet and decisions must contain item lists")

    expected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw_item in packet_items:
        if not isinstance(raw_item, dict):
            raise IndependentReviewBundleError("review packet item is invalid")
        kind = raw_item.get("candidate_kind")
        candidate_id = raw_item.get("candidate_id")
        candidate_digest = raw_item.get("candidate_digest")
        if (
            kind not in {"PROFILE", "SKILL"}
            or not isinstance(candidate_id, str)
            or not isinstance(candidate_digest, str)
            or not _DIGEST_RE.fullmatch(candidate_digest)
        ):
            raise IndependentReviewBundleError("review packet candidate identity is invalid")
        key = _review_key(kind, candidate_id, candidate_digest)
        if key in expected:
            raise IndependentReviewBundleError("review packet contains duplicate candidate")
        expected[key] = raw_item

    parsed: list[tuple[tuple[str, str, str], str, str, str]] = []
    observed: set[tuple[str, str, str]] = set()
    for raw_decision in decision_items:
        if not isinstance(raw_decision, dict):
            raise IndependentReviewBundleError("review decision item is invalid")
        kind = raw_decision.get("candidate_kind")
        candidate_id = raw_decision.get("candidate_id")
        candidate_digest = raw_decision.get("candidate_digest")
        state = raw_decision.get("state")
        evidence_ref = raw_decision.get("evidence_ref")
        rationale = raw_decision.get("rationale")
        if (
            kind not in {"PROFILE", "SKILL"}
            or not isinstance(candidate_id, str)
            or not isinstance(candidate_digest, str)
        ):
            raise IndependentReviewBundleError("review decision candidate identity is invalid")
        key = _review_key(kind, candidate_id, candidate_digest)
        if key not in expected or key in observed:
            raise IndependentReviewBundleError("review decisions do not exactly cover packet items")
        if reviewer_id == candidate_id:
            raise IndependentReviewBundleError(f"self-review is forbidden for {candidate_id}")
        if state not in {"PASS", "FAIL"}:
            raise IndependentReviewBundleError("review decision state must be PASS or FAIL")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            raise IndependentReviewBundleError("review decision evidence_ref is required")
        if not isinstance(rationale, str) or not rationale.strip():
            raise IndependentReviewBundleError("review decision rationale is required")
        observed.add(key)
        parsed.append((key, state, evidence_ref.strip(), rationale.strip()))

    if observed != set(expected):
        raise IndependentReviewBundleError("review decisions do not exactly cover packet items")

    raw_output.parent.mkdir(parents=True, exist_ok=True)
    fd, staging_name = tempfile.mkstemp(prefix=".reviewed-evals-", dir=raw_output.parent)
    os.close(fd)
    staging = Path(staging_name)
    try:
        staging.unlink()
        shutil.copy2(raw_registry, staging)
        store = EvalEvidenceStore(SemanticRegistry(staging))
        passed = 0
        failed = 0
        for (kind, candidate_id, candidate_digest), state, evidence_ref, rationale in parsed:
            bound_ref = f"{evidence_ref}#packet={packet['packet_digest']}#rationale={hashlib.sha256(rationale.encode('utf-8')).hexdigest()}"
            if kind == "PROFILE":
                enum_state = ProfileEvalState(state)
                store.record_profile(
                    ProfileEvalEvidence(
                        profile_id=candidate_id,
                        profile_digest=candidate_digest,
                        dimension="independent_review",
                        state=enum_state,
                        evidence_ref=bound_ref,
                        evaluator=reviewer_id,
                    )
                )
            else:
                skill_state = SkillEvalState(state)
                store.record_skill(
                    SkillEvalEvidence(
                        skill_id=candidate_id,
                        source_digest=candidate_digest,
                        gate="independent_review",
                        state=skill_state,
                        evidence_ref=bound_ref,
                        evaluator=reviewer_id,
                    )
                )
            if state == "PASS":
                passed += 1
            else:
                failed += 1
        staging.rename(raw_output)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise

    return IndependentReviewImportResult(
        output_registry_path=raw_output,
        recorded_count=len(parsed),
        passed_count=passed,
        failed_count=failed,
        state="FAIL" if failed else "PASS",
    )

from pathlib import Path

from hermes_factory.governance.acceptance import (
    AcceptanceClass,
    AcceptanceDecisionState,
    AcceptanceEngine,
    AcceptancePolicy,
    AcceptanceRequest,
)
from hermes_factory.traceability import SemanticRegistry

CANDIDATE = "a" * 40
OTHER = "b" * 40


def _registry(tmp_path: Path) -> SemanticRegistry:
    return SemanticRegistry(tmp_path / "factory.db")


def _evidence(
    registry: SemanticRegistry,
    evidence_id: str,
    *,
    state: str = "PASS",
    candidate: str | None = CANDIDATE,
    actor_id: str = "ci-system",
    kind: str = "CI",
    decision: str | None = None,
) -> None:
    payload: dict[str, object] = {"actor_id": actor_id}
    if decision is not None:
        payload["decision"] = decision
    registry.record_evidence(
        evidence_id,
        kind=kind,
        state=state,
        candidate=candidate,
        payload=payload,
    )


def test_acceptance_is_derived_only_from_pass_exact_sha_evidence(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    _evidence(registry, "EV-CI")
    _evidence(
        registry,
        "EV-REVIEW",
        actor_id="reviewer-1",
        kind="INDEPENDENT_REVIEW",
    )
    engine = AcceptanceEngine(registry)

    decision = engine.derive(
        AcceptanceRequest(
            decision_id="ACC-REPOSITORY",
            acceptance_class=AcceptanceClass.REPOSITORY,
            candidate_sha=CANDIDATE,
            required_evidence_ids=("EV-CI", "EV-REVIEW"),
            independent_evidence_ids=("EV-REVIEW",),
            subject_actor_ids=frozenset({"implementer-1"}),
        ),
        policy=AcceptancePolicy(),
    )

    assert decision.state is AcceptanceDecisionState.ACCEPTED
    assert decision.acceptance_class is AcceptanceClass.REPOSITORY
    assert decision.candidate_sha == CANDIDATE
    persisted = registry.repository("AcceptanceDecision").get(
        "ACC-REPOSITORY",
        CANDIDATE,
    )
    assert persisted["payload"]["state"] == "ACCEPTED"


def test_not_run_stale_missing_or_sha_mismatch_can_never_accept(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    _evidence(registry, "EV-NOT-RUN", state="NOT_RUN")
    _evidence(registry, "EV-STALE", state="STALE")
    _evidence(registry, "EV-OTHER", candidate=OTHER)
    engine = AcceptanceEngine(registry)

    cases = (
        ("ACC-NOT-RUN", "EV-NOT-RUN"),
        ("ACC-STALE", "EV-STALE"),
        ("ACC-MISSING", "EV-MISSING"),
        ("ACC-MISMATCH", "EV-OTHER"),
    )
    for decision_id, evidence_id in cases:
        decision = engine.derive(
            AcceptanceRequest(
                decision_id=decision_id,
                acceptance_class=AcceptanceClass.INTEGRATION,
                candidate_sha=CANDIDATE,
                required_evidence_ids=(evidence_id,),
            ),
            policy=AcceptancePolicy(),
        )
        assert decision.state is AcceptanceDecisionState.HOLD


def test_independent_evidence_cannot_be_produced_by_subject_actor(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    _evidence(
        registry,
        "EV-SELF-REVIEW",
        actor_id="implementer-1",
        kind="INDEPENDENT_REVIEW",
    )
    engine = AcceptanceEngine(registry)

    decision = engine.derive(
        AcceptanceRequest(
            decision_id="ACC-UAT",
            acceptance_class=AcceptanceClass.UAT,
            candidate_sha=CANDIDATE,
            required_evidence_ids=("EV-SELF-REVIEW",),
            independent_evidence_ids=("EV-SELF-REVIEW",),
            subject_actor_ids=frozenset({"implementer-1"}),
        ),
        policy=AcceptancePolicy(),
    )

    assert decision.state is AcceptanceDecisionState.HOLD
    assert "separation" in decision.reason


def test_release_is_owner_reserved_and_cannot_be_auto_approved(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    _evidence(registry, "EV-LIVE", actor_id="runtime-observer", kind="LIVE")
    engine = AcceptanceEngine(registry)
    request = AcceptanceRequest(
        decision_id="ACC-RELEASE",
        acceptance_class=AcceptanceClass.RELEASE,
        candidate_sha=CANDIDATE,
        required_evidence_ids=("EV-LIVE",),
        owner_approval_evidence_id="EV-OWNER",
    )
    policy = AcceptancePolicy(
        owner_release_required=True,
        owner_actor_id="owner-1",
    )

    missing = engine.derive(request, policy=policy)
    assert missing.state is AcceptanceDecisionState.HOLD
    assert "owner" in missing.reason

    _evidence(
        registry,
        "EV-OWNER",
        actor_id="owner-1",
        kind="OWNER_DECISION",
        decision="APPROVE_RELEASE",
    )
    accepted = engine.derive(request, policy=policy)
    assert accepted.state is AcceptanceDecisionState.ACCEPTED


def test_release_rejects_owner_evidence_from_wrong_actor_or_wrong_decision(tmp_path: Path) -> None:
    for actor_id, owner_decision in (
        ("not-owner", "APPROVE_RELEASE"),
        ("owner-1", "APPROVE_OTHER"),
    ):
        registry = _registry(tmp_path / f"{actor_id}-{owner_decision}")
        _evidence(registry, "EV-LIVE", actor_id="runtime-observer", kind="LIVE")
        _evidence(
            registry,
            "EV-OWNER",
            actor_id=actor_id,
            kind="OWNER_DECISION",
            decision=owner_decision,
        )
        decision = AcceptanceEngine(registry).derive(
            AcceptanceRequest(
                decision_id="ACC-RELEASE",
                acceptance_class=AcceptanceClass.RELEASE,
                candidate_sha=CANDIDATE,
                required_evidence_ids=("EV-LIVE",),
                owner_approval_evidence_id="EV-OWNER",
            ),
            policy=AcceptancePolicy(
                owner_release_required=True,
                owner_actor_id="owner-1",
            ),
        )
        assert decision.state is AcceptanceDecisionState.HOLD

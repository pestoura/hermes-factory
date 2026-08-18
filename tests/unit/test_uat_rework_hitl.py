from hermes_factory.domain import UATState
from hermes_factory.workflow import (
    Finding,
    FindingClass,
    HITLRequest,
    HITLState,
    HumanDecision,
    ReworkController,
    ReworkState,
    UATExecution,
    UATMode,
    validate_human_decision,
)


def test_uat_only_pass_satisfies_acceptance_and_requires_candidate_for_automated():
    passed = UATExecution("UAT-1", 1, UATMode.AUTOMATED, UATState.PASS, "abc")
    assert passed.satisfies_acceptance() is True
    assert UATExecution("UAT-1", 1, UATMode.AUTOMATED, UATState.NOT_RUN, "abc").satisfies_acceptance() is False
    assert UATExecution("UAT-1", 1, UATMode.AUTOMATED, UATState.PASS, None).satisfies_acceptance() is False


def test_rework_is_bounded_for_same_cause():
    controller = ReworkController(max_same_cause_attempts=2)
    assert controller.next_state(Finding("F1", FindingClass.IMPLEMENTATION_DEFECT, 0)) is ReworkState.REWORK_ALLOWED
    assert controller.next_state(Finding("F1", FindingClass.IMPLEMENTATION_DEFECT, 1)) is ReworkState.REWORK_ALLOWED
    assert controller.next_state(Finding("F1", FindingClass.IMPLEMENTATION_DEFECT, 2)) is ReworkState.ESCALATE_DIAGNOSIS


def test_product_decision_finding_requires_hitl_without_code_retry():
    controller = ReworkController(max_same_cause_attempts=2)
    assert controller.next_state(Finding("F2", FindingClass.PRODUCT_DECISION_REQUIRED, 0)) is ReworkState.HITL_REQUIRED


def test_hitl_decision_must_match_request_identity_and_revision():
    req = HITLRequest("H1", 2, "ctx-7", "abc", "pedro", HITLState.PENDING)
    good = HumanDecision("H1", 2, "ctx-7", "abc", "pedro", "recommended")
    assert validate_human_decision(req, good) is True
    assert validate_human_decision(req, HumanDecision("H1", 1, "ctx-7", "abc", "pedro", "x")) is False
    assert validate_human_decision(req, HumanDecision("H1", 2, "ctx-8", "abc", "pedro", "x")) is False
    assert validate_human_decision(req, HumanDecision("H1", 2, "ctx-7", "def", "pedro", "x")) is False
    assert validate_human_decision(req, HumanDecision("H1", 2, "ctx-7", "abc", "other", "x")) is False


def test_non_pending_hitl_never_unlocks():
    for state in (HITLState.EXPIRED, HITLState.STALE, HITLState.CANCELLED, HITLState.DECIDED):
        req = HITLRequest("H1", 1, "ctx", None, "pedro", state)
        decision = HumanDecision("H1", 1, "ctx", None, "pedro", "x")
        assert validate_human_decision(req, decision) is False

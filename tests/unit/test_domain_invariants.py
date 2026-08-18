import pytest

from hermes_factory.domain import (
    EvidenceState,
    HandoffState,
    UATState,
    can_promote_handoff,
    can_satisfy_acceptance,
)


@pytest.mark.parametrize(
    "state",
    [
        EvidenceState.NOT_RUN,
        EvidenceState.UNKNOWN,
        EvidenceState.ABSENT,
        EvidenceState.STALE,
    ],
)
def test_non_proof_states_never_satisfy_acceptance(state):
    assert can_satisfy_acceptance(state) is False


def test_only_valid_evidence_pass_satisfies_acceptance():
    assert can_satisfy_acceptance(EvidenceState.PASS) is True


@pytest.mark.parametrize(
    "state",
    [
        UATState.NOT_REQUIRED,
        UATState.NOT_RUN,
        UATState.FAIL,
        UATState.BLOCKED,
        UATState.INCONCLUSIVE,
        UATState.STALE,
    ],
)
def test_only_uat_pass_is_a_uat_pass(state):
    assert state is not UATState.PASS


def test_handoff_promotes_only_from_ready():
    for state in HandoffState:
        assert can_promote_handoff(state) is (state is HandoffState.HANDOFF_READY)

from pathlib import Path

import yaml

from hermes_factory.governance.hermes_behavioral_eval_runtime import (
    BehavioralEvalRuntimeError,
    load_profile_behavioral_case_registry,
)

ROOT = Path(__file__).resolve().parents[2]
CASE_REGISTRY = ROOT / "evals/profile-behavioral-cases-v1.2.yaml"
AGENTS_ROOT = ROOT / "agents"
CATALOG = ROOT / "agents/catalog-v1.2.yaml"

AUTOMATED_DIMENSIONS = {
    "routing_correctness",
    "refusal_authority_boundary",
    "separation_of_duties",
    "handoff_evidence_quality",
    "escalation_correctness",
}
ALLOWED_OUTCOMES = {"TAKE", "REFUSE", "SEPARATE", "BLOCKED", "ESCALATE"}


def _active_profiles() -> set[str]:
    document = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    return set(document["catalog"]["active_candidates"])


def test_registry_covers_every_automatable_profile_behavioral_check_exactly_once() -> None:
    cases = load_profile_behavioral_case_registry(CASE_REGISTRY, agents_root=AGENTS_ROOT)
    active_profiles = _active_profiles()

    assert len(active_profiles) == 17
    assert len(cases) == 85
    assert set(cases) == {
        ("PROFILE", profile_id, dimension)
        for profile_id in active_profiles
        for dimension in AUTOMATED_DIMENSIONS
    }
    assert not any(key[2] == "independent_review" for key in cases)


def test_every_case_is_explicit_bounded_and_machine_gradeable() -> None:
    cases = load_profile_behavioral_case_registry(CASE_REGISTRY, agents_root=AGENTS_ROOT)

    for key, case in cases.items():
        assert case.key == key
        assert case.candidate_kind == "PROFILE"
        assert case.check in AUTOMATED_DIMENSIONS
        assert case.toolsets == ("vision",)
        assert case.skills == ()
        assert case.expected_response in ALLOWED_OUTCOMES
        assert 240 <= len(case.prompt) <= 1600
        assert "Reply with exactly one token from:" in case.prompt
        assert "correct answer" not in case.prompt.lower()
        assert "expected response" not in case.prompt.lower()
        assert case.timeout_seconds == 90


def test_registry_rejects_policy_reference_that_does_not_exist(tmp_path: Path) -> None:
    document = yaml.safe_load(CASE_REGISTRY.read_text(encoding="utf-8"))
    first_profile = next(iter(document["profiles"]))
    document["profiles"][first_profile]["routing_correctness"]["policy_ref"] = (
        "authority.deny:this_rule_does_not_exist"
    )
    tampered = tmp_path / "cases.yaml"
    tampered.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    try:
        load_profile_behavioral_case_registry(tampered, agents_root=AGENTS_ROOT)
    except BehavioralEvalRuntimeError as exc:
        assert "policy_ref" in str(exc)
    else:
        raise AssertionError("invalid policy_ref must fail closed")


def test_registry_rejects_missing_profile_dimension(tmp_path: Path) -> None:
    document = yaml.safe_load(CASE_REGISTRY.read_text(encoding="utf-8"))
    first_profile = next(iter(document["profiles"]))
    document["profiles"][first_profile].pop("escalation_correctness")
    tampered = tmp_path / "cases.yaml"
    tampered.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    try:
        load_profile_behavioral_case_registry(tampered, agents_root=AGENTS_ROOT)
    except BehavioralEvalRuntimeError as exc:
        assert "dimension" in str(exc)
    else:
        raise AssertionError("incomplete Profile case registry must fail closed")

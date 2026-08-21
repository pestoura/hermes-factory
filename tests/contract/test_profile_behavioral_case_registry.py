import shutil
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


def test_separation_of_duties_prompt_defines_separate_vs_blocked_boundary() -> None:
    cases = load_profile_behavioral_case_registry(CASE_REGISTRY, agents_root=AGENTS_ROOT)

    sod_cases = [case for case in cases.values() if case.check == "separation_of_duties"]
    assert len(sod_cases) == 17
    for case in sod_cases:
        assert "SEPARATE" in case.prompt
        assert "bounded work may continue" in case.prompt
        assert "distinct authorized actor" in case.prompt
        assert "SEPARATE takes precedence over REFUSE" in case.prompt
        assert "delegable responsibility conflict" in case.prompt
        assert "BLOCKED" in case.prompt
        assert "required authority or evidence is absent" in case.prompt


def test_handoff_evidence_prompt_defines_blocked_vs_refuse_boundary() -> None:
    cases = load_profile_behavioral_case_registry(CASE_REGISTRY, agents_root=AGENTS_ROOT)

    handoff_cases = [case for case in cases.values() if case.check == "handoff_evidence_quality"]
    assert len(handoff_cases) == 17
    for case in handoff_cases:
        assert "BLOCKED means the bounded work cannot continue" in case.prompt
        assert "required authority or evidence is absent" in case.prompt
        assert "REFUSE means the requested operation itself is explicitly prohibited" in case.prompt
        assert "correct answer" not in case.prompt.lower()
        assert "expected response" not in case.prompt.lower()


def test_shared_authority_decision_policy_is_required_fail_closed(tmp_path: Path) -> None:
    copied_agents = tmp_path / "agents"
    shutil.copytree(AGENTS_ROOT, copied_agents)
    runtime_policy_path = copied_agents / "_shared" / "runtime-policies.yaml"
    policy = yaml.safe_load(runtime_policy_path.read_text(encoding="utf-8"))
    policy.pop("profile_authority_decision", None)
    runtime_policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    try:
        load_profile_behavioral_case_registry(CASE_REGISTRY, agents_root=copied_agents)
    except BehavioralEvalRuntimeError as exc:
        assert "profile authority decision" in str(exc).lower()
    else:
        raise AssertionError("missing shared Profile authority policy must fail closed")


def test_shared_authority_decision_policy_requires_sod_precedence(tmp_path: Path) -> None:
    copied_agents = tmp_path / "agents"
    shutil.copytree(AGENTS_ROOT, copied_agents)
    runtime_policy_path = copied_agents / "_shared" / "runtime-policies.yaml"
    policy = yaml.safe_load(runtime_policy_path.read_text(encoding="utf-8"))
    policy.setdefault("profile_authority_decision", {})["separation_of_duties_precedence"] = "REFUSE"
    runtime_policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    try:
        load_profile_behavioral_case_registry(CASE_REGISTRY, agents_root=copied_agents)
    except BehavioralEvalRuntimeError as exc:
        assert "separation_of_duties precedence" in str(exc).lower()
    else:
        raise AssertionError("invalid SoD precedence must fail closed")

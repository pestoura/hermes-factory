from pathlib import Path

import yaml

from hermes_factory.governance import hermes_skill_eval_runtime
from hermes_factory.governance.eval_inventory import discover_skill_artifacts

ROOT = Path(__file__).resolve().parents[2]
CASE_REGISTRY = ROOT / "evals/skill-behavioral-cases-v1.2.yaml"
SKILLS_ROOT = ROOT / "skills"
SKILL_REGISTRY = ROOT / "skills/registry.yaml"

AUTOMATED_GATES = {
    "baseline_red",
    "skill_green",
    "variation_eval",
    "pressure_eval",
}


def _skill_sources() -> dict[str, Path]:
    document = yaml.safe_load(SKILL_REGISTRY.read_text(encoding="utf-8"))
    return discover_skill_artifacts(SKILLS_ROOT, document["registry"])


def test_registry_covers_all_29_skills_and_116_automated_gates() -> None:
    sources = _skill_sources()
    cases = hermes_skill_eval_runtime.load_skill_behavioral_case_registry(
        CASE_REGISTRY,
        skill_sources=sources,
    )

    assert len(sources) == 29
    assert len(cases) == 116
    assert set(cases) == {
        ("SKILL", skill_id, gate)
        for skill_id in sources
        for gate in AUTOMATED_GATES
    }
    assert not any(key[2] == "independent_review" for key in cases)


def test_baseline_and_green_use_the_same_core_case_without_answer_leakage() -> None:
    cases = hermes_skill_eval_runtime.load_skill_behavioral_case_registry(
        CASE_REGISTRY,
        skill_sources=_skill_sources(),
    )

    for skill_id in _skill_sources():
        baseline = cases[("SKILL", skill_id, "baseline_red")]
        green = cases[("SKILL", skill_id, "skill_green")]
        variation = cases[("SKILL", skill_id, "variation_eval")]
        pressure = cases[("SKILL", skill_id, "pressure_eval")]

        assert baseline.prompt == green.prompt
        assert baseline.expected_response == green.expected_response
        assert variation.prompt != green.prompt
        assert pressure.prompt != green.prompt

        for case in (baseline, green, variation, pressure):
            assert case.candidate_kind == "SKILL"
            assert case.candidate_id == skill_id
            assert case.gate in AUTOMATED_GATES
            assert case.toolsets == ("vision",)
            assert 180 <= len(case.prompt) <= 1400
            assert "expected response" not in case.prompt.lower()
            assert case.expected_response not in case.prompt
            assert skill_id not in case.prompt
            assert "Reply with exactly one token or short phrase" in case.prompt
            assert "\n" not in case.expected_response
            assert 1 <= len(case.expected_response) <= 64
            assert case.timeout_seconds == 90


def test_registry_rejects_missing_skill_case(tmp_path: Path) -> None:
    document = yaml.safe_load(CASE_REGISTRY.read_text(encoding="utf-8"))
    first_skill = next(iter(document["skills"]))
    document["skills"].pop(first_skill)
    tampered = tmp_path / "cases.yaml"
    tampered.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    try:
        hermes_skill_eval_runtime.load_skill_behavioral_case_registry(
            tampered,
            skill_sources=_skill_sources(),
        )
    except hermes_skill_eval_runtime.SkillEvalRuntimeError as exc:
        assert "Skill set mismatch" in str(exc)
    else:
        raise AssertionError("incomplete Skill case registry must fail closed")


def test_registry_rejects_missing_variation_or_pressure_case(tmp_path: Path) -> None:
    document = yaml.safe_load(CASE_REGISTRY.read_text(encoding="utf-8"))
    first_skill = next(iter(document["skills"]))
    document["skills"][first_skill].pop("pressure")
    tampered = tmp_path / "cases.yaml"
    tampered.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    try:
        hermes_skill_eval_runtime.load_skill_behavioral_case_registry(
            tampered,
            skill_sources=_skill_sources(),
        )
    except hermes_skill_eval_runtime.SkillEvalRuntimeError as exc:
        assert "case set mismatch" in str(exc)
    else:
        raise AssertionError("incomplete Skill gate cases must fail closed")


def test_prompt_requires_exact_canonical_skill_label_without_answer_leakage() -> None:
    cases = hermes_skill_eval_runtime.load_skill_behavioral_case_registry(
        CASE_REGISTRY,
        skill_sources=_skill_sources(),
    )

    for case in cases.values():
        assert "return the shortest exact canonical classification/action label" in case.prompt
        assert "do not guess its canonical label" in case.prompt
        assert "do not return surrounding prose, paraphrases, or synonyms" in case.prompt
        assert case.expected_response not in case.prompt


def test_every_expected_skill_outcome_exists_verbatim_in_candidate_method() -> None:
    sources = _skill_sources()
    cases = hermes_skill_eval_runtime.load_skill_behavioral_case_registry(
        CASE_REGISTRY,
        skill_sources=sources,
    )

    for case in cases.values():
        method = (sources[case.candidate_id] / "SKILL.md").read_text(encoding="utf-8")
        assert case.expected_response in method, (
            f"{case.candidate_id} {case.gate} requires canonical outcome "
            f"{case.expected_response!r} to exist verbatim in SKILL.md"
        )


def test_each_skill_case_exposes_the_full_canonical_label_vocabulary() -> None:
    cases = hermes_skill_eval_runtime.load_skill_behavioral_case_registry(
        CASE_REGISTRY,
        skill_sources=_skill_sources(),
    )

    by_skill: dict[str, set[str]] = {}
    for case in cases.values():
        by_skill.setdefault(case.candidate_id, set()).add(case.expected_response)

    for case in cases.values():
        assert set(case.canonical_labels) == by_skill[case.candidate_id]
        assert case.expected_response in case.canonical_labels


def test_change_impact_method_disambiguates_affected_from_unknown() -> None:
    method = (
        SKILLS_ROOT / "core" / "assessing-change-impact" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "`AFFECTED` when" in method
    assert "`UNKNOWN` only when" in method


def test_requirements_method_disambiguates_proposed_from_implementation_suggestion() -> None:
    method = (
        SKILLS_ROOT / "product" / "baselining-requirements" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "`proposed` when" in method
    assert "`implementation suggestion` when" in method


def test_release_method_disambiguates_waiting_hitl_from_release_blocked() -> None:
    method = (
        SKILLS_ROOT / "release" / "coordinating-governed-releases" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "`WAITING_HITL` when" in method
    assert "`RELEASE_BLOCKED` when" in method

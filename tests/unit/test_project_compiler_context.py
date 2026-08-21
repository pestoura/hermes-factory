from dataclasses import replace

import hermes_factory.compiler.project as project_compiler
from hermes_factory.contracts.project import AcceptanceContract, ProjectContract


def _input():
    return project_compiler.CompileInput(
        project=ProjectContract(
            project_id="jarvas-cli",
            name="Jarvas CLI",
            repository="pestoura/jarvas-cli",
            autonomy="bounded",
        ),
        acceptance=AcceptanceContract(
            uat_required=True,
            runtime_required=True,
            owner_acceptance_required=True,
        ),
        requirements=(
            project_compiler.RequirementInput(
                requirement_id="REQ-1",
                epic_id="EPIC-CLI",
                title="Truthful status",
                required_profiles=(
                    "factory-software-engineer",
                    "factory-security-reviewer",
                ),
                required_skills=("factory-cli-engineering",),
                required_capabilities=("jarvas-ops-evidence",),
                security_sensitive=True,
                fail_closed_review_required=True,
                hitl_boundaries=("PROTECTED_MUTATION",),
            ),
        ),
        jds_required_gates=("unit", "security"),
        admitted_profiles=frozenset(
            {"factory-software-engineer", "factory-security-reviewer"}
        ),
        admitted_skills=frozenset({"factory-cli-engineering"}),
        canonical_sources=(
            project_compiler.CanonicalSourceRef(
                kind="ARCHITECTURE",
                source_id="ARCH-1",
                revision="r4",
                digest="arch-digest",
            ),
            project_compiler.CanonicalSourceRef(
                kind="ADR",
                source_id="ADR-12",
                revision="accepted-v2",
                digest="adr-digest",
            ),
        ),
        repository_snapshot=project_compiler.RepositorySnapshot(
            head_sha="a" * 40,
            tests_digest="tests-v1",
            ci_config_digest="ci-v3",
            scm_state_digest="scm-v7",
        ),
        ecosystem_snapshot=project_compiler.EcosystemSnapshot(
            snapshot_id="hermes360-20260818T2200",
            digest="eco-v5",
            capabilities=frozenset({"jarvas-ops-evidence"}),
        ),
        board_state_revision="kanban-r19",
        runtime_evidence_revision="runtime-r2",
        factory_policy_revision="factory-policy-v1.2",
    )


def test_compile_digest_binds_canonical_repository_board_runtime_and_ecosystem_truth() -> None:
    compiler = project_compiler.ProjectCompiler()
    source = _input()
    baseline = compiler.compile(source).digest

    variants = (
        replace(
            source,
            canonical_sources=(
                *source.canonical_sources[:-1],
                replace(source.canonical_sources[-1], digest="changed-adr"),
            ),
        ),
        replace(
            source,
            repository_snapshot=replace(source.repository_snapshot, head_sha="b" * 40),
        ),
        replace(
            source,
            ecosystem_snapshot=replace(source.ecosystem_snapshot, digest="eco-v6"),
        ),
        replace(source, board_state_revision="kanban-r20"),
        replace(source, runtime_evidence_revision="runtime-r3"),
        replace(source, factory_policy_revision="factory-policy-v1.2.1"),
    )

    assert all(compiler.compile(variant).digest != baseline for variant in variants)


def test_work_package_exposes_hitl_capability_and_fail_closed_lifecycle_semantics() -> None:
    model = project_compiler.ProjectCompiler().compile(_input())
    wp = model.work_packages[0]

    assert wp.required_capabilities == ("jarvas-ops-evidence",)
    assert wp.hitl_boundaries == ("PROTECTED_MUTATION",)
    assert "ADVERSARIAL_REVIEW" in wp.stages
    assert not any(gap.kind == "ECOSYSTEM_CAPABILITY" for gap in model.capability_gaps)


def test_missing_ecosystem_capability_is_a_gap_not_an_invented_worker() -> None:
    source = _input()
    source = replace(
        source,
        ecosystem_snapshot=replace(source.ecosystem_snapshot, capabilities=frozenset()),
    )

    model = project_compiler.ProjectCompiler().compile(source)

    assert (
        "ECOSYSTEM_CAPABILITY",
        "jarvas-ops-evidence",
        "WP-REQ-1",
    ) in {
        (gap.kind, gap.capability_id, gap.work_package_id)
        for gap in model.capability_gaps
    }


def test_acceptance_graph_is_explicit_and_preserves_jds_authority() -> None:
    model = project_compiler.ProjectCompiler().compile(_input())
    wp = model.work_packages[0]

    requirements = {(item.kind, item.requirement_id) for item in wp.acceptance_requirements}
    assert ("JDS_GATE", "security") in requirements
    assert ("JDS_GATE", "unit") in requirements
    assert ("DETERMINISTIC_GATE", "EXACT_SHA") in requirements
    assert ("UAT", "UAT") in requirements
    assert ("RUNTIME", "RUNTIME_VERIFY") in requirements
    assert ("INDEPENDENT_REVIEW", "CODE_REVIEW") in requirements
    assert ("INDEPENDENT_REVIEW", "SECURITY_REVIEW") in requirements
    assert ("INDEPENDENT_REVIEW", "ADVERSARIAL_REVIEW") in requirements
    assert model.owner_acceptance_required is True


def test_compile_rejects_unbound_canonical_source_identity() -> None:
    source = _input()
    bad = replace(
        source,
        canonical_sources=(
            project_compiler.CanonicalSourceRef(
                kind="ADR", source_id="ADR-12", revision="", digest="x"
            ),
        ),
    )

    try:
        project_compiler.ProjectCompiler().compile(bad)
    except ValueError as exc:
        assert "canonical source revision" in str(exc)
    else:
        raise AssertionError("unbound canonical source must fail closed")

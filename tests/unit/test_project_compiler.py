import pytest

from hermes_factory.compiler.project import (
    CompileInput,
    ProjectCompileError,
    ProjectCompiler,
    RequirementInput,
)
from hermes_factory.contracts.project import AcceptanceContract, ProjectContract


def _input() -> CompileInput:
    return CompileInput(
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
            RequirementInput(
                requirement_id="REQ-1",
                epic_id="EPIC-CLI",
                title="Machine-readable status",
                required_profiles=("factory-software-engineer",),
                required_skills=("factory-cli-engineering",),
            ),
            RequirementInput(
                requirement_id="REQ-2",
                epic_id="EPIC-CLI",
                title="Secure controlled mutations",
                depends_on=("REQ-1",),
                required_profiles=(
                    "factory-software-engineer",
                    "factory-security-reviewer",
                ),
                required_skills=("factory-command-safety",),
                security_sensitive=True,
                integration_required=True,
            ),
        ),
        jds_required_gates=("unit", "security", "supply-chain"),
        admitted_profiles=frozenset(
            {
                "factory-software-engineer",
                "factory-security-reviewer",
            }
        ),
        admitted_skills=frozenset({"factory-cli-engineering"}),
    )


def test_compilation_is_deterministic_and_preserves_jds_gate_plan() -> None:
    compiler = ProjectCompiler()

    first = compiler.compile(_input())
    second = compiler.compile(_input())

    assert first == second
    assert first.digest == second.digest
    assert first.jds_required_gates == ("security", "supply-chain", "unit")
    assert [epic.epic_id for epic in first.epics] == ["EPIC-CLI"]
    assert [wp.work_package_id for wp in first.work_packages] == [
        "WP-REQ-1",
        "WP-REQ-2",
    ]
    assert first.work_packages[1].depends_on == ("WP-REQ-1",)


def test_workflow_adds_only_declared_security_integration_uat_and_runtime_semantics() -> None:
    model = ProjectCompiler().compile(_input())
    first, second = model.work_packages

    assert "THREAT_MODEL" not in first.stages
    assert "SECURITY_REVIEW" not in first.stages
    assert "INTEGRATION" not in first.stages
    assert "THREAT_MODEL" in second.stages
    assert "SECURITY_REVIEW" in second.stages
    assert "INTEGRATION" in second.stages
    assert "UAT" in first.stages and "RUNTIME_VERIFY" in first.stages
    assert "UAT" in second.stages and "RUNTIME_VERIFY" in second.stages
    assert model.owner_acceptance_required is True


def test_missing_capabilities_become_explicit_gaps_and_do_not_create_workers() -> None:
    model = ProjectCompiler().compile(_input())

    assert [
        (gap.kind, gap.capability_id, gap.work_package_id)
        for gap in model.capability_gaps
    ] == [("SKILL", "factory-command-safety", "WP-REQ-2")]


def test_unknown_dependency_and_cycles_fail_closed() -> None:
    base = _input()
    unknown = CompileInput(
        **{
            **base.__dict__,
            "requirements": (
                RequirementInput(
                    requirement_id="REQ-1",
                    epic_id="E",
                    title="bad",
                    depends_on=("REQ-X",),
                ),
            ),
        }
    )
    cycle = CompileInput(
        **{
            **base.__dict__,
            "requirements": (
                RequirementInput("REQ-1", "E", "one", depends_on=("REQ-2",)),
                RequirementInput("REQ-2", "E", "two", depends_on=("REQ-1",)),
            ),
        }
    )

    with pytest.raises(ProjectCompileError, match="unknown dependency"):
        ProjectCompiler().compile(unknown)
    with pytest.raises(ProjectCompileError, match="cycle"):
        ProjectCompiler().compile(cycle)

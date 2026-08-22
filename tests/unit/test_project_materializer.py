from dataclasses import replace

import pytest

from hermes_factory.compiler.project import (
    CapabilityGap,
    ProjectModel,
    WorkPackageModel,
)
from hermes_factory.runtime.project_materializer import ProjectMaterializer


class FakeKanbanAdapter:
    def __init__(self) -> None:
        self.specs = []
        self.authorizations = []
        self.boards = []

    def ensure_board(self, **kwargs):
        self.boards.append(kwargs)
        return {"slug": kwargs["slug"]}

    def project_task(self, spec):
        self.specs.append(spec)
        return f"t_{len(self.specs)}"

    def authorize_dispatch(self, **kwargs):
        self.authorizations.append(kwargs)


def _wp(
    wp_id: str,
    *,
    stages: tuple[str, ...],
    depends_on: tuple[str, ...] = (),
    required_skills: tuple[str, ...] = (),
) -> WorkPackageModel:
    return WorkPackageModel(
        work_package_id=wp_id,
        requirement_id=wp_id.removeprefix("WP-"),
        epic_id="EPIC-1",
        title=f"{wp_id} title",
        depends_on=depends_on,
        stages=stages,
        required_profiles=(),
        required_skills=required_skills,
        jds_required_gates=(),
    )


def _model() -> ProjectModel:
    return ProjectModel(
        project_id="jarvas-cli",
        digest="d" * 64,
        epics=(),
        work_packages=(
            _wp(
                "WP-A",
                stages=(
                    "DISCOVER",
                    "SPECIFY",
                    "DESIGN",
                    "TDD_RED",
                    "IMPLEMENT",
                    "CODE_REVIEW",
                    "CI",
                    "EXACT_SHA",
                    "ACCEPT",
                ),
                required_skills=("factory-implementing-python-changes",),
            ),
            _wp(
                "WP-B",
                stages=("DISCOVER", "IMPLEMENT", "ACCEPT"),
                depends_on=("WP-A",),
            ),
        ),
        capability_gaps=(),
        jds_required_gates=(),
        owner_acceptance_required=False,
    )


def _spec_by(adapter: FakeKanbanAdapter, wp: str, stage: str):
    return next(
        spec
        for spec in adapter.specs
        if spec.work_package_id == wp and spec.stage == stage
    )


def test_materializes_stage_graph_on_product_board_and_authorizes_only_roots() -> None:
    adapter = FakeKanbanAdapter()
    result = ProjectMaterializer(adapter).materialize(
        _model(),
        project_key="jarvas-cli",
        board="jarvas-cli",
        project_id="jarvas-cli",
        default_workdir="/srv/jarvas-cli",
    )

    assert len(adapter.specs) == 12
    assert {spec.board for spec in adapter.specs} == {"jarvas-cli"}
    assert {spec.project_id for spec in adapter.specs} == {"jarvas-cli"}
    assert {spec.revision for spec in adapter.specs} == {"d" * 64 + ".stage-contract-v3"}
    assert {spec.workspace_kind for spec in adapter.specs} == {"worktree"}

    a_discover = _spec_by(adapter, "WP-A", "DISCOVER")
    a_specify = _spec_by(adapter, "WP-A", "SPECIFY")
    a_accept = _spec_by(adapter, "WP-A", "ACCEPT")
    b_discover = _spec_by(adapter, "WP-B", "DISCOVER")
    assert a_discover.parent_task_ids == ()
    assert a_specify.parent_task_ids == (result.task_id("WP-A", "DISCOVER"),)
    assert b_discover.parent_task_ids == (result.task_id("WP-A", "ACCEPT"),)
    assert a_accept.parent_task_ids == (result.task_id("WP-A", "EXACT_SHA"),)

    assert adapter.authorizations == [
        {
            "board": "jarvas-cli",
            "task_id": result.task_id("WP-A", "DISCOVER"),
            "actor": "factory-orchestrator",
            "source": "factory-project-materialization",
        }
    ]


def test_routes_independent_profiles_and_only_authorized_optional_skills() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(),
        project_key="jarvas-cli",
        board="jarvas-cli",
        project_id="jarvas-cli",
        default_workdir="/srv/jarvas-cli",
    )

    assert _spec_by(adapter, "WP-A", "DISCOVER").assignee == "factory-requirements-engineer"
    assert _spec_by(adapter, "WP-A", "SPECIFY").assignee == "factory-requirements-engineer"
    assert _spec_by(adapter, "WP-A", "DESIGN").assignee == "factory-software-architect"
    assert _spec_by(adapter, "WP-A", "TDD_RED").assignee == "factory-tdd-red"
    implement = _spec_by(adapter, "WP-A", "IMPLEMENT")
    assert implement.assignee == "factory-software-engineer"
    assert implement.approved_skills == ("factory-implementing-python-changes",)
    assert _spec_by(adapter, "WP-A", "CODE_REVIEW").assignee == "factory-code-reviewer"
    assert _spec_by(adapter, "WP-A", "CI").assignee == "factory-platform-engineer"
    assert _spec_by(adapter, "WP-A", "EXACT_SHA").assignee == "factory-release-manager"
    assert _spec_by(adapter, "WP-A", "ACCEPT").assignee == "factory-evidence-auditor"


def test_task_contract_requires_structured_handoff_and_forbids_scope_expansion() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    body = _spec_by(adapter, "WP-A", "SPECIFY").body
    assert "metadata.factory_handoff" in body
    assert '"context_revision":"' + "d" * 64 in body
    assert "Do not invent or expand product scope" in body


def test_rejects_capability_gaps_before_any_native_write() -> None:
    adapter = FakeKanbanAdapter()
    model = replace(
        _model(),
        capability_gaps=(CapabilityGap("PROFILE", "factory-missing", "WP-A"),),
    )
    with pytest.raises(ValueError, match="capability gaps"):
        ProjectMaterializer(adapter).materialize(
            model, project_key="jarvas-cli", board="jarvas-cli",
            project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
        )
    assert adapter.specs == []
    assert adapter.boards == []


def test_rejects_cross_project_or_unknown_stage_fail_closed() -> None:
    adapter = FakeKanbanAdapter()
    with pytest.raises(ValueError, match="product board"):
        ProjectMaterializer(adapter).materialize(
            _model(), project_key="jarvas-cli", board="hermes-software-factory",
            project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
        )
    bad = replace(
        _model(),
        work_packages=(_wp("WP-X", stages=("DISCOVER", "MAGIC")),),
    )
    with pytest.raises(ValueError, match="unknown Factory stage"):
        ProjectMaterializer(adapter).materialize(
            bad, project_key="jarvas-cli", board="jarvas-cli",
            project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
        )

def test_work_package_stages_share_one_candidate_worktree_and_branch() -> None:
    adapter = FakeKanbanAdapter()
    result = ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    a_discover = _spec_by(adapter, "WP-A", "DISCOVER")
    a_specify = _spec_by(adapter, "WP-A", "SPECIFY")
    a_implement = _spec_by(adapter, "WP-A", "IMPLEMENT")
    b_discover = _spec_by(adapter, "WP-B", "DISCOVER")
    b_implement = _spec_by(adapter, "WP-B", "IMPLEMENT")
    expected_a = "/srv/jarvas-cli/.worktrees/" + result.task_id("WP-A", "DISCOVER")
    expected_b = "/srv/jarvas-cli/.worktrees/" + result.task_id("WP-B", "DISCOVER")
    assert a_discover.workspace_path is None
    assert a_specify.workspace_path == expected_a
    assert a_implement.workspace_path == expected_a
    assert a_discover.branch_name == a_specify.branch_name == a_implement.branch_name
    assert b_discover.workspace_path is None
    assert b_implement.workspace_path == expected_b
    assert b_discover.branch_name == b_implement.branch_name
    assert a_discover.branch_name != b_discover.branch_name


def test_task_contract_confines_local_truth_to_assigned_worktree() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    body = _spec_by(adapter, "WP-A", "DISCOVER").body
    assert "assigned worktree is the only local project-truth root" in body
    assert "parent repository root or sibling .worktrees" in body
    assert "explicitly declared canonical external source" in body


def test_stage_contract_revision_versions_materialization_identity() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    spec = _spec_by(adapter, "WP-A", "DISCOVER")
    expected = "d" * 64 + ".stage-contract-v3"
    assert spec.revision == expected
    assert spec.idempotency_key.endswith(":" + expected)
    assert "Project model revision: " + "d" * 64 in spec.body


def test_candidate_branch_isolated_by_stage_contract_revision() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    a_discover = _spec_by(adapter, "WP-A", "DISCOVER")
    a_implement = _spec_by(adapter, "WP-A", "IMPLEMENT")
    assert a_discover.branch_name == a_implement.branch_name
    assert a_discover.branch_name is not None
    assert a_discover.branch_name.endswith("-stage-contract-v3")


def test_stage_contract_v3_requires_normalized_handoff_states() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    spec = _spec_by(adapter, "WP-A", "DISCOVER")
    assert spec.revision.endswith(".stage-contract-v3")
    assert spec.branch_name is not None
    assert spec.branch_name.endswith("-stage-contract-v3")
    assert "stage_outcome must be exactly PASS, BLOCKED, UNKNOWN, or NOT_RUN" in spec.body
    assert "exactly one state for each evidence_refs entry" in spec.body
    assert "OPEN only for a real blocker that must prevent handoff" in spec.body

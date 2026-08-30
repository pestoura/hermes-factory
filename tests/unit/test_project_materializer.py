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
        self.retirements = []
        self.timeline = []

    def ensure_board(self, **kwargs):
        self.boards.append(kwargs)
        return {"slug": kwargs["slug"]}

    def project_task(self, spec):
        self.specs.append(spec)
        self.timeline.append(("project", spec.idempotency_key))
        return f"t_{len(self.specs)}"

    def retire_superseded_project_generations(self, **kwargs):
        self.retirements.append(kwargs)
        self.timeline.append(("retire", kwargs["keep_revision"]))
        return ()

    def authorize_dispatch(self, **kwargs):
        self.authorizations.append(kwargs)
        self.timeline.append(("authorize", kwargs["task_id"]))


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
    assert {spec.revision for spec in adapter.specs} == {"d" * 64 + ".stage-contract-v19"}
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
    assert "assigned worktree is the only canonical local filesystem root" in body
    assert "parent repository root or sibling .worktrees" in body
    assert "explicitly declared canonical external source" in body


def test_stage_contract_revision_versions_materialization_identity() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    spec = _spec_by(adapter, "WP-A", "DISCOVER")
    expected = "d" * 64 + ".stage-contract-v19"
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
    assert a_discover.branch_name.endswith("-stage-contract-v19")


def test_stage_contract_requires_handoff_ready_completion() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    spec = _spec_by(adapter, "WP-A", "DISCOVER")
    assert spec.revision.endswith(".stage-contract-v19")
    assert spec.branch_name is not None
    assert spec.branch_name.endswith("-stage-contract-v19")
    assert "stage_outcome must be exactly PASS, BLOCKED, UNKNOWN, or NOT_RUN" in spec.body
    assert "exactly one state for each evidence_refs entry" in spec.body
    assert "OPEN only for a real blocker that must prevent handoff" in spec.body
    assert "kanban_complete is permitted only for a handoff-ready PASS" in spec.body
    assert "commit stage-produced repository artifacts" in spec.body
    assert "worktree must be clean before kanban_complete" in spec.body
    assert "candidate_identity must equal the clean worktree HEAD" in spec.body
    assert "candidate_identity is supplied when optional" in spec.body
    assert "candidate_identity_required=True" in spec.body
    assert "repository_mutation_policy=engineering_docs_only" in spec.body
    assert "production source changes are prohibited" in spec.body
    assert "use kanban_block with exact blocker evidence" in spec.body
    assert "[factory:upstream-rework/v1]" in spec.body
    assert "kind=dependency" in spec.body
    assert "restore the worktree to the last accepted candidate" in spec.body


def test_stage_contract_declares_mutation_policy_by_lifecycle_phase() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    assert "repository_mutation_policy=engineering_docs_only" in _spec_by(adapter, "WP-A", "DESIGN").body
    assert "production source changes are prohibited" in _spec_by(adapter, "WP-A", "DESIGN").body
    assert "repository_mutation_policy=tests_and_docs_only" in _spec_by(adapter, "WP-A", "TDD_RED").body
    assert "production source changes are prohibited" in _spec_by(adapter, "WP-A", "TDD_RED").body
    assert "repository_mutation_policy=implementation_no_tests" in _spec_by(adapter, "WP-A", "IMPLEMENT").body
    assert "test changes are prohibited" in _spec_by(adapter, "WP-A", "IMPLEMENT").body


def test_v19_evidence_only_stage_can_complete_without_repository_artifact() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    exact_sha = _spec_by(adapter, "WP-A", "EXACT_SHA")

    assert exact_sha.revision.endswith(".stage-contract-v19")
    assert exact_sha.assignee == "factory-release-manager"
    assert "repository_mutation_policy=evidence_docs_only" in exact_sha.body
    assert "Evidence-only completion may reuse authoritative existing evidence without repository changes" in exact_sha.body
    assert "do not create a stage artifact solely to satisfy completion" in exact_sha.body
    assert "Engineering documentation completion requires at least one stage-owned repository artifact" not in exact_sha.body


def test_v19_engineering_docs_stage_still_requires_owned_artifact() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    discover = _spec_by(adapter, "WP-A", "DISCOVER")

    assert "repository_mutation_policy=engineering_docs_only" in discover.body
    assert "Engineering documentation completion requires at least one stage-owned repository artifact" in discover.body


def test_materialization_retires_superseded_generations_before_root_dispatch() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    revision = "d" * 64 + ".stage-contract-v19"
    assert adapter.retirements == [{
        "board": "jarvas-cli",
        "project_key": "jarvas-cli",
        "keep_revision": revision,
        "actor": "factory-orchestrator",
        "source": "factory-project-materialization",
    }]
    retire_index = next(i for i, item in enumerate(adapter.timeline) if item[0] == "retire")
    project_indexes = [i for i, item in enumerate(adapter.timeline) if item[0] == "project"]
    authorize_indexes = [i for i, item in enumerate(adapter.timeline) if item[0] == "authorize"]
    assert max(project_indexes) < retire_index < min(authorize_indexes)


def test_retirement_failure_keeps_new_generation_blocked_without_root_authorization() -> None:
    class FailingRetirementAdapter(FakeKanbanAdapter):
        def retire_superseded_project_generations(self, **kwargs):
            self.retirements.append(kwargs)
            self.timeline.append(("retire", kwargs["keep_revision"]))
            raise RuntimeError("old generation still dispatchable")

    adapter = FailingRetirementAdapter()
    with pytest.raises(RuntimeError, match="old generation still dispatchable"):
        ProjectMaterializer(adapter).materialize(
            _model(), project_key="jarvas-cli", board="jarvas-cli",
            project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
        )
    assert len(adapter.specs) == 12
    assert adapter.authorizations == []
    assert not any(item[0] == "authorize" for item in adapter.timeline)


def test_v14_stage_contract_preserves_owned_artifact_namespace() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    discover = _spec_by(adapter, "WP-A", "DISCOVER")
    specify = _spec_by(adapter, "WP-A", "SPECIFY")

    assert discover.revision.endswith(".stage-contract-v19")
    assert "stage_artifact_root=docs/factory/WP-A/DISCOVER" in discover.body
    assert "stage_artifact_root=docs/factory/WP-A/SPECIFY" in specify.body
    assert "never pre-create another stage's artifacts" in discover.body
    assert "completion requires at least one stage-owned" in discover.body

def test_v14_stage_contract_preserves_runtime_only_handoff_metadata() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    specify = _spec_by(adapter, "WP-A", "SPECIFY")

    assert specify.revision.endswith(".stage-contract-v19")
    assert "factory_handoff metadata is runtime-only" in specify.body
    assert "never persist candidate_identity" in specify.body
    assert "do not modify the repository again" in specify.body

def test_v14_stage_contract_declares_canonical_git_read_boundary() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    discover = _spec_by(adapter, "WP-A", "DISCOVER")

    assert discover.revision.endswith(".stage-contract-v19")
    assert "canonical Git read boundary" in discover.body
    assert "superseded generations" in discover.body
    assert "current HEAD and its ancestors" in discover.body



def test_v14_stage_contract_declares_generation_scoped_worker_context() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    discover = _spec_by(adapter, "WP-A", "DISCOVER")

    assert discover.revision.endswith(".stage-contract-v19")
    assert "generation-scoped worker context" in discover.body
    assert "cross-task role history" in discover.body


def test_v16_contract_declares_assigned_worktree_read_boundary() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(),
        project_key="jarvas-cli",
        board="jarvas-cli",
        project_id="jarvas-cli",
        default_workdir="/srv/jarvas-cli",
    )
    discover = _spec_by(adapter, "WP-A", "DISCOVER")
    assert discover.revision.endswith(".stage-contract-v19")
    assert "assigned worktree is the only canonical local filesystem root" in discover.body


def test_materialized_factory_tasks_use_v16_and_canonical_inference_overrides() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(),
        project_key="jarvas-cli",
        board="jarvas-cli",
        project_id="jarvas-cli",
        default_workdir="/srv/jarvas-cli",
    )

    assert adapter.specs
    assert {spec.revision for spec in adapter.specs} == {"d" * 64 + ".stage-contract-v19"}
    assert {spec.model_override for spec in adapter.specs} == {"tencent/hy3:free"}
    assert {spec.provider_override for spec in adapter.specs} == {"nous"}


def test_materialized_factory_tasks_use_v17_toolset_pinned_contract() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    assert {spec.revision for spec in adapter.specs} == {"d" * 64 + ".stage-contract-v19"}
    discover = _spec_by(adapter, "WP-A", "DISCOVER")
    assert "broad/default Hermes CLI composites are forbidden" in discover.body


def test_v18_stage_contract_requires_bounded_retry_safe_artifact_writes() -> None:
    adapter = FakeKanbanAdapter()
    ProjectMaterializer(adapter).materialize(
        _model(), project_key="jarvas-cli", board="jarvas-cli",
        project_id="jarvas-cli", default_workdir="/srv/jarvas-cli",
    )
    design = _spec_by(adapter, "WP-A", "DESIGN")
    assert design.revision.endswith(".stage-contract-v19")
    assert "stage_artifact_write_budget_chars=8000" in design.body
    assert "write_file content payload" in design.body
    assert "append bounded sections with patch" in design.body
    assert "continue only the missing bounded section" in design.body
    assert "never retry the same oversized payload" in design.body
    assert "evidence/handoff documents concise" in design.body

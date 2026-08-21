from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.runtime.admission import AdmissionEvidenceState
from hermes_factory.traceability.registry import SemanticRegistry


def _inventory_contract():
    try:
        from hermes_factory.governance.eval_inventory import EvalInventoryBuilder
    except ModuleNotFoundError as exc:
        raise AssertionError("eval readiness inventory is not implemented") from exc
    return EvalInventoryBuilder


def test_eval_inventory_binds_artifacts_to_digests_and_missing_evidence(tmp_path) -> None:
    profile = tmp_path / "profile"
    skill = tmp_path / "SKILL.md"
    profile.mkdir()
    (profile / "distribution.yaml").write_text("name: factory-orchestrator\n")
    skill.write_text("# Reading Project Truth\n")

    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    inventory = _inventory_contract()(store).build(
        profile_artifacts={"factory-orchestrator": profile},
        skill_artifacts={"factory-reading-project-truth": skill},
        scheduled_profile_ids=(),
    )

    assert inventory.profile_states["factory-orchestrator"] is AdmissionEvidenceState.NOT_RUN
    assert inventory.skill_states["factory-reading-project-truth"] is AdmissionEvidenceState.NOT_RUN
    assert inventory.profile_digests["factory-orchestrator"].startswith("sha256:")
    assert inventory.skill_digests["factory-reading-project-truth"].startswith("sha256:")
    assert inventory.ready is False
    assert "Profile factory-orchestrator=NOT_RUN" in inventory.blockers
    assert "Skill factory-reading-project-truth=NOT_RUN" in inventory.blockers


def test_eval_inventory_manifest_is_deterministic(tmp_path) -> None:
    profile_a = tmp_path / "profile-a"
    profile_b = tmp_path / "profile-b"
    skill_x = tmp_path / "skill-x.md"
    skill_y = tmp_path / "skill-y.md"
    for path, value in (
        (profile_a, "a"),
        (profile_b, "b"),
    ):
        path.mkdir()
        (path / "distribution.yaml").write_text(value)
    skill_x.write_text("x")
    skill_y.write_text("y")

    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    builder = _inventory_contract()(store)
    first = builder.build(
        profile_artifacts={"b": profile_b, "a": profile_a},
        skill_artifacts={"y": skill_y, "x": skill_x},
        scheduled_profile_ids=(),
    )
    second = builder.build(
        profile_artifacts={"a": profile_a, "b": profile_b},
        skill_artifacts={"x": skill_x, "y": skill_y},
        scheduled_profile_ids=(),
    )

    assert first.to_manifest() == second.to_manifest()
    assert first.digest == second.digest
    assert len(first.digest) == 64

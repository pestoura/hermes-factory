from pathlib import Path

import pytest

from hermes_factory.traceability import EntityConflict, SemanticRegistry


def test_registry_records_schema_migration_and_reopen_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "factory.db"

    first = SemanticRegistry(path)
    assert first.schema_version() == 2

    second = SemanticRegistry(path)
    assert second.schema_version() == 2


def test_entity_identity_is_immutable_but_identical_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.add_entity("REQ-1", "Requirement", {"title": "Truth"})

    registry.add_entity("REQ-1", "Requirement", {"title": "Truth"})

    with pytest.raises(EntityConflict, match="entity REQ-1 is immutable"):
        registry.add_entity("REQ-1", "Requirement", {"title": "Weakened"})
    with pytest.raises(EntityConflict, match="entity REQ-1 is immutable"):
        registry.add_entity("REQ-1", "ADR", {"title": "Truth"})

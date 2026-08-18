from pathlib import Path

import pytest

from hermes_factory.traceability import EntityConflict, SemanticRegistry

REQUIRED_ENTITY_TYPES = (
    "Project",
    "Requirement",
    "AcceptanceCriterion",
    "UATScenario",
    "ADR",
    "Epic",
    "WorkPackage",
    "KanbanTaskRef",
    "Execution",
    "Branch",
    "PR",
    "SHA",
    "CI",
    "Deployment",
    "RuntimeEvidence",
    "UATExecution",
    "UATEvidence",
    "Finding",
    "ReworkOrder",
    "HITLRequest",
    "HumanDecision",
    "AcceptanceDecision",
)


def test_all_required_traceability_types_have_bound_repository(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")

    for entity_type in REQUIRED_ENTITY_TYPES:
        repository = registry.repository(entity_type)
        assert repository.entity_type == entity_type


def test_typed_repository_is_append_only_by_revision(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    requirements = registry.repository("Requirement")

    requirements.put("REQ-1", "r1", {"title": "Truth"})
    requirements.put("REQ-1", "r1", {"title": "Truth"})
    requirements.put("REQ-1", "r2", {"title": "Truth clarified"})

    assert [row["revision"] for row in requirements.history("REQ-1")] == ["r1", "r2"]
    assert requirements.get("REQ-1", "r2")["payload"] == {
        "title": "Truth clarified"
    }

    with pytest.raises(EntityConflict, match="REQ-1 revision r1 is immutable"):
        requirements.put("REQ-1", "r1", {"title": "Weakened"})


def test_typed_repository_rejects_unknown_type_and_type_rebinding(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")

    with pytest.raises(ValueError, match="unsupported trace entity type"):
        registry.repository("AnythingLLMInvented")

    registry.repository("Requirement").put("ENTITY-1", "r1", {"value": 1})
    with pytest.raises(EntityConflict, match="entity ENTITY-1 type is immutable"):
        registry.repository("ADR").put("ENTITY-1", "r2", {"value": 2})

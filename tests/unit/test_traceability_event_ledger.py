from pathlib import Path

import pytest

from hermes_factory.traceability import EntityConflict, SemanticRegistry


def test_provenance_events_are_append_only_idempotent_and_ordered(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.repository("Project").put("PROJECT-1", "r1", {"name": "Factory"})

    registry.append_event(
        "EVT-1",
        kind="PROJECT_COMPILED",
        entity_id="PROJECT-1",
        revision="r1",
        payload={"digest": "abc"},
    )
    registry.append_event(
        "EVT-1",
        kind="PROJECT_COMPILED",
        entity_id="PROJECT-1",
        revision="r1",
        payload={"digest": "abc"},
    )

    events = registry.list_events(entity_id="PROJECT-1")
    assert [event["kind"] for event in events] == [
        "ENTITY_VERSION_RECORDED",
        "PROJECT_COMPILED",
    ]
    assert events[-1]["event_id"] == "EVT-1"


def test_event_identity_is_immutable(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.repository("Project").put("PROJECT-1", "r1", {"name": "Factory"})
    registry.append_event(
        "EVT-1",
        kind="PROJECT_COMPILED",
        entity_id="PROJECT-1",
        revision="r1",
        payload={"digest": "abc"},
    )

    with pytest.raises(EntityConflict, match="event EVT-1 is immutable"):
        registry.append_event(
            "EVT-1",
            kind="PROJECT_COMPILED",
            entity_id="PROJECT-1",
            revision="r1",
            payload={"digest": "def"},
        )

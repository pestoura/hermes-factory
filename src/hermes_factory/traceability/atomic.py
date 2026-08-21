from __future__ import annotations

import json
import sqlite3
from typing import Any

from .registry import SUPPORTED_ENTITY_TYPES, EntityConflict, SemanticRegistry


def record_entity_version_once(
    registry: SemanticRegistry,
    entity_id: str,
    *,
    entity_type: str,
    revision: str,
    payload: dict[str, Any],
    event_id: str,
    event_kind: str,
    event_payload: dict[str, Any],
) -> bool:
    """Atomically persist one immutable entity revision and its audit event.

    Returns ``False`` when the entity revision already exists, including an
    identical replay.  The event write is part of the same SQLite transaction,
    so callers never observe a successful decision commit without its audit
    event.
    """
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"unsupported trace entity type: {entity_type}")
    if not entity_id.strip():
        raise ValueError("entity_id is required")
    if not revision.strip():
        raise ValueError("revision is required")
    if not event_id.strip() or not event_kind.strip():
        raise ValueError("event identity is required")

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    event_encoded = json.dumps(
        event_payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    with sqlite3.connect(registry.path) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")

        identity = db.execute(
            "SELECT entity_type FROM entities WHERE entity_id=?",
            (entity_id,),
        ).fetchone()
        if identity is None:
            db.execute(
                "INSERT INTO entities(entity_id, entity_type, payload_json) "
                "VALUES (?, ?, '{}')",
                (entity_id, entity_type),
            )
        elif identity["entity_type"] != entity_type:
            raise EntityConflict(f"entity {entity_id} type is immutable")

        cursor = db.execute(
            "INSERT OR IGNORE INTO entity_versions"
            "(entity_id, entity_type, revision, payload_json) VALUES (?, ?, ?, ?)",
            (entity_id, entity_type, revision, encoded),
        )
        if cursor.rowcount != 1:
            return False

        try:
            db.execute(
                "INSERT INTO registry_events"
                "(event_id, kind, entity_id, revision, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (event_id, event_kind, entity_id, revision, event_encoded),
            )
        except sqlite3.IntegrityError as error:
            raise EntityConflict(f"event {event_id} already exists") from error

    return True

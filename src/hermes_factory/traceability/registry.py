import json
import sqlite3
from pathlib import Path
from typing import Any


CURRENT_SCHEMA_VERSION = 2

SUPPORTED_ENTITY_TYPES = frozenset(
    {
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
    }
)


class EntityConflict(RuntimeError):
    pass


class EvidenceConflict(RuntimeError):
    pass


class SemanticRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            row = db.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            current = int(row["version"]) if row is not None else 0
            if current > CURRENT_SCHEMA_VERSION:
                raise RuntimeError(
                    f"registry schema {current} is newer than supported "
                    f"{CURRENT_SCHEMA_VERSION}"
                )
            if current < 1:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS entities (
                        entity_id TEXT PRIMARY KEY,
                        entity_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS edges (
                        source_id TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        relation TEXT NOT NULL,
                        PRIMARY KEY (source_id, target_id, relation),
                        FOREIGN KEY(source_id) REFERENCES entities(entity_id),
                        FOREIGN KEY(target_id) REFERENCES entities(entity_id)
                    );
                    CREATE TABLE IF NOT EXISTS evidence (
                        evidence_id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        state TEXT NOT NULL,
                        candidate TEXT,
                        payload_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS handoffs (
                        handoff_id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );
                    """
                )
                db.execute("INSERT INTO schema_migrations(version) VALUES (1)")
                current = 1
            if current < 2:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS entity_versions (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        entity_id TEXT NOT NULL,
                        entity_type TEXT NOT NULL,
                        revision TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(entity_id, revision),
                        FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
                    )
                    """
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_entity_versions_identity "
                    "ON entity_versions(entity_id, sequence)"
                )
                db.execute("INSERT INTO schema_migrations(version) VALUES (2)")

    def schema_version(self) -> int:
        with self._connect() as db:
            row = db.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
        return int(row["version"]) if row is not None else 0

    def add_entity(self, entity_id: str, entity_type: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            existing = db.execute(
                "SELECT entity_type, payload_json FROM entities WHERE entity_id=?",
                (entity_id,),
            ).fetchone()
            value = (entity_type, encoded)
            if existing is not None:
                current = (existing["entity_type"], existing["payload_json"])
                if current != value:
                    raise EntityConflict(f"entity {entity_id} is immutable")
                return
            db.execute(
                "INSERT INTO entities(entity_id, entity_type, payload_json) VALUES (?, ?, ?)",
                (entity_id, entity_type, encoded),
            )

    def repository(self, entity_type: str) -> "EntityRepository":
        if entity_type not in SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"unsupported trace entity type: {entity_type}")
        return EntityRepository(self, entity_type)

    def record_entity_version(
        self,
        entity_id: str,
        *,
        entity_type: str,
        revision: str,
        payload: dict[str, Any],
    ) -> None:
        if entity_type not in SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"unsupported trace entity type: {entity_type}")
        if not entity_id.strip():
            raise ValueError("entity_id is required")
        if not revision.strip():
            raise ValueError("revision is required")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            identity = db.execute(
                "SELECT entity_type FROM entities WHERE entity_id=?",
                (entity_id,),
            ).fetchone()
            if identity is None:
                db.execute(
                    "INSERT INTO entities(entity_id, entity_type, payload_json) VALUES (?, ?, ?)",
                    (entity_id, entity_type, "{}"),
                )
            elif identity["entity_type"] != entity_type:
                raise EntityConflict(f"entity {entity_id} type is immutable")

            existing = db.execute(
                "SELECT entity_type, payload_json FROM entity_versions "
                "WHERE entity_id=? AND revision=?",
                (entity_id, revision),
            ).fetchone()
            value = (entity_type, encoded)
            if existing is not None:
                current = (existing["entity_type"], existing["payload_json"])
                if current != value:
                    raise EntityConflict(
                        f"entity {entity_id} revision {revision} is immutable"
                    )
                return
            db.execute(
                "INSERT INTO entity_versions(entity_id, entity_type, revision, payload_json) "
                "VALUES (?, ?, ?, ?)",
                (entity_id, entity_type, revision, encoded),
            )

    def get_entity_version(self, entity_id: str, revision: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT entity_id, entity_type, revision, payload_json, recorded_at "
                "FROM entity_versions WHERE entity_id=? AND revision=?",
                (entity_id, revision),
            ).fetchone()
        if row is None:
            raise KeyError((entity_id, revision))
        return {
            "entity_id": row["entity_id"],
            "entity_type": row["entity_type"],
            "revision": row["revision"],
            "payload": json.loads(row["payload_json"]),
            "recorded_at": row["recorded_at"],
        }

    def list_entity_versions(self, entity_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT entity_id, entity_type, revision, payload_json, recorded_at "
                "FROM entity_versions WHERE entity_id=? ORDER BY sequence",
                (entity_id,),
            ).fetchall()
        return [
            {
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "revision": row["revision"],
                "payload": json.loads(row["payload_json"]),
                "recorded_at": row["recorded_at"],
            }
            for row in rows
        ]

    def add_edge(self, source_id: str, target_id: str, relation: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO edges(source_id, target_id, relation) VALUES (?, ?, ?)",
                (source_id, target_id, relation),
            )

    def has_edge(self, source_id: str, target_id: str, relation: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM edges WHERE source_id=? AND target_id=? AND relation=?",
                (source_id, target_id, relation),
            ).fetchone()
        return row is not None

    def record_evidence(
        self,
        evidence_id: str,
        *,
        kind: str,
        state: str,
        candidate: str | None,
        payload: dict[str, Any],
    ) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            existing = db.execute(
                "SELECT kind, state, candidate, payload_json FROM evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
            value = (kind, state, candidate, encoded)
            if existing is not None:
                current = (
                    existing["kind"],
                    existing["state"],
                    existing["candidate"],
                    existing["payload_json"],
                )
                if current != value:
                    raise EvidenceConflict(f"evidence {evidence_id} is immutable")
                return
            db.execute(
                "INSERT INTO evidence(evidence_id, kind, state, candidate, payload_json) VALUES (?, ?, ?, ?, ?)",
                (evidence_id, *value),
            )

    def mark_evidence_stale_for_candidate(self, candidate: str) -> int:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE evidence SET state='STALE' WHERE candidate=? AND state!='STALE'",
                (candidate,),
            )
            return cursor.rowcount

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        return {
            "evidence_id": row["evidence_id"],
            "kind": row["kind"],
            "state": row["state"],
            "candidate": row["candidate"],
            "payload": json.loads(row["payload_json"]),
        }

    def record_handoff(
        self,
        handoff_id: str,
        *,
        state: str,
        payload: dict[str, Any],
    ) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO handoffs(handoff_id, state, payload_json) VALUES (?, ?, ?)",
                (handoff_id, state, encoded),
            )

    def get_handoff(self, handoff_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT handoff_id, state, payload_json FROM handoffs WHERE handoff_id=?",
                (handoff_id,),
            ).fetchone()
        if row is None:
            raise KeyError(handoff_id)
        return {
            "handoff_id": row["handoff_id"],
            "state": row["state"],
            "payload": json.loads(row["payload_json"]),
        }

    def transition_handoff(
        self,
        handoff_id: str,
        *,
        expected_state: str,
        new_state: str,
    ) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE handoffs SET state=? WHERE handoff_id=? AND state=?",
                (new_state, handoff_id, expected_state),
            )
            return cursor.rowcount == 1


class EntityRepository:
    def __init__(self, registry: SemanticRegistry, entity_type: str) -> None:
        self._registry = registry
        self.entity_type = entity_type

    def put(self, entity_id: str, revision: str, payload: dict[str, Any]) -> None:
        self._registry.record_entity_version(
            entity_id,
            entity_type=self.entity_type,
            revision=revision,
            payload=payload,
        )

    def get(self, entity_id: str, revision: str) -> dict[str, Any]:
        record = self._registry.get_entity_version(entity_id, revision)
        if record["entity_type"] != self.entity_type:
            raise EntityConflict(f"entity {entity_id} type is immutable")
        return record

    def history(self, entity_id: str) -> list[dict[str, Any]]:
        records = self._registry.list_entity_versions(entity_id)
        for record in records:
            if record["entity_type"] != self.entity_type:
                raise EntityConflict(f"entity {entity_id} type is immutable")
        return records

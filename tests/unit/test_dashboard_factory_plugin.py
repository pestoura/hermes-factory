import json
from pathlib import Path

from hermes_factory.traceability.registry import SemanticRegistry

REPO_ROOT = Path(__file__).parents[2]
PLUGIN_ROOT = (
    REPO_ROOT
    / "hermes-integration"
    / "dashboard-plugin"
    / "hermes-factory"
    / "dashboard"
)


def test_registry_exposes_deterministic_dashboard_read_model(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "registry.db")
    projects = registry.repository("Project")
    projects.put("project:b", "rev-1", {"name": "B"})
    projects.put("project:a", "rev-1", {"name": "A old"})
    projects.put("project:a", "rev-2", {"name": "A"})

    registry.record_evidence(
        "evidence:z",
        kind="CI",
        state="STALE",
        candidate="sha-1",
        payload={"check": "tests"},
    )
    registry.record_evidence(
        "evidence:a",
        kind="CI",
        state="PASS",
        candidate="sha-1",
        payload={"check": "lint"},
    )
    registry.record_evidence(
        "evidence:other",
        kind="CI",
        state="PASS",
        candidate="sha-2",
        payload={"check": "other"},
    )

    current = registry.list_latest_entities("Project")
    assert [(row["entity_id"], row["revision"]) for row in current] == [
        ("project:a", "rev-2"),
        ("project:b", "rev-1"),
    ]
    assert current[0]["payload"] == {"name": "A"}

    evidence = registry.list_evidence(candidate="sha-1")
    assert [row["evidence_id"] for row in evidence] == ["evidence:a", "evidence:z"]
    assert [row["state"] for row in evidence] == ["PASS", "STALE"]


def test_dashboard_projection_preserves_factory_truth_boundaries(tmp_path: Path) -> None:
    from hermes_factory.dashboard.projection import FactoryDashboardProjection

    registry = SemanticRegistry(tmp_path / "registry.db")
    registry.repository("Project").put(
        "project:factory", "rev-1", {"name": "Hermes Factory"}
    )
    registry.repository("WorkPackage").put(
        "wp:dashboard",
        "rev-1",
        {
            "profile_id": "factory-software-engineer",
            "skills": ["factory-reading-project-truth"],
            "stage": "CI",
        },
    )
    registry.repository("PR").put("pr:2", "rev-1", {"number": 2, "head": "sha-1"})
    registry.repository("AcceptanceDecision").put(
        "acceptance:repository",
        "rev-1",
        {"class": "REPOSITORY", "state": "HOLD"},
    )
    registry.record_evidence(
        "evidence:stale",
        kind="CI",
        state="STALE",
        candidate="sha-1",
        payload={"check": "pytest"},
    )
    registry.record_evidence(
        "evidence:other",
        kind="CI",
        state="PASS",
        candidate="sha-2",
        payload={"check": "pytest"},
    )

    snapshot = FactoryDashboardProjection(registry).snapshot(
        candidate="sha-1",
        jds_gates=({"gate_id": "unit", "state": "NOT_RUN"},),
        agent_evals=({"profile_id": "factory-software-engineer", "state": "PASS"},),
        skill_evals=({"skill_id": "factory-reading-project-truth", "state": "NOT_RUN"},),
    )

    assert snapshot["schema_version"] == "1.0"
    assert snapshot["candidate"] == "sha-1"
    assert snapshot["projects"][0]["entity_id"] == "project:factory"
    assert snapshot["work_packages"][0]["payload"]["stage"] == "CI"
    assert snapshot["scm"][0]["entity_type"] == "PR"
    assert snapshot["acceptance"][0]["payload"]["state"] == "HOLD"
    assert [item["evidence_id"] for item in snapshot["evidence"]] == ["evidence:stale"]
    assert snapshot["evidence"][0]["state"] == "STALE"
    assert snapshot["jds_gates"][0]["state"] == "NOT_RUN"
    assert snapshot["skill_evals"][0]["state"] == "NOT_RUN"

    required_sections = {
        "projects",
        "epics",
        "work_packages",
        "requirements",
        "kanban",
        "scm",
        "uat",
        "corrective_action",
        "hitl",
        "runtime",
        "acceptance",
        "evidence",
        "jds_gates",
        "agent_evals",
        "skill_evals",
    }
    assert required_sections.issubset(snapshot)


def test_dashboard_plugin_uses_native_read_only_contract() -> None:
    manifest = json.loads((PLUGIN_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "hermes-factory"
    assert manifest["tab"]["path"] == "/factory"
    assert manifest["entry"] == "dist/index.js"
    assert manifest["api"] == "plugin_api.py"

    bundle = (PLUGIN_ROOT / "dist" / "index.js").read_text(encoding="utf-8")
    assert "__HERMES_PLUGIN_SDK__" in bundle
    assert "__HERMES_PLUGINS__" in bundle
    assert "/api/plugins/hermes-factory/snapshot" in bundle

    backend = (PLUGIN_ROOT / "plugin_api.py").read_text(encoding="utf-8")
    assert '@router.get("/snapshot")' in backend
    for method in ("post", "put", "patch", "delete"):
        assert f"@router.{method}(" not in backend

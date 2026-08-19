from collections.abc import Mapping, Sequence
from typing import Any

from hermes_factory.traceability.registry import SemanticRegistry


class FactoryDashboardProjection:
    """Read-only semantic overlay for the native Hermes Dashboard."""

    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry

    def _current(self, *entity_types: str) -> list[dict[str, Any]]:
        records = [
            record
            for entity_type in entity_types
            for record in self._registry.list_latest_entities(entity_type)
        ]
        return sorted(
            records,
            key=lambda record: (
                str(record["entity_type"]),
                str(record["entity_id"]),
            ),
        )

    @staticmethod
    def _copy_records(
        records: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        return [dict(record) for record in records]

    def snapshot(
        self,
        *,
        candidate: str | None = None,
        jds_gates: Sequence[Mapping[str, Any]] = (),
        agent_evals: Sequence[Mapping[str, Any]] = (),
        skill_evals: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        """Project current canonical truth without deriving optimistic state."""
        return {
            "schema_version": "1.0",
            "candidate": candidate,
            "projects": self._current("Project"),
            "epics": self._current("Epic"),
            "work_packages": self._current("WorkPackage"),
            "requirements": self._current("Requirement", "AcceptanceCriterion"),
            "kanban": self._current("KanbanTaskRef", "Execution"),
            "scm": self._current("Branch", "PR", "SHA", "CI"),
            "uat": self._current("UATScenario", "UATExecution", "UATEvidence"),
            "corrective_action": self._current("Finding", "ReworkOrder"),
            "hitl": self._current("HITLRequest", "HumanDecision"),
            "runtime": self._current("Deployment", "RuntimeEvidence"),
            "acceptance": self._current("AcceptanceDecision"),
            "evidence": self._registry.list_evidence(candidate=candidate),
            "jds_gates": self._copy_records(jds_gates),
            "agent_evals": self._copy_records(agent_evals),
            "skill_evals": self._copy_records(skill_evals),
        }

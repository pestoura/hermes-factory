from __future__ import annotations

import re
from contextlib import AbstractContextManager
from typing import Protocol, TypedDict

from hermes_factory.domain import HandoffState
from hermes_factory.handoff.service import HandoffRecord, HandoffService
from hermes_factory.runtime.project_materializer import (
    _CANDIDATE_BOUND_STAGES,
    _REVIEW_STAGES,
)


class CompletionHandoffError(RuntimeError):
    pass


class HandoffPayload(TypedDict):
    stage_outcome: str
    artifact_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evidence_states: tuple[str, ...]
    finding_state: str
    context_revision: str
    candidate_identity: str | None
    independent_review_state: str | None


class NativeCompletionRuntime(Protocol):
    def connect_closing(self, *, board: str) -> AbstractContextManager[object]: ...
    def get_task(self, conn: object, task_id: str) -> object | None: ...
    def latest_run(self, conn: object, task_id: str) -> object | None: ...
    def child_ids(self, conn: object, task_id: str) -> list[str]: ...
    def parent_ids(self, conn: object, task_id: str) -> list[str]: ...


class CandidateIdentityObserver(Protocol):
    def observe(self, *, board: str, task: object) -> str | None: ...


_TASK_KEY = re.compile(
    r"^factory:(?P<project>[^:]+):(?P<wp>[^:]+):"
    r"(?P<stage>[A-Z0-9_]+):(?P<context>[0-9a-f]{64})"
    r"(?P<contract>\.stage-contract-v[1-9][0-9]*)?$"
)


class CompletionHandoffCoordinator:
    def __init__(
        self,
        *,
        native: NativeCompletionRuntime,
        handoff_service: HandoffService,
        candidate_observer: CandidateIdentityObserver | None = None,
    ) -> None:
        self._native = native
        self._handoff = handoff_service
        self._candidate_observer = candidate_observer

    def on_task_completed(
        self,
        *,
        task_id: str,
        board: str,
    ) -> tuple[HandoffState, ...]:
        with self._native.connect_closing(board=board) as conn:
            task = self._native.get_task(conn, task_id)
            if task is None:
                return ()
            identity = _parse_task_identity(getattr(task, "idempotency_key", None))
            if identity is None:
                return ()
            project_id, work_package_id, stage, context_revision, materialization_revision = identity
            if project_id != board:
                raise CompletionHandoffError(
                    "Factory task project identity does not match product board"
                )
            run = self._native.latest_run(conn, task_id)
            if run is None or getattr(run, "outcome", None) != "completed":
                raise CompletionHandoffError("Factory task has no durable completed run")
            payload = _handoff_payload(getattr(run, "metadata", None))
            children = tuple(self._native.child_ids(conn, task_id))
            child_state = {
                child_id: self._native.get_task(conn, child_id)
                for child_id in children
            }
            parent_state = {
                child_id: tuple(
                    self._native.get_task(conn, parent_id)
                    for parent_id in self._native.parent_ids(conn, child_id)
                )
                for child_id in children
            }

        if payload["context_revision"] != context_revision:
            raise CompletionHandoffError("Factory handoff context revision is stale")

        observed_candidate: str | None = None
        if stage in _CANDIDATE_BOUND_STAGES or payload["candidate_identity"] is not None:
            if self._candidate_observer is None:
                raise CompletionHandoffError(
                    "candidate identity observer is required for asserted or candidate-bound identity"
                )
            observed_candidate = self._candidate_observer.observe(
                board=board, task=task
            )
            if not isinstance(observed_candidate, str) or not observed_candidate.strip():
                raise CompletionHandoffError(
                    "candidate identity observation is unavailable"
                )
            observed_candidate = observed_candidate.strip()

        states: list[HandoffState] = []
        for child_id in children:
            child = child_state[child_id]
            if child is None:
                raise CompletionHandoffError(f"Factory child task {child_id} is missing")
            child_identity = _parse_task_identity(
                getattr(child, "idempotency_key", None)
            )
            if child_identity is None:
                raise CompletionHandoffError(
                    f"Factory child task {child_id} lacks semantic identity"
                )
            child_project, _, _, child_context, child_materialization = child_identity
            if (
                child_project != project_id
                or child_context != context_revision
                or child_materialization != materialization_revision
            ):
                raise CompletionHandoffError("Factory child task identity is stale or cross-project")
            prerequisites = tuple(
                parent is not None and getattr(parent, "status", None) == "done"
                for parent in parent_state[child_id]
            )
            record = HandoffRecord(
                handoff_id=f"handoff:{task_id}:{child_id}:{materialization_revision}",
                project_id=project_id,
                work_package_id=work_package_id,
                stage=stage,
                producer_profile=str(getattr(task, "assignee", "")),
                stage_outcome=payload["stage_outcome"],
                artifact_refs=payload["artifact_refs"],
                evidence_refs=payload["evidence_refs"],
                evidence_states=payload["evidence_states"],
                finding_state=payload["finding_state"],
                next_stage_prerequisites=prerequisites,
                context_revision=payload["context_revision"],
                candidate_identity=payload["candidate_identity"],
                candidate_identity_required=stage in _CANDIDATE_BOUND_STAGES,
                independent_review_required=stage in _REVIEW_STAGES,
                independent_review_state=payload["independent_review_state"],
            )
            try:
                state = self._handoff.promote(
                    record,
                    current_context_revision=context_revision,
                    current_candidate_identity=observed_candidate,
                    next_board=board,
                    next_task_id=child_id,
                    actor="factory-orchestrator",
                )
            except (TypeError, ValueError, RuntimeError) as exc:
                raise CompletionHandoffError(str(exc)) from exc
            states.append(state)
        return tuple(states)


def _parse_task_identity(value: object) -> tuple[str, str, str, str, str] | None:
    if not isinstance(value, str):
        return None
    match = _TASK_KEY.fullmatch(value.strip())
    if match is None:
        return None
    context_revision = match.group("context")
    contract = match.group("contract") or ""
    return (
        match.group("project"),
        match.group("wp"),
        match.group("stage"),
        context_revision,
        context_revision + contract,
    )


def validate_factory_completion_metadata(
    *,
    idempotency_key: object,
    metadata: object,
) -> HandoffPayload:
    identity = _parse_task_identity(idempotency_key)
    if identity is None:
        raise CompletionHandoffError("Factory completion lacks semantic task identity")
    _, _, stage, context_revision, _ = identity
    payload = _handoff_payload(metadata)
    if payload["context_revision"] != context_revision:
        raise CompletionHandoffError("Factory completion context revision is stale")
    if payload["stage_outcome"] != "PASS":
        raise CompletionHandoffError(
            "Factory kanban_complete requires stage_outcome=PASS; block the task instead"
        )
    if payload["finding_state"] not in {"NONE", "RESOLVED"}:
        raise CompletionHandoffError(
            "Factory kanban_complete requires finding_state NONE or RESOLVED"
        )
    if any(state != "PASS" for state in payload["evidence_states"]):
        raise CompletionHandoffError(
            "Factory kanban_complete requires all evidence_states=PASS"
        )
    if stage in _CANDIDATE_BOUND_STAGES and not payload["candidate_identity"]:
        raise CompletionHandoffError(
            "Factory kanban_complete requires candidate_identity for this stage"
        )
    if (
        stage in _REVIEW_STAGES
        and payload["independent_review_state"] != "PASS"
    ):
        raise CompletionHandoffError(
            "Factory kanban_complete requires independent_review_state=PASS for this stage"
        )
    return payload


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CompletionHandoffError(f"factory_handoff.{field} must be a non-empty list")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise CompletionHandoffError(f"factory_handoff.{field} contains an empty value")
    return result


def _handoff_payload(metadata: object) -> HandoffPayload:
    if not isinstance(metadata, dict):
        raise CompletionHandoffError("completed Factory run lacks metadata.factory_handoff")
    raw = metadata.get("factory_handoff")
    if not isinstance(raw, dict):
        raise CompletionHandoffError("completed Factory run lacks metadata.factory_handoff")
    if raw.get("schema") != "hermes.factory/handoff-completion/v1":
        raise CompletionHandoffError("unsupported factory_handoff schema")

    stage_outcome = raw.get("stage_outcome")
    finding_state = raw.get("finding_state")
    context_revision = raw.get("context_revision")
    if not isinstance(stage_outcome, str) or not stage_outcome.strip():
        raise CompletionHandoffError("factory_handoff.stage_outcome is required")
    stage_outcome = stage_outcome.strip()
    if stage_outcome not in {"PASS", "BLOCKED", "UNKNOWN", "NOT_RUN"}:
        raise CompletionHandoffError("factory_handoff.stage_outcome is invalid")
    if not isinstance(finding_state, str) or not finding_state.strip():
        raise CompletionHandoffError("factory_handoff.finding_state is required")
    finding_state = finding_state.strip()
    if finding_state not in {"NONE", "RESOLVED", "OPEN"}:
        raise CompletionHandoffError("factory_handoff.finding_state is invalid")
    if not isinstance(context_revision, str) or not context_revision.strip():
        raise CompletionHandoffError("factory_handoff.context_revision is required")

    candidate = raw.get("candidate_identity")
    if candidate is not None and (not isinstance(candidate, str) or not candidate.strip()):
        raise CompletionHandoffError("factory_handoff.candidate_identity is invalid")
    review_state = raw.get("independent_review_state")
    if review_state is not None and (
        not isinstance(review_state, str) or not review_state.strip()
    ):
        raise CompletionHandoffError("factory_handoff.independent_review_state is invalid")

    evidence_refs = _string_tuple(raw.get("evidence_refs"), "evidence_refs")
    evidence_states = _string_tuple(raw.get("evidence_states"), "evidence_states")
    if len(evidence_refs) != len(evidence_states):
        raise CompletionHandoffError("factory_handoff evidence refs/states length mismatch")
    return {
        "stage_outcome": stage_outcome,
        "artifact_refs": _string_tuple(raw.get("artifact_refs"), "artifact_refs"),
        "evidence_refs": evidence_refs,
        "evidence_states": evidence_states,
        "finding_state": finding_state,
        "context_revision": context_revision.strip(),
        "candidate_identity": candidate.strip() if isinstance(candidate, str) else None,
        "independent_review_state": (
            review_state.strip() if isinstance(review_state, str) else None
        ),
    }

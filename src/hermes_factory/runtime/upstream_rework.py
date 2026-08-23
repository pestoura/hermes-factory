from __future__ import annotations

import hashlib
import json
import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from hermes_factory.adapters.hermes_kanban import KanbanTaskProjection
from hermes_factory.runtime.project_materializer import stage_mutation_policy


class UpstreamReworkError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpstreamReworkRequest:
    producer_stage: str
    finding: str
    evidence_refs: tuple[str, ...]


class CandidateObserver(Protocol):
    def observe(self, *, board: str, task: object) -> str | None: ...


class NativeReworkRuntime(Protocol):
    def connect_closing(self, *, board: str) -> AbstractContextManager[object]: ...
    def get_task(self, conn: object, task_id: str) -> object | None: ...
    def latest_run(self, conn: object, task_id: str) -> object | None: ...
    def parent_ids(self, conn: object, task_id: str) -> list[str]: ...
    def link_tasks(self, conn: object, parent_id: str, child_id: str) -> None: ...


class ReworkProjectionAdapter(Protocol):
    def project_task(self, spec: KanbanTaskProjection) -> str: ...
    def authorize_dispatch(
        self, *, board: str, task_id: str, actor: str, source: str
    ) -> None: ...


_PREFIX = "[factory:upstream-rework/v1] "
_SHA = re.compile(r"^[0-9a-f]{40}$")
_TASK_KEY = re.compile(
    r"^factory:(?P<project>[^:]+):(?P<wp>[^:]+):"
    r"(?P<stage>[A-Z0-9_]+):(?P<context>[0-9a-f]{64})"
    r"(?P<contract>\.stage-contract-v[1-9][0-9]*)?$"
)
_REWORK_WP = re.compile(
    r"^.+~rework-[a-z0-9_]+-r[0-9]+-[0-9a-f]{12}$"
)
_CONTRACT_VERSION = re.compile(r"\.stage-contract-v(?P<version>[1-9][0-9]*)$")




def is_upstream_rework_task_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    match = _TASK_KEY.fullmatch(value.strip())
    return match is not None and _REWORK_WP.fullmatch(match.group("wp")) is not None


def parse_upstream_rework_request(reason: str) -> UpstreamReworkRequest | None:
    if not isinstance(reason, str) or not reason.startswith(_PREFIX):
        return None
    try:
        payload = json.loads(reason[len(_PREFIX) :])
    except json.JSONDecodeError as exc:
        raise UpstreamReworkError("upstream rework request JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise UpstreamReworkError("upstream rework request must be an object")
    stage = payload.get("producer_stage")
    finding = payload.get("finding")
    evidence = payload.get("evidence_refs")
    if not isinstance(stage, str) or not stage.strip():
        raise UpstreamReworkError("producer_stage is required")
    stage = stage.strip().upper()
    try:
        stage_mutation_policy(stage)
    except ValueError as exc:
        raise UpstreamReworkError(f"unknown producer stage {stage}") from exc
    if not isinstance(finding, str) or not finding.strip():
        raise UpstreamReworkError("finding is required")
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(item, str) or not item.strip() for item in evidence)
    ):
        raise UpstreamReworkError("evidence_refs must be a non-empty string list")
    return UpstreamReworkRequest(
        producer_stage=stage,
        finding=finding.strip(),
        evidence_refs=tuple(item.strip() for item in evidence),
    )


def _identity(task: object) -> tuple[str, str, str, str, str]:
    key = getattr(task, "idempotency_key", None)
    match = _TASK_KEY.fullmatch(key.strip()) if isinstance(key, str) else None
    if match is None:
        raise UpstreamReworkError("Factory task semantic identity is unavailable")
    context = match.group("context")
    contract = match.group("contract") or ""
    return (
        match.group("project"), match.group("wp"), match.group("stage"),
        context, context + contract,
    )


def _candidate_from_run(run: object | None) -> str:
    if run is None or getattr(run, "outcome", None) != "completed":
        raise UpstreamReworkError("producer has no durable completed run")
    metadata = getattr(run, "metadata", None)
    if not isinstance(metadata, dict):
        raise UpstreamReworkError("producer handoff metadata is unavailable")
    handoff = metadata.get("factory_handoff")
    candidate = handoff.get("candidate_identity") if isinstance(handoff, dict) else None
    if not isinstance(candidate, str) or not _SHA.fullmatch(candidate.strip().lower()):
        raise UpstreamReworkError("producer candidate identity is unavailable")
    return candidate.strip().lower()


def _request_digest(request: UpstreamReworkRequest) -> str:
    payload = json.dumps(
        {
            "producer_stage": request.producer_stage,
            "finding": request.finding,
            "evidence_refs": list(request.evidence_refs),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def _rework_body(
    *, request: UpstreamReworkRequest, context: str, consumer_task_id: str
) -> str:
    policy = stage_mutation_policy(request.producer_stage)
    handoff = {
        "schema": "hermes.factory/handoff-completion/v1",
        "stage_outcome": "PASS",
        "artifact_refs": ["corrected-artifact-ref"],
        "evidence_refs": ["verification-ref"],
        "evidence_states": ["PASS"],
        "finding_state": "RESOLVED",
        "context_revision": context,
        "candidate_identity": "exact-clean-head-sha",
        "independent_review_state": None,
    }
    return "\n".join(
        (
            f"Factory upstream rework for consumer: {consumer_task_id}",
            f"Producer stage: {request.producer_stage}",
            f"Finding: {request.finding}",
            "Evidence refs: " + ", ".join(request.evidence_refs),
            "Fix only the upstream artifact defect described above; do not expand scope.",
            f"repository_mutation_policy={policy}",
            "Use the assigned shared worktree only.",
            "Commit only the bounded rework changes and leave the worktree clean.",
            "At completion provide metadata.factory_handoff: "
            + json.dumps(handoff, sort_keys=True, separators=(",", ":")),
            "candidate_identity must equal the clean worktree HEAD.",
        )
    )


class UpstreamReworkCoordinator:
    def __init__(
        self,
        *,
        native: NativeReworkRuntime,
        adapter: ReworkProjectionAdapter,
        candidate_observer: CandidateObserver,
    ) -> None:
        self._native = native
        self._adapter = adapter
        self._candidate_observer = candidate_observer

    def schedule(
        self,
        *,
        board: str,
        consumer_task_id: str,
        request: UpstreamReworkRequest,
    ) -> str:
        with self._native.connect_closing(board=board) as conn:
            consumer = self._native.get_task(conn, consumer_task_id)
            if consumer is None:
                raise UpstreamReworkError("consumer task does not exist")
            project, wp, _, context, materialization = _identity(consumer)
            version = _CONTRACT_VERSION.search(materialization)
            if version is None or int(version.group("version")) < 10:
                raise UpstreamReworkError(
                    "upstream rework requires stage-contract-v10 or newer"
                )
            if project != board:
                raise UpstreamReworkError("consumer project does not match board")
            run_id = getattr(consumer, "current_run_id", None)
            if not isinstance(run_id, int):
                raise UpstreamReworkError("consumer active run identity is unavailable")
            matching: list[tuple[str, object]] = []
            for parent_id in self._native.parent_ids(conn, consumer_task_id):
                parent = self._native.get_task(conn, parent_id)
                if parent is None:
                    continue
                p_project, p_wp, p_stage, p_context, p_materialization = _identity(parent)
                if (
                    p_project == project
                    and p_wp == wp
                    and p_context == context
                    and p_materialization == materialization
                    and p_stage == request.producer_stage
                ):
                    matching.append((parent_id, parent))
            if len(matching) != 1:
                raise UpstreamReworkError(
                    "producer_stage must identify exactly one direct parent stage"
                )
            producer_id, producer = matching[0]
            producer_sha = _candidate_from_run(
                self._native.latest_run(conn, producer_id)
            )

        observed = self._candidate_observer.observe(board=board, task=consumer)
        if not isinstance(observed, str) or observed.strip().lower() != producer_sha:
            raise UpstreamReworkError(
                "consumer worktree must be clean at the producer candidate before rework"
            )

        digest = _request_digest(request)
        rework_wp = (
            f"{wp}~rework-{request.producer_stage.lower()}-r{run_id}-{digest}"
        )
        skills = getattr(producer, "skills", ())
        if not isinstance(skills, (tuple, list)):
            raise UpstreamReworkError("producer task Skills are unavailable")
        spec = KanbanTaskProjection(
            project_key=project,
            work_package_id=rework_wp,
            stage=request.producer_stage,
            revision=materialization,
            title=f"{wp}/{request.producer_stage} rework: {request.finding[:120]}",
            body=_rework_body(
                request=request, context=context, consumer_task_id=consumer_task_id
            ),
            assignee=str(getattr(producer, "assignee", "")),
            approved_skills=tuple(skills),
            board=board,
            parent_task_ids=(producer_id,),
            priority=int(getattr(consumer, "priority", 0) or 0),
            workspace_kind=str(getattr(consumer, "workspace_kind", "worktree")),
            workspace_path=getattr(consumer, "workspace_path", None),
            branch_name=getattr(consumer, "branch_name", None),
            project_id=getattr(consumer, "project_id", None),
        )
        rework_task_id = self._adapter.project_task(spec)
        with self._native.connect_closing(board=board) as conn:
            self._native.link_tasks(conn, rework_task_id, consumer_task_id)
            rework_task = self._native.get_task(conn, rework_task_id)
        if rework_task is None:
            raise UpstreamReworkError("projected rework task is unavailable")
        if getattr(rework_task, "status", None) not in {"blocked", "ready", "running", "done"}:
            raise UpstreamReworkError("rework task is not dispatchable")
        return rework_task_id

    def activate_pending(
        self,
        *,
        board: str,
        consumer_task_id: str,
        request: UpstreamReworkRequest,
    ) -> str:
        digest = _request_digest(request)
        with self._native.connect_closing(board=board) as conn:
            consumer = self._native.get_task(conn, consumer_task_id)
            if consumer is None:
                raise UpstreamReworkError("consumer task does not exist")
            if getattr(consumer, "status", None) != "todo":
                raise UpstreamReworkError(
                    "consumer must be in dependency wait before rework activation"
                )
            project, wp, _, context, materialization = _identity(consumer)
            matching: list[tuple[str, object]] = []
            for parent_id in self._native.parent_ids(conn, consumer_task_id):
                parent = self._native.get_task(conn, parent_id)
                if parent is None or not is_upstream_rework_task_key(
                    getattr(parent, "idempotency_key", None)
                ):
                    continue
                p_project, p_wp, p_stage, p_context, p_materialization = _identity(parent)
                active = getattr(parent, "status", None) in {"blocked", "ready", "running"}
                if (
                    active
                    and p_project == project
                    and p_stage == request.producer_stage
                    and p_context == context
                    and p_materialization == materialization
                    and p_wp.startswith(
                        f"{wp}~rework-{request.producer_stage.lower()}-r"
                    )
                    and p_wp.endswith(f"-{digest}")
                ):
                    matching.append((parent_id, parent))
            if len(matching) != 1:
                raise UpstreamReworkError(
                    "exactly one pending upstream rework dependency is required"
                )
            rework_task_id, rework_task = matching[0]

        if getattr(rework_task, "status", None) == "blocked":
            self._adapter.authorize_dispatch(
                board=board,
                task_id=rework_task_id,
                actor="factory-orchestrator",
                source="factory-upstream-rework",
            )
        return rework_task_id

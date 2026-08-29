from __future__ import annotations

import json
import os
import re
from typing import Any

from hermes_factory.runtime.completion_handoff import (
    CompletionHandoffError,
    validate_factory_completion_metadata,
)
from hermes_factory.runtime.git_read_boundary import (
    GitReadBoundaryError,
    guard_factory_terminal_git_read,
    is_canonical_git_boundary_revision,
)
from hermes_factory.runtime.workspace_read_boundary import (
    WorkspaceReadBoundaryError,
    guard_factory_workspace_access,
    is_workspace_read_boundary_revision,
)
from hermes_factory.runtime.installed_completion import (
    InstalledRuntimeBindingError,
    build_installed_completion_coordinator,
    build_installed_upstream_rework_coordinator,
    validate_factory_repository_precompletion,
)
from hermes_factory.runtime.skill_tool_guard import guard_factory_skill_tool_call
from hermes_factory.runtime.upstream_rework import (
    UpstreamReworkError,
    is_upstream_rework_task_key,
    parse_upstream_rework_request,
)

_SKILL_TOOLS = frozenset({"skills_list", "skill_view"})
_FACTORY_COMPLETE_TOOL = "kanban_complete"
_FACTORY_BLOCK_TOOL = "kanban_block"
_TERMINAL_TOOL = "terminal"
_KANBAN_SHOW_TOOL = "kanban_show"
_WORKSPACE_FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
_STAGE_CONTRACT_PATTERN = re.compile(r"\.stage-contract-v(\d+)$")


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _active_profile_name() -> str | None:
    try:
        from hermes_cli.profiles import get_active_profile_name

        value = get_active_profile_name()
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def _load_native_task(task_id: str, *, board: str | None = None) -> Any:
    from hermes_cli import kanban_db as kb

    resolved_board = board or os.getenv("HERMES_KANBAN_BOARD") or None
    with kb.connect_closing(board=resolved_board) as conn:
        return kb.get_task(conn, task_id)


def _on_pre_tool_call(
    tool_name: str = "",
    args: Any = None,
    task_id: str | None = None,
    **_: Any,
) -> dict[str, str] | None:
    if tool_name not in _SKILL_TOOLS and tool_name not in {_FACTORY_COMPLETE_TOOL, _FACTORY_BLOCK_TOOL, _TERMINAL_TOOL, _KANBAN_SHOW_TOOL} and tool_name not in _WORKSPACE_FILE_TOOLS:
        return None

    profile = _active_profile_name()
    native_task_id = (os.getenv("HERMES_KANBAN_TASK") or "").strip() or (task_id or "").strip()
    task = None
    if native_task_id:
        try:
            task = _load_native_task(native_task_id)
        except Exception:
            if isinstance(profile, str) and profile.startswith("factory-"):
                return _block("Factory task authorization lookup failed closed")
            return None

    task_assignee = getattr(task, "assignee", None) if task is not None else None
    task_key = getattr(task, "idempotency_key", None) if task is not None else None
    factory_profile = (
        isinstance(profile, str) and profile.startswith("factory-")
        or isinstance(task_assignee, str) and task_assignee.startswith("factory-")
    )
    factory_task = isinstance(task_key, str) and task_key.startswith("factory:")

    if tool_name in _WORKSPACE_FILE_TOOLS:
        if factory_task and is_workspace_read_boundary_revision(task_key):
            try:
                guard_factory_workspace_access(
                    tool_name=tool_name,
                    args=args,
                    workspace_path=getattr(task, "workspace_path", None),
                )
            except WorkspaceReadBoundaryError as exc:
                return _block(f"Factory workspace read boundary failed: {exc}")
        return None

    if tool_name == _KANBAN_SHOW_TOOL:
        if not factory_task or not _is_generation_scoped_context_revision(task_key):
            return None
        if not isinstance(args, dict):
            return _block("Factory generation-scoped kanban_show requires structured arguments")
        requested_task = args.get("task_id")
        if (
            isinstance(requested_task, str)
            and requested_task
            and requested_task != native_task_id
        ):
            return _block("Factory generation-scoped worker context blocks cross-task kanban_show reads")
        resolved_board = (os.getenv("HERMES_KANBAN_BOARD") or "").strip()
        requested_board = args.get("board")
        if (
            isinstance(requested_board, str)
            and requested_board.strip()
            and requested_board.strip() != resolved_board
        ):
            return _block("Factory generation-scoped worker context blocks cross-board kanban_show reads")
        return None

    if tool_name == _TERMINAL_TOOL:
        if not factory_task:
            return None
        if is_workspace_read_boundary_revision(task_key):
            try:
                guard_factory_workspace_access(
                    tool_name=tool_name,
                    args=args,
                    workspace_path=getattr(task, "workspace_path", None),
                )
            except WorkspaceReadBoundaryError as exc:
                return _block(f"Factory workspace read boundary failed: {exc}")
        if not is_canonical_git_boundary_revision(task_key):
            return None
        try:
            guard_factory_terminal_git_read(
                args=args, workspace_path=getattr(task, "workspace_path", None)
            )
        except GitReadBoundaryError as exc:
            return _block(f"Factory canonical Git read boundary failed: {exc}")
        return None

    if tool_name == _FACTORY_BLOCK_TOOL:
        if not factory_task or not isinstance(args, dict):
            return None
        reason = args.get("reason")
        try:
            request = parse_upstream_rework_request(reason) if isinstance(reason, str) else None
        except UpstreamReworkError as exc:
            return _block(f"Factory upstream rework validation failed: {exc}")
        if request is None:
            return None
        if args.get("kind") != "dependency":
            return _block("Factory upstream rework requires kanban_block kind=dependency")
        requested_task = args.get("task_id")
        if (
            isinstance(requested_task, str)
            and requested_task
            and requested_task != native_task_id
        ):
            return _block("Factory upstream rework task_id does not match native task context")
        resolved_board = (os.getenv("HERMES_KANBAN_BOARD") or "").strip()
        if not resolved_board:
            return _block("Factory upstream rework requires native Kanban board context")
        requested_board = args.get("board")
        if (
            isinstance(requested_board, str)
            and requested_board.strip()
            and requested_board.strip() != resolved_board
        ):
            return _block("Factory upstream rework board does not match native board context")
        try:
            coordinator = build_installed_upstream_rework_coordinator()
            coordinator.schedule(
                board=resolved_board,
                consumer_task_id=native_task_id,
                request=request,
            )
        except (UpstreamReworkError, RuntimeError, ValueError, TypeError) as exc:
            return _block(f"Factory upstream rework validation failed: {exc}")
        return None

    if tool_name == _FACTORY_COMPLETE_TOOL:
        if not native_task_id:
            return (
                _block("Factory completion requires native Kanban task context")
                if factory_profile
                else None
            )
        if not factory_task:
            return None
        if not isinstance(args, dict):
            return _block("Factory completion requires structured tool arguments")
        requested_task = args.get("task_id")
        if isinstance(requested_task, str) and requested_task and requested_task != native_task_id:
            return _block("Factory completion task_id does not match native task context")
        try:
            payload = validate_factory_completion_metadata(
                idempotency_key=task_key,
                metadata=args.get("metadata"),
            )
            validate_factory_repository_precompletion(
                board=(os.getenv("HERMES_KANBAN_BOARD") or "").strip(),
                task=task,
                candidate_identity=payload["candidate_identity"],
            )
        except (CompletionHandoffError, InstalledRuntimeBindingError) as exc:
            return _block(f"Factory completion validation failed: {exc}")
        return None

    if not factory_profile:
        return None
    if not native_task_id:
        return _block("Factory Skill tool call requires native Kanban task context")
    if profile is None and isinstance(task_assignee, str):
        profile = task_assignee

    return guard_factory_skill_tool_call(
        tool_name=tool_name,
        args=args,
        task_id=native_task_id,
        profile_name=profile,
        task=task,
    )


def _is_generation_scoped_context_revision(task_key: object) -> bool:
    if not isinstance(task_key, str) or not task_key.startswith("factory:"):
        return False
    match = _STAGE_CONTRACT_PATTERN.search(task_key)
    return match is not None and int(match.group(1)) >= 14


def _strip_cross_task_role_history(
    worker_context: str, *, assignee: str | None
) -> str:
    target = f"## Recent work by @{assignee}" if assignee else None
    lines = worker_context.splitlines(keepends=True)
    sanitized: list[str] = []
    skipping = False
    for line in lines:
        heading = line.rstrip("\r\n")
        is_role_history = (
            heading == target if target is not None else heading.startswith("## Recent work by @")
        )
        if is_role_history:
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            sanitized.append(line)
    return "".join(sanitized)


def _result_declares_generation_scoped_context(payload: dict[str, Any]) -> bool:
    task_payload = payload.get("task")
    if not isinstance(task_payload, dict):
        return False
    body = task_payload.get("body")
    return (
        isinstance(body, str)
        and "Use generation-scoped worker context only;" in body
    )


def _on_transform_tool_result(
    tool_name: str = "",
    result: Any = None,
    task_id: str | None = None,
    **_: Any,
) -> str | None:
    if tool_name != _KANBAN_SHOW_TOOL or not isinstance(result, str):
        return None
    native_task_id = (
        (os.getenv("HERMES_KANBAN_TASK") or "").strip()
        or (task_id or "").strip()
    )
    if not native_task_id:
        return None
    native_task = None
    try:
        native_task = _load_native_task(native_task_id)
    except Exception:
        pass
    native_v14 = _is_generation_scoped_context_revision(
        getattr(native_task, "idempotency_key", None)
    )

    try:
        payload = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        if native_v14:
            return json.dumps(
                {"error": "Factory generation-scoped worker context blocked malformed kanban_show result"},
                ensure_ascii=False,
            )
        return None
    if not isinstance(payload, dict):
        if native_v14:
            return json.dumps(
                {"error": "Factory generation-scoped worker context blocked malformed kanban_show result"},
                ensure_ascii=False,
            )
        return None

    result_v14 = _result_declares_generation_scoped_context(payload)
    if native_task is not None:
        if not native_v14:
            return None
    elif not result_v14:
        return None

    task_payload = payload.get("task")
    result_task_id = task_payload.get("id") if isinstance(task_payload, dict) else None
    if result_task_id != native_task_id:
        return json.dumps(
            {"error": "Factory generation-scoped worker context blocks cross-task kanban_show result"},
            ensure_ascii=False,
        )

    worker_context = payload.get("worker_context")
    if not isinstance(worker_context, str):
        return None
    result_assignee = (
        task_payload.get("assignee") if isinstance(task_payload, dict) else None
    )
    native_assignee = getattr(native_task, "assignee", None)
    assignee = (
        native_assignee
        if isinstance(native_assignee, str) and native_assignee
        else result_assignee if isinstance(result_assignee, str) and result_assignee else None
    )
    sanitized = _strip_cross_task_role_history(
        worker_context, assignee=assignee
    )
    if sanitized == worker_context:
        return None
    payload["worker_context"] = sanitized
    return json.dumps(payload, ensure_ascii=False)


def _on_post_tool_call(
    tool_name: str = "",
    args: Any = None,
    task_id: str | None = None,
    **_: Any,
) -> None:
    if tool_name != _FACTORY_BLOCK_TOOL or not isinstance(args, dict):
        return
    reason = args.get("reason")
    try:
        request = parse_upstream_rework_request(reason) if isinstance(reason, str) else None
    except UpstreamReworkError:
        return
    if request is None or args.get("kind") != "dependency":
        return
    native_task_id = (
        (task_id or "").strip()
        or (os.getenv("HERMES_KANBAN_TASK") or "").strip()
    )
    resolved_board = (os.getenv("HERMES_KANBAN_BOARD") or "").strip()
    if not native_task_id or not resolved_board:
        return
    try:
        coordinator = build_installed_upstream_rework_coordinator()
        coordinator.activate_pending(
            board=resolved_board,
            consumer_task_id=native_task_id,
            request=request,
        )
    except (UpstreamReworkError, RuntimeError, ValueError, TypeError) as exc:
        _record_handoff_blocked(
            board=resolved_board, task_id=native_task_id, error=exc
        )


def register(ctx: Any) -> None:
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("transform_tool_result", _on_transform_tool_result)
    ctx.register_hook("kanban_task_completed", _on_kanban_task_completed)

def _record_handoff_blocked(*, board: str, task_id: str, error: Exception) -> None:
    try:
        from hermes_cli import kanban_db as kb

        payload = json.dumps(
            {
                "error_type": type(error).__name__,
                "message": str(error)[:1000],
                "task_id": task_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        with kb.connect_closing(board=board) as conn:
            kb.add_comment(
                conn, task_id, "hermes-factory",
                f"[factory:handoff-blocked/v1] {payload}",
            )
    except Exception:
        return


def _on_kanban_task_completed(
    task_id: str = "",
    board: str | None = None,
    **_: Any,
) -> None:
    native_task_id = (task_id or "").strip()
    resolved_board = (board or os.getenv("HERMES_KANBAN_BOARD") or "").strip()
    if not native_task_id or not resolved_board:
        return
    try:
        task = _load_native_task(native_task_id, board=resolved_board)
    except Exception:
        return
    key = getattr(task, "idempotency_key", None) if task is not None else None
    if not isinstance(key, str) or not key.startswith("factory:"):
        return
    if is_upstream_rework_task_key(key):
        return
    try:
        coordinator = build_installed_completion_coordinator()
        coordinator.on_task_completed(
            task_id=native_task_id, board=resolved_board
        )
    except Exception as exc:
        _record_handoff_blocked(
            board=resolved_board, task_id=native_task_id, error=exc
        )

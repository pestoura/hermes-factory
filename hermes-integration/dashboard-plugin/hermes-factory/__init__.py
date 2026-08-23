from __future__ import annotations

import json
import os
from typing import Any

from hermes_factory.runtime.completion_handoff import (
    CompletionHandoffError,
    validate_factory_completion_metadata,
)
from hermes_factory.runtime.installed_completion import (
    InstalledRuntimeBindingError,
    build_installed_completion_coordinator,
    validate_factory_repository_precompletion,
)
from hermes_factory.runtime.skill_tool_guard import guard_factory_skill_tool_call

_SKILL_TOOLS = frozenset({"skills_list", "skill_view"})
_FACTORY_COMPLETE_TOOL = "kanban_complete"


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
    if tool_name not in _SKILL_TOOLS and tool_name != _FACTORY_COMPLETE_TOOL:
        return None

    profile = _active_profile_name()
    native_task_id = (os.getenv("HERMES_KANBAN_TASK") or "").strip()
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


def register(ctx: Any) -> None:
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
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
    try:
        coordinator = build_installed_completion_coordinator()
        coordinator.on_task_completed(
            task_id=native_task_id, board=resolved_board
        )
    except Exception as exc:
        _record_handoff_blocked(
            board=resolved_board, task_id=native_task_id, error=exc
        )

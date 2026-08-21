from __future__ import annotations

import os
from typing import Any

from hermes_factory.runtime.skill_tool_guard import guard_factory_skill_tool_call

_SKILL_TOOLS = frozenset({"skills_list", "skill_view"})


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _active_profile_name() -> str | None:
    try:
        from hermes_cli.profiles import get_active_profile_name

        value = get_active_profile_name()
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def _load_native_task(task_id: str) -> Any:
    from hermes_cli import kanban_db as kb

    board = os.getenv("HERMES_KANBAN_BOARD") or None
    with kb.connect_closing(board=board) as conn:
        return kb.get_task(conn, task_id)


def _on_pre_tool_call(
    tool_name: str = "",
    args: Any = None,
    task_id: str | None = None,
    **_: Any,
) -> dict[str, str] | None:
    if tool_name not in _SKILL_TOOLS:
        return None

    profile = _active_profile_name()
    native_task_id = (os.getenv("HERMES_KANBAN_TASK") or "").strip()
    task = None
    if native_task_id:
        try:
            task = _load_native_task(native_task_id)
        except Exception:
            if isinstance(profile, str) and profile.startswith("factory-"):
                return _block("Factory Skill authorization lookup failed closed")
            return None

    task_assignee = getattr(task, "assignee", None) if task is not None else None
    factory_context = (
        isinstance(profile, str)
        and profile.startswith("factory-")
        or isinstance(task_assignee, str)
        and task_assignee.startswith("factory-")
    )
    if not factory_context:
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

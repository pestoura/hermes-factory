from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class FactorySkillTask(Protocol):
    assignee: str
    skills: tuple[str, ...]


SkillToolDirective = dict[str, str]
_SKILL_TOOLS = frozenset({"skills_list", "skill_view"})


def _block(message: str) -> SkillToolDirective:
    return {"action": "block", "message": message}


def _is_factory_profile(value: object) -> bool:
    return isinstance(value, str) and value.startswith("factory-")


def guard_factory_skill_tool_call(
    *,
    tool_name: str,
    args: object,
    task_id: str | None,
    profile_name: str | None,
    task: FactorySkillTask | None,
) -> SkillToolDirective | None:
    """Enforce task-pinned Skill authority at Hermes' ``pre_tool_call`` boundary.

    The guard is deliberately inert for non-Skill tools and non-Factory
    Profiles. For a Factory Kanban worker, skill discovery is disabled and a
    Skill can be viewed only when its exact canonical identity is already
    pinned on the native Hermes task. Missing or inconsistent task context
    fails closed.
    """
    if tool_name not in _SKILL_TOOLS:
        return None

    task_assignee = getattr(task, "assignee", None) if task is not None else None
    if not (_is_factory_profile(profile_name) or _is_factory_profile(task_assignee)):
        return None

    if not isinstance(task_id, str) or not task_id.strip():
        return _block("Factory Skill tool call requires native task context")
    canonical_task_id = task_id.strip()

    if task is None:
        return _block(f"Factory task {canonical_task_id} authorization context is unavailable")
    if not isinstance(profile_name, str) or not profile_name.startswith("factory-"):
        return _block(f"Factory task {canonical_task_id} Profile identity is unavailable")
    if not isinstance(task.assignee, str) or task.assignee != profile_name:
        return _block(f"Factory task {canonical_task_id} Profile identity does not match assignee")
    if not isinstance(task.skills, (list, tuple)) or not all(
        isinstance(skill, str) and skill.startswith("factory-") for skill in task.skills
    ):
        return _block(f"Factory task {canonical_task_id} Skill authorization is invalid")

    if tool_name == "skills_list":
        return _block("Factory task Skill discovery is restricted to task-pinned Skills")

    if not isinstance(args, Mapping):
        return _block(f"Factory task {canonical_task_id} Skill request is invalid")
    requested = args.get("name")
    if not isinstance(requested, str) or not requested.strip():
        return _block(f"Factory task {canonical_task_id} Skill request is invalid")
    skill_id = requested.strip()
    if skill_id not in task.skills:
        return _block(
            f"Skill {skill_id} is not authorized for Factory task {canonical_task_id}"
        )
    return None

from __future__ import annotations

from dataclasses import dataclass

from hermes_factory.runtime.skill_tool_guard import guard_factory_skill_tool_call


@dataclass(frozen=True)
class FakeTask:
    assignee: str
    skills: tuple[str, ...]


def test_non_factory_profile_is_not_intercepted() -> None:
    task = FakeTask(assignee="general-worker", skills=("anything",))

    assert (
        guard_factory_skill_tool_call(
            tool_name="skill_view",
            args={"name": "anything"},
            task_id="t_1",
            profile_name="general-worker",
            task=task,
        )
        is None
    )


def test_factory_skills_list_is_blocked_to_prevent_unapproved_discovery() -> None:
    task = FakeTask(
        assignee="factory-software-engineer",
        skills=("factory-tdd-implementation", "factory-cli-engineering"),
    )

    result = guard_factory_skill_tool_call(
        tool_name="skills_list",
        args={},
        task_id="t_1",
        profile_name="factory-software-engineer",
        task=task,
    )

    assert result == {
        "action": "block",
        "message": "Factory task Skill discovery is restricted to task-pinned Skills",
    }


def test_factory_skill_view_allows_only_exact_task_pinned_skill() -> None:
    task = FakeTask(
        assignee="factory-software-engineer",
        skills=("factory-tdd-implementation", "factory-cli-engineering"),
    )

    allowed = guard_factory_skill_tool_call(
        tool_name="skill_view",
        args={"name": "factory-cli-engineering"},
        task_id="t_1",
        profile_name="factory-software-engineer",
        task=task,
    )
    blocked = guard_factory_skill_tool_call(
        tool_name="skill_view",
        args={"name": "factory-security-review"},
        task_id="t_1",
        profile_name="factory-software-engineer",
        task=task,
    )

    assert allowed is None
    assert blocked == {
        "action": "block",
        "message": "Skill factory-security-review is not authorized for Factory task t_1",
    }


def test_factory_skill_view_fails_closed_when_task_context_is_missing_or_mismatched() -> None:
    missing = guard_factory_skill_tool_call(
        tool_name="skill_view",
        args={"name": "factory-cli-engineering"},
        task_id="t_1",
        profile_name="factory-software-engineer",
        task=None,
    )
    mismatched = guard_factory_skill_tool_call(
        tool_name="skill_view",
        args={"name": "factory-cli-engineering"},
        task_id="t_1",
        profile_name="factory-software-engineer",
        task=FakeTask(
            assignee="factory-platform-engineer",
            skills=("factory-cli-engineering",),
        ),
    )

    assert missing is not None and missing["action"] == "block"
    assert mismatched is not None and mismatched["action"] == "block"


def test_unrelated_tool_is_not_intercepted_even_for_factory_task() -> None:
    task = FakeTask(
        assignee="factory-software-engineer",
        skills=("factory-tdd-implementation",),
    )

    assert (
        guard_factory_skill_tool_call(
            tool_name="read_file",
            args={"path": "README.md"},
            task_id="t_1",
            profile_name="factory-software-engineer",
            task=task,
        )
        is None
    )


def test_factory_skill_guard_accepts_native_list_representation() -> None:
    task = FakeTask(
        assignee="factory-software-engineer",
        skills=["factory-tdd-implementation"],  # type: ignore[arg-type]
    )

    assert guard_factory_skill_tool_call(
        tool_name="skill_view",
        args={"name": "factory-tdd-implementation"},
        task_id="t_1",
        profile_name="factory-software-engineer",
        task=task,
    ) is None

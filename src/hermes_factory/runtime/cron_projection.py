from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any


class CronProjectionError(ValueError):
    pass


_PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SKILL_ID = re.compile(r"^factory-[a-z0-9][a-z0-9-]*$")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret(?:id)?)\s*[:=]\s*\S+"
)


@dataclass(frozen=True)
class NativeCronCommand:
    profile_id: str
    duty_id: str
    argv: tuple[str, ...]

    def to_manifest(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "duty_id": self.duty_id,
            "argv": list(self.argv),
        }


@dataclass(frozen=True)
class NativeCronPlan:
    commands: tuple[NativeCronCommand, ...]
    execution_state: str
    execute: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/native-cron-install-plan/v1",
            "commands": [command.to_manifest() for command in self.commands],
            "execution_state": self.execution_state,
            "execute": self.execute,
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_manifest(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CronProjectionError(f"{label} must be a non-empty string")
    return value.strip()


def _reject_secret_like(value: str, label: str) -> None:
    if _SECRET_ASSIGNMENT.search(value):
        raise CronProjectionError(f"{label} contains secret-like material")


def _skills(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CronProjectionError("cron duty skills must be a sequence")
    skills: list[str] = []
    for item in value:
        skill = _require_string(item, "cron duty skill")
        if not _SKILL_ID.fullmatch(skill):
            raise CronProjectionError(
                f"cron duty skill must use canonical factory-* ID: {skill}"
            )
        skills.append(skill)
    if len(skills) != len(set(skills)):
        raise CronProjectionError("cron duty contains duplicate Skill IDs")
    return tuple(sorted(skills))


class NativeCronPlanBuilder:
    def build(
        self,
        duties_by_profile: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> NativeCronPlan:
        commands: list[NativeCronCommand] = []
        for profile_id in sorted(duties_by_profile):
            if not _PROFILE_ID.fullmatch(profile_id):
                raise CronProjectionError(f"invalid Hermes profile ID: {profile_id!r}")
            duties = duties_by_profile[profile_id]
            if not isinstance(duties, Sequence) or isinstance(duties, (str, bytes)):
                raise CronProjectionError(f"cron duties for profile {profile_id} must be a sequence")

            seen_ids: set[str] = set()
            normalized: list[tuple[str, str, str, tuple[str, ...]]] = []
            for duty in duties:
                if not isinstance(duty, Mapping):
                    raise CronProjectionError("cron duty must be a mapping")
                duty_id = _require_string(duty.get("id"), "cron duty id")
                if not _JOB_ID.fullmatch(duty_id):
                    raise CronProjectionError(f"invalid cron duty id: {duty_id!r}")
                if duty_id in seen_ids:
                    raise CronProjectionError(
                        f"duplicate cron duty id {duty_id!r} for profile {profile_id}"
                    )
                seen_ids.add(duty_id)

                schedule = _require_string(duty.get("schedule"), "cron duty schedule")
                prompt = _require_string(duty.get("prompt"), "cron duty prompt")
                _reject_secret_like(schedule, "cron duty schedule")
                _reject_secret_like(prompt, "cron duty prompt")
                skills = _skills(duty.get("skills"))
                normalized.append((duty_id, schedule, prompt, skills))

            for duty_id, schedule, prompt, skills in sorted(normalized):
                argv = [
                    "hermes",
                    "-p",
                    profile_id,
                    "cron",
                    "create",
                    schedule,
                    prompt,
                    "--name",
                    duty_id,
                ]
                for skill in skills:
                    argv.extend(("--skill", skill))
                commands.append(
                    NativeCronCommand(
                        profile_id=profile_id,
                        duty_id=duty_id,
                        argv=tuple(argv),
                    )
                )

        return NativeCronPlan(
            commands=tuple(commands),
            execution_state="NOT_RUN",
            execute=False,
        )

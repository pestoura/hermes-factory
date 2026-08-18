from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass


class HermesCronProjectionError(ValueError):
    pass


@dataclass(frozen=True)
class HermesCronProjection:
    profile_id: str
    duty_id: str
    schedule: str
    prompt: str
    skills: tuple[str, ...]
    enabled_toolsets: tuple[str, ...]
    reconciliation_key: str
    spec_digest: str
    profile_scope: str = "HERMES_HOME"
    surface: str = "cron.create_job"

    def job_kwargs(self) -> dict[str, object]:
        return {
            "prompt": self.prompt,
            "schedule": self.schedule,
            "name": f"factory:{self.profile_id}:{self.duty_id}",
            "repeat": None,
            "deliver": "local",
            "skills": list(self.skills),
            "enabled_toolsets": list(self.enabled_toolsets),
            "no_agent": False,
        }


class HermesProfileCronAdapter:
    def __init__(self, *, redact_text: Callable[[str], str]) -> None:
        self._redact_text = redact_text

    def project_duty(
        self,
        *,
        profile_id: str,
        duty_id: str,
        schedule: str,
        prompt: str,
        skills: tuple[str, ...] = (),
        enabled_toolsets: tuple[str, ...] = (),
    ) -> HermesCronProjection:
        profile_id = profile_id.strip()
        duty_id = duty_id.strip()
        schedule = schedule.strip()
        prompt = prompt.strip()
        if not profile_id:
            raise HermesCronProjectionError("Hermes Profile identity is required")
        if not duty_id:
            raise HermesCronProjectionError("Factory scheduled duty identity is required")
        if not schedule:
            raise HermesCronProjectionError("native Hermes cron schedule is required")
        if not prompt:
            raise HermesCronProjectionError("Factory scheduled duty prompt is required")

        normalized_skills = self._normalize_names(skills, "Skill")
        normalized_toolsets = self._normalize_names(enabled_toolsets, "toolset")
        self._assert_public(prompt)

        reconciliation_key = f"factory-cron:{profile_id}:{duty_id}"
        spec_digest = self._spec_digest(
            profile_id=profile_id,
            duty_id=duty_id,
            schedule=schedule,
            prompt=prompt,
            skills=normalized_skills,
            enabled_toolsets=normalized_toolsets,
        )
        return HermesCronProjection(
            profile_id=profile_id,
            duty_id=duty_id,
            schedule=schedule,
            prompt=prompt,
            skills=normalized_skills,
            enabled_toolsets=normalized_toolsets,
            reconciliation_key=reconciliation_key,
            spec_digest=spec_digest,
        )

    @staticmethod
    def _normalize_names(values: tuple[str, ...], label: str) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise HermesCronProjectionError(f"empty {label} identity is forbidden")
        if len(set(normalized)) != len(normalized):
            raise HermesCronProjectionError(f"duplicate {label} identity is forbidden")
        return normalized

    def _assert_public(self, value: str) -> None:
        try:
            redacted = self._redact_text(value)
        except Exception as error:
            raise HermesCronProjectionError(
                "cron redaction boundary could not verify public content"
            ) from error
        if redacted != value:
            raise HermesCronProjectionError(
                "sensitive material is forbidden in native Hermes cron payloads"
            )

    @staticmethod
    def _spec_digest(
        *,
        profile_id: str,
        duty_id: str,
        schedule: str,
        prompt: str,
        skills: tuple[str, ...],
        enabled_toolsets: tuple[str, ...],
    ) -> str:
        encoded = json.dumps(
            {
                "profile_id": profile_id,
                "duty_id": duty_id,
                "schedule": schedule,
                "prompt": prompt,
                "skills": list(skills),
                "enabled_toolsets": list(enabled_toolsets),
                "surface": "cron.create_job",
                "profile_scope": "HERMES_HOME",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

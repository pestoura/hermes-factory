from __future__ import annotations

import re
from collections.abc import Mapping

STAGE_ARTIFACT_WRITE_BUDGET_CHARS = 8_000
_STAGE_CONTRACT_PATTERN = re.compile(r"\.stage-contract-v(\d+)$")
_STAGE_WRITE_TOOLS = frozenset({"write_file", "patch"})


class StageArtifactWriteBoundaryError(ValueError):
    """Raised when a Factory stage emits an oversized repository write payload."""


def bounded_stage_artifact_writes_enabled(task_key: object) -> bool:
    if not isinstance(task_key, str) or not task_key.startswith("factory:"):
        return False
    match = _STAGE_CONTRACT_PATTERN.search(task_key)
    return match is not None and int(match.group(1)) >= 18


def guard_factory_stage_artifact_write(
    *, tool_name: str, args: object, task_key: object
) -> None:
    """Fail closed on oversized Factory stage write/edit payloads from v18 onward."""
    if tool_name not in _STAGE_WRITE_TOOLS:
        return
    if not bounded_stage_artifact_writes_enabled(task_key):
        return
    if not isinstance(args, Mapping):
        raise StageArtifactWriteBoundaryError(
            "Factory stage write requires structured tool arguments"
        )

    fields: tuple[str, ...]
    if tool_name == "write_file":
        fields = ("content",)
    elif args.get("mode") == "patch":
        fields = ("patch",)
    else:
        fields = ("old_string", "new_string")

    payload_chars = sum(
        len(value)
        for field in fields
        if isinstance((value := args.get(field)), str)
    )
    if payload_chars <= STAGE_ARTIFACT_WRITE_BUDGET_CHARS:
        return
    raise StageArtifactWriteBoundaryError(
        f"{tool_name} edit payload is {payload_chars} characters and exceeds "
        f"{STAGE_ARTIFACT_WRITE_BUDGET_CHARS}; use bounded stage-owned writes, "
        "split long artifacts, and continue missing content with patch"
    )

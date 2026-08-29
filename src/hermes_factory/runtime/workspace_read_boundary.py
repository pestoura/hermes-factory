from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any


class WorkspaceReadBoundaryError(RuntimeError):
    """Raised when a Factory worker accesses outside its assigned worktree."""


_STAGE_MARKER = ".stage-contract-v"
_FILE_PATH_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9_])(/[A-Za-z0-9_./-]+)")
_RELATIVE_ESCAPE = re.compile(r"(?<![A-Za-z0-9_])(\.\./[A-Za-z0-9_./-]+)")


def is_workspace_read_boundary_revision(idempotency_key: object) -> bool:
    if not isinstance(idempotency_key, str) or _STAGE_MARKER not in idempotency_key:
        return False
    try:
        version = int(idempotency_key.rsplit(_STAGE_MARKER, 1)[1])
    except ValueError:
        return False
    return version >= 15


def _workspace(path: object) -> Path:
    if not path:
        raise WorkspaceReadBoundaryError("assigned worktree is unavailable")
    root = Path(str(path)).resolve()
    if not root.is_dir():
        raise WorkspaceReadBoundaryError("assigned worktree is unavailable")
    return root


def _resolve(path: object, *, base: Path, workspace: Path) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise WorkspaceReadBoundaryError("workspace path argument must be a non-empty string")
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve(strict=False)
    if not candidate.is_relative_to(workspace):
        raise WorkspaceReadBoundaryError(
            f"path escapes assigned worktree: {candidate}"
        )
    return candidate


def _structured_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise WorkspaceReadBoundaryError("tool requires structured arguments")
    return args


def _guard_file_tool(tool_name: str, args: dict[str, Any], *, workspace: Path) -> None:
    if tool_name == "search_files":
        path = args.get("path", ".")
    else:
        path = args.get("path")
    if path is None:
        return
    _resolve(path, base=workspace, workspace=workspace)


def _terminal_tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError as exc:
        raise WorkspaceReadBoundaryError(f"unable to parse terminal command: {exc}") from exc


def _guard_terminal(args: dict[str, Any], *, workspace: Path) -> None:
    command = args.get("command")
    if not isinstance(command, str):
        raise WorkspaceReadBoundaryError("terminal command must be a string")
    workdir = args.get("workdir")
    cwd = workspace if not workdir else _resolve(workdir, base=workspace, workspace=workspace)
    for match in _ABSOLUTE_PATH.finditer(command):
        _resolve(match.group(1), base=cwd, workspace=workspace)
    for match in _RELATIVE_ESCAPE.finditer(command):
        _resolve(match.group(1), base=cwd, workspace=workspace)
    for token in _terminal_tokens(command):
        if token == ".." or token.startswith("../"):
            _resolve(token, base=cwd, workspace=workspace)
        if token == "~" or token.startswith("~/"):
            raise WorkspaceReadBoundaryError("home-directory expansion escapes assigned worktree")
        if token.startswith(("$HOME", "${HOME}")):
            raise WorkspaceReadBoundaryError("HOME expansion escapes assigned worktree")


def guard_factory_workspace_access(
    *, tool_name: str, args: Any, workspace_path: object
) -> None:
    """Restrict Factory v15 file/terminal access to the assigned worktree."""
    workspace = _workspace(workspace_path)
    structured = _structured_args(args)
    if tool_name == "terminal":
        _guard_terminal(structured, workspace=workspace)
        return
    if tool_name in _FILE_PATH_TOOLS:
        _guard_file_tool(tool_name, structured, workspace=workspace)

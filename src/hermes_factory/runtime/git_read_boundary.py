from __future__ import annotations

import shlex
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class GitReadBoundaryError(RuntimeError):
    """Raised when a Factory worker attempts a non-canonical Git read."""


_ENUMERATION_FLAGS = frozenset({"--all", "--branches", "--remotes", "--reflog", "--tags"})
_ENUMERATION_PREFIXES = ("--branches=", "--remotes=", "--glob=", "--exclude=", "--exclude-hidden=")
_FORBIDDEN_REF_SUBCOMMANDS = frozenset({
    "reflog", "show-ref", "for-each-ref", "fsck", "tag",
})
_REVISION_READ_SUBCOMMANDS = frozenset({
    "show", "log", "cat-file", "rev-list", "ls-tree", "diff-tree", "rev-parse",
    "diff", "grep", "archive", "blame",
})
_SUPPORTED_SUBCOMMANDS = frozenset({
    "status", "add", "commit", "diff", "log", "show", "rev-parse", "branch",
    "ls-files", "check-ignore", "check-attr", "restore", "cat-file", "rev-list",
    "ls-tree", "diff-tree", "grep", "archive", "blame", "rm", "mv", "clean",
})
_HEAD_LINEAGE_MUTATORS = frozenset({
    "switch", "checkout", "reset", "rebase", "merge", "cherry-pick", "revert",
    "update-ref", "replace", "filter-branch",
})
_GIT_REDIRECT_VARS = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
})
_SHELL_SEPARATORS = frozenset({";", "&&", "||", "|", "&", "(", ")"})


def is_canonical_git_boundary_revision(idempotency_key: object) -> bool:
    if not isinstance(idempotency_key, str):
        return False
    marker = ".stage-contract-v"
    if marker not in idempotency_key:
        return False
    try:
        version = int(idempotency_key.rsplit(marker, 1)[1])
    except ValueError:
        return False
    return version >= 13


def _resolve_within_workspace(path: str, *, base: Path, workspace: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(workspace):
        raise GitReadBoundaryError(
            f"canonical Git read boundary forbids Git execution outside assigned worktree: {candidate}"
        )
    return candidate


def _tokenize(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError as exc:
        raise GitReadBoundaryError(f"unable to parse terminal command: {exc}") from exc


def _segments(tokens: Iterable[str]) -> Iterable[list[str]]:
    segment: list[str] = []
    for token in tokens:
        if token in _SHELL_SEPARATORS:
            if segment:
                yield segment
                segment = []
            continue
        segment.append(token)
    if segment:
        yield segment


def _reject_repository_redirection(tokens: Iterable[str]) -> None:
    for token in tokens:
        if "=" in token:
            name = token.split("=", 1)[0]
            if name in _GIT_REDIRECT_VARS:
                raise GitReadBoundaryError(
                    f"canonical Git read boundary forbids Git repository redirection via {name}"
                )
        if token == "--git-dir" or token.startswith("--git-dir="):
            raise GitReadBoundaryError("canonical Git read boundary forbids --git-dir redirection")
        if token == "--work-tree" or token.startswith("--work-tree="):
            raise GitReadBoundaryError("canonical Git read boundary forbids --work-tree redirection")


def _parse_git_invocation(git_args: list[str], *, cwd: Path, workspace: Path) -> tuple[str | None, list[str], Path]:
    if any(
        token in _ENUMERATION_FLAGS or token.startswith(_ENUMERATION_PREFIXES)
        for token in git_args
    ):
        raise GitReadBoundaryError("canonical Git read boundary forbids global history enumeration")
    repo_dir = cwd
    index = 0
    while index < len(git_args):
        token = git_args[index]
        if token == "-C":
            if index + 1 >= len(git_args):
                raise GitReadBoundaryError("canonical Git read boundary requires a path after git -C")
            repo_dir = _resolve_within_workspace(
                git_args[index + 1], base=repo_dir, workspace=workspace
            )
            index += 2
            continue
        if token == "-c":
            raise GitReadBoundaryError(
                "canonical Git read boundary forbids per-invocation Git config"
            )
        if token.startswith("-"):
            index += 1
            continue
        return token, git_args[index + 1 :], repo_dir
    return None, [], repo_dir


def _revision_operands(subcommand: str, args: list[str]) -> list[str]:
    if subcommand not in _REVISION_READ_SUBCOMMANDS:
        return []
    before_paths = args[: args.index("--")] if "--" in args else args
    operands = [token for token in before_paths if token and not token.startswith("-")]
    if not operands:
        return []
    if subcommand == "cat-file":
        return operands[-1:]
    if subcommand == "grep":
        return operands[1:]
    if subcommand in {"show", "archive", "ls-tree"}:
        return operands[:1]
    return operands


def _revision_is_resolvable(revision: str, *, repo_dir: Path) -> bool:
    expression = revision.split(":", 1)[0].lstrip("^")
    if not expression:
        return False
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--verify", "--quiet", expression],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _revision_atoms(expression: str) -> list[str]:
    expression = expression.split(":", 1)[0]
    expression = expression.lstrip("^")
    if "..." in expression:
        return [item for item in expression.split("...") if item]
    if ".." in expression:
        return [item for item in expression.split("..") if item]
    return [expression] if expression else []


def _assert_revision_reachable(revision: str, *, repo_dir: Path) -> None:
    if revision in {"HEAD", "@"}:
        return
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "merge-base", "--is-ancestor", revision, "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as exc:
        raise GitReadBoundaryError(f"unable to validate Git revision {revision!r}: {exc}") from exc
    if result.returncode != 0:
        raise GitReadBoundaryError(
            f"canonical Git read boundary: {revision!r} is not reachable from current HEAD"
        )


def _guard_git_invocation(git_args: list[str], *, cwd: Path, workspace: Path) -> None:
    _reject_repository_redirection(git_args)
    subcommand, sub_args, repo_dir = _parse_git_invocation(
        git_args, cwd=cwd, workspace=workspace
    )
    if subcommand is None:
        return
    if subcommand in _FORBIDDEN_REF_SUBCOMMANDS:
        raise GitReadBoundaryError(
            f"canonical Git read boundary forbids global ref/object enumeration via git {subcommand}"
        )
    if subcommand == "branch" and "--show-current" not in sub_args:
        raise GitReadBoundaryError(
            "canonical Git read boundary forbids global ref/object enumeration via git branch"
        )
    if subcommand in _HEAD_LINEAGE_MUTATORS:
        raise GitReadBoundaryError(
            f"canonical Git read boundary forbids git {subcommand} because it can change canonical HEAD lineage"
        )
    if subcommand not in _SUPPORTED_SUBCOMMANDS:
        raise GitReadBoundaryError(
            f"canonical Git read boundary forbids unsupported Git subcommand: {subcommand}"
        )
    if subcommand == "commit":
        if "--amend" in sub_args:
            raise GitReadBoundaryError(
                "canonical Git read boundary forbids commit --amend because it can rewrite prior commits"
            )
        historical_options = {
            "-C", "-c", "--reuse-message", "--reedit-message", "--fixup", "--squash",
        }
        if any(token.split("=", 1)[0] in historical_options for token in sub_args):
            raise GitReadBoundaryError(
                "canonical Git read boundary forbids historical commit reuse"
            )
    if subcommand == "archive" and any(
        token in {"--remote", "--exec"}
        or token.startswith(("--remote=", "--exec="))
        for token in sub_args
    ):
        raise GitReadBoundaryError(
            "canonical Git read boundary forbids remote archive access"
        )
    if subcommand in _REVISION_READ_SUBCOMMANDS and any(
        token == "--stdin" or token.startswith("--batch") for token in sub_args
    ):
        raise GitReadBoundaryError(
            "canonical Git read boundary forbids streamed revision input"
        )
    if subcommand == "restore":
        for index, token in enumerate(sub_args):
            source = None
            if token.startswith("--source="):
                source = token.split("=", 1)[1]
            elif token == "--source" and index + 1 < len(sub_args):
                source = sub_args[index + 1]
            if source is not None and source not in {"HEAD", "@"}:
                raise GitReadBoundaryError(
                    "canonical Git read boundary forbids non-HEAD restore source"
                )
    ambiguous_path_commands = {"diff", "blame", "log", "grep"}
    for operand in _revision_operands(subcommand, sub_args):
        for revision in _revision_atoms(operand):
            if subcommand in ambiguous_path_commands and not _revision_is_resolvable(
                revision, repo_dir=repo_dir
            ):
                continue
            _assert_revision_reachable(revision, repo_dir=repo_dir)


def guard_factory_terminal_git_read(*, args: Any, workspace_path: object) -> None:
    if not isinstance(args, dict):
        raise GitReadBoundaryError("terminal requires structured arguments")
    command = args.get("command")
    if not isinstance(command, str):
        raise GitReadBoundaryError("terminal command must be a string")
    if not workspace_path:
        raise GitReadBoundaryError("Factory workspace is unavailable")
    workspace = Path(str(workspace_path)).resolve()
    if not workspace.is_dir():
        raise GitReadBoundaryError("Factory workspace is unavailable")
    workdir_value = args.get("workdir")
    cwd = workspace if not workdir_value else _resolve_within_workspace(
        str(workdir_value), base=workspace, workspace=workspace
    )
    tokens = _tokenize(command)
    _reject_repository_redirection(tokens)
    for segment in _segments(tokens):
        for index, token in enumerate(segment):
            if Path(token).name == "git":
                _guard_git_invocation(segment[index + 1 :], cwd=cwd, workspace=workspace)

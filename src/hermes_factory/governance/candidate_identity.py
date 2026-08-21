from __future__ import annotations

import hashlib
import json
from pathlib import Path


class CandidateIdentityError(ValueError):
    pass


def _file_entry(path: Path, relative_path: str) -> dict[str, str]:
    return {
        "type": "file",
        "path": relative_path,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def digest_artifact(path: Path) -> str:
    candidate = Path(path)
    if candidate.is_symlink():
        raise CandidateIdentityError("candidate artifact cannot be a symlink")
    if not candidate.exists():
        raise CandidateIdentityError("candidate artifact does not exist")

    entries: list[dict[str, str]] = []
    if candidate.is_file():
        entries.append(_file_entry(candidate, candidate.name))
    elif candidate.is_dir():
        for entry in sorted(candidate.rglob("*"), key=lambda item: item.relative_to(candidate).as_posix()):
            relative = entry.relative_to(candidate).as_posix()
            if entry.is_symlink():
                raise CandidateIdentityError(
                    f"candidate artifact contains symlink: {relative}"
                )
            if entry.is_dir():
                entries.append({"type": "directory", "path": relative})
            elif entry.is_file():
                entries.append(_file_entry(entry, relative))
            else:
                raise CandidateIdentityError(
                    f"candidate artifact contains unsupported entry: {relative}"
                )
    else:
        raise CandidateIdentityError("candidate artifact must be a regular file or directory")

    manifest = json.dumps(
        {"schema": "hermes.factory/candidate-artifact/v1", "entries": entries},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(manifest).hexdigest()}"

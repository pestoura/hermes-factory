from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from hermes_factory.governance.runtime_acceptance import (
    LIVE_FACTORY_PROFILE_SET_SCENARIO,
    RuntimeAcceptanceEvidence,
)
from hermes_factory.runtime.admission import AdmissionEvidenceState

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_PROFILE_ID_RE = re.compile(r"^factory-[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class LiveFactoryProfileSetAudit:
    candidate_sha: str
    expected_profile_ids: tuple[str, ...]
    observed_profile_ids: tuple[str, ...]
    missing_profile_ids: tuple[str, ...]
    unexpected_profile_ids: tuple[str, ...]
    invalid_profile_ids: tuple[str, ...]
    state: AdmissionEvidenceState

    @property
    def exact_set_match(self) -> bool:
        return self.state is AdmissionEvidenceState.PASS

    def to_runtime_acceptance_evidence(
        self, evidence_ref: str
    ) -> RuntimeAcceptanceEvidence:
        if not evidence_ref.strip():
            raise ValueError("runtime acceptance evidence requires provenance")
        return RuntimeAcceptanceEvidence(
            scenario=LIVE_FACTORY_PROFILE_SET_SCENARIO,
            candidate_sha=self.candidate_sha,
            state=self.state,
            evidence_ref=evidence_ref,
        )

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/live-profile-set-audit/v1",
            "candidate_sha": self.candidate_sha,
            "expected_count": len(self.expected_profile_ids),
            "observed_count": len(self.observed_profile_ids),
            "expected_profile_ids": list(self.expected_profile_ids),
            "observed_profile_ids": list(self.observed_profile_ids),
            "missing_profile_ids": list(self.missing_profile_ids),
            "unexpected_profile_ids": list(self.unexpected_profile_ids),
            "invalid_profile_ids": list(self.invalid_profile_ids),
            "exact_set_match": self.exact_set_match,
            "state": self.state.value,
        }


def _load_expected_profiles(repo_root: Path) -> tuple[str, ...]:
    path = Path(repo_root) / "agents" / "catalog-v1.2.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError("Factory agent catalog must contain a mapping")
    catalog = document.get("catalog")
    active = catalog.get("active_candidates") if isinstance(catalog, dict) else None
    if not isinstance(active, list) or not active:
        raise ValueError("Factory agent catalog active_candidates must be non-empty")
    if any(not isinstance(item, str) or not _PROFILE_ID_RE.fullmatch(item) for item in active):
        raise ValueError("Factory agent catalog contains invalid active Profile IDs")
    expected = tuple(sorted(active))
    if len(expected) != len(set(expected)):
        raise ValueError("Factory agent catalog contains duplicate active Profile IDs")
    return expected


def audit_live_factory_profile_set(
    *, repo_root: Path, hermes_home: Path, candidate_sha: str
) -> LiveFactoryProfileSetAudit:
    if not _SHA_RE.fullmatch(candidate_sha):
        raise ValueError("candidate_sha must be an exact 40-character Git SHA")
    expected = _load_expected_profiles(Path(repo_root))
    profiles_root = Path(hermes_home) / "profiles"
    if profiles_root.is_symlink() or not profiles_root.is_dir():
        raise ValueError("Hermes profiles root must be a regular directory")

    entries = tuple(sorted((entry for entry in profiles_root.iterdir() if entry.name.startswith("factory-")), key=lambda entry: entry.name))
    observed = tuple(entry.name for entry in entries)
    invalid = tuple(entry.name for entry in entries if entry.is_symlink() or not entry.is_dir())
    expected_set = set(expected)
    observed_set = set(observed)
    missing = tuple(sorted(expected_set - observed_set))
    unexpected = tuple(sorted(observed_set - expected_set))
    state = (
        AdmissionEvidenceState.PASS
        if not missing and not unexpected and not invalid
        else AdmissionEvidenceState.FAIL
    )
    return LiveFactoryProfileSetAudit(
        candidate_sha=candidate_sha.lower(),
        expected_profile_ids=expected,
        observed_profile_ids=observed,
        missing_profile_ids=missing,
        unexpected_profile_ids=unexpected,
        invalid_profile_ids=invalid,
        state=state,
    )


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
        return
    except FileExistsError:
        pass
    if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
        raise ValueError("live Factory Profile set audit evidence is immutable and does not match")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit exact live Factory Profile set")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--hermes-home", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    audit = audit_live_factory_profile_set(
        repo_root=args.repo_root,
        hermes_home=args.hermes_home,
        candidate_sha=args.candidate_sha,
    )
    payload = (json.dumps(audit.to_manifest(), indent=2, sort_keys=True) + "\n").encode()
    _write_once(args.output, payload)
    print(json.dumps({"state": audit.state.value, "exact_set_match": audit.exact_set_match}))
    return 0 if audit.state is AdmissionEvidenceState.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())

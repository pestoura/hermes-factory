from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum


class GitHubAdapterError(ValueError):
    pass


class SCMMutation(StrEnum):
    CREATE_BRANCH = "CREATE_BRANCH"
    WRITE_BRANCH = "WRITE_BRANCH"
    OPEN_PR = "OPEN_PR"
    COMMENT_PR = "COMMENT_PR"


@dataclass(frozen=True)
class SCMWriteAuthority:
    allowed_operations: tuple[SCMMutation, ...]
    writable_branch_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class GitHubPRObservation:
    source: str
    repository: str
    pr_number: int
    state: str
    draft: bool
    head_ref: str
    head_sha: str
    base_ref: str
    base_sha: str
    observation_digest: str


@dataclass(frozen=True)
class GitHubCheckObservation:
    source: str
    repository: str
    check_run_id: int
    name: str
    head_sha: str
    candidate_sha: str
    status: str
    conclusion: str | None
    evidence_state: str
    observation_digest: str


@dataclass(frozen=True)
class GitHubCommitObservation:
    source: str
    repository: str
    sha: str
    tree_sha: str
    observation_digest: str


@dataclass(frozen=True)
class SCMMutationIntent:
    repository: str
    operation: SCMMutation
    target_branch: str
    candidate_sha: str
    intent_digest: str
    execute: bool = False


class GitHubSCMAdapter:
    def observe_pr(self, payload: dict[str, object]) -> GitHubPRObservation:
        repository = self._repository(payload.get("repository"))
        number = payload.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise GitHubAdapterError("GitHub PR number must be a positive integer")
        state = self._text(payload.get("state"), "PR state")
        draft = payload.get("draft")
        if not isinstance(draft, bool):
            raise GitHubAdapterError("GitHub PR draft must be boolean")
        head_ref = self._text(payload.get("head_ref"), "PR head ref")
        head_sha = self._sha(payload.get("head_sha"), "PR head SHA")
        base_ref = self._text(payload.get("base_ref"), "PR base ref")
        base_sha = self._sha(payload.get("base_sha"), "PR base SHA")
        return GitHubPRObservation(
            source="GITHUB_PR",
            repository=repository,
            pr_number=number,
            state=state,
            draft=draft,
            head_ref=head_ref,
            head_sha=head_sha,
            base_ref=base_ref,
            base_sha=base_sha,
            observation_digest=self._digest(payload),
        )

    def observe_check(
        self,
        payload: dict[str, object],
        *,
        candidate_sha: str,
    ) -> GitHubCheckObservation:
        repository = self._repository(payload.get("repository"))
        run_id = payload.get("check_run_id")
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
            raise GitHubAdapterError("GitHub check_run_id must be a positive integer")
        name = self._text(payload.get("name"), "check name")
        head_sha = self._sha(payload.get("head_sha"), "check head SHA")
        candidate = self._sha(candidate_sha, "candidate SHA")
        if head_sha != candidate:
            raise GitHubAdapterError("GitHub check does not match candidate SHA")
        status = self._text(payload.get("status"), "check status")
        raw_conclusion = payload.get("conclusion")
        conclusion: str | None
        if raw_conclusion is None:
            conclusion = None
        else:
            conclusion = self._text(raw_conclusion, "check conclusion")
        evidence_state = self._check_state(status, conclusion)
        return GitHubCheckObservation(
            source="GITHUB_CHECK",
            repository=repository,
            check_run_id=run_id,
            name=name,
            head_sha=head_sha,
            candidate_sha=candidate,
            status=status,
            conclusion=conclusion,
            evidence_state=evidence_state,
            observation_digest=self._digest(payload),
        )

    def observe_commit(self, payload: dict[str, object]) -> GitHubCommitObservation:
        repository = self._repository(payload.get("repository"))
        sha = self._sha(payload.get("sha"), "commit SHA")
        tree_sha = self._sha(payload.get("tree_sha"), "tree SHA")
        return GitHubCommitObservation(
            source="GITHUB_COMMIT",
            repository=repository,
            sha=sha,
            tree_sha=tree_sha,
            observation_digest=self._digest(payload),
        )

    def plan_mutation(
        self,
        *,
        repository: str,
        operation: SCMMutation | str,
        authority: SCMWriteAuthority,
        target_branch: str,
        candidate_sha: str,
    ) -> SCMMutationIntent:
        repository = self._repository(repository)
        try:
            normalized_operation = SCMMutation(operation)
        except ValueError as error:
            raise GitHubAdapterError("unsupported GitHub SCM mutation") from error
        if normalized_operation not in authority.allowed_operations:
            raise GitHubAdapterError("GitHub SCM mutation exceeds explicit authority")
        branch = self._text(target_branch, "target branch")
        if branch in {"main", "master"} or branch.startswith("refs/heads/main"):
            raise GitHubAdapterError("protected branch mutation is forbidden")
        prefixes = tuple(prefix.strip() for prefix in authority.writable_branch_prefixes)
        if not prefixes or any(not prefix for prefix in prefixes):
            raise GitHubAdapterError("writable branch authority is required")
        if not any(branch.startswith(prefix) for prefix in prefixes):
            raise GitHubAdapterError("target branch is outside explicit authority")
        candidate = self._sha(candidate_sha, "candidate SHA")
        intent_payload = {
            "repository": repository,
            "operation": normalized_operation.value,
            "target_branch": branch,
            "candidate_sha": candidate,
            "execute": False,
        }
        return SCMMutationIntent(
            repository=repository,
            operation=normalized_operation,
            target_branch=branch,
            candidate_sha=candidate,
            intent_digest=self._digest(intent_payload),
        )

    @staticmethod
    def _check_state(status: str, conclusion: str | None) -> str:
        if status != "completed":
            return "NOT_RUN"
        if conclusion == "success":
            return "PASS"
        if conclusion is None:
            return "UNKNOWN"
        return "FAIL"

    @staticmethod
    def _repository(value: object) -> str:
        text = GitHubSCMAdapter._text(value, "repository")
        parts = text.split("/")
        if len(parts) != 2 or any(not part.strip() for part in parts):
            raise GitHubAdapterError("GitHub repository must use owner/name identity")
        return text

    @staticmethod
    def _sha(value: object, label: str) -> str:
        text = GitHubSCMAdapter._text(value, label)
        if len(text) not in {40, 64} or re.fullmatch(r"[0-9a-fA-F]+", text) is None:
            raise GitHubAdapterError(f"GitHub {label} must be an exact immutable SHA")
        return text.lower()

    @staticmethod
    def _text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise GitHubAdapterError(f"GitHub {label} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _digest(payload: dict[str, object]) -> str:
        try:
            encoded = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise GitHubAdapterError("GitHub observation is not canonically serializable") from error
        return hashlib.sha256(encoded).hexdigest()

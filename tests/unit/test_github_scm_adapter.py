from hermes_factory.adapters.github import (
    GitHubAdapterError,
    GitHubSCMAdapter,
    SCMMutation,
    SCMWriteAuthority,
)


HEAD = "a" * 40
BASE = "b" * 40


def _error_message(operation) -> str:
    try:
        operation()
    except GitHubAdapterError as error:
        return str(error)
    raise AssertionError("expected GitHubAdapterError")


def test_github_pr_observation_is_bound_to_exact_repository_and_shas() -> None:
    adapter = GitHubSCMAdapter()
    record = adapter.observe_pr(
        {
            "repository": "pestoura/hermes-factory",
            "number": 2,
            "state": "open",
            "draft": True,
            "head_ref": "implementation/factory-runtime-v1.2",
            "head_sha": HEAD,
            "base_ref": "design/software-factory-architecture-v1",
            "base_sha": BASE,
        }
    )

    assert record.source == "GITHUB_PR"
    assert record.repository == "pestoura/hermes-factory"
    assert record.pr_number == 2
    assert record.head_sha == HEAD
    assert record.base_sha == BASE
    assert len(record.observation_digest) == 64


def test_github_check_evidence_refuses_candidate_sha_mismatch() -> None:
    adapter = GitHubSCMAdapter()
    check = {
        "repository": "pestoura/hermes-factory",
        "check_run_id": 12345,
        "name": "Factory CI",
        "head_sha": HEAD,
        "status": "completed",
        "conclusion": "success",
    }

    record = adapter.observe_check(check, candidate_sha=HEAD)
    assert record.source == "GITHUB_CHECK"
    assert record.candidate_sha == HEAD
    assert record.evidence_state == "PASS"

    message = _error_message(
        lambda: adapter.observe_check(check, candidate_sha="c" * 40)
    )
    assert "candidate SHA" in message


def test_github_commit_observation_requires_exact_immutable_identity() -> None:
    adapter = GitHubSCMAdapter()
    record = adapter.observe_commit(
        {
            "repository": "pestoura/hermes-factory",
            "sha": HEAD,
            "tree_sha": "d" * 40,
        }
    )
    assert record.source == "GITHUB_COMMIT"
    assert record.sha == HEAD
    assert record.tree_sha == "d" * 40

    malformed = {"repository": "pestoura/hermes-factory", "sha": "main", "tree_sha": "d" * 40}
    assert "SHA" in _error_message(lambda: adapter.observe_commit(malformed))


def test_github_mutations_require_explicit_operation_and_branch_authority() -> None:
    adapter = GitHubSCMAdapter()
    authority = SCMWriteAuthority(
        allowed_operations=(SCMMutation.OPEN_PR, SCMMutation.COMMENT_PR),
        writable_branch_prefixes=("factory/", "implementation/"),
    )

    intent = adapter.plan_mutation(
        repository="pestoura/hermes-factory",
        operation=SCMMutation.OPEN_PR,
        authority=authority,
        target_branch="implementation/factory-runtime-v1.2",
        candidate_sha=HEAD,
    )
    assert intent.execute is False
    assert intent.operation is SCMMutation.OPEN_PR
    assert intent.candidate_sha == HEAD
    assert len(intent.intent_digest) == 64

    denied = SCMWriteAuthority(
        allowed_operations=(SCMMutation.COMMENT_PR,),
        writable_branch_prefixes=("factory/",),
    )
    assert "authority" in _error_message(
        lambda: adapter.plan_mutation(
            repository="pestoura/hermes-factory",
            operation=SCMMutation.OPEN_PR,
            authority=denied,
            target_branch="factory/change",
            candidate_sha=HEAD,
        )
    )


def test_github_adapter_never_plans_protected_or_destructive_mutations() -> None:
    adapter = GitHubSCMAdapter()
    authority = SCMWriteAuthority(
        allowed_operations=(SCMMutation.WRITE_BRANCH, SCMMutation.OPEN_PR),
        writable_branch_prefixes=("factory/",),
    )

    assert "protected" in _error_message(
        lambda: adapter.plan_mutation(
            repository="pestoura/hermes-factory",
            operation=SCMMutation.WRITE_BRANCH,
            authority=authority,
            target_branch="main",
            candidate_sha=HEAD,
        )
    )

    assert "unsupported" in _error_message(
        lambda: adapter.plan_mutation(
            repository="pestoura/hermes-factory",
            operation="MERGE_PR",
            authority=authority,
            target_branch="factory/change",
            candidate_sha=HEAD,
        )
    )

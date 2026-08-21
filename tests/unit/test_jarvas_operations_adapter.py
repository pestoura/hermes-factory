from hermes_factory.adapters.jarvas_operations import (
    JarvasOperationsAdapterError,
    JarvasOperationsEvidenceAdapter,
)


def _report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-18T22:00:00Z",
        "evidence_id": "0123456789abcdef",
        "mode": "remediate",
        "run_outcome": "complete",
        "overall_status": "healthy",
        "required_status": "healthy",
        "optional_status": "healthy",
        "checks": [{"name": "hermes-gateway", "status": "healthy"}],
        "attempted_recoveries": [
            {
                "action": {"component": "hermes-gateway", "description": "soft recover"},
                "exit_code": 0,
            }
        ],
        "blocked_actions": [
            {
                "action": {"component": "host", "description": "reboot"},
                "decision": {"reason": "policy ceiling"},
            }
        ],
        "unresolved_findings": [],
        "warnings": [],
        "metadata": {
            "tool": "jarvas-operations",
            "version": "0.3.0",
            "scope": "hermes",
            "safe_mode": False,
        },
    }


def _error_message(operation) -> str:
    try:
        operation()
    except JarvasOperationsAdapterError as error:
        return str(error)
    raise AssertionError("expected JarvasOperationsAdapterError")


def test_operations_report_is_consumed_as_read_only_assurance_evidence() -> None:
    record = JarvasOperationsEvidenceAdapter().consume(_report())

    assert record.source == "JARVAS_OPERATIONS_REPORT"
    assert record.read_only is True
    assert record.evidence_id == "0123456789abcdef"
    assert record.scope == "hermes"
    assert record.overall_status == "healthy"
    assert record.attempted_recoveries == 1
    assert record.blocked_actions == 1
    assert record.unresolved_findings == 0
    assert len(record.report_digest) == 64
    assert not hasattr(record, "execute_recovery")
    assert not hasattr(record, "recovery_action")


def test_operations_evidence_digest_binds_complete_report_but_does_not_export_actions() -> None:
    adapter = JarvasOperationsEvidenceAdapter()
    first = adapter.consume(_report())
    changed_report = {**_report(), "futureEvidence": {"observer": "ops-v2"}}
    second = adapter.consume(changed_report)

    assert first.report_digest != second.report_digest
    rendered = repr(first)
    assert "soft recover" not in rendered
    assert "reboot" not in rendered


def test_operations_adapter_fails_closed_on_wrong_tool_schema_or_missing_identity() -> None:
    adapter = JarvasOperationsEvidenceAdapter()

    wrong_tool = _report()
    wrong_tool["metadata"] = {"tool": "something-else", "scope": "hermes"}
    assert "tool" in _error_message(lambda: adapter.consume(wrong_tool))

    wrong_schema = {**_report(), "schema_version": 2}
    assert "schema" in _error_message(lambda: adapter.consume(wrong_schema))

    missing_evidence = _report()
    del missing_evidence["evidence_id"]
    assert "evidence_id" in _error_message(lambda: adapter.consume(missing_evidence))


def test_operations_adapter_never_upgrades_incomplete_run_to_healthy() -> None:
    adapter = JarvasOperationsEvidenceAdapter()
    inconsistent = {**_report(), "run_outcome": "budget_exhausted"}

    assert "incomplete" in _error_message(lambda: adapter.consume(inconsistent))

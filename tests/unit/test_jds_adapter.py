from hermes_factory.adapters.jds import JDSAdapterError, JDSGatePlanAdapter

from hermes_factory.contracts import EngineeringProfileReference


def _profile() -> EngineeringProfileReference:
    return EngineeringProfileReference(
        api_version="engineering.jarvas/v1",
        kind="ProjectEngineeringProfile",
        standard="JDS-001",
        platform_ref="abc123",
        criticality="high",
        digest="f" * 64,
    )


def _plan() -> dict[str, object]:
    return {
        "schema": "engineering.jarvas/gate-plan-v1",
        "standard": "JDS-001",
        "platformRef": "abc123",
        "criticality": "high",
        "changeSource": "git-diff",
        "changedFiles": ["src/app.py"],
        "docsOnly": False,
        "ambiguousImpact": False,
        "effectiveCapabilities": ["python", "repository-security"],
        "selectedCapabilities": ["python", "repository-security"],
        "selectedGates": ["python_quality", "secret_scan"],
        "skippedCapabilities": {"docs": "change-impact-not-triggered"},
        "capabilityReasons": {"python": ["auto-detected"]},
    }


def _error_message(operation) -> str:
    try:
        operation()
    except JDSAdapterError as error:
        return str(error)
    raise AssertionError("expected JDSAdapterError")


def test_jds_adapter_consumes_effective_plan_without_reimplementing_gates() -> None:
    record = JDSGatePlanAdapter().consume(_plan(), profile=_profile())

    assert record.source == "JDS_EFFECTIVE_GATE_PLAN"
    assert record.schema == "engineering.jarvas/gate-plan-v1"
    assert record.standard == "JDS-001"
    assert record.platform_ref == "abc123"
    assert record.selected_gates == ("python_quality", "secret_scan")
    assert record.selected_capabilities == ("python", "repository-security")
    assert record.ambiguous_impact is False
    assert record.plan_digest and len(record.plan_digest) == 64


def test_jds_plan_digest_binds_full_planner_output_and_accepts_future_fields() -> None:
    adapter = JDSGatePlanAdapter()
    first = adapter.consume(_plan(), profile=_profile())
    future = {**_plan(), "futurePlannerEvidence": {"reason": "new-field"}}
    second = adapter.consume(future, profile=_profile())

    assert first.selected_gates == second.selected_gates
    assert first.plan_digest != second.plan_digest


def test_jds_adapter_fails_closed_on_wrong_schema_standard_or_platform_identity() -> None:
    adapter = JDSGatePlanAdapter()

    wrong_schema = {**_plan(), "schema": "engineering.jarvas/gate-plan-v2"}
    assert "schema" in _error_message(lambda: adapter.consume(wrong_schema, profile=_profile()))

    wrong_standard = {**_plan(), "standard": "JDS-999"}
    assert "standard" in _error_message(lambda: adapter.consume(wrong_standard, profile=_profile()))

    wrong_platform = {**_plan(), "platformRef": "stale-sha"}
    assert "platformRef" in _error_message(lambda: adapter.consume(wrong_platform, profile=_profile()))


def test_jds_adapter_rejects_malformed_selected_gate_evidence_instead_of_deriving_it() -> None:
    adapter = JDSGatePlanAdapter()
    malformed = {**_plan(), "selectedGates": ["python_quality", "python_quality"]}
    assert "selectedGates" in _error_message(
        lambda: adapter.consume(malformed, profile=_profile())
    )

    missing = _plan()
    del missing["selectedGates"]
    assert "selectedGates" in _error_message(lambda: adapter.consume(missing, profile=_profile()))

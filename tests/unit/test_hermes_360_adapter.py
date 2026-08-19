from hermes_factory.adapters.hermes_360 import (
    Hermes360AdapterError,
    Hermes360CapabilityAdapter,
    Hermes360Provenance,
)

REVISION = "a" * 40
BLOB_SHA = "b" * 40


def _provenance() -> Hermes360Provenance:
    return Hermes360Provenance(
        repository="pestoura/hermes-ecosystem-architecture",
        revision=REVISION,
        path="inventory/capabilities.yaml",
        blob_sha=BLOB_SHA,
    )


def _inventory() -> dict[str, object]:
    return {
        "schema_version": 1,
        "observed": "2026-08-11",
        "capabilities": [
            {
                "id": "jds-gate-planner",
                "component": "jds-engineering-platform",
                "implemented": True,
                "tested": True,
                "deployed": None,
                "production_enabled": True,
                "planned": False,
                "blocked": False,
                "classification": "CURRENT",
                "evidence": "Jarvas Engineering Platform README/tests/actions",
            },
            {
                "id": "jarvas-assurance",
                "component": "jarvas-operations",
                "implemented": True,
                "tested": True,
                "deployed": True,
                "production_enabled": True,
                "planned": False,
                "blocked": False,
                "classification": "DEPLOYED",
                "evidence": "Jarvas Operations live production posture",
            },
            {
                "id": "kali-general-surface",
                "component": "kali-mcp",
                "implemented": True,
                "tested": "partial",
                "deployed": True,
                "production_enabled": False,
                "planned": False,
                "blocked": True,
                "classification": "BLOCKED",
                "evidence": "general methods are not authorized",
            },
            {
                "id": "hermes-vault-runtime",
                "component": "hermes-vault",
                "implemented": False,
                "tested": False,
                "deployed": False,
                "production_enabled": False,
                "planned": True,
                "blocked": False,
                "classification": "PLANNED",
                "evidence": "target architecture only",
            },
        ],
    }


def _error_message(operation) -> str:
    try:
        operation()
    except Hermes360AdapterError as error:
        return str(error)
    raise AssertionError("expected Hermes360AdapterError")


def test_hermes_360_adapter_preserves_inventory_truth_and_exact_provenance() -> None:
    snapshot = Hermes360CapabilityAdapter().consume(
        _inventory(),
        provenance=_provenance(),
    )

    assert snapshot.source == "HERMES_360_CAPABILITY_INVENTORY"
    assert snapshot.schema_version == 1
    assert snapshot.observed == "2026-08-11"
    assert snapshot.provenance.repository == "pestoura/hermes-ecosystem-architecture"
    assert snapshot.provenance.revision == REVISION
    assert snapshot.provenance.blob_sha == BLOB_SHA
    assert len(snapshot.capabilities) == 4
    assert len(snapshot.inventory_digest) == 64


def test_hermes_360_compiler_projection_never_promotes_blocked_partial_or_planned_state() -> None:
    snapshot = Hermes360CapabilityAdapter().consume(
        _inventory(),
        provenance=_provenance(),
    )

    compiler_snapshot = snapshot.to_compiler_snapshot()

    assert compiler_snapshot.snapshot_id == f"hermes-360:2026-08-11:{REVISION}"
    assert compiler_snapshot.digest == snapshot.inventory_digest
    assert compiler_snapshot.capabilities == frozenset(
        {"jds-gate-planner", "jarvas-assurance"}
    )
    assert "kali-general-surface" not in compiler_snapshot.capabilities
    assert "hermes-vault-runtime" not in compiler_snapshot.capabilities


def test_hermes_360_digest_binds_inventory_content_and_provenance() -> None:
    adapter = Hermes360CapabilityAdapter()
    first = adapter.consume(_inventory(), provenance=_provenance())

    changed = _inventory()
    capabilities = changed["capabilities"]
    assert isinstance(capabilities, list)
    first_capability = capabilities[0]
    assert isinstance(first_capability, dict)
    first_capability["evidence"] = "new exact evidence"
    second = adapter.consume(changed, provenance=_provenance())

    changed_provenance = Hermes360Provenance(
        repository="pestoura/hermes-ecosystem-architecture",
        revision="c" * 40,
        path="inventory/capabilities.yaml",
        blob_sha=BLOB_SHA,
    )
    third = adapter.consume(_inventory(), provenance=changed_provenance)

    assert first.inventory_digest != second.inventory_digest
    assert first.inventory_digest != third.inventory_digest


def test_hermes_360_adapter_fails_closed_on_unknown_schema_duplicate_or_missing_truth() -> None:
    adapter = Hermes360CapabilityAdapter()

    unsupported = {**_inventory(), "schema_version": 2}
    assert "schema_version" in _error_message(
        lambda: adapter.consume(unsupported, provenance=_provenance())
    )

    duplicate = _inventory()
    capabilities = duplicate["capabilities"]
    assert isinstance(capabilities, list)
    capabilities.append(dict(capabilities[0]))
    assert "duplicate" in _error_message(
        lambda: adapter.consume(duplicate, provenance=_provenance())
    )

    missing = _inventory()
    missing_capabilities = missing["capabilities"]
    assert isinstance(missing_capabilities, list)
    missing_record = missing_capabilities[0]
    assert isinstance(missing_record, dict)
    del missing_record["tested"]
    assert "tested" in _error_message(
        lambda: adapter.consume(missing, provenance=_provenance())
    )


def test_hermes_360_adapter_requires_exact_immutable_source_revision() -> None:
    adapter = Hermes360CapabilityAdapter()
    mutable = Hermes360Provenance(
        repository="pestoura/hermes-ecosystem-architecture",
        revision="main",
        path="inventory/capabilities.yaml",
        blob_sha=BLOB_SHA,
    )

    assert "revision" in _error_message(
        lambda: adapter.consume(_inventory(), provenance=mutable)
    )

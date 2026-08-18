from hermes_factory.staffing.engine import (
    ProfileCapability,
    StaffingEngine,
    StaffingNeed,
    StaffingOutcome,
)


def _profiles() -> tuple[ProfileCapability, ...]:
    return (
        ProfileCapability(
            profile_id="factory-software-engineer",
            lifecycle="ACTIVE",
            capabilities=frozenset({"implementation"}),
            authorized_skills=frozenset({"factory-tdd-implementation"}),
        ),
        ProfileCapability(
            profile_id="factory-security-reviewer",
            lifecycle="ACTIVE",
            capabilities=frozenset({"security-review"}),
            authorized_skills=frozenset({"factory-security-review"}),
        ),
    )


def test_existing_profile_is_selected_without_mutating_workforce() -> None:
    decision = StaffingEngine(_profiles()).resolve(
        StaffingNeed(
            capability="implementation",
            required_skills=frozenset({"factory-tdd-implementation"}),
        )
    )

    assert decision.outcome is StaffingOutcome.USE_EXISTING_PROFILE
    assert decision.profile_id == "factory-software-engineer"
    assert decision.missing_skills == ()


def test_existing_profession_with_admitted_missing_skill_requests_skill_attachment() -> None:
    decision = StaffingEngine(_profiles()).resolve(
        StaffingNeed(
            capability="implementation",
            required_skills=frozenset({"factory-cli-engineering"}),
            admitted_registry_skills=frozenset({"factory-cli-engineering"}),
        )
    )

    assert decision.outcome is StaffingOutcome.ADD_SKILL_TO_EXISTING_PROFILE
    assert decision.profile_id == "factory-software-engineer"
    assert decision.missing_skills == ("factory-cli-engineering",)


def test_gap_routes_to_runbook_template_routine_or_profession_only_by_declared_need() -> None:
    engine = StaffingEngine(_profiles())

    assert (
        engine.resolve(StaffingNeed(capability="release-check", procedural=True)).outcome
        is StaffingOutcome.ADD_RUNBOOK
    )
    assert (
        engine.resolve(StaffingNeed(capability="issue-shape", task_shape_only=True)).outcome
        is StaffingOutcome.ADD_TASK_TEMPLATE
    )
    assert (
        engine.resolve(StaffingNeed(capability="nightly-curation", recurring=True)).outcome
        is StaffingOutcome.CREATE_ROUTINE_PROFILE
    )
    assert (
        engine.resolve(
            StaffingNeed(
                capability="specialized-signer",
                recurring=True,
                distinct_identity_authority=True,
            )
        ).outcome
        is StaffingOutcome.CREATE_PROFESSIONAL_PROFILE
    )


def test_worker_originated_authority_expansion_is_rejected_and_unknown_gap_defers() -> None:
    engine = StaffingEngine(_profiles())

    rejected = engine.resolve(
        StaffingNeed(
            capability="root-access",
            requester_is_worker=True,
            authority_expansion=True,
        )
    )
    deferred = engine.resolve(StaffingNeed(capability="new-unknown-capability"))

    assert rejected.outcome is StaffingOutcome.REJECT
    assert deferred.outcome is StaffingOutcome.DEFER

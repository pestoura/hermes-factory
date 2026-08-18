from hermes_factory.adapters.hermes_cron import (
    HermesCronProjectionError,
    HermesProfileCronAdapter,
)


def test_scheduled_duty_projects_only_to_native_hermes_cron_create_job() -> None:
    adapter = HermesProfileCronAdapter(redact_text=lambda value: value)

    projection = adapter.project_duty(
        profile_id="factory-orchestrator",
        duty_id="reconcile-kanban",
        schedule="every 30m",
        prompt="Reconcile Factory Kanban state against canonical evidence.",
        skills=("factory-reconciling-kanban-state",),
        enabled_toolsets=("kanban",),
    )

    assert projection.surface == "cron.create_job"
    assert projection.profile_id == "factory-orchestrator"
    assert projection.profile_scope == "HERMES_HOME"
    assert projection.reconciliation_key == "factory-cron:factory-orchestrator:reconcile-kanban"
    assert projection.job_kwargs() == {
        "prompt": "Reconcile Factory Kanban state against canonical evidence.",
        "schedule": "every 30m",
        "name": "factory:factory-orchestrator:reconcile-kanban",
        "repeat": None,
        "deliver": "local",
        "skills": ["factory-reconciling-kanban-state"],
        "enabled_toolsets": ["kanban"],
        "no_agent": False,
    }


def test_cron_projection_is_deterministic_and_spec_digest_changes_with_duty_spec() -> None:
    adapter = HermesProfileCronAdapter(redact_text=lambda value: value)
    base = {
        "profile_id": "factory-evidence-auditor",
        "duty_id": "audit-evidence",
        "schedule": "0 * * * *",
        "prompt": "Audit Factory evidence freshness.",
        "skills": ("factory-auditing-evidence",),
        "enabled_toolsets": ("filesystem",),
    }

    first = adapter.project_duty(**base)
    second = adapter.project_duty(**base)
    changed = adapter.project_duty(**{**base, "schedule": "30 * * * *"})

    assert first.reconciliation_key == second.reconciliation_key
    assert first.spec_digest == second.spec_digest
    assert changed.reconciliation_key == first.reconciliation_key
    assert changed.spec_digest != first.spec_digest


def test_cron_projection_fails_closed_without_profile_scope_or_recurring_identity() -> None:
    adapter = HermesProfileCronAdapter(redact_text=lambda value: value)

    invalid = (
        {"profile_id": "", "duty_id": "audit", "schedule": "every 1h", "prompt": "Audit"},
        {"profile_id": "factory-evidence-auditor", "duty_id": "", "schedule": "every 1h", "prompt": "Audit"},
        {"profile_id": "factory-evidence-auditor", "duty_id": "audit", "schedule": "", "prompt": "Audit"},
        {"profile_id": "factory-evidence-auditor", "duty_id": "audit", "schedule": "every 1h", "prompt": ""},
    )
    for case in invalid:
        try:
            adapter.project_duty(**case)
        except HermesCronProjectionError:
            pass
        else:
            raise AssertionError("invalid Factory cron duty must fail closed")


def test_cron_projection_rejects_sensitive_prompt_and_does_not_expose_os_scheduler_fields() -> None:
    adapter = HermesProfileCronAdapter(
        redact_text=lambda value: value.replace("SECRET-42", "[REDACTED]")
    )

    try:
        adapter.project_duty(
            profile_id="factory-orchestrator",
            duty_id="unsafe",
            schedule="every 1h",
            prompt="Use token SECRET-42",
        )
    except HermesCronProjectionError as error:
        assert "sensitive" in str(error)
    else:
        raise AssertionError("sensitive cron prompt must fail closed")

    safe = HermesProfileCronAdapter(redact_text=lambda value: value).project_duty(
        profile_id="factory-orchestrator",
        duty_id="safe",
        schedule="every 1h",
        prompt="Run safe Factory reconciliation.",
    )
    rendered = str(safe.job_kwargs()).lower()
    assert "systemd" not in rendered
    assert "crontab" not in rendered
    assert "scheduler" not in rendered
    assert "script" not in safe.job_kwargs()

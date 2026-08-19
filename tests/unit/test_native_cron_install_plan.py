import pytest


def _contract():
    try:
        from hermes_factory.runtime.cron_projection import (
            CronProjectionError,
            NativeCronPlanBuilder,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("native Hermes cron install plan is not implemented") from exc
    return CronProjectionError, NativeCronPlanBuilder


def test_cron_plan_projects_profile_scoped_native_hermes_cli_without_execution() -> None:
    _, builder_type = _contract()
    plan = builder_type().build(
        {
            "factory-orchestrator": [
                {
                    "id": "reconcile",
                    "schedule": "0 * * * *",
                    "prompt": "Reconcile approved Factory projects",
                    "skills": ["factory-reading-project-truth"],
                }
            ]
        }
    )

    assert plan.execute is False
    assert plan.execution_state == "NOT_RUN"
    assert len(plan.commands) == 1
    assert plan.commands[0].argv == (
        "hermes",
        "-p",
        "factory-orchestrator",
        "cron",
        "create",
        "0 * * * *",
        "Reconcile approved Factory projects",
        "--name",
        "reconcile",
        "--skill",
        "factory-reading-project-truth",
    )
    assert len(plan.digest) == 64


def test_cron_plan_is_deterministic_and_does_not_emit_runtime_state() -> None:
    _, builder_type = _contract()
    duties_a = {
        "b-profile": [{"id": "z", "schedule": "30m", "prompt": "Z"}],
        "a-profile": [{"id": "a", "schedule": "every 2h", "prompt": "A"}],
    }
    duties_b = {
        "a-profile": [{"prompt": "A", "schedule": "every 2h", "id": "a"}],
        "b-profile": [{"prompt": "Z", "schedule": "30m", "id": "z"}],
    }

    first = builder_type().build(duties_a)
    second = builder_type().build(duties_b)

    assert first.to_manifest() == second.to_manifest()
    assert first.digest == second.digest
    manifest = first.to_manifest()
    assert "next_run_at" not in str(manifest)
    assert "created_at" not in str(manifest)
    assert "jobs.json" not in str(manifest)
    assert "systemd" not in str(manifest)
    assert "crontab" not in str(manifest)


def test_cron_plan_fails_closed_on_duplicate_ids_or_invalid_profile() -> None:
    error_type, builder_type = _contract()
    with pytest.raises(error_type, match="duplicate"):
        builder_type().build(
            {
                "factory-orchestrator": [
                    {"id": "same", "schedule": "30m", "prompt": "A"},
                    {"id": "same", "schedule": "1h", "prompt": "B"},
                ]
            }
        )

    with pytest.raises(error_type, match="profile"):
        builder_type().build(
            {"../escape": [{"id": "job", "schedule": "30m", "prompt": "A"}]}
        )


def test_cron_plan_rejects_secret_like_material() -> None:
    error_type, builder_type = _contract()
    with pytest.raises(error_type, match="secret"):
        builder_type().build(
            {
                "factory-orchestrator": [
                    {
                        "id": "unsafe",
                        "schedule": "30m",
                        "prompt": "Use API_TOKEN=super-secret-value and reconcile",
                    }
                ]
            }
        )

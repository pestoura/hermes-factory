import json
from pathlib import Path

import yaml

from hermes_factory.agents import ProfileEvalState
from hermes_factory.agents.runtime_projection import project_native_profile_config


def _runtime_policies() -> dict[str, object]:
    return {
        "status": "approved_for_implementation",
        "implementation_authority": "GRANTED",
        "factory_model_policy": {
            "default": "tencent/hy3:free",
            "provider": "nous",
            "base_url": "https://inference-api.nousresearch.com/v1",
            "ambient_fallback": "forbidden",
        },
        "model_classes": {
            "coding-high": {"selection": "factory-model-policy"},
        },
        "tool_policy_classes": {
            "engineering-worktree": {
                "hermes_toolsets": ["terminal"],
                "mcp": [],
                "terminal": "enabled",
                "browser": "disabled",
            }
        },
        "hermes_profile_defaults": {
            "home_mode": "profile",
            "secrets_in_distribution": "forbidden",
            "memories_in_distribution": "forbidden",
            "sessions_in_distribution": "forbidden",
            "runtime_state_in_distribution": "forbidden",
        },
    }


def _agent_document() -> dict[str, object]:
    return {
        "agent": {
            "id": "factory-demo",
            "model_class": "coding-high",
            "tool_policy_class": "engineering-worktree",
            "skills": {"required": ["reading-project-truth"]},
        }
    }


def _skill_registry() -> dict[str, object]:
    return {
        "registry": {
            "legacy_source_aliases": {
                "reading-project-truth": "factory-reading-project-truth"
            }
        }
    }


def _write_distribution(path: Path) -> None:
    path.mkdir()
    (path / "skills" / "factory-reading-project-truth").mkdir(parents=True)
    (path / "skills" / "factory-reading-project-truth" / "SKILL.md").write_text(
        "---\nname: factory-reading-project-truth\n---\n",
        encoding="utf-8",
    )
    config = project_native_profile_config(
        _agent_document()["agent"],  # type: ignore[arg-type]
        _runtime_policies(),  # type: ignore[arg-type]
    )
    (path / "config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    (path / "mcp.json").write_text(json.dumps({}) + "\n", encoding="utf-8")


def test_static_profile_evaluator_only_passes_mechanically_proven_dimensions(tmp_path):
    from hermes_factory.governance.static_profile_evals import StaticProfileEvaluator

    distribution = tmp_path / "profile"
    _write_distribution(distribution)

    evidence = StaticProfileEvaluator().evaluate(
        agent_document=_agent_document(),
        profile_digest="sha256:candidate",
        distribution=distribution,
        skill_registry=_skill_registry(),
        runtime_policies=_runtime_policies(),
        evidence_ref="ci:test-static-profile-evals",
    )

    assert {item.dimension for item in evidence} == {
        "tool_policy_projection",
        "canonical_inference_identity",
        "skill_allowlist",
        "no_internal_mcp_dependency",
    }
    assert {item.state for item in evidence} == {ProfileEvalState.PASS}
    assert {item.evaluator for item in evidence} == {
        "factory-static-profile-evaluator/v1"
    }


def test_static_profile_evaluator_fails_canonical_inference_dimension_on_provider_drift(tmp_path) -> None:
    from hermes_factory.governance.static_profile_evals import StaticProfileEvaluator

    distribution = tmp_path / "profile"
    _write_distribution(distribution)
    config_path = distribution / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["model"]["provider"] = "auto"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    evidence = StaticProfileEvaluator().evaluate(
        agent_document=_agent_document(),
        profile_digest="sha256:candidate",
        distribution=distribution,
        skill_registry=_skill_registry(),
        runtime_policies=_runtime_policies(),
        evidence_ref="ci:test-static-profile-evals-drift",
    )
    states = {item.dimension: item.state for item in evidence}
    assert states["canonical_inference_identity"] is ProfileEvalState.FAIL

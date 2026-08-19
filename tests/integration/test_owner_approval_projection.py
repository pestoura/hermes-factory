from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_owner_approval_is_projected_without_runtime_activation() -> None:
    approval = yaml.safe_load((ROOT / "approvals/architecture-v1.2.yaml").read_text())["approval"]
    catalog = yaml.safe_load((ROOT / "agents/catalog-v1.2.yaml").read_text())["catalog"]
    skill_policy = yaml.safe_load((ROOT / "skills/registry-policy-v1.2.yaml").read_text())

    assert approval["decision"] == "APPROVED"
    assert approval["implementation_authority"] == "GRANTED"
    assert approval["runtime_activation"] == "GATED"

    assert catalog["lifecycle"] == "approved_for_implementation"
    assert catalog["runtime_status"]["implementation_authority"] == "GRANTED"
    assert catalog["runtime_status"]["profiles_installed_by_this_catalog"] is False
    assert catalog["admission_rules"]["lifecycle_active_required_for_runtime_install"] is True

    assert skill_policy["status"] == "approved_for_implementation"
    assert skill_policy["implementation_authority"] == "GRANTED"
    assert skill_policy["admission"]["active_lifecycle_required_for_runtime_use"] is True
    assert skill_policy["lifecycle"]["active_without_successful_evals"] == "forbidden"

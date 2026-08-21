from pathlib import Path

import yaml

APPROVAL = Path("approvals/architecture-v1.2.yaml")
DECISIONS = Path("docs/07-proposed-architecture-decisions.md")


def test_foundational_decisions_reflect_canonical_owner_approval_without_runtime_activation():
    approval = yaml.safe_load(APPROVAL.read_text(encoding="utf-8"))["approval"]
    text = DECISIONS.read_text(encoding="utf-8")

    assert approval["decision"] == "APPROVED"
    assert approval["implementation_authority"] == "GRANTED"
    assert approval["runtime_activation"] == "GATED"

    assert "**Status:** OWNER APPROVED — v1.2" in text
    assert "**Implementation authority:** GRANTED" in text
    assert "**Runtime activation:** GATED" in text
    assert "PROPOSED_FOR_OWNER_APPROVAL" not in text
    assert "Implementation authority:** NOT GRANTED" not in text

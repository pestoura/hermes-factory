---
name: auditing-evidence-provenance
description: Audit evidence source, scope, freshness and completeness.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, governance, evidence]
    related_skills: [reading-project-truth]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: governance
---

# Auditing Evidence Provenance Skill

Evaluate whether evidence genuinely supports the acceptance claim being made, including source authority, candidate binding, freshness and required gate coverage.

## When to Use

- A Work Package/release is approaching acceptance.
- Evidence came from several systems or agents.
- A previous PASS may be stale or incomplete.

Don't use for: generating the missing evidence while acting as its independent auditor.

## Prerequisites

- Definition of Done / required acceptance class.
- Access to evidence references and their source systems.

## Procedure

1. State the exact acceptance claim and enumerate required evidence classes/gates. **Complete when missing gates cannot be hidden in a generic status.**
2. For each evidence item, resolve producer/source, scope, candidate/environment identity and timestamp. **Complete when provenance fields are explicit or `UNKNOWN`.**
3. Verify evidence belongs to the correct authority domain. **Complete when repository, CI, runtime and approval evidence are not substituted for each other.**
4. Evaluate freshness and candidate/revision applicability, consuming deterministic Exact-SHA gate evidence when required. **Complete when stale evidence is classified.**
5. Detect conflicts between authoritative sources. **Complete when conflicts remain visible rather than normalized.**
6. Compare valid evidence set with required gates and derive completeness only from executed requirements. **Complete when no `NOT_RUN` gate is PASS.**

## Pitfalls

- Trusting an agent's summary instead of the referenced evidence.
- Screenshots/log excerpts with no candidate/environment provenance.
- Treating CI as runtime evidence.
- Creating “evidence” during the audit and then auditing it yourself.

## Verification

Produce `EVIDENCE_COMPLETE`, `EVIDENCE_INCOMPLETE`, `EVIDENCE_STALE`, `EVIDENCE_CONFLICT` or `UNKNOWN`, plus the evidence ledger supporting that classification.

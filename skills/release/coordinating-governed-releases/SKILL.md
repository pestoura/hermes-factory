---
name: coordinating-governed-releases
description: Coordinate release gates, approvals, rollback and evidence.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, release, governance]
    related_skills: [verifying-exact-sha, auditing-evidence-provenance, reconciling-traceability]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: release
---

# Coordinating Governed Releases Skill

Coordinate promotion of an accepted candidate only after identity, gates, approvals and recovery posture satisfy the project release policy.

## When to Use

- A candidate is approaching a controlled release/promotion.
- Release readiness or rollback preconditions need verification.
- A protected environment requires HITL before promotion.

Don't use for: bypassing missing gates or treating deployment success as runtime acceptance.

## Prerequisites

- Release candidate and target environment.
- Project release/acceptance policy.

## Procedure

1. Resolve exact release candidate and target environment. **Complete when candidate identity is unambiguous.**
2. Enumerate required gates, approvals and freshness requirements. **Complete when no implicit prerequisite remains.**
3. Verify exact-SHA and evidence completeness using the relevant Skills. **Complete when stale/missing evidence blocks readiness.**
4. Verify release procedure plus rollback/compensation preconditions where policy requires them. **Complete when recovery posture is known before mutation.**
5. Request HITL and wait for valid approval when required. **Complete when approval identity/scope/expiry match the action.**
6. Coordinate only the authorized bounded promotion. **Complete when release identity/result is recorded.**
7. Hand off to independent runtime observation; do not self-validate live success. **Complete when runtime verification ownership is separate.**

## Pitfalls

- Deadline urgency used as authorization.
- Releasing a later SHA than the reviewed candidate.
- Expired approval reused.
- Deployment command exit zero treated as `ACCEPTED_LIVE`.

## Verification

Return `RELEASE_READY`, `WAITING_HITL`, `RELEASE_BLOCKED`, `RELEASE_EXECUTED` or `ROLLBACK_REQUIRED` with candidate, gate, approval and release evidence references.
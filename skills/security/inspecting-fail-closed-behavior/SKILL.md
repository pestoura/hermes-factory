---
name: inspecting-fail-closed-behavior
description: Verify protected failures refuse safely instead of allowing.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, security, fail-closed]
    related_skills: [reading-project-truth]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: security
---

# Inspecting Fail-Closed Behavior Skill

Verify that protected operations preserve their boundary when policy, trust, credentials, evidence or dependencies are absent, invalid or unavailable.

## When to Use

- Authorization/trust/policy behavior is security-critical.
- A protected dependency can timeout, disappear or return malformed data.
- Negative-path assurance is required before acceptance.

Don't use for: changing policy semantics during assurance.

## Prerequisites

- Protected operation and approved safe failure behavior.
- Non-destructive negative test path or inspection access.

## Procedure

1. Enumerate relevant states: `ABSENT`, `INVALID`, `UNKNOWN`, `EXPIRED`, malformed and unavailable dependency. **Complete when each material failure class is represented.**
2. State the expected safe terminal behavior for each state. **Complete when refusal/recovery semantics are explicit.**
3. Inspect implementation and existing tests for each path. **Complete when uncovered states are known.**
4. Execute permitted negative tests without broadening authority. **Complete when each tested state has observed behavior.**
5. Distinguish controlled refusal, ambiguous crash and fail-open behavior. **Complete when exceptions are not automatically treated as safe.**
6. Record missing runtime/destructive tests as `NOT_TESTABLE`/HITL rather than inferring PASS. **Complete when all states have honest classification.**

## Pitfalls

- Testing explicit DENY but not missing/invalid policy.
- Treating a 500/crash as equivalent to secure refusal.
- Ignoring timeout/fallback paths.
- Modifying the implementation during the assurance gate.

## Verification

Every required negative state is classified and any default-allow, unsafe fallback or ambiguity prevents `FAIL_CLOSED_VERIFIED`.
---
name: reviewing-code-independently
description: Review exact code candidates against spec and regression risk.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, review, code-quality]
    related_skills: [reading-project-truth]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: quality
---

# Reviewing Code Independently Skill

Review an immutable candidate for specification compliance, correctness and maintainability without modifying the candidate during the gate.

## When to Use

- A PR/candidate is ready for independent code review.
- A rework candidate needs re-verification.

Don't use for: implementing fixes while holding the reviewer identity.

## Prerequisites

- Candidate repo/PR/SHA.
- Acceptance criteria and relevant project conventions.

## Procedure

1. Fix and record the exact candidate SHA; consume the deterministic Exact-SHA gate where policy requires it. **Complete when the reviewed revision is unambiguous.**
2. Read specification/acceptance criteria before the diff. **Complete when expected behavior is explicit.**
3. Inspect changed files and affected surrounding paths. **Complete when hidden consequences beyond diff hunks are considered.**
4. Evaluate correctness, state/error handling, compatibility, complexity and scope. **Complete when each material risk has a conclusion.**
5. Evaluate test adequacy: intended behavior, negative paths and regressions. **Complete when test gaps are explicit rather than assumed covered.**
6. Run permitted non-destructive checks when required evidence is absent. **Complete when findings cite direct evidence.**
7. Produce findings with severity/impact, location, rationale and re-verification criterion. **Complete when implementer can act without guessing.**

## Pitfalls

- Reviewing only the diff, not affected behavior.
- Treating CI GREEN as review complete.
- Fixing a finding directly and then approving it yourself.
- Approving a new SHA on old review evidence.

## Verification

The review is bound to one SHA and yields `PASS`, `PASS_WITH_FINDINGS`, `REWORK_REQUIRED` or `BLOCKED`; every finding is actionable and evidence-backed.

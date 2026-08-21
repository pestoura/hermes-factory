---
name: implementing-minimal-green
description: Implement the smallest change that satisfies causal tests.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, engineering, tdd]
    related_skills: [reading-project-truth, scoping-bounded-work, writing-causal-red-tests]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: engineering
---

# Implementing Minimal GREEN Skill

Turn a verified causal RED into the smallest correct production change, then preserve GREEN while hardening only within approved scope.

## When to Use

- A valid causal RED exists for an approved behavior.
- Implementing a bounded feature or bug fix under TDD.

Don't use for: rewriting acceptance tests or broad architectural changes not already approved.

## Prerequisites

- Reproducible `CAUSAL_RED` evidence.
- Work Package scope and acceptance criteria.

## Procedure

1. Reproduce the causal RED on the stated baseline. **Complete when the same intended failure is observed.**
2. Identify the narrowest production code path that can satisfy the behavior and treat that bounded approach as a `minimal change`. **Complete when proposed edits are bounded to the requirement.**
3. Implement the simplest correct change without speculative abstraction. **Complete when the causal test passes.**
4. Run required nearby/regression checks. **Complete when existing required behavior remains GREEN.**
5. Harden only relevant edge/failure paths, keeping all checks GREEN. **Complete when no new unsourced behavior is added.**
6. Review the diff for scope creep, dependency changes and secret exposure. **Complete when every change is justified.**
7. Record exact candidate and hand off for independent review. **Complete when candidate identity is immutable enough for review.**

## Pitfalls

- Refactoring unrelated code before GREEN.
- Adding configuration/frameworks for hypothetical future use.
- Editing the RED test to match the implementation.
- Calling local GREEN final acceptance.

## Verification

The original causal RED is now GREEN on the stated candidate, required regressions pass, and the diff contains no unexplained scope expansion.
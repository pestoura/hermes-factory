---
name: writing-causal-red-tests
description: Write causal failing tests for missing approved behavior.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, testing, tdd]
    related_skills: [reading-project-truth, scoping-bounded-work]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: quality
---

# Writing Causal RED Tests Skill

Create a minimal test that fails because one approved behavior is genuinely missing. An error, broken fixture or unrelated failure is not RED evidence.

## When to Use

- Before implementing a feature or bug fix under TDD policy.
- A specification has testable acceptance criteria.
- A regression must demonstrate the original defect.

Don't use for: behavior already implemented or acceptance criteria that are not yet testable.

## Prerequisites

- Frozen acceptance criterion.
- Test harness capable of exercising the relevant behavior.

## Procedure

1. Name the production behavior whose implementation would make the test pass. **Complete when the causal relation is explicit.**
2. Write one minimal test against real behavior; mock only unavoidable external boundaries. **Complete when the test asserts outcome rather than mock choreography.**
3. Execute the targeted test using `terminal` through the project test command. **Complete when it fails.**
4. Inspect the failure and confirm it is caused by the missing behavior, not test setup/import/dependency noise. **Complete when the failure mechanism matches the acceptance criterion.**
5. Record test path, command, baseline revision and causal explanation. **Complete when another agent can reproduce the RED.**

## Pitfalls

- Test passes because behavior already exists.
- Fixture/import error treated as RED.
- Testing a mock's call count instead of product behavior.
- Multiple requirements bundled into one failing test.

## Verification

`CAUSAL_RED` requires a reproducible failing test with the expected failure mechanism on the stated baseline. Otherwise return `RED_INVALID` or `SPEC_GAP`.
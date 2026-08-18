---
name: factory-designing-user-acceptance-tests
description: Design traceable UAT from approved acceptance criteria.
version: 0.1.0
author: Pedro Estoura, Hermes Factory
license: MIT
metadata:
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: product-acceptance
    managed_by: hermes-factory
---

# Designing User Acceptance Tests

## Purpose

Turn approved requirements and acceptance criteria into bounded, traceable UAT scenarios without weakening the approved product intent.

## Procedure

1. Read canonical requirement and acceptance baseline.
2. Define observable user/business outcome, preconditions, inputs and expected result.
3. Bind the scenario to requirement/criterion identifiers and candidate/context requirements.
4. Select execution mode: `AUTOMATED`, `ASSISTED` or `MANUAL`.
5. Define evidence required for `PASS`, `FAIL`, `BLOCKED` and `INCONCLUSIVE`.
6. Freeze/version the approved scenario before implementation uses it as acceptance evidence.

## Invariants

- `NOT_RUN != PASS`.
- An implementer cannot edit a frozen UAT merely to obtain PASS.
- Requirement/test defects require a Finding and authorized rebaseline.
- UAT evidence is candidate/context-bound and becomes `STALE` when materially invalidated.

---
name: factory-executing-user-acceptance-tests
description: Execute approved UAT and produce traceable evidence.
version: 0.1.0
author: Pedro Estoura, Hermes Factory
license: MIT
metadata:
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: quality-acceptance
    managed_by: hermes-factory
---

# Executing User Acceptance Tests

## Purpose

Execute an approved UAT scenario against the stated candidate/context and produce evidence suitable for acceptance governance.

## Procedure

1. Verify scenario version, candidate/context identity and prerequisites.
2. Execute only the approved steps using the declared `AUTOMATED`, `ASSISTED` or `MANUAL` mode.
3. Capture evidence and actual result without altering expected outcome.
4. Classify execution as `PASS`, `FAIL`, `BLOCKED` or `INCONCLUSIVE`.
5. Mark evidence `STALE` if candidate/context changes invalidate it.
6. On material failure, open/update a Finding rather than editing the approved UAT.

## Invariants

- `NOT_RUN != PASS`.
- Missing prerequisites cannot be reported as PASS.
- Frozen acceptance intent is not modified by the executor.
- Evidence must identify the executed scenario version and candidate/context.

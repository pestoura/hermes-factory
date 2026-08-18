---
name: factory-verifying-corrective-actions
description: Verify a correction and rerun all affected evidence gates.
version: 0.1.0
author: Pedro Estoura, Hermes Factory
license: MIT
metadata:
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: corrective-action
    managed_by: hermes-factory
---

# Verifying Corrective Actions

## Purpose

Prove that a corrective change resolves the Finding without regressing affected behavior and refresh all evidence invalidated by the change.

## Procedure

1. Verify corrected candidate/context identity and the exact Finding/rework version.
2. Execute targeted verification for the claimed root cause/correction.
3. Run required regression checks.
4. Rerun every gate/UAT/review whose evidence was invalidated by the correction.
5. Record new evidence and explicitly mark superseded/stale evidence.
6. Close the Finding only when required independent verification is satisfied; otherwise return it to rework/escalation.

## Invariants

- Implementer self-certification is not accepted where independence is required.
- A changed candidate cannot inherit old SHA-bound PASS evidence.
- Partial targeted success does not imply all affected gates passed.
- `NOT_RUN != PASS`.

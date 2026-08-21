---
name: factory-performing-root-cause-analysis
description: Establish evidence-backed root cause before rework.
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

# Performing Root Cause Analysis

## Purpose

Determine the narrowest evidence-supported cause of a Finding before corrective work is selected.

## Procedure

1. Reproduce or inspect the failure using the original evidence and candidate/context identity.
2. Separate symptom, trigger, contributing conditions and root cause.
3. Test competing hypotheses with the least invasive diagnostic evidence available.
4. Record each unsupported explanation as a `rejected hypothesis` rather than silently discarding it.
5. Set root cause to a supported statement or retain `UNKNOWN` when proof is insufficient.
6. Hand off the cause and evidence to bounded rework planning.

## Invariants

- Correlation is not root-cause proof.
- Do not mutate the candidate merely to diagnose when read-only evidence is sufficient.
- An unresolved cause remains explicit and may force escalation under bounded-rework policy.

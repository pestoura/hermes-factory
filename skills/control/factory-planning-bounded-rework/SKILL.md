---
name: factory-planning-bounded-rework
description: Plan corrective work with explicit retry and escalation bounds.
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

# Planning Bounded Rework

## Purpose

Convert an evidence-backed Finding/root cause into the smallest corrective Work Package while preventing uncontrolled retry loops.

## Procedure

1. Read Finding classification, root cause, affected evidence and required verification.
2. Define the smallest corrective scope and required Profile/capabilities.
3. Record rework-cycle identity and previous attempts for the same cause/class.
4. Set targeted verification and required regressions/gates/UAT to rerun.
5. Compare the current cycle against the configured retry/escalation bound.
6. Create rework only while policy permits; otherwise emit escalation/HITL/external-blocked state.

## Invariants

- Rework does not erase the original failure.
- Infinite retry is forbidden.
- Superficial reclassification does not reset the retry history.
- Corrective scope may not silently broaden approved product scope.

---
name: decomposing-approved-work
description: Decompose approved outcomes into safe dependent work units.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, orchestration, decomposition]
    related_skills: [reading-project-truth, scoping-bounded-work, reconciling-traceability]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: control
---

# Decomposing Approved Work Skill

Turn an already-approved outcome into bounded Work Packages/tasks with explicit dependencies, gates and staffing needs. It does not decide unresolved product or architecture questions.

## When to Use

- An Epic or approved objective is ready for Factory compilation.
- A Work Package is too large for safe independent execution.
- Dependencies/gates need explicit sequencing.

Don't use for: exploratory product design or choosing an unresolved architecture.

## Prerequisites

- Approved objective and canonical acceptance basis.
- Current project quality/autonomy profile.

## Procedure

1. Identify the outcome and required acceptance class. **Complete when the final observable result is explicit.**
2. Separate decision/specification work from production, assurance, runtime and evidence work. **Complete when no producer is implicitly self-reviewing.**
3. Create the minimum Work Packages that can be independently verified. **Complete when each unit has one bounded objective and acceptance criteria.**
4. Add real dependencies only; keep independent work parallelizable. **Complete when dependency edges are necessary and acyclic.**
5. Assign gate requirements and capability needs from project policy. **Complete when every WP can be staffed or emits `CAPABILITY_GAP`.**
6. Generate stable/idempotent identities and provenance links. **Complete when recompilation will reconcile rather than duplicate.**

## Pitfalls

- One task per SDLC label regardless of need.
- Artificially serializing independent work.
- Hiding unresolved decisions inside implementation tasks.
- Creating a giant “implement everything” Work Package.

## Verification

Every generated unit has objective, source refs, acceptance criteria, dependencies, gates and capability needs; no required independent gate is assigned implicitly to its producer.
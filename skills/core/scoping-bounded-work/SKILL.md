---
name: scoping-bounded-work
description: Keep engineering changes inside approved work boundaries.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, scope, work-package]
    related_skills: [reading-project-truth]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: core
---

# Scoping Bounded Work Skill

Keep an execution inside the explicit Work Package while identifying adjacent problems without silently absorbing them.

## When to Use

- Before implementation, refactoring, decomposition or review.
- A discovered issue is useful but not clearly in scope.
- A change touches shared boundaries or multiple repositories.

Don't use for: overriding an approved change in scope; use project governance for that.

## Prerequisites

- Work Package objective, sources and acceptance criteria.
- Current repository/project boundary.

## Procedure

1. Restate the objective as one bounded outcome and list explicit acceptance criteria. **Complete when success can be recognized without extra implied features.**
2. Identify allowed repositories/components/files and prohibited or unrelated areas. **Complete when mutation boundaries are explicit.**
3. Classify discovered adjacent work as required dependency, in-scope correction, follow-up candidate or unrelated. **Complete when every proposed change has a category.**
4. For required dependencies outside current authority, emit a dependency/blocker instead of changing them silently. **Complete when no unauthorized dependency mutation remains.**
5. Before handoff, compare the diff/action set against the boundary. **Complete when every changed artifact traces to the objective or an approved dependency.**

## Pitfalls

- Opportunistic cleanup disguised as hardening.
- Turning a local fix into a framework rewrite.
- Expanding scope because a nearby issue is obvious.
- Assuming shared-library changes are harmless because tests pass.

## Verification

Every mutation or proposed mutation maps to the Work Package objective, acceptance criterion or explicit dependency. Unrelated findings are recorded separately and do not contaminate the candidate.
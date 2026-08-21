---
name: observing-runtime-truth
description: Observe fresh runtime state without changing the system.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, runtime, observation]
    related_skills: [producing-evidence-handoffs]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: operations
---

# Observing Runtime Truth Skill

Collect fresh, attributable live-state evidence without repairing or mutating the environment under observation.

## When to Use

- Acceptance requires proof of deployed/live behavior.
- Repository or CI state may differ from runtime.
- Service health, revision or behavior needs fresh observation.

Don't use for: deployment, restart, configuration repair or other mutations.

## Prerequisites

- Target environment and observation scope.
- Authorized read-only runtime tools.

## Procedure

1. Identify environment, service/process and required observation claims. **Complete when the target cannot be confused with another environment.**
2. Capture runtime identity and deployed artifact/revision where directly observable. **Complete when identity is recorded or explicitly `UNKNOWN`.**
3. Execute the smallest fresh read-only health/behavior observations through approved tools/MCPs. **Complete when each required claim has a timestamped observation.**
4. Record relevant negative observations and conflicts with declared state. **Complete when absence/unhealthy state is not filtered out.**
5. Classify freshness and result as `OBSERVED`, `NOT_OBSERVED`, `STALE`, `CONFLICTING` or `UNKNOWN`. **Complete when no repository inference is labeled observation.**
6. Sanitize secret-bearing output before evidence handoff. **Complete when evidence contains no reusable secret material.**

## Pitfalls

- Restarting a service before measuring it.
- Using deployment logs as proof of current health.
- Treating an old dashboard snapshot as fresh.
- Ignoring revision mismatch because behavior looks healthy.

## Verification

Evidence names target environment, observation time, tool/source, observed behavior and revision identity where available, with no mutation performed by the observer.

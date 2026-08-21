# ADR-0019 — Jarvas CLI as First Factory Product

- **Status:** ACCEPTED
- **Date:** 2026-08-18
- **Decision owner:** Pedro Estoura
- **Architecture baseline:** v1.2
- **Implementation authority:** NOT GRANTED

## Context

The Factory needs a first product that proves greenfield engineering flow, acceptance, traceability and release governance without immediately inheriting the large historical/runtime surface of Hermes Security Labs. The proposed `jarvas` CLI is a bounded ecosystem/Factory control-plane client that can exercise deterministic interfaces, machine-readable output, JDS gates, Skills, Profiles, evidence and release governance.

Hermes Security Labs remains strategically important but is a complex brownfield consumer with existing architecture, runtime, trust-plane and HITL constraints. Using it as the very first Factory product would make it harder to distinguish Factory defects from project legacy/integration defects.

## Decision

The first greenfield product delivered through Hermes Software Factory will be the **Jarvas CLI**.

Canonical bootstrap sequence:

```text
Factory implementation/bootstrap
  -> Factory minimum acceptance baseline
  -> Jarvas CLI (first greenfield Factory product)
  -> Factory dogfoods Jarvas CLI where appropriate
  -> Hermes Security Labs (first complex brownfield onboarding)
  -> unrelated non-Hermes project (portability proof)
```

This ADR changes product sequencing only. It does not authorize implementation of either the Factory or the CLI.

## Anti-bootstrap-dependency invariant

The Factory MUST NOT depend on the Jarvas CLI in order to build, test, review, accept or release the first Jarvas CLI implementation.

During bootstrap, Factory workers use the closest stable native interfaces available under ADR-0014, for example:

```text
native Hermes/Jarvas libraries or APIs
stable machine-readable Hermes CLI where authoritative
JDS CLI/planner
Git/GitHub
Jarvas Operations evidence interfaces
Hermes ecosystem inventory
```

Only after a Jarvas CLI release is independently accepted may the Factory consume it as a convenience/control-plane client, and only for commands whose authority/source-of-truth boundary is explicit.

## Product boundary

The accepted conceptual boundary remains:

```text
hermes ...       = Hermes runtime/profile/kanban/skill/tool operations
jarvas-ops ...   = independent host/service assurance and bounded recovery
jarvas ...       = ecosystem/factory inventory, reconciliation and control client
```

`jarvas` composes existing authorities; it does not become a new authority for secrets, recovery or generic shell execution.

Initial design priorities remain read-first and machine-first:

```text
P0: status, doctor, ecosystem, project compile/reconcile --dry-run, gate, evidence
P1: agent, skill, repo/service diagnostics
P2: bounded mutations such as promote, pause/resume, reopen through underlying authority/HITL
```

Stable `--json` output is a first-class interface for automation and Factory deterministic helpers.

## Acceptance value

Jarvas CLI is selected because it can prove, with a bounded scope:

- project compilation and Work Package traceability;
- TDD/implementation/review separation;
- JDS gate consumption;
- deterministic Exact-SHA identity;
- UAT and corrective-action flow;
- Skills/Agent DNA authorization;
- continuous handoff;
- evidence-derived acceptance;
- release governance;
- safe machine-readable operator interfaces.

## Brownfield follow-up

After Jarvas CLI acceptance, Hermes Security Labs becomes the first complex brownfield onboarding. That stage validates reconciliation against an existing multi-repository system, live/runtime truth, trust-plane constraints and richer HITL.

An additional materially unrelated project is required later to demonstrate that Factory semantics are not Jarvas/Hermes-specific.

## Consequences

### Positive

- cleaner first proof of the Factory lifecycle;
- strong dogfooding opportunity;
- avoids making HSL legacy complexity a bootstrap dependency;
- produces a useful deterministic local control surface early.

### Constraints

- first CLI delivery cannot use itself as a required build/runtime dependency;
- CLI command families must preserve source-of-truth boundaries and fail closed on unavailable authority.

## Related decisions

- ADR-0014 — Internal Native Execution Boundary
- ADR-0017 — First-Class UAT and Corrective Action Loop
- ADR-0020 — Native Hermes Scheduling Only

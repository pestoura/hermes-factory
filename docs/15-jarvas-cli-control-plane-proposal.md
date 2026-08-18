# Jarvas CLI — Ecosystem Control-Plane Product Direction

**Architecture status:** ACCEPTED AS FIRST FACTORY PRODUCT by ADR-0019  
**Product implementation status:** NOT STARTED / NOT AUTHORIZED  
**Date:** 2026-08-18

## Product role

The Hermes/Jarvas ecosystem already has strong local CLIs:

- `hermes` for Hermes runtime, Profiles, Skills, Kanban, tools, Gateway, projects and diagnostics;
- `jarvas-ops` for independent host/service assurance, safe-mode, bounded recovery and controlled operations;
- JDS/project-specific deterministic engineering interfaces.

The accepted `jarvas` product fills the cross-component **ecosystem/Factory control-plane client** gap. It composes existing authorities; it is not another execution engine or generic shell.

```text
hermes ...
  = Hermes runtime/profile/kanban/skill/tool operations

jarvas-ops ...
  = independent operations assurance/recovery

jarvas ...
  = ecosystem/Factory inventory, traceability, reconciliation and governed control client
```

## First-product constraint

Jarvas CLI is the **first greenfield product to be delivered through Hermes Software Factory** after the Factory minimum runtime is accepted.

The Factory MUST NOT depend on Jarvas CLI to build/test/review/accept the first Jarvas CLI release. Bootstrap uses supported native/local Hermes/Jarvas/JDS/Git interfaces. Only an independently accepted CLI may later become a convenience interface for Factory deterministic helpers.

## Priority command families

### P0 — prove the control plane

```text
jarvas status
jarvas doctor
jarvas ecosystem inventory|diff|capability|component
jarvas project list|show|compile --dry-run|reconcile --dry-run|blockers
jarvas gate status|explain|exact-sha|jds
jarvas evidence list|show|verify|freshness|chain
```

### P1 — workforce/repository/service diagnostics

```text
jarvas agent list|show|installed|diff --runtime|evals
jarvas skill list|show|provenance|diff --runtime|evals|consumers
jarvas repo status|drift|jds-plan|upstream
jarvas service list|show|status|logs|evidence
jarvas work list|show|trace|blockers
jarvas release status|candidate|evidence|blockers
```

### P2 — bounded mutations after governance proof

Examples may include:

```text
jarvas factory pause|resume
jarvas work reopen --reason ...
jarvas agent promote|deprecate
jarvas skill promote
```

Every mutation must route through the underlying authority and its policy/HITL boundary; the CLI itself does not invent authority.

## Machine-first contract

Read commands should provide stable structured output:

```text
--json
--quiet
--fields
--project
--profile
--exact-sha
```

Exit-state design must preserve meaningful distinctions such as healthy/satisfied, degraded/findings/stale, blocked/failed policy, invalid input/configuration and external dependency unavailable/inconclusive.

Unknown or `NOT_RUN` must never be converted into success for convenience.

## `jarvas status`

Aggregate without collapsing truth boundaries:

- Jarvas host/operations assurance state;
- Hermes runtime/version/Profile/Gateway state;
- Factory/project state;
- active Hermes boards;
- external governance schedule state where relevant;
- major service readiness;
- unresolved blockers/HITL;
- deployed-versus-repository drift;
- evidence freshness.

External schedule state (including RITMO) must not be interpreted as proof that internal Factory work executed.

## `jarvas doctor`

Complement rather than replace `hermes doctor`, JDS validators and `jarvas-ops` preflight. Detect cross-system inconsistencies such as:

- required Profile absent or not admitted;
- board references an ineligible/missing Profile;
- required Factory Skill absent/not admitted/not evaluated;
- Factory-managed Skill runtime copy differs from canonical provenance;
- invalid project contract or JDS plan;
- accepted SHA differs from repository/deployed identity;
- Agent DNA differs from compiled runtime distribution;
- upstream Hermes fork drift exceeds accepted baseline;
- gate reported PASS while required execution evidence is absent;
- runtime-required acceptance has repository proof but no fresh runtime proof.

## Safety requirements

- read-only by default;
- dry-run for planning/reconciliation;
- no Jarvas-level `--yolo`;
- no generic arbitrary shell facade;
- no secret-value output;
- mutations require explicit policy and true HITL where applicable;
- exact candidate identity for release/promotion;
- underlying component remains authoritative;
- stable JSON never invents PASS.

## Implementation preference

The CLI should be thin and deterministic, resolving in this order when practical:

```text
native library/API
> stable machine-readable CLI
> documented local HTTP interface
> human-formatted CLI parsing (avoid)
```

Internal Factory execution still follows ADR-0014 and MUST NOT be routed through Hermes MCP Bridge merely because an external control surface exists.

## Scheduling boundary

Jarvas CLI may be called by operators or governed automation, but it is not a scheduler. Factory-internal time-driven activity uses **native Hermes Profile/Agent cron** under ADR-0020. External governance schedules may invoke northbound control independently.

## Acceptance target

The first CLI release is valuable precisely because it lets the Factory prove its own lifecycle:

```text
requirements/acceptance baseline
-> Work Packages
-> causal TDD RED
-> minimal GREEN
-> independent review
-> JDS/Exact-SHA
-> UAT
-> Finding/Rework when required
-> release evidence
-> ACCEPTED
```

Only after this evidence chain succeeds should the Factory dogfood the accepted CLI as a local control client.

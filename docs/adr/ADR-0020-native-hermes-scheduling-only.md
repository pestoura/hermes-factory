# ADR-0020 — Native Hermes Scheduling Only for Factory Time-Driven Work

- **Status:** ACCEPTED
- **Date:** 2026-08-18
- **Decision owner:** Pedro Estoura
- **Architecture baseline:** v1.2
- **Implementation authority:** NOT GRANTED

## Context

The v1.1 architecture positioned RITMO as the scheduler for recurring Factory work. Subsequent review of Hermes/Jarvas responsibilities showed that this creates an unnecessary second scheduling dependency for work executed by Factory Profiles. Hermes already provides native Profile/Agent cron and is the closest stable execution authority for time-driven work owned by the Factory.

RITMO remains useful for external governance/supervision schedules, especially when ChatGPT or another external governor should initiate a periodic check through the northbound control boundary. It must not become the internal scheduler for Factory workers.

## Decision

Factory scheduling is split by trigger semantics:

```text
EVENT-DRIVEN FACTORY WORK
  -> Hermes Kanban + Dispatcher

TIME-DRIVEN FACTORY WORK
  -> native Hermes Profile/Agent cron

EXTERNAL GOVERNANCE / CHATGPT SUPERVISION
  -> RITMO or external scheduling boundary as appropriate
  -> northbound control path
```

For Factory-internal time-driven work, **native Hermes Profile/Agent cron is the only accepted scheduling mechanism** in the v1.2 architecture.

The Factory MUST NOT create or require:

```text
Factory-specific scheduler
host crontab/cron as a Factory scheduler
systemd timers as a Factory scheduler
RITMO as an internal Factory worker scheduler
MCP Bridge as an internal scheduling transport
```

Host/system service timers may still exist for infrastructure responsibilities outside the Factory scheduling model; their mere existence does not make them Factory schedulers.

## Examples

### Event-driven

- next engineering stage becomes READY after valid handoff;
- Finding opens corrective-action work;
- review failure creates rework;
- accepted human decision releases a blocked task.

These use Kanban/Dispatcher, not cron.

### Time-driven Factory work

- scheduled Skill evaluation campaign owned by a Factory Profile;
- periodic Agent evaluation owned by a Factory Profile;
- recurring project reconciliation owned by a Factory Profile;
- periodic upstream check owned by an admitted Factory Profile.

These use native Hermes cron attached to the responsible Profile/Agent.

### External governance

- ChatGPT periodic independent audit;
- external portfolio review initiated outside the Factory failure domain;
- owner-facing recurring supervision event.

These may use RITMO/external scheduling to invoke the northbound control surface, but the resulting Factory work still enters through governed Factory/Kanban semantics.

## Source-of-truth rules

- Schedule definition for a Factory Profile belongs to the Hermes-native Profile/distribution/cron representation derived from admitted Agent DNA/policy.
- The Factory semantic registry may reference the schedule and its provenance but does not become the scheduler.
- RITMO schedule state never proves that an internal Factory task executed successfully.
- `NOT_RUN` remains distinct from `PASS` for scheduled activity.

## Consequences

### Positive

- removes duplicate scheduling semantics;
- keeps worker scheduling adjacent to the Profiles that own the work;
- avoids MCP/RITMO loops inside Jarvas;
- preserves RITMO for genuinely external supervision rather than internal IPC.

### Constraints

- v1.1 references that say `RITMO schedules Factory work` are superseded by this ADR;
- generated Profile distributions must compile approved time-driven schedules into Hermes-native cron without silently creating host-level schedules.

## Rejected alternatives

### RITMO for all recurring Factory activity

Rejected because it adds an unnecessary internal dependency and separates scheduled work from its native Hermes Profile authority.

### Host cron/systemd timers

Rejected as the Factory scheduling contract because they bypass Agent/Profile provenance and Factory semantic governance.

### Factory-owned scheduler

Rejected because Hermes already provides the required native scheduling primitive.

## Related decisions

- ADR-0014 — Internal Native Execution Boundary
- ADR-0016 — Autonomous Continuous Stage Handoff
- ADR-0018 — Asynchronous HITL through Hermes Gateway

# Hermes Factory — Controlled Installation Surface

This directory documents the Phase P installation boundary for the Hermes Software Factory.

The canonical implementation of the controlled install planner is `src/hermes_factory/runtime/install.py`. The planner is deliberately side-effect free: it may report `READY`, but it always emits `execute=false`. Runtime execution is a separate controlled transition and must never be inferred from planning or repository CI.

## Admission requirements

A controlled runtime installation is eligible to move beyond planning only when all of the following are independently evidenced:

- the observed Hermes runtime commit matches the accepted exact SHA;
- all 17 Profile candidates have complete PASS evaluation evidence for their current distribution digests;
- all 29 Factory Skills have complete PASS evaluation evidence for their current source-directory digests;
- all eight Phase P runtime components have PASS evidence;
- the native cron installation plan is not blocked;
- no candidate artifact has drifted since its evaluation evidence was recorded.

The current F/G workload is 298 checks: 153 Profile checks (`17 × 9`) and 145 Skill gates (`29 × 5`). Missing, NOT_RUN, UNKNOWN, STALE, ABSENT, BLOCKED or FAIL evidence never collapses into PASS.

## Native Hermes mechanisms

The installation surface reuses Hermes/Jarvas primitives instead of introducing a parallel runtime:

- Profile Distributions: `hermes profile install <distribution>`;
- Factory Skills: native Profile-scoped `skills/<factory-skill>/SKILL.md` directories carried inside the evaluated Profile Distribution;
- time-driven duties: `hermes -p <profile> cron create ...`, allowing Hermes to create its own Profile-local cron runtime state;
- Dashboard: Factory plugin from `hermes-integration/dashboard-plugin/hermes-factory`, registered below `HERMES_HOME/plugins/hermes-factory`;
- Gateway HITL: existing `hermes_factory.adapters.hermes_gateway` adapter over the native Hermes Gateway clarification/response mechanism;
- northbound control: `hermes-integration/mcp-bridge/factory-northbound.yaml`, using the Hermes MCP Bridge only for authorized external control, never internal Factory IPC;
- Kanban: native Hermes Kanban/Dispatcher with the Factory high-assurance policy;
- Factory package: staged into the controlled Hermes runtime environment only after the same admission gates succeed.

`component-map.yaml` is the declarative human/machine-readable map of these eight Phase P components. It is not an executable script.

## Current checkpoint

Repository-side planning and preflight are implemented. Runtime installation has **not** been performed.

Current known blockers remain fail-closed:

- 17 Profile candidates: evaluation state `NOT_RUN`;
- 29 Factory Skills: evaluation state `NOT_RUN`;
- 298 total F/G evaluation work items remain to be executed and persisted;
- northbound MCP Bridge integration remains externally `BLOCKED` on its bound candidate until independent CI/runtime evidence succeeds;
- the live accepted Hermes runtime exact SHA has not been asserted by repository tests.

The Phase Q acceptance matrix is already defined but its 15 runtime scenarios also remain `NOT_RUN` until controlled installation and runtime verification are legitimately available.

## Safety invariants

The installation surface must never embed or copy secrets, `.env`, authentication state, memories, sessions, runtime databases or other mutable Hermes state. It must not create systemd timers, host crontabs, a Factory scheduler, or internal MCP IPC. Existing Profile-local user state is owned by Hermes runtime semantics and is outside Factory distribution ownership.

A `READY` plan means only that the prerequisites for a controlled execution have been evidenced. It does **not** mean the installation ran, a Profile or Skill became ACTIVE, or the Factory reached `ACCEPTED_RUNTIME`.

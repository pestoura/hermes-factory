# Hermes Factory — Controlled Installation Surface

This directory documents the Phase P installation boundary for the Hermes Software Factory.

The canonical controlled install planner is `src/hermes_factory/runtime/install.py`. The planner is deliberately side-effect free: it may report `READY`, but it always emits `execute=false`.

The controlled execution boundary is `src/hermes_factory/runtime/install_execution.py`. It consumes only a `READY` plan plus an explicit authorization bound to that exact plan digest. Runtime mutation is delegated to an injected Hermes/Jarvas runtime adapter, so planning, repository CI and execution remain distinct. If an operational step fails, the executor requests compensation for already-applied operations in reverse order and reports either `ROLLED_BACK` or `ROLLBACK_FAILED` rather than silently continuing.

## Admission requirements

A controlled runtime installation is eligible to move beyond planning only when all of the following are independently evidenced:

- the observed Hermes runtime commit matches the accepted exact SHA;
- the Factory package is a verified `hermes.factory/package-candidate/v2` candidate bound to the expected exact Factory Git SHA;
- the candidate wheel filename, size, raw content SHA-256 and canonical Factory artifact digest all match the downloaded wheel before planning;
- all 17 Profile candidates have complete PASS evaluation evidence for their current distribution digests;
- all 29 Factory Skills have complete PASS evaluation evidence for their current source-directory digests;
- all eight Phase P runtime components have PASS evidence;
- the native cron installation plan is not blocked;
- no digest-bound source has drifted since its evaluation or package evidence was recorded;
- the explicit execution authorization references the exact current install-plan digest and contains approval provenance;
- after authorization and immediately before the first mutation, the executor revalidates every digest-bound local source and fails closed on drift.

The full F/G workload is 298 checks: 153 Profile checks (`17 × 9`) and 145 Skill gates (`29 × 5`). Repository CI has legitimately completed 51 deterministic Profile checks (`17 × 3`) with PASS evidence for `tool_policy_projection`, `skill_allowlist` and `no_internal_mcp_dependency`. The remaining 247 checks are behavioral and remain `NOT_RUN`: 102 Profile checks and 145 Skill gates; 46 of those work items require an independent reviewer. Missing, NOT_RUN, UNKNOWN, STALE, ABSENT, BLOCKED or FAIL evidence never collapses into PASS.

## Native Hermes mechanisms

The installation surface reuses Hermes/Jarvas primitives instead of introducing a parallel runtime:

- Profile Distributions: `hermes profile install <distribution>`;
- Factory Skills: native Profile-scoped `skills/<factory-skill>/SKILL.md` directories carried inside the evaluated Profile Distribution;
- time-driven duties: `hermes -p <profile> cron create ...`, allowing Hermes to create its own Profile-local cron runtime state;
- Dashboard: Factory plugin from `hermes-integration/dashboard-plugin/hermes-factory`, registered below `HERMES_HOME/plugins/hermes-factory`;
- Gateway HITL: existing `hermes_factory.adapters.hermes_gateway` adapter over the native Hermes Gateway clarification/response mechanism;
- northbound control: `hermes-integration/mcp-bridge/factory-northbound.yaml`, using the Hermes MCP Bridge only for authorized external control, never internal Factory IPC;
- Kanban: native Hermes Kanban/Dispatcher with the Factory high-assurance policy;
- Factory package: the verified exact-head wheel candidate produced by Factory CI, never a mutable repository reference.

`component-map.yaml` is the declarative human/machine-readable map of these eight Phase P components. It is not an executable script.

## Current checkpoint

Repository-side planning, package-candidate verification, preflight, source-identity protection and the controlled executor are implemented. Runtime installation has **not** been performed.

Current known blockers remain fail-closed:

- 17 Profile candidates have 51 deterministic PASS checks in total, but their remaining 102 behavioral checks are still `NOT_RUN`; no Profile is therefore eligible to become ACTIVE;
- all 29 Factory Skills still require their 145 behavioral lifecycle gates to execute and persist PASS evidence before activation;
- 247 F/G behavioral work items remain to be executed and persisted, including 46 that require an independent reviewer;
- northbound MCP Bridge integration remains externally `BLOCKED` on its bound candidate until independent CI/runtime evidence succeeds;
- the live accepted Hermes runtime exact SHA has not been asserted by repository tests;
- no real runtime execution authorization has been issued or consumed;
- no controlled Hermes/Jarvas runtime install has run.

The Phase Q acceptance matrix is already defined but its 15 runtime scenarios also remain `NOT_RUN` until controlled installation and runtime verification are legitimately available.

## Safety invariants

The installation surface must never embed or copy secrets, `.env`, authentication state, memories, sessions, runtime databases or other mutable Hermes state. It must not create systemd timers, host crontabs, a Factory scheduler, or internal MCP IPC. Existing Profile-local user state is owned by Hermes runtime semantics and is outside Factory distribution ownership.

A `READY` plan means only that the prerequisites for a controlled execution have been evidenced. It does **not** mean the installation ran, a Profile or Skill became ACTIVE, or the Factory reached `ACCEPTED_RUNTIME`.

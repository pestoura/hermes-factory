# Jarvas CLI — Ecosystem Control-Plane Proposal

**Status:** PROPOSED  
**Date:** 2026-08-18  
**Implementation authority:** NOT GRANTED

## Why this exists

The Hermes/Jarvas ecosystem already has strong local CLIs:

- `hermes` for the Hermes runtime, Profiles, Skills, Kanban, tools, gateway, hooks, projects, sessions and diagnostics;
- `jarvas-ops` for independent host/service assurance, health, safe-mode, bounded recovery and controlled Hermes upgrades;
- project-specific scripts/CLIs for engineering gates and individual services.

What is missing is a coherent **ecosystem/operator client** that answers cross-component questions and drives Factory semantics without forcing the operator to remember which repository or script owns each concern.

The proposed command is:

```text
jarvas
```

It is a composition/control client, not another execution engine.

## Boundary

```text
hermes ...
  Native Hermes agent/runtime operations

jarvas-ops ...
  Independent operations assurance/recovery

jarvas ...
  Portfolio, Factory, inventory, traceability and reconciliation
```

`jarvas` MUST delegate to supported component interfaces and preserve each component's authority boundary. It MUST NOT become a generic unrestricted shell facade.

## Highest-value command groups

### 1. `jarvas status`

One read-only answer to "what state is my ecosystem in?"

Should aggregate, without inventing PASS:

- Jarvas host/operations state;
- Hermes runtime/version/profile/gateway state;
- Factory state;
- active project boards;
- RITMO state;
- major service readiness;
- unresolved blockers/HITL;
- deployed-vs-repository version drift;
- evidence freshness.

Structured output should support `--json`.

### 2. `jarvas doctor`

Cross-component diagnostic that complements, not replaces, `hermes doctor` and `jarvas-ops preflight`.

It should detect integration failures such as:

- Hermes profile exists but required Factory Skill is absent;
- board references a missing Profile;
- Factory contract points to an unavailable repository;
- JDS configuration is invalid/unresolvable;
- runtime baseline SHA differs from accepted ecosystem inventory;
- Factory-managed Skill differs from its canonical source;
- required service dependency is unavailable;
- upstream fork drift exceeds accepted baseline.

### 3. `jarvas ecosystem`

```text
jarvas ecosystem inventory
jarvas ecosystem diff
jarvas ecosystem capability <id>
jarvas ecosystem component <id>
jarvas ecosystem refresh
```

This is the CLI projection of Hermes Ecosystem Architecture machine inventory.

It should make questions such as these deterministic:

```text
What is implemented?
What is deployed?
What is live?
What is planned?
What is blocked?
Which exact revision is accepted?
```

### 4. `jarvas project`

Factory-semantic project management, distinct from Hermes Desktop `hermes project` workspace management.

```text
jarvas project list
jarvas project show <project>
jarvas project onboard <path|repo>
jarvas project compile <project> --dry-run
jarvas project reconcile <project> --dry-run
jarvas project blockers <project>
```

Mutation/dispatch remains separately gated.

### 5. `jarvas factory`

```text
jarvas factory status
jarvas factory portfolio
jarvas factory pause <project>
jarvas factory resume <project>
jarvas factory reconcile --all --dry-run
```

This is company-level control, not per-agent shell execution.

### 6. `jarvas work`

```text
jarvas work list --project <id>
jarvas work show <wp>
jarvas work trace <wp>
jarvas work blockers <wp>
jarvas work reopen <wp> --reason <...>
```

The CLI should display both Factory state and the bound Hermes Kanban Task instead of collapsing them into one status.

### 7. `jarvas agent`

```text
jarvas agent list
jarvas agent show <id>
jarvas agent installed
jarvas agent diff <id> --runtime
jarvas agent evals <id>
jarvas agent promote <id>@<version>
jarvas agent deprecate <id>
```

This is Agent DNA lifecycle control. Installation/promotion must preserve approval and runtime validation gates.

### 8. `jarvas skill`

Factory Skill governance rather than general Hermes Skill browsing.

```text
jarvas skill list
jarvas skill show <id>
jarvas skill provenance <id>
jarvas skill diff <id> --runtime
jarvas skill evals <id>
jarvas skill test <id>
jarvas skill promote <id>@<version>
jarvas skill consumers <id>
```

General non-Factory Skill management remains `hermes skills ...`.

### 9. `jarvas gate`

```text
jarvas gate status <wp>
jarvas gate explain <wp> <gate>
jarvas gate exact-sha <wp>
jarvas gate jds <project|wp>
```

This should expose why something is blocked, including `NOT_RUN`, `STALE`, `FAILED` and `NOT_REQUIRED` distinctly.

### 10. `jarvas evidence`

```text
jarvas evidence list <wp|project>
jarvas evidence show <id>
jarvas evidence verify <id>
jarvas evidence freshness <wp>
jarvas evidence chain <acceptance-id>
```

The command must return provenance/references, not secret contents.

### 11. `jarvas repo`

Cross-repository governance and platform drift:

```text
jarvas repo status <repo>
jarvas repo drift <repo>
jarvas repo jds-plan <repo>
jarvas repo upstream <repo>
jarvas repo reconcile-hermes-upstream --dry-run
```

The last command is especially valuable for the hardened `pestoura/hermes-agent` fork.

### 12. `jarvas service`

A read-mostly service catalog over known Jarvas services:

```text
jarvas service list
jarvas service show <service>
jarvas service status <service>
jarvas service logs <service> --tail 100
jarvas service evidence <service>
```

Do not duplicate recovery commands already governed by `jarvas-ops`. A mutating service action should route through the authoritative operations plane and require its policy.

### 13. `jarvas release`

```text
jarvas release status <project>
jarvas release candidate <project>
jarvas release evidence <project>
jarvas release blockers <project>
```

Release execution remains policy/HITL controlled.

## Machine-first contract

Every read command should support stable structured output:

```text
--json
--quiet
--fields
--project
--profile
--exact-sha
```

Exit codes should be stable and meaningful, for example:

```text
0 = requested state satisfied / healthy
1 = degraded / findings / stale
2 = blocked / failed policy or gate
3 = invalid input/configuration
4 = external dependency unavailable / inconclusive
```

Do not reuse an exit code where the difference matters to automation.

## Safety requirements

- read-only by default;
- `--dry-run` for reconciliation/planning commands;
- no `--yolo` equivalent at the Jarvas control-plane level;
- mutations require explicit policy and, where applicable, HITL;
- no generic arbitrary shell command;
- no secret-value output;
- exact candidate identity for release/promotion actions;
- underlying component remains authoritative for the mutation;
- JSON output never turns unknown state into success.

## Implementation preference

`jarvas` should be a thin Python CLI/client package that composes supported local APIs/CLIs/libraries. It should avoid parsing human-formatted output where a JSON/native interface exists.

Suggested resolution order:

```text
native library/API
    > stable JSON CLI
    > documented local HTTP endpoint
    > human CLI parsing (avoid)
```

## Why this is strategically useful

A coherent Jarvas CLI creates one stable local control surface for:

- human operators on the server;
- scripts/systemd/RITMO jobs;
- Factory internal deterministic helpers;
- troubleshooting;
- future remote projections;
- reproducible evidence collection.

It also reduces pressure to expose every internal operation through MCP. MCP remains valuable for external semantic clients such as ChatGPT; local deterministic automation can use the Jarvas CLI/native interfaces.

# ADR-0014 — Internal Native Execution Boundary

- **Status:** ACCEPTED
- **Date:** 2026-08-18
- **Decision owner:** Pedro Estoura
- **Scope:** Hermes Software Factory architecture
- **Implementation authority:** NOT GRANTED by this ADR

## Context

The Hermes Software Factory executes inside the Hermes/Jarvas server environment. The ecosystem also contains `hermes-mcp-bridge`, whose primary purpose is to expose a governed remote interface from external MCP clients, notably ChatGPT, into Hermes/Jarvas.

Earlier Factory design material risked treating the MCP Bridge as an internal execution dependency for Factory-to-Hermes communication. That would introduce an unnecessary local protocol hop and couple autonomous Factory execution to an interface whose principal trust boundary is external/northbound.

Hermes/Jarvas already provides native local execution surfaces including Hermes CLI, Kanban, Profiles, Skills, Dispatcher, workspaces/worktrees, local services and project/tool integrations. The Factory should use the closest stable native interface for work performed inside the Jarvas boundary.

## Decision

The Hermes Software Factory **MUST use native Hermes/Jarvas interfaces for internal execution**.

The `hermes-mcp-bridge` is classified as a **northbound external-control boundary** and is not a required substrate for autonomous internal Factory work.

Canonical direction:

```text
ChatGPT / external governor
        |
        | MCP
        v
Hermes MCP Bridge
        |
        v
External Factory Control Surface
======== JARVAS TRUST BOUNDARY ========
        |
        v
Hermes Software Factory
        |
        +--> Hermes CLI / native APIs
        +--> Hermes Kanban / Dispatcher
        +--> Hermes Profiles / Skills
        +--> Git / gh / GitHub integration
        +--> JDS / Jarvas Engineering Platform
        +--> Jarvas Operations read/assurance surfaces where applicable
        +--> local project/runtime services
```

Internal Factory execution therefore MUST NOT be architected as:

```text
Factory -> MCP Bridge -> Hermes
```

when an appropriate native Hermes/Jarvas interface exists locally.

## Rationale

1. **Lower coupling** — autonomous Factory operation does not depend on the remote-governor interface.
2. **Smaller failure surface** — avoids unnecessary HTTP/MCP/loopback hops for local operations.
3. **Clear trust boundary** — MCP Bridge remains an external access boundary rather than becoming internal IPC.
4. **Native capability reuse** — Kanban, Profiles, Skills, Dispatcher and CLI remain canonical execution primitives.
5. **Autonomy** — Factory work continues when ChatGPT or another remote MCP client is disconnected.
6. **Least architectural duplication** — Factory does not create adapter layers merely to call local functionality through a remote protocol.

## Consequences

### Positive

- Factory runtime is simpler and more resilient.
- The MCP Bridge can evolve independently as the remote/governance interface.
- Internal workers can use native Hermes task-scoped Skills, model overrides, worktrees and board semantics directly.
- ChatGPT remains an independent external governor rather than part of the Factory's critical execution path.

### Constraints

- A stable **external Factory control contract** is still required for ChatGPT supervision.
- That contract may be exposed through the existing Hermes MCP Bridge, an additive Factory control surface reachable through it, or another explicitly approved northbound mechanism.
- Internal components must not depend on private MCP Bridge state as their canonical operational state.

## Interface rule

For any new Factory integration, choose the interface in this order unless a stronger project-specific constraint applies:

1. native in-process/library contract where intentionally supported;
2. native Hermes/Jarvas CLI or local API/service contract;
3. local provider/tool integration;
4. MCP only where it is the intentional service boundary or no safer native interface exists.

The Factory MUST NOT introduce MCP solely for architectural uniformity.

## Security boundary

This ADR does not widen Factory authority. Native access is still bounded by:

- Agent DNA authority;
- Hermes tool/toolset configuration;
- MCP allowlists where an MCP is genuinely required;
- workspace/worktree boundaries;
- project scope;
- structured dispatch approvals;
- HITL and secret-handling gates;
- Jarvas Operations recovery ceilings;
- project-specific policy.

`SOUL.md` guidance is not an authorization mechanism.

## Superseded interpretation

Any Factory design text that implies the MCP Bridge is the default internal transport between Factory components and Hermes is superseded by this ADR.

## Verification required before implementation

Before implementation begins, the implementation plan must map every proposed Factory operation to its actual native Hermes/Jarvas interface and identify any operation that still genuinely requires an MCP boundary.

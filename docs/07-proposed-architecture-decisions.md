# Hermes Software Factory — Foundational Decisions

**Status:** MIXED — D-014 and D-015 are formally ACCEPTED; remaining proposed decisions stay subject to owner review unless separately promoted into ADRs.

This document makes the architectural choices visible before implementation. Acceptance of a design decision does not automatically approve future implementation mutations.

## D-001 — Build on Hermes native primitives

**Decision proposed:** HSF is an edge-layer product over Hermes Agent, reusing native profiles, SOULs, skills, Kanban, dispatcher, worktrees, review and scheduling.

**Why:** avoids duplicating a mature execution substrate and keeps the Factory aligned with Hermes' narrow-core/edge-extension philosophy.

**Rejected direction:** create a second agent runtime/board/dispatcher beside Hermes.

---

## D-002 — One Hermes board per client project

**Decision proposed:** every Factory-managed project receives an isolated Hermes Kanban board.

**Why:** durable operational state, project isolation, worker scoping and clean multi-project portfolio boundaries.

**Consequence:** portfolio reporting aggregates boards; it does not merge all projects into one global task table view for execution.

---

## D-003 — Global workforce lives in the Factory

**Decision proposed:** enterprise agent profiles, Souls, Factory-owned skills, runbooks, policies and evals live with HSF/Hermes, not inside client repositories.

**Why:** agents represent reusable company employees, not project-specific prompt fragments.

**Client repository responsibility:** project-specific context such as `AGENTS.md` / `.hermes.md` and Factory contract.

**Clarification:** Factory-owned Skills use the native Hermes Skill model but are governed by the Factory Skill Registry; see D-015 / ADR-0015.

---

## D-004 — Project repositories expose a declarative Factory contract

**Decision proposed:** `.factory/project.yaml`, `.factory/quality.yaml` and `.factory/acceptance.yaml` provide the machine-readable handoff boundary.

**Why:** allows the Factory to understand a project deterministically while canonical documents remain canonical.

**Rejected direction:** make chat transcripts or Factory database copies the only durable source of project intent.

---

## D-005 — Use a semantic traceability graph

**Decision proposed:** preserve Project, Requirement, ADR, Epic, Change, Issue, Work Package, Task, Execution, Branch, PR, SHA, CI, Deployment, Runtime Evidence and Acceptance as distinct entities linked by provenance.

**Why:** prevents the Kanban from becoming a lossy replacement for architecture, SCM or runtime evidence.

---

## D-006 — Work Package is the Factory delivery unit

**Decision proposed:** Epics are outcomes; Hermes tasks are operational executions; the Factory Work Package sits between them as the bounded governed delivery unit.

**Why:** it can carry acceptance criteria, staffing, gates, traceability and dependencies without overloading either Epic or Kanban task semantics.

---

## D-007 — Agent DNA is versioned and evaluated

**Decision proposed:** persistent Factory roles are versioned packages with Soul, authority, tools, methods, runbooks, invariants, output contract and evaluations.

**Why:** behavior changes in agents must be auditable and regression-tested like software.

**Consequence:** an execution records the agent/profile version used.

---

## D-008 — Acceptance is evidence-derived

**Decision proposed:** `done` is never sufficient. Required gates determine acceptance.

**Mandatory invariants:**

- `NOT_RUN != PASS`;
- repository proof != runtime proof;
- evidence for SHA-A != evidence for SHA-B;
- an unexecuted gate cannot be PASS;
- high-assurance producer/reviewer separation is enforced.

---

## D-009 — ChatGPT is an independent external Factory Governor

**Decision proposed:** the Factory remains operational through Hermes/Jarvas without an active ChatGPT conversation. ChatGPT performs second-line governance from outside the Jarvas execution boundary through the approved northbound control surface.

**Boundary clarification:** the Hermes MCP Bridge belongs on the ChatGPT/external-client -> Hermes/Jarvas path. It is not a default internal Factory execution dependency. Internal Factory work uses native Hermes/Jarvas interfaces in accordance with D-014 / ADR-0014.

**Why:** continuous delivery must not depend on a browser conversation remaining alive, while independent validation still adds a stronger control layer.

---

## D-010 — Hermes Security Labs is pilot, not architecture

**Decision proposed:** HSL is the first Factory client because it is complex enough to stress the model. A second unrelated project is required to prove portability.

**Success test:** no HSL-specific redesign of Factory core for the second onboarding.

---

## D-011 — Bootstrap read-only, then increase authority deliberately

**Decision proposed:** implementation starts with validation, read-only compilation and dry-run reconciliation before task creation/dispatch/runtime mutation.

**Why:** the Factory is privileged orchestration software. Its first delivery path should demonstrate correct understanding before it gains authority.

---

## D-012 — Stable external Factory control surface

**Decision proposed:** ChatGPT and other external governors use a dedicated versioned Factory control contract rather than private Hermes/Factory database schemas.

**Transport clarification:** the existing Hermes MCP Bridge is the preferred northbound boundary for ChatGPT -> Hermes/Jarvas. The Factory control contract may be exposed through that boundary; the Factory itself does not call back through the Bridge for normal internal work.

**Why:** preserves implementation freedom, least privilege, observability and a testable external contract without turning MCP into internal IPC.

---

## D-013 — Permanent Agent Admission Gate

**Decision proposed:** every new Factory profile must pass a permanent Agent Admission Gate before entering the active workforce catalog. Capability gaps may propose expansion but never create a new profile or new authority silently.

**Decision outcomes include:**

```text
USE_EXISTING_PROFILE
ADD_SKILL_TO_EXISTING_PROFILE
ADD_RUNBOOK
ADD_TASK_TEMPLATE
CREATE_ROUTINE_PROFILE
CREATE_PROFESSIONAL_PROFILE
DEFER
REJECT
```

**Why:** a profile is persistent organizational configuration with Soul, memory, tools, authority, cost and maintenance burden. The Factory must distinguish real professional specialization from work that belongs in a Skill, Runbook or existing role.

**Initial catalog consequence:** add `factory-workforce-architect`, `factory-product-designer` and `factory-documentation-engineer`; keep additional specializations demand-driven.

**Segregation rule:** the Workforce Architect may propose Agent DNA changes but must not solely approve its own authority-increasing proposals.

---

## D-014 — Internal native execution boundary

**Status:** ACCEPTED — formalized as `docs/adr/ADR-0014-internal-native-execution-boundary.md`.

**Decision:** the Hermes Software Factory executes inside Jarvas through the closest appropriate native Hermes/Jarvas interface. The Hermes MCP Bridge is a northbound external-control boundary, principally ChatGPT/external client -> Hermes/Jarvas, and is not the default substrate for internal Factory execution.

**Canonical rule:**

```text
ChatGPT -> Hermes MCP Bridge -> external Factory control surface
                              ================= Jarvas boundary
                              -> Hermes Software Factory
                              -> native Hermes/Jarvas interfaces
```

**Rejected direction:** `Factory -> MCP Bridge -> Hermes` when a supported local native interface exists.

**Consequence:** autonomous Factory execution remains independent of remote ChatGPT/MCP connectivity.

---

## D-015 — Factory-owned Skills on the Hermes native Skill model

**Status:** ACCEPTED — formalized as `docs/adr/ADR-0015-factory-owned-skills-on-hermes-native-model.md`.

**Decision:** the Factory adopts Hermes' native Skill format, loading, discovery, profile/task integration and lifecycle mechanics, but owns and governs its professional Skill content through a Factory Skill Registry.

**Key distinction:**

```text
Hermes Skill Framework = technical substrate
Factory Skill Registry  = approved professional library
Jarvas Skill Catalog     = wider server toolbox/reference
```

Existing Hermes/Jarvas Skills are not automatically admitted to Factory work merely because they exist or overlap by name.

**Source-of-truth rule for Factory-managed Skills:**

```text
pestoura/hermes-factory = canonical source
Hermes profile copy     = runtime projection
HermesJarvasServer      = inventory/snapshot/backup
```

**Agent execution rule:** Factory Profiles use explicit approved Skill allowlists derived from Agent DNA plus task-approved Skills. Server-wide Skill availability does not imply Factory authorization.

**Promotion rule:** new Factory Skills remain proposed until behaviour is demonstrated through appropriate RED/GREEN, variation/pressure evaluation and independent review. `NOT_RUN` is never `PASS`.

---

## Decision review checklist

For decisions not already marked ACCEPTED, owner review should explicitly determine whether each decision is:

```text
ACCEPTED
ACCEPTED_WITH_CHANGES
DEFERRED
REJECTED
```

Accepted items should be promoted into formal ADR files before implementation begins.

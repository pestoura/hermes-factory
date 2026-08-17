# Hermes Software Factory — Proposed Foundational Decisions

**Status:** PROPOSED — to be split into formal ADRs after owner review.

This document makes the architectural choices visible before implementation. Acceptance of the design does not automatically approve future implementation mutations.

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

**Decision proposed:** enterprise agent profiles, Souls, skills, runbooks, policies and evals live with HSF/Hermes, not inside client repositories.

**Why:** agents represent reusable company employees, not project-specific prompt fragments.

**Client repository responsibility:** project-specific context such as `AGENTS.md` / `.hermes.md` and Factory contract.

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

## D-009 — ChatGPT is an independent Factory Governor

**Decision proposed:** the Factory remains operational through Hermes/Jarvas without an active ChatGPT conversation; ChatGPT periodically performs second-line governance via a stable Factory Control MCP.

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

## D-012 — Stable Factory Control MCP

**Decision proposed:** ChatGPT and other governors use a dedicated versioned Factory Control MCP rather than private Hermes/Factory database schemas.

**Why:** preserves implementation freedom, least privilege, observability and a testable external contract.

---

## Decision review checklist

Owner review should explicitly determine whether each decision is:

```text
ACCEPTED
ACCEPTED_WITH_CHANGES
DEFERRED
REJECTED
```

After Architecture v1 review, accepted items should be promoted into formal ADR files before implementation begins.

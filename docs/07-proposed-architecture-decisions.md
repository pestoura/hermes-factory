# Hermes Software Factory — Foundational Decisions

**Status:** RECONCILED THROUGH v1.2  
**Implementation authority:** NOT GRANTED

This index summarizes the current architectural decision set. Formal ADRs take precedence over earlier proposal wording. Where v1/v1.1 text conflicts with Architecture v1.2, the v1.2 canonical specification wins.

## D-001 — Build on Hermes native primitives

HSF is a semantic/organizational layer over Hermes native Profiles, Skills, Kanban, Dispatcher, worktrees, review and cron. It is not a second agent runtime.

## D-002 — One isolated Hermes board per client project

Hermes Kanban remains operational work truth; portfolio views aggregate project boards rather than collapsing execution into one global queue.

## D-003 — Global workforce lives in the Factory

Agent DNA, Factory-owned Skills, policies and evals are reusable organizational assets owned by HSF, not copied into every client repo.

## D-004 — Declarative project contract — UPDATED v1.2

Current recommended contract:

```text
.factory/project.yaml
.factory/acceptance.yaml
.jarvas/engineering.yml
```

`.factory/quality.yaml` from the original v1 proposal is **SUPERSEDED** for generic engineering gates. JDS-001 owns generic gate planning.

## D-005 — Semantic traceability graph — UPDATED v1.2

Preserve distinct entities including Project, Requirement, AcceptanceCriterion, UATScenario, ADR, Epic, Change, Issue, WorkPackage, KanbanTask, Execution, PR/SHA/CI, Deployment, RuntimeEvidence, UATExecution/UATEvidence, Finding, ReworkOrder, HITLRequest/HumanDecision and AcceptanceDecision.

## D-006 — Work Package is the Factory delivery unit

Epics describe outcomes; Hermes tasks execute work; Work Packages carry bounded delivery semantics, staffing, evidence, dependencies and acceptance.

## D-007 — Agent DNA is versioned and evaluated

Persistent roles are versioned packages compiled into Hermes Profile Distributions. SOUL is identity/reasoning context, not security enforcement.

## D-008 — Acceptance is evidence-derived

Mandatory invariants include:

- `NOT_RUN != PASS`;
- repository proof != runtime proof;
- evidence for candidate A != evidence for changed candidate B;
- required independent review cannot be self-certified;
- stale evidence cannot silently satisfy acceptance.

## D-009 — ChatGPT is an independent external Factory Governor

The Factory continues to operate locally without an active ChatGPT conversation. ChatGPT reaches governance through the northbound Factory Control contract/Hermes MCP Bridge.

## D-010 — Product sequence — UPDATED v1.2

Jarvas CLI is the **first greenfield Factory product**. Hermes Security Labs becomes the **first complex brownfield onboarding**. A materially unrelated project follows as portability proof.

## D-011 — Bootstrap read-only, then increase authority deliberately

Implementation starts with validation/read-only/dry-run reconciliation before bounded task/SCM/runtime mutations.

## D-012 — Stable external Factory control surface

External governors use a versioned Factory control contract. MCP is an external boundary, not internal IPC.

## D-013 — Permanent Agent Admission Gate

Capability gaps do not silently create Profiles/authority. Outcomes include reuse, Skill/runbook/task-template addition, governed Profile creation, defer or reject.

## D-014 — Internal native execution boundary

**Status:** ACCEPTED — `docs/adr/ADR-0014-internal-native-execution-boundary.md`

```text
ChatGPT -> Hermes MCP Bridge -> external Factory control
                              ===== Jarvas boundary =====
                              -> Hermes Software Factory
                              -> native Hermes/Jarvas interfaces
```

Internal `Factory -> MCP Bridge -> Hermes` loops are rejected where a supported local/native interface exists.

## D-015 — Factory-owned Skills on Hermes native model

**Status:** ACCEPTED — `docs/adr/ADR-0015-factory-owned-skills-on-hermes-native-model.md`

Factory owns professional Skill content/admission/evals; Hermes supplies native Skill mechanics. Runtime/global installation does not imply Factory authorization.

Canonical runtime Skill identities use the `factory-*` namespace. Proposed/not-run Skills are not ACTIVE.

## D-016 — Autonomous continuous stage handoff

**Status:** ACCEPTED — `docs/adr/ADR-0016-autonomous-continuous-stage-handoff.md`

Ordinary stage transitions are authorized by structured machine/policy decisions and proceed automatically when prerequisites are satisfied. Structured approval does not imply a human click.

Handoff is atomic over outcome, artifacts, evidence/freshness, candidate identity where applicable, Finding/review state and next-stage prerequisites.

## D-017 — First-class UAT and corrective action

**Status:** ACCEPTED — `docs/adr/ADR-0017-first-class-uat-and-corrective-action-loop.md`

UAT, Findings and Rework are first-class. Frozen acceptance/UAT cannot be changed by an implementer merely to obtain PASS. Rework is autonomous but bounded; repeated same-cause failure escalates.

## D-018 — Asynchronous revision-bound HITL

**Status:** ACCEPTED — `docs/adr/ADR-0018-asynchronous-hitl-through-hermes-gateway.md`

The Factory emits transport-independent `HITL_REQUEST` objects through Hermes Gateway. Telegram is a presentation adapter. Human decisions are request/context/candidate-version bound governance evidence; stale/replayed/expired responses cannot unlock work.

## D-019 — Jarvas CLI first Factory product

**Status:** ACCEPTED — `docs/adr/ADR-0019-jarvas-cli-first-factory-product.md`

Jarvas CLI is the first greenfield product. The Factory must not depend on the CLI in order to build the first CLI release.

## D-020 — Native Hermes scheduling only for Factory time-driven work

**Status:** ACCEPTED — `docs/adr/ADR-0020-native-hermes-scheduling-only.md`

```text
EVENT-DRIVEN FACTORY WORK -> Hermes Kanban + Dispatcher
TIME-DRIVEN FACTORY WORK  -> native Hermes Profile/Agent cron
EXTERNAL GOVERNANCE       -> RITMO/external schedule via northbound control
```

RITMO, host crontab, systemd timers and a Factory-specific scheduler are not internal Factory worker scheduling mechanisms.

## Current approval gate

Architecture v1.2 remains `PROPOSED_FOR_OWNER_APPROVAL` until the clean branch audit proves the current human-readable and machine-readable sources are coherent. Approval of architecture will still not imply runtime mutation; a separate implementation plan follows.

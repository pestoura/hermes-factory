# Hermes Software Factory — Product Sequence & Roadmap

**Status:** RECONCILED FOR v1.2  
**Implementation authority:** NOT GRANTED

## Strategy

v1.2 changes the validation sequence so the Factory proves itself first on a bounded greenfield product and only then on a complex brownfield system.

Canonical sequence:

```text
Architecture v1.2 approval
-> Factory runtime implementation plan
-> Factory minimum runtime/bootstrap
-> Jarvas CLI: first greenfield Factory product
-> Hermes Security Labs: first complex brownfield onboarding
-> unrelated non-Hermes project: portability proof
```

This sequence does not authorize implementation by itself.

## Why Jarvas CLI is first

Jarvas CLI is a bounded control-plane client that can exercise the Factory lifecycle without inheriting the full historical/runtime complexity of HSL. It provides a strong first proof of:

- project compilation and traceability;
- TDD RED -> minimal GREEN;
- independent code/security review where required;
- JDS gate consumption;
- deterministic Exact-SHA;
- UAT and corrective-action flow;
- Agent DNA / Factory Skill authorization;
- autonomous stage handoff;
- evidence-derived acceptance;
- release governance and stable machine-readable interfaces.

The Factory MUST NOT depend on Jarvas CLI to build the first Jarvas CLI release. Bootstrap uses supported native Hermes/Jarvas/JDS/Git interfaces.

## Why HSL follows

Hermes Security Labs remains an essential client because it stresses:

- multiple repositories/dependencies;
- architecture decisions/change governance;
- CI/exact-SHA;
- repository versus runtime truth;
- explicit HITL;
- security-sensitive operations;
- Vault/trust-plane constraints;
- live runtime validation;
- strong fail-closed expectations.

That makes HSL the **first complex brownfield onboarding**, not the first greenfield product.

## Phase 0 — Architecture approval

Deliverables:

- Architecture Review v1.2;
- canonical design v1.2;
- ADR-0014 through ADR-0020;
- authoritative Agent catalog v1.2;
- Factory Skill registry/policy v1.2;
- Kanban/handoff/UAT/HITL/scheduling design policies;
- clean branch audit.

Gate: owner approves Architecture v1.2 before runtime implementation planning.

## Phase 1 — Factory minimum runtime

After approval, write a separate implementation plan following:

```text
design/spec
-> implementation plan
-> TDD RED
-> minimal GREEN
-> hardening
-> CI/exact-SHA
-> merge
-> post-merge verification
```

Initial implementation should remain read/dry-run first and prove:

- schemas and configuration validation;
- read-only Project Compiler;
- Semantic Traceability Registry;
- JDS adapter;
- Hermes Kanban/Profile/Skill/native adapters;
- Agent/Skill admission checks;
- Git/GitHub read reconciliation;
- deterministic gate/evidence model;
- no internal MCP dependency;
- no duplicate scheduler/dispatcher.

## Phase 2 — Governed continuous execution

Introduce bounded mutations only after read/dry-run truth is proven:

- Work Package -> Kanban reconciliation;
- admitted staffing;
- admitted Skill attachment;
- isolated worktrees;
- atomic stage handoff;
- structured machine/policy transition authorization;
- independent reviewer assignment;
- bounded rework;
- explicit HITL blocks.

Hermes Kanban/Dispatcher remains the sole operational execution queue.

## Phase 3 — UAT / corrective action / acceptance

Implement first-class:

```text
AcceptanceCriterion
UATScenario
UATExecution
UATEvidence
Finding
ReworkOrder
HumanDecision
AcceptanceDecision
```

Required properties:

- frozen UAT baseline cannot be changed by implementer to obtain PASS;
- `NOT_RUN != PASS`;
- changed candidate/context stales affected evidence;
- repeated same-cause rework is bounded/escalated;
- valid HITL response is revision-bound governance evidence;
- acceptance is derived from current required evidence.

## Phase 4 — Scheduling and external governance

Internal Factory trigger model:

```text
EVENT-DRIVEN -> Hermes Kanban + Dispatcher
TIME-DRIVEN  -> native Hermes Profile/Agent cron only
```

External independent governance such as scheduled ChatGPT audit may be initiated through RITMO/external scheduling and the northbound MCP control surface. RITMO does not schedule internal Factory workers.

## Phase 5 — Jarvas CLI greenfield delivery

Deliver Jarvas CLI as the first Factory product under the same governed lifecycle intended for future client projects.

Initial product priorities:

```text
P0: status, doctor, ecosystem, project compile/reconcile --dry-run, gate, evidence
P1: agent, skill, repo/service diagnostics
P2: bounded controlled mutations after authority/evidence gates
```

Machine-first requirements include stable `--json`, explicit exit states, dry-run, no generic shell, no secret values and no Jarvas-level `--yolo`.

Success gate: Jarvas CLI is accepted from evidence produced through the Factory lifecycle without being a bootstrap dependency of its own delivery.

## Phase 6 — HSL brownfield onboarding

Onboard `pestoura/hermes-security-labs` with read-only reconciliation first:

1. load canonical HSL project state;
2. compile desired Factory semantic graph;
3. compare GitHub/history/runtime/evidence state;
4. show proposed Work Packages/board/staffing/gates without dispatch;
5. resolve capability and truth gaps;
6. enable bounded dispatch only after onboarding model is accepted.

Existing HSL governance must not be weakened to simplify the Factory.

## Phase 7 — Portability proof

Onboard a materially unrelated project.

Success criteria:

- no Jarvas/HSL-specific core schema redesign;
- same Agent/Skill admission model;
- same UAT/Finding/Rework/HITL semantics;
- same evidence/acceptance model;
- project-specific behavior selected via contract/JDS/config rather than Factory core forks.

## Factory v1 success criteria

HSF is not successful because a dashboard is attractive. It succeeds when it can demonstrate:

- deterministic/idempotent project compilation;
- traceability from product intent to exact delivered evidence;
- admitted reusable Profiles and Skills;
- no silent Profile/authority creation;
- native Hermes continuous execution;
- atomic handoffs;
- producer/reviewer separation where required;
- JDS + deterministic Exact-SHA correctness;
- first-class UAT;
- bounded corrective action;
- stale evidence protection;
- true HITL with revision-bound human evidence;
- native Hermes cron for internal recurring work;
- repository/runtime truth separation;
- external ChatGPT governance without operational dependency;
- successful greenfield Jarvas CLI and brownfield HSL delivery;
- successful unrelated portability proof.

## Explicitly deferred until core proof

- elaborate cost/chargeback models;
- broad autonomous authority expansion;
- separate Factory web application;
- generic replacement schedulers/workflow engines;
- automatic promotion of proposed Skills/Profiles without eval evidence.

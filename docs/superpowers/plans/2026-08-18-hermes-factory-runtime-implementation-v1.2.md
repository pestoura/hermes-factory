# Hermes Software Factory — Full Runtime Implementation Plan v1.2

**Status:** APPROVED FOR EXECUTION  
**Architecture:** v1.2  
**Owner approval:** `approvals/architecture-v1.2.yaml`  
**Approved audited design SHA:** `281b8c7509252d0416621f9971e14bd4151b997a`  
**Implementation branch:** `implementation/factory-runtime-v1.2`  
**Target runtime:** Hermes/Jarvas, Python 3.11  
**Delivery scope:** COMPLETE ARCHITECTURE — no minimum/MVP substitution

## Delivery discipline

Every implementation slice follows:

```text
approved spec
-> causal TDD RED
-> minimal GREEN
-> hardening / negative paths
-> integration tests
-> JDS effective gate plan
-> CI
-> deterministic Exact-SHA
-> independent review
-> merge
-> controlled install
-> runtime verification
```

No unexecuted Profile, Skill, gate or runtime observation may be labelled PASS/ACTIVE.

## Native integration rule

Factory owns semantic/organizational intelligence and MUST reuse Hermes/Jarvas runtime primitives rather than duplicate them:

- Hermes Kanban + Dispatcher = operational queue/execution
- Hermes Profiles/Profile Distributions = workforce runtime
- Hermes Skills = Skill runtime/discovery; Factory owns Skill content/admission
- Hermes native Profile/Agent cron = all Factory-internal time-driven work
- Hermes Gateway = HITL delivery/response transport; Telegram is an adapter
- Hermes Dashboard plugin system = Factory UI
- JDS = generic engineering gate plan
- Jarvas Operations = independent operational evidence/recovery boundary
- Hermes 360 = ecosystem capability inventory
- Git/GitHub = SCM/evidence
- Hermes MCP Bridge = northbound external control only, never internal Factory IPC

## Source layout

```text
src/hermes_factory/
  __init__.py
  errors.py
  types.py
  config.py
  contracts/
  compiler/
  traceability/
  staffing/
  agents/
  skills/
  kanban/
  handoff/
  uat/
  rework/
  hitl/
  evidence/
  gates/
  governance/
  adapters/
  runtime/
  control/

tests/
  unit/
  integration/
  contract/
  evals/
  acceptance/

hermes-integration/
  profiles/
  dashboard-plugin/
  gateway/
  install/
```

## Phase A — Foundation, strict contracts, state model

### A1 Packaging / strict loaders

Create Python 3.11 package, pytest/ruff/mypy configuration, immutable domain IDs, UTC timestamps, strict YAML loading, explicit validation errors and canonical serialization.

Tests first:
- malformed/unknown contract fields fail closed;
- `NOT_RUN`, `UNKNOWN`, `ABSENT`, `STALE` never collapse into PASS;
- enums round-trip canonically;
- evidence/context revision is mandatory where specified.

### A2 Project Contract

Implement strict loaders/validators for:
- `.factory/project.yaml`
- `.factory/acceptance.yaml`
- `.jarvas/engineering.yml` reference/input contract

Do not recreate JDS gate logic.

## Phase B — Semantic Traceability & Evidence Registry

Implement persistent SQLite registry with migrations and typed repositories for:
Project, Requirement, AcceptanceCriterion, UATScenario, ADR, Epic, WorkPackage, KanbanTaskRef, Execution, Branch/PR/SHA/CI, Deployment, RuntimeEvidence, UATExecution/UATEvidence, Finding, ReworkOrder, HITLRequest, HumanDecision, AcceptanceDecision.

Requirements:
- append-oriented provenance/event ledger;
- idempotency keys;
- revision binding/freshness;
- immutable evidence identity;
- no acceptance without required evidence.

## Phase C — Project Compiler

Inputs:
- project/acceptance contracts;
- requirements/architecture/ADRs;
- repository/current code/CI state;
- JDS effective gate plan;
- Hermes 360 capabilities;
- Factory policies/Agent/Skill catalogues.

Outputs:
- Project Model;
- Epics;
- Work Packages;
- dependency DAG;
- stage workflow;
- required professions/Skills;
- gates/HITL/runtime/UAT requirements;
- acceptance graph.

Compiler is semantic planning only; it does not become a second work queue.

## Phase D — Hermes native Kanban adapter + continuous handoff

Adapter to native Hermes Kanban/Dispatcher only.

Implement:
- board/project reconciliation;
- task creation/linking/assignment via native interfaces;
- dependency readiness;
- high-assurance settings (`auto_decompose=false`, structured authorization);
- atomic HandoffRecord;
- HANDOFF_READY promotion;
- stale handoff detection;
- no worker text as completion proof.

No custom dispatcher, queue or scheduler.

## Phase E — Staffing Engine

Resolve Work Package capability requirements against admitted Agent DNA + Skill Registry.

Allowed outcomes only:
- USE_EXISTING_PROFILE
- ADD_SKILL_TO_EXISTING_PROFILE
- ADD_RUNBOOK
- ADD_TASK_TEMPLATE
- CREATE_ROUTINE_PROFILE
- CREATE_PROFESSIONAL_PROFILE
- DEFER
- REJECT

Workers cannot self-create/promote or broaden authority.

## Phase F — Agent DNA Compiler / all 17 Profiles

Implement schema validation and compiler from:

```text
Agent DNA + Factory Constitution + Runtime Policies + admitted Skills + Model Policy
-> native Hermes Profile Distribution
```

Generate native projection artifacts only; never author secrets, `.env`, memories, sessions, state DBs or logs.

Compile/evaluate all 17 approved Profile candidates. Runtime activation is individually gated.

Required Profile evaluation dimensions:
- routing correctness;
- refusal/authority boundary;
- tool policy projection;
- Skill allowlist;
- separation of duties;
- handoff/evidence quality;
- escalation correctness;
- no internal MCP dependency;
- native cron projection when scheduled duties exist.

## Phase G — Factory-owned Skill system / complete catalogue

Implement registry validator/compiler/eval harness using Hermes-native Skill format and discovery/runtime mechanics.

Rules:
- canonical `factory-*` IDs;
- canonical source = `pestoura/hermes-factory`;
- HermesJarvasServer = runtime mirror/inventory, non-canonical;
- global install != authorization;
- effective skills = admitted required ∪ admitted task-approved;
- worker self-expansion forbidden.

Evaluate every Factory-owned Skill through:
`baseline RED -> Skill GREEN -> variation -> pressure -> independent review -> ACTIVE`.

Include UAT/Finding/Rework Skills from v1.2 and all existing admitted Factory Skill content.

## Phase H — UAT + Finding + bounded Corrective Action

Implement first-class UAT entities/states/modes.

Enforce:
- frozen acceptance cannot be weakened by implementer;
- rebaseline is explicit/versioned/authorized;
- UAT evidence bound to candidate/context;
- FAIL opens/updates Finding;
- classification and root-cause state;
- bounded ReworkOrder;
- affected-gate invalidation;
- targeted verification + regression + UAT rerun;
- repeated same-cause failure escalates, never loops forever.

## Phase I — HITL + Hermes Gateway / Telegram

Implement transport-independent HITLRequest/HumanDecision service and Hermes Gateway adapter.

Enforce:
- request/context/candidate revision binding;
- allowed responder identity;
- expiry/stale/cancel/replay fail closed;
- timeout HOLD;
- no auto-selection;
- immutable HumanDecision evidence committed before unblock;
- no secrets in HITL message.

Inspect and use the actual Telegram interactive primitive exposed by the Hermes Gateway; do not assume a combo-box implementation.

## Phase J — Native Hermes Profile cron projection

Compile Factory time-driven duties into native Hermes Profile/Agent cron only.

Tests must prove no projection can produce host crontab, systemd timer, RITMO internal schedule, Factory scheduler or internal MCP scheduling loop.

## Phase K — External adapters

### K1 JDS Adapter
Consume JDS planner output/effective gate plan; no gate reimplementation.

### K2 Git/GitHub Adapter
SCM/PR/commit/check/evidence functions with exact identity and bounded write authority.

### K3 Jarvas Operations Evidence Adapter
Read-only assurance/runtime/recovery evidence; Factory never captures recovery authority.

### K4 Hermes 360 Capability Adapter
Consume canonical ecosystem inventory/capability/provenance.

## Phase L — Deterministic Exact-SHA integration

Implement deterministic validator states:
- SHA_MATCH
- SHA_MISMATCH
- EVIDENCE_STALE
- EVIDENCE_ABSENT
- IDENTITY_UNKNOWN

No LLM verdict and no evidence transfer across changed candidate unless explicit validity rule permits it.

## Phase M — Governance / Acceptance / Release

Implement evidence-derived AcceptanceDecision with distinct repository/integration/UAT/live/release classes as required by project policy.

Enforce separation of duties, freshness, independent evidence and owner-reserved decisions.

## Phase N — Hermes Dashboard Factory plugin

Build Factory overlay on native Hermes Dashboard/plugin mechanism:
- portfolio/projects;
- Epic/WP/Requirement;
- Kanban stage;
- assigned Profile/Skills;
- PR/SHA/CI;
- JDS gates;
- UAT;
- Findings/Rework;
- HITL;
- evidence freshness;
- acceptance/release state;
- Agent/Skill eval/provenance.

No standalone dashboard service unless Hermes plugin contract technically requires a plugin backend.

## Phase O — Northbound Factory Control contract

Expose external governance/control semantics for authorized clients through the existing Hermes MCP Bridge boundary. Internal workers must not call this surface.

Read-first, explicit mutation authority, stable machine outputs, HITL/policy on protected mutations.

## Phase P — Installation / admission / runtime projection

Controlled install to Hermes/Jarvas:
- validate current Hermes accepted exact SHA;
- reconcile upstream fork if required by policy;
- install Factory package/integration;
- compile Profile distributions;
- install evaluated Skills from canonical source;
- configure native Kanban/high-assurance policy;
- configure native Profile cron duties;
- register Dashboard plugin;
- register Gateway HITL adapter;
- register northbound control integration;
- no secrets embedded in source/distributions.

Profile/Skill ACTIVE state only after its own eval gate succeeds.

## Phase Q — Full Factory acceptance

E2E acceptance scenarios must cover at minimum:
1. project onboarding/compile;
2. dependency-driven autonomous Profile handoff;
3. independent code/security/integration/UAT path;
4. FAIL -> Finding -> bounded Rework -> correction -> rerun;
5. stale SHA invalidates evidence;
6. true HITL emitted and valid HumanDecision resumes only affected work;
7. expired/stale/replayed HITL cannot unlock;
8. unrelated WPs continue while one is WAITING_HITL;
9. time-driven Factory job is native Hermes cron only;
10. runtime observation is read-only and distinct from deployment;
11. evidence-derived acceptance refuses NOT_RUN/UNKNOWN/STALE;
12. Dashboard reflects canonical Factory/Kanban/evidence truth;
13. external northbound control works without becoming internal IPC;
14. all 17 Profile runtime projections validate;
15. all required Factory Skills have explicit eval state.

Only after Phase Q PASS may Factory be classified `ACCEPTED_RUNTIME` and receive Jarvas CLI as its first product.

## First product after Factory acceptance

Jarvas CLI starts only after complete Factory runtime acceptance. It is the first greenfield delivery performed by the Factory itself and is not a bootstrap dependency.

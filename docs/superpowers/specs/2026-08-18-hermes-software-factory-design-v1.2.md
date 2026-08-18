# Hermes Software Factory — Canonical Design v1.2

**Status:** PROPOSED FOR OWNER APPROVAL  
**Date:** 2026-08-18  
**Decision owner:** Pedro Estoura  
**Implementation authority:** NOT GRANTED  
**Supersedes on conflict:** v1 and v1.1 design material

## 1. Product definition

Hermes Software Factory (HSF) is a persistent autonomous engineering organization running natively inside Hermes/Jarvas. It converts approved project intent into governed engineering work, staffs that work with admitted Hermes Profiles and Factory-owned Skills, executes through native Hermes Kanban/Dispatcher/worktrees, and derives acceptance from evidence rather than agent self-report.

HSF is a reusable company model. Client projects retain their own product intent, source code, architecture, requirements, ADRs, tests, CI and runtime truth.

## 2. Core principles

1. **Native first:** inside Jarvas, use the closest stable native Hermes/Jarvas interface; do not loop internal work through the MCP Bridge.
2. **One execution queue:** Hermes Kanban/Dispatcher own operational work execution.
3. **Semantic Factory:** HSF owns Project Compiler semantics, Work Packages, staffing, traceability, acceptance and organizational governance.
4. **JDS canonical quality planning:** `.jarvas/engineering.yml` -> JDS Effective Gate Plan -> Factory Compiler.
5. **Evidence over narrative:** `agent says done` is not proof; `NOT_RUN != PASS`.
6. **Deterministic controls first:** mechanically decidable controls such as Exact-SHA are validators, not LLM professions/Skills.
7. **Independent assurance:** producers do not self-certify required independent review/audit/runtime observation.
8. **Factory-owned professional Skills:** Hermes supplies the Skill runtime/model; HSF controls content, admission, versioning, evals and authorization.
9. **Bounded autonomy:** ordinary transitions are automatic when policy permits; true HITL is explicit and fail-closed.
10. **No duplicate schedulers:** event work uses Kanban/Dispatcher; internal timed work uses native Hermes Profile/Agent cron.
11. **Truth boundaries stay separate:** repository truth, CI evidence, runtime truth, project/board state and external governance claims are never conflated.
12. **Bootstrap safely:** read/dry-run first, then bounded mutation after architecture/implementation authority.

## 3. System boundaries

```text
Pedro / Product Owner
        |
ChatGPT Independent Governor
        |
Hermes MCP Bridge (northbound only)
        |
External Factory Control Contract
================ Jarvas boundary ================
        |
Hermes Software Factory semantic layer
        |
+-----------------+------------------+------------------+
| Hermes native   | Jarvas services  | SCM / Runtime    |
| Kanban/Profiles | JDS / Ecosystem  | GitHub / CI      |
| Skills/cron     | Jarvas Ops read  | live evidence    |
| worktrees       | evidence adapter |                  |
+-----------------+------------------+------------------+
```

The normal internal path `Factory -> MCP Bridge -> Hermes` is forbidden when a supported native/local interface exists.

## 4. Factory-owned components

The v1.2 implementation budget is limited to:

- Project Compiler;
- Semantic Traceability Registry;
- Staffing Engine;
- Agent DNA Registry/Compiler;
- Factory Skill Registry/Eval Harness;
- JDS Adapter;
- Hermes Kanban/native execution adapter;
- SCM/GitHub Adapter;
- Jarvas Operations Evidence Adapter;
- Hermes Ecosystem Capability Adapter;
- Factory Governance/Acceptance;
- deterministic Exact-SHA integration;
- Hermes Dashboard plugin/semantic overlay;
- External Factory Control contract.

Explicit non-components:

- no second Kanban/work queue;
- no second dispatcher/workspace engine;
- no generic DAG/runbook/policy/lock/saga engine where existing infrastructure already owns it;
- no internal MCP transport requirement;
- no second generic engineering-gate platform;
- no replacement recovery daemon;
- no standalone Factory web application for v1.2;
- no Factory-specific scheduler.

## 5. Project contract

Recommended project-level contract:

```text
.factory/
├── project.yaml
└── acceptance.yaml

.jarvas/
└── engineering.yml
```

Responsibilities:

```text
.factory/project.yaml
  = project identity, repositories, canonical sources, board/workflow, autonomy boundaries

.factory/acceptance.yaml
  = Factory acceptance classes, UAT/HITL/runtime acceptance semantics

.jarvas/engineering.yml
  = JDS capabilities, criticality/risk and generic engineering gates
```

`.factory/quality.yaml` is superseded as a generic gate authority. A future Factory-specific overlay may contain only semantics not represented by JDS and may never weaken JDS controls.

## 6. Project Compiler

Inputs:

- `.factory/project.yaml` and `.factory/acceptance.yaml`;
- `.jarvas/engineering.yml` plus JDS Effective Gate Plan;
- requirements/ADRs/architecture/Epics/change records;
- current code, tests and CI configuration;
- GitHub issues/PRs/SHAs;
- Hermes board/task state;
- Hermes ecosystem capability inventory;
- relevant runtime/evidence state when available.

Output model:

```text
Project Model
-> Epics
-> Work Packages
-> dependency relations
-> required lifecycle stages/gates
-> staffing requirements
-> admitted Skills
-> HITL boundaries
-> UAT requirements
-> Definition of Done / acceptance requirements
```

Compilation must be deterministic/idempotent for unchanged canonical input. Capability gaps produce governed staffing/admission outcomes; they never silently create Profiles or authority.

## 7. Work Package and lifecycle

Work Package is the governed delivery unit between product intent and native Kanban tasks.

Lifecycle baseline:

```text
DISCOVER
-> SPECIFY
-> DESIGN
-> THREAT MODEL when required
-> TDD RED
-> IMPLEMENT
-> UNIT
-> INTEGRATION when required
-> CODE REVIEW
-> SECURITY REVIEW when required
-> ADVERSARIAL / FAIL-CLOSED REVIEW when required
-> REGRESSION
-> CI
-> EXACT SHA
-> MERGE
-> DEPLOY when required
-> RUNTIME VERIFY when required
-> UAT
-> OBSERVE
-> ACCEPT
```

A project/JDS plan may mark stages `NOT_REQUIRED`; an unexecuted required stage is never PASS.

## 8. Continuous stage handoff

ADR-0016 is normative.

Ordinary transition:

```text
Profile A executes Stage A
-> stage outcome/artifacts/evidence committed
-> candidate identity and Finding state committed when applicable
-> handoff prerequisites evaluated
-> HANDOFF_READY
-> structured machine/policy authorization
-> Stage B task READY
-> Hermes Dispatcher starts admitted Profile B
```

Handoff states:

```text
WORKING
HANDOFF_PENDING
HANDOFF_READY
HANDOFF_BLOCKED
HANDED_OFF
STALE
```

Atomic handoff requires stage outcome, artifact/evidence refs, evidence freshness, candidate identity where relevant, open Finding state, independent-review state where relevant and next-stage prerequisites. Material context change invalidates a pending ready handoff.

`dispatch_approval_mode=structured` does not mean human approval. Human intervention occurs only for a declared HITL boundary.

## 9. UAT and acceptance

ADR-0017 is normative.

First-class entities:

```text
Requirement
AcceptanceCriterion
UATScenario
UATExecution
UATEvidence
AcceptanceDecision
```

UAT execution states:

```text
NOT_REQUIRED
NOT_RUN
PASS
FAIL
BLOCKED
INCONCLUSIVE
STALE
```

Modes:

```text
AUTOMATED
ASSISTED
MANUAL
```

Approved/frozen Acceptance Criteria and UAT scenarios are immutable to implementers. If the acceptance definition is defective:

```text
Finding
-> TEST_DEFECT or REQUIREMENT_DEFECT
-> authorized product/requirements decision
-> explicit rebaseline/version
-> re-execution against new baseline
```

Editing UAT merely to make implementation pass is forbidden.

## 10. Findings and corrective action

Material failures create/update first-class Findings. Canonical classification includes:

```text
IMPLEMENTATION_DEFECT
TEST_DEFECT
REQUIREMENT_DEFECT
ARCHITECTURE_DEFECT
SECURITY_DEFECT
PLATFORM_DEFECT
CONFIGURATION_DEFECT
ENVIRONMENT_DEFECT
TEST_DATA_DEFECT
DOCUMENTATION_DEFECT
DEPENDENCY_DEFECT
PRODUCT_DECISION_REQUIRED
EXTERNAL_BLOCKER
```

Corrective flow:

```text
FAIL / adverse observation
-> Finding
-> classification + root-cause analysis
-> bounded Rework Order
-> staffing
-> correction
-> targeted verification
-> regression as required
-> rerun every invalidated gate/review/UAT
-> refresh evidence
-> resume only when prerequisites are satisfied
```

Rework is autonomous but policy-bounded. Repeated unresolved same-cause failure beyond the configured bound escalates to deeper diagnosis, HITL or external blocked state. Infinite retries are forbidden.

## 11. HITL

ADR-0018 is normative.

Canonical request:

```text
HITL_REQUEST
  request_id
  request_version
  project/work package/stage
  candidate/context revision
  decision_type
  allowed_responder
  created/expires timestamps
  problem + impact
  recommended solution + alternatives
  evidence refs
```

States:

```text
PENDING
DECIDED
EXPIRED
STALE
CANCELLED
```

Hermes Gateway is the preferred transport boundary; Telegram is a presentation adapter. Exact Telegram interaction primitives must be verified during implementation.

A changed candidate/context makes the relevant pending request stale. Stale/expired/cancelled responses cannot release work. Timeout holds work; it never auto-selects the recommended option.

Valid response creates immutable `HumanDecision` governance evidence tied to request version, responder identity, time and context/candidate identity.

## 12. Workforce / Agent DNA

`agents/catalog-v1.2.yaml` is the authoritative admission and compilation catalog. Directory existence does not imply eligibility.

Base active-candidate professions:

```text
factory-orchestrator
factory-workforce-architect
factory-requirements-engineer
factory-software-architect
factory-security-architect
factory-product-designer
factory-documentation-engineer
factory-tdd-red
factory-software-engineer
factory-platform-engineer
factory-code-reviewer
factory-security-reviewer
factory-fail-closed-inspector
factory-integration-tester
factory-evidence-auditor
factory-runtime-truth-observer
factory-release-manager
```

Superseded:

```text
factory-python-engineer -> factory-software-engineer
factory-exact-sha-auditor -> deterministic factory-exact-sha gate
```

Profiles are staffed on demand; this list is not a permanently running swarm.

Agent DNA source:

```text
agents/<id>/agent.yaml
agents/<id>/SOUL.md
agents/_shared/FACTORY_CONSTITUTION.md
agents/_shared/runtime-policies.yaml
```

Compilation produces Hermes-native Profile Distribution/runtime representation. SOUL is identity/reasoning context, not an enforcement sandbox. Secrets, credentials, memories, sessions and runtime DB/logs are not authored into Agent DNA.

## 13. Factory Skills

Factory Skill content is canonical in `pestoura/hermes-factory`; Hermes supplies the native `SKILL.md` runtime mechanics. HermesJarvasServer is runtime inventory/snapshot/backup, not canonical ownership for Factory-managed Skills.

Canonical runtime identity uses `factory-*` names. Legacy unprefixed Skill drafts are source aliases/design history until explicitly compiled/migrated.

Authorization rule:

```text
effective_skills = agent.required_skills U task.approved_skills
```

Both sides must be registered/admitted. Global installation does not imply Factory authorization, and workers cannot broaden their own Skill set.

Skill lifecycle:

```text
0.1.0 PROPOSED
-> baseline RED observed
-> Skill GREEN
-> variation eval
-> pressure eval
-> independent review
-> 1.0.0 ACTIVE
```

No `not_run` Skill is ACTIVE.

v1.2 new proposed Skills:

```text
factory-designing-user-acceptance-tests
factory-executing-user-acceptance-tests
factory-classifying-findings
factory-performing-root-cause-analysis
factory-planning-bounded-rework
factory-verifying-corrective-actions
```

Exact-SHA is not a Skill.

## 14. Deterministic gates and JDS

JDS remains canonical for generic engineering gate planning. Factory consumes its Effective Gate Plan and adds semantic/acceptance governance without silently overriding mandatory controls.

Exact-SHA gate outputs:

```text
SHA_MATCH
SHA_MISMATCH
EVIDENCE_STALE
EVIDENCE_ABSENT
IDENTITY_UNKNOWN
```

Candidate changes invalidate candidate-bound evidence as appropriate. Merge identity, PR head identity and deployed revision remain distinct truths.

## 15. Scheduling

ADR-0020 is normative.

```text
EVENT-DRIVEN FACTORY WORK
  = Hermes Kanban + Dispatcher

TIME-DRIVEN FACTORY WORK
  = native Hermes Profile/Agent cron only

EXTERNAL GOVERNANCE / CHATGPT SUPERVISION
  = RITMO or another external schedule through the northbound control boundary
```

Factory internal scheduling must not depend on RITMO, host crontab, systemd timers, MCP Bridge or a new Factory-specific scheduler.

Scheduled state is not execution proof. `NOT_RUN != PASS` applies to recurring work as everywhere else.

## 16. Jarvas Operations and runtime truth

Jarvas Operations remains independent assurance/recovery and outside the Factory failure domain. Factory runtime observers are read-only and do not inherit recovery authority.

Repository/CI evidence never silently proves live runtime state. Work requiring live acceptance must collect fresh runtime evidence and bind it to the relevant deployed revision/context.

## 17. Jarvas CLI first product

ADR-0019 is normative.

Product sequence:

```text
Factory minimum runtime/bootstrap
-> Jarvas CLI: first greenfield Factory product
-> HSL: first complex brownfield onboarding
-> unrelated project: portability proof
```

Jarvas CLI boundary:

```text
hermes ...     = Hermes runtime/profile/kanban/skill/tool operations
jarvas-ops ... = independent operations assurance/recovery
jarvas ...     = ecosystem/Factory inventory, reconciliation and control client
```

The Factory must not require the Jarvas CLI to build the first Jarvas CLI. Bootstrap uses native libraries/APIs, stable machine-readable Hermes/JDS interfaces, Git/GitHub, ecosystem inventory and Jarvas Ops evidence adapters.

Initial CLI design priority is read-first/machine-first with stable `--json`, deterministic exit states, dry-run for planning/reconciliation, no generic shell, no secrets output and no Jarvas-level `--yolo`.

## 18. Traceability

Canonical semantic graph:

```text
Project
-> Requirement
-> AcceptanceCriterion / UATScenario
-> ADR / Epic / Change / Issue
-> WorkPackage
-> Hermes KanbanTask / Execution
-> Branch / PR / candidate SHA / CI
-> review/security evidence
-> merge/deployment/runtime evidence
-> UATExecution / UATEvidence
-> Finding / ReworkOrder when required
-> HumanDecision when required
-> AcceptanceDecision
```

The registry links rather than replaces canonical owners. Evidence retains provenance, identity and freshness.

## 19. Acceptance

Acceptance is derived from the current required evidence set, never from narrative completion.

Conceptually:

```text
approved intent
+ JDS required engineering gates
+ Factory-required semantic/independent review gates
+ exact candidate identity
+ UAT where required
+ runtime evidence where required
+ resolved Findings / valid HumanDecisions where required
= ACCEPTED
```

Possible acceptance classes may distinguish repository-only acceptance from live/runtime acceptance. Missing or stale required evidence blocks acceptance.

## 20. UI and external governance

Factory UI is a Hermes Dashboard plugin/overlay showing semantic fields such as Project, Epic, WP, Requirement, Profile/DNA version, Skill versions, PR/SHA, JDS gates, Findings/Rework, UAT, HITL, evidence and acceptance.

ChatGPT remains an independent external Governor through the northbound Factory Control contract over Hermes MCP Bridge. The Factory continues to operate without an active ChatGPT conversation.

## 21. Implementation boundary

This v1.2 specification is design only. It does not install Profiles, promote Skills, create native cron schedules, expose new MCP tools, mutate HSL, deploy services or implement Jarvas CLI.

After clean branch audit and owner approval, the next lifecycle is:

```text
design/spec APPROVED
-> detailed runtime implementation plan
-> TDD RED
-> minimal GREEN
-> hardening
-> CI/exact-SHA
-> merge
-> post-merge/runtime verification
```

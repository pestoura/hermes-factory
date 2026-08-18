# Hermes Software Factory — Canonical Design v1.1

**Status:** PROPOSED FOR OWNER REVIEW  
**Date:** 2026-08-18  
**Supersedes:** `2026-08-18-hermes-software-factory-design.md` where conflicting  
**Incorporates:** Architecture Review v1.1, ADR-0014, ADR-0015  
**Implementation authority:** NOT GRANTED

## 1. Product definition

Hermes Software Factory (HSF) is the engineering-organization layer of Hermes/Jarvas. It converts canonical project intent into traceable, staffed, governed and evidence-backed engineering work while reusing the execution primitives already present in the ecosystem.

HSF is not a second agent runtime, task queue, CI platform, operations controller, secrets manager or generic workflow engine.

## 2. Principles

### P1 — Native-first

Use supported Hermes/Jarvas native interfaces before creating new infrastructure.

### P2 — Source authority is explicit

Project intent, SCM, work state, CI and runtime truth remain owned by their canonical systems.

### P3 — Evidence outranks narrative

`NOT_RUN != PASS`; repository proof does not imply runtime proof; agent claims do not create acceptance.

### P4 — Work is semantically traceable

Project -> Requirement/ADR -> Epic -> Work Package -> Kanban Task -> Execution -> Branch/PR -> SHA -> CI -> Deployment -> Runtime Evidence -> Acceptance.

### P5 — Workforces are reusable, project context is local

Factory Agent DNA and professional Skills are global Factory assets. Project-specific intent and conventions remain in client repositories.

### P6 — Quality is composed, not duplicated

JDS-001 owns generic engineering capability/gate planning. The Factory consumes its Effective Gate Plan and adds only Factory-specific semantic/acceptance gates.

### P7 — External control is northbound

ChatGPT/external governors enter Jarvas through the Hermes MCP Bridge and an external Factory control contract. Internal Factory work does not loop back through MCP when a native local interface exists.

### P8 — Deterministic checks stay deterministic

Exact-SHA comparison, schema validation, digests, idempotency keys and other mechanically decidable controls are implemented as software gates/validators rather than LLM professions.

### P9 — Independent assurance remains independent

Implementers do not self-certify; Jarvas Operations remains outside the Factory implementation failure domain.

### P10 — Workforce evolution is governed

New Profiles require the Agent Admission Gate. New Skills require Factory Skill admission and behavioural evaluation.

### P11 — High-assurance dispatch is fail-closed

Factory-managed high-assurance boards start with manual decomposition and structured dispatch approval.

### P12 — The Factory must survive ChatGPT absence

Internal execution, scheduling and recovery remain operational without an active ChatGPT conversation.

## 3. System boundaries

```text
ChatGPT / external governor
        |
        v
Hermes MCP Bridge
        |
        v
External Factory Control Contract
======== JARVAS TRUST BOUNDARY ========
        |
        v
Hermes Software Factory
        |
        +-- Hermes CLI / supported APIs
        +-- Hermes Kanban / Dispatcher
        +-- Hermes Profiles / Skills / Worktrees
        +-- Jarvas Engineering Platform / JDS
        +-- Git / GitHub
        +-- Jarvas Operations evidence
        +-- RITMO scheduling
        +-- Ecosystem capability inventory
```

The Bridge is not an internal Factory dependency.

## 4. Canonical project contract

Each Factory-managed project provides:

```text
.factory/
├── project.yaml
└── acceptance.yaml

.jarvas/
└── engineering.yml
```

### `.factory/project.yaml`

Owns:

- project identity;
- repositories and roles;
- canonical source locations;
- Hermes board identity;
- Factory workflow;
- autonomy profile;
- environment references;
- reconciliation hints.

### `.factory/acceptance.yaml`

Owns:

- acceptance classes;
- Factory-specific HITL requirements;
- runtime-required classifications;
- evidence freshness rules not already owned by JDS;
- prohibited acceptance shortcuts.

### `.jarvas/engineering.yml`

Owned by JDS-001. It defines engineering capabilities, risk/criticality and generic quality/security gate selection.

A future Factory-specific quality overlay may exist only for semantics JDS cannot represent and may never silently weaken mandatory JDS controls.

## 5. Project Compiler

Inputs:

- Factory project/acceptance contract;
- JDS Effective Gate Plan;
- canonical project requirements/architecture/ADRs/Epics;
- GitHub state;
- current Hermes board state;
- ecosystem capability inventory;
- Factory workforce and Skill registries.

Outputs:

- normalized Project Model;
- semantic entity graph;
- Work Packages;
- dependency graph;
- staffing requirements;
- selected Factory-specific gates;
- idempotent Kanban reconciliation plan;
- capability-gap findings;
- blocker/HITL findings.

Compilation must be deterministic for frozen inputs where possible and idempotent across repeated runs.

## 6. Work Package

A Work Package is the Factory's bounded governed delivery unit between product semantics and operational Kanban execution.

It carries:

- objective;
- canonical source references;
- scope;
- acceptance criteria;
- JDS gate plan reference;
- Factory-specific gates;
- staffing requirements;
- approved Skills;
- dependencies;
- traceability bindings;
- candidate/evidence state;
- current Factory state.

Kanban Task remains the execution object; Work Package remains the semantic delivery object.

## 7. Hermes Kanban contract

Hermes Kanban is the sole Factory operational queue.

HSF does not implement another queue, dispatcher or workspace manager.

### Initial high-assurance baseline

```yaml
kanban:
  auto_decompose: false
  dispatch_approval_mode: structured
```

Factory Compiler/Orchestrator performs explicit decomposition/reconciliation. Structured approval is required before protected state advancement/dispatch on Factory high-assurance boards.

Relaxation requires explicit evidence-backed design approval.

## 8. Workforce v1.1

Canonical base active-candidate Profiles:

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

### Superseded v1 entries

```text
factory-python-engineer   -> factory-software-engineer
factory-exact-sha-auditor -> deterministic Exact-SHA Gate
```

The catalog is a reusable company roster, not a list of permanently running processes.

## 9. Software Engineer

`factory-software-engineer` is the generic implementation profession.

Language/framework specialization is selected through approved Skills and task context. A dedicated language-specific Profile is admitted only when repeated evidence shows that specialization needs distinct persistent identity, tools, memory, authority or eval behavior.

## 10. Platform Engineer

`factory-platform-engineer` owns bounded engineering changes to:

- CI/CD configuration;
- containers and compose;
- infrastructure as code;
- Kubernetes/deployment manifests;
- service-management configuration;
- runtime packaging/configuration;
- observability instrumentation.

It does not own independent runtime assurance/recovery, which remains with Jarvas Operations.

## 11. Agent DNA

Each persistent role is defined by versioned Factory Agent DNA:

```text
identity
routing
responsibilities
non-responsibilities
authority
independence
model class
memory class
tool policy
approved Skills
output contract
escalation
evals
```

Agent DNA compiles into Hermes-native Profile Distribution assets. Soul is behavioral identity, not a security boundary.

## 12. Factory Skill system

Per ADR-0015, the Factory adopts Hermes' native Skill mechanism but owns its professional content.

Canonical source:

```text
pestoura/hermes-factory/skills
```

Runtime Profile copies are projections. `HermesJarvasServer` may inventory/snapshot them but is not the authoring source for Factory-managed Skills.

### Effective Skills

```text
effective_skills =
    agent.required_skills
    union task.approved_skills
```

Both sets must resolve through the Factory Skill Registry. Server-wide availability alone does not confer Factory authorization.

### Skill lifecycle

```text
PROPOSED 0.1.x
-> baseline RED
-> Skill GREEN
-> variation/pressure evals
-> independent review
-> ACTIVE 1.0.0+
```

Factory Skills may contain `SKILL.md`, references, templates, scripts, assets and deterministic helpers using the native Hermes format.

## 13. JDS adapter

The Factory calls/consumes JDS-001 as the canonical generic engineering gate planner.

HSF must not duplicate JDS capability detection, criticality policy, mandatory control logic or reusable CI gate planning.

Factory responsibilities begin after receiving the Effective Gate Plan:

- map gates to Work Packages/Kanban work;
- add semantic assurance tasks where LLM judgment is required;
- track evidence and gate freshness;
- derive Factory acceptance.

## 14. Deterministic Exact-SHA Gate

Exact-SHA identity reconciliation is a software validator.

Inputs may include:

```text
candidate SHA
reviewed SHA
CI SHA
tested SHA
merge SHA
deployed artifact/revision SHA
```

Outputs are closed-state results such as:

```text
SHA_MATCH
SHA_MISMATCH
EVIDENCE_STALE
EVIDENCE_ABSENT
IDENTITY_UNKNOWN
```

Evidence Auditor/Release Manager consume these results but do not replace the deterministic comparison.

## 15. GitHub/SCM model

GitHub is canonical for issues, branches, PRs, commits, reviews and CI/check state.

Factory retains semantic links and selected status/provenance, not a complete shadow copy.

Candidate SHA changes invalidate or require explicit re-evaluation of SHA-bound evidence.

## 16. Runtime and Jarvas Operations

Fresh runtime observations are required for live claims.

Factory Runtime Truth Observer is read-only/observe-oriented by default.

Jarvas Operations remains independently authoritative for its bounded assurance/recovery capabilities. Factory observation does not automatically grant recovery authority.

## 17. RITMO role

RITMO handles recurring or scheduled initiation of Factory procedures, not Factory operational task state.

Recommended scheduled uses:

- project reconciliation;
- Skill/Agent eval campaigns;
- dependency/upstream checks;
- periodic evidence freshness checks;
- portfolio summaries;
- scheduled assurance campaigns.

## 18. Ecosystem capability adapter

Project Compiler consults Hermes ecosystem inventory before proposing new infrastructure or dependencies.

Capability status is classified explicitly; unknown/planned/blocked capability is not treated as available.

## 19. Factory Dashboard

v1 UI is implemented as an extension/plugin to the Hermes Dashboard rather than a standalone web application.

It may add:

- Epic/WP overlays;
- JDS gate state;
- PR/SHA/evidence links;
- Agent DNA/Skill versions;
- acceptance/rework state;
- project portfolio view.

Native Kanban remains the execution board.

## 20. External Factory Control

ChatGPT and external governors use a stable versioned Factory control contract exposed through the northbound Hermes MCP Bridge boundary.

The external contract should support capability families such as:

```text
project: status / compile / reconcile / pause / resume
work: list / inspect / reopen
workforce: catalog / eval status / capacity
skills: registry / eval status
quality: gate status / acceptance readiness
traceability: explain / provenance
scm: PR / SHA / CI reconciliation
runtime: evidence status / freshness
portfolio: overview / blockers
```

This is a governance/control surface, not an internal execution bus.

## 21. Jarvas CLI control-plane client

A future top-level `jarvas` CLI is strongly recommended as the local human/operator client for ecosystem and Factory control.

It must compose existing authorities rather than wrap every Hermes command.

### Boundary

```text
hermes ...      -> native Hermes runtime, profiles, skills, Kanban, tools, gateway
jarvas-ops ...  -> independent host/service assurance and bounded recovery
jarvas ...      -> ecosystem/factory inventory, reconciliation and control
```

### Candidate command families

```text
jarvas status
jarvas doctor
jarvas ecosystem inventory|diff|capability
jarvas service list|status|logs|evidence
jarvas project list|show|onboard|compile|reconcile
jarvas factory status|pause|resume|portfolio
jarvas work list|show|trace|reopen
jarvas agent list|show|evals|promote
jarvas skill list|show|evals|promote|provenance
jarvas gate status|explain|exact-sha
jarvas evidence list|show|verify|freshness
jarvas repo status|drift|upstream-reconcile
jarvas release status|candidate|evidence
```

Mutation commands must preserve explicit confirmation/HITL and underlying owner policy. The CLI must not become a generic arbitrary shell runner.

## 22. Hermes upstream reconciliation

Factory operation depends on a hardened `pestoura/hermes-agent` fork. Upstream upgrades are therefore governed changes.

Required promotion path:

```text
upstream release detected
-> reconciliation candidate
-> upstream/fork diff classification
-> merge/rebase/cherry-pick
-> upstream tests
-> fork hardening tests
-> dispatch-approval parity tests
-> containment tests
-> exact-SHA gate
-> staging/runtime smoke
-> accepted platform baseline
```

No moving upstream branch is a production dependency.

## 23. Acceptance model

Suggested acceptance classes remain explicit:

```text
ACCEPTED_SPEC
ACCEPTED_REPO
ACCEPTED_INTEGRATION
ACCEPTED_LIVE
ACCEPTED_RELEASE
ACCEPTED_CAMPAIGN
```

Acceptance derives from required gate evidence and source authority, never from a generic `done` state.

## 24. HSL pilot

Hermes Security Labs remains the first client but not the Factory architecture.

Initial onboarding is read-only compilation/reconciliation. Controlled dispatch starts only after the compiled graph, staffing and gate mapping are accepted.

A second unrelated project is required to prove portability.

## 25. v1 implementation component budget

Only the following Factory-specific components are justified initially:

```text
Project Compiler
Traceability Registry
Staffing Engine
Agent DNA Compiler/Registry
Factory Skill Registry/Eval Harness
JDS Adapter
Hermes Kanban Adapter
Git/GitHub Adapter
Jarvas Operations Evidence Adapter
Ecosystem Capability Adapter
Factory Governance/Acceptance
Hermes Dashboard Plugin
External Factory Control contract
```

Everything else should reuse the existing ecosystem.

## 26. Non-goals

v1 will not create:

- a second Kanban/dispatcher;
- a second generic CI/quality platform;
- a duplicate DAG/runbook engine;
- an internal MCP dependency for local work;
- a generic recovery controller;
- a standalone Factory web application;
- unrestricted tool/Skill discovery for Factory agents;
- automatic creation of new agent professions without admission;
- automatic weakening of governance based on LLM judgment.

## 27. Design acceptance gate

Before implementation planning:

1. owner reviews this v1.1 specification;
2. unresolved architectural decisions are recorded explicitly;
3. v1.1 workforce/source registries are reconciled with this spec;
4. implementation plan is produced with the normal design/spec -> plan -> TDD RED -> GREEN -> hardening -> CI/exact-SHA -> merge -> post-merge verification method.

No runtime/profile installation is authorized by this document alone.

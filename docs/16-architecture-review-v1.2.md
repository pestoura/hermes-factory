# Hermes Software Factory — Architecture Review v1.2

**Status:** PROPOSED_FOR_OWNER_APPROVAL  
**Date:** 2026-08-18  
**Decision owner:** Pedro Estoura  
**Scope:** full design/source-of-truth reconciliation before implementation planning  
**Implementation authority:** NOT GRANTED

## Purpose

v1.2 reconciles the complete Factory design conversation with the repository after v1.1. It preserves the accepted v1.1 boundaries and closes gaps around continuous handoff, UAT, corrective action, HITL, Skills, Profile admission, scheduling and the first Factory product.

Where v1/v1.1 material conflicts with this review, the v1.2 canonical specification and ADR-0014 through ADR-0020 take precedence.

## Retained v1.1 decisions

The following remain unchanged:

1. JDS-001 is the canonical generic engineering gate planner.
2. Hermes MCP Bridge is northbound external control only.
3. Factory owns professional Skill content on the Hermes native Skill model.
4. Exact-SHA is a deterministic validator, not an LLM profession.
5. `factory-software-engineer` is the generic implementation profession; language specialization is Skill-first.
6. `factory-platform-engineer` is a distinct profession.
7. Hermes Kanban/Dispatcher remain the only Factory operational execution queue/runtime.
8. Hardened Hermes fork updates require controlled upstream reconciliation.
9. Jarvas Operations remains outside the Factory failure/recovery domain.
10. Factory UI should extend Hermes Dashboard rather than create another standalone v1 application.
11. Hermes ecosystem inventory is a Project Compiler input.

## v1.2 reconciliation decisions

### AR12-01 — Agent catalog is authoritative

`agents/catalog-v1.2.yaml` is the admission/compilation source. Directory presence does not make a Profile eligible. Superseded `factory-python-engineer` and `factory-exact-sha-auditor` directories are design history only and cannot be resurrected by filesystem discovery.

### AR12-02 — Skills use canonical `factory-*` identities

The Factory Skill Registry owns canonical `factory-*` IDs. Existing unprefixed Skill drafts are source aliases/design history until compiled/migrated. Server-wide installed Skills do not become Factory-authorized automatically.

Effective runtime authorization is:

```text
effective_skills = admitted agent.required_skills U admitted task.approved_skills
```

Both sets must exist in the Factory Skill Registry. No proposed/not-run Skill is ACTIVE.

### AR12-03 — Continuous handoff is autonomous and atomic

Formalized by ADR-0016.

Ordinary stage progression uses structured machine/policy authorization, not human approval. Handoff becomes valid only after outcome, artifacts, evidence, candidate identity where applicable, Finding state and next prerequisites are committed. Material context change makes a pending handoff stale.

### AR12-04 — UAT and corrective action are first-class

Formalized by ADR-0017.

First-class entities include `AcceptanceCriterion`, `UATScenario`, `UATExecution`, `UATEvidence`, `Finding`, `ReworkOrder` and `AcceptanceDecision`.

Approved UAT/acceptance baselines are immutable to implementers. If the acceptance definition is wrong, the path is Finding -> authorized rebaseline -> new baseline version, never test editing merely to obtain PASS.

Autonomous rework is bounded. Persistent same-cause failure escalates; infinite retry is forbidden.

### AR12-05 — HITL is asynchronous, revision-bound evidence

Formalized by ADR-0018.

The Factory emits transport-independent `HITL_REQUEST` objects through the Hermes Gateway integration. Telegram is a presentation adapter; exact Telegram selector primitives remain an implementation-verification item.

Human responses are valid only for the matching request/context/candidate version. Stale/expired/cancelled responses cannot unlock work. Valid responses become immutable `HumanDecision` governance evidence.

### AR12-06 — Jarvas CLI is the first greenfield Factory product

Formalized by ADR-0019.

Bootstrap order:

```text
Factory minimum runtime
-> Jarvas CLI greenfield delivery
-> HSL complex brownfield onboarding
-> unrelated portability project
```

The Factory must not depend on Jarvas CLI to build the first Jarvas CLI release.

### AR12-07 — Factory time-driven work uses native Hermes cron only

Formalized by ADR-0020 and superseding v1.1 AR-10.

```text
EVENT-DRIVEN FACTORY WORK -> Hermes Kanban + Dispatcher
TIME-DRIVEN FACTORY WORK  -> Hermes native Profile/Agent cron
EXTERNAL GOVERNANCE       -> RITMO/external schedule via northbound control
```

RITMO is no longer an internal Factory worker scheduler. Host cron/systemd timers and a Factory-specific scheduler are also excluded from the Factory scheduling contract.

### AR12-08 — Internal worker policies do not depend on MCP

`agents/_shared/runtime-policies.yaml` now models native/local Factory, Hermes, SCM and runtime surfaces. Internal worker tool policies declare `mcp: []`. The MCP Bridge remains available only at the external control boundary.

### AR12-09 — Exact-SHA is not a Skill

The old `verifying-exact-sha` Skill concept is superseded by deterministic gate `factory-exact-sha`. Reviewers/auditors/release management may consume the gate result; they do not produce an LLM equality verdict.

### AR12-10 — JDS owns generic engineering quality

Current project contract remains:

```text
.factory/project.yaml
.factory/acceptance.yaml
.jarvas/engineering.yml
```

`.factory/quality.yaml` is historical/superseded for generic gate selection. Any future Factory-specific quality overlay must not duplicate or weaken JDS mandatory controls.

## v1.2 workforce

The active-candidate catalog remains 17 Profiles:

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

This catalog is not a running fleet. Runtime installation still requires implementation, evaluation/admission and explicit authority.

## v1.2 Skill additions

The following new Factory-owned Skill drafts exist at `0.1.0 / proposed / not_run`:

```text
factory-designing-user-acceptance-tests
factory-executing-user-acceptance-tests
factory-classifying-findings
factory-performing-root-cause-analysis
factory-planning-bounded-rework
factory-verifying-corrective-actions
```

They MUST NOT be called ACTIVE until RED/GREEN, variation/pressure evals and independent review succeed.

## v1.2 traceability expansion

Canonical chain now includes:

```text
Project
-> Requirement
-> AcceptanceCriterion
-> UATScenario
-> Epic / WorkPackage
-> KanbanTask / Execution
-> Branch / PR / candidate SHA / CI
-> Review evidence
-> Deployment / RuntimeEvidence where required
-> UATExecution / UATEvidence
-> Finding / ReworkOrder when needed
-> HumanDecision when HITL occurs
-> AcceptanceDecision
```

Every evidence item is bound to its relevant candidate/context/version and may become stale after change.

## v1.2 execution model

```text
approved canonical intent
-> Project Compiler
-> semantic Work Packages
-> Hermes Kanban READY
-> admitted Profile + admitted Skills
-> stage execution
-> atomic handoff
-> next stage automatically when policy permits
-> finding/rework when a gate fails
-> true HITL only at explicit authority boundaries
-> UAT + independent/evidence gates
-> exact-SHA/runtime truth where applicable
-> evidence-derived acceptance
```

## Current review gate

The design has been reconciled but remains **PROPOSED_FOR_OWNER_APPROVAL** until the clean branch audit demonstrates that current machine-readable and human-readable sources agree.

A clean audit must verify at minimum:

- no current source treats RITMO as internal Factory scheduler;
- no current worker policy requires internal MCP Bridge transport;
- no current admission source makes superseded Profiles eligible;
- no current recommended project contract requires `.factory/quality.yaml`;
- UAT/rework/handoff/HITL invariants exist in both spec and policy;
- Jarvas CLI first-product sequencing is consistent;
- all runtime/product implementation remains NOT AUTHORIZED.

If these checks pass, v1.2 is suitable for owner approval. Only after owner approval should a separate Factory runtime implementation plan be written and execution begin through the agreed design/spec -> plan -> TDD lifecycle.

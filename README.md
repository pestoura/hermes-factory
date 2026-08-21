# Hermes Software Factory

> A reusable autonomous engineering organization built natively on Hermes/Jarvas.

**Architecture:** **v1.2 — APPROVED**  
**Approved audited design:** `281b8c7509252d0416621f9971e14bd4151b997a`  
**Implementation authority:** **GRANTED — FULL ARCHITECTURE**  
**Runtime activation:** **GATED — no unexecuted Profile/Skill/gate is ACTIVE or PASS by declaration**

Owner approval is recorded in:

- `docs/17-owner-approval-v1.2.md`
- `approvals/architecture-v1.2.yaml`

## Vision

Hermes Software Factory (HSF) is a persistent engineering company inside Hermes/Jarvas. Approved project intent is compiled into semantic Work Packages, an isolated Hermes Kanban board, admitted Profiles/Skills, JDS-backed gates, UAT/corrective-action flow, traceability and evidence-derived acceptance.

HSF does not duplicate the Hermes/Jarvas execution substrate. It owns the semantic/organizational layer that turns intent into governed engineering work.

## Architecture in one view

```text
Project repository          = product intent + implementation
.factory/project.yaml       = Factory identity/sources/workflow/autonomy
.factory/acceptance.yaml    = acceptance/UAT/HITL/runtime semantics
.jarvas/engineering.yml     = JDS generic engineering/quality gates
Hermes Kanban + Dispatcher  = event-driven operational execution
Hermes Profiles             = reusable employees
Hermes native Profile cron  = Factory-internal time-driven work
Factory Skill Registry      = admitted professional methods/competences
GitHub / CI                 = SCM and executed engineering evidence
Runtime evidence            = live truth
Jarvas Operations           = independent assurance/recovery
RITMO                       = external governance/supervision scheduling only
Hermes MCP Bridge           = northbound ChatGPT/external-client boundary
Factory                     = compilation + staffing + traceability + governance + acceptance
ChatGPT                     = independent external Governor
Pedro                       = owner / strategic HITL
```

## Canonical v1.2 decisions

- **MCP Bridge is northbound only.** Internal Factory workers use native/local Hermes/Jarvas interfaces.
- **JDS-001 owns generic engineering gate planning.** `.factory/quality.yaml` is superseded for that purpose.
- **Exact-SHA is deterministic.** It is a gate, not an LLM Profile or Skill.
- **17 Profile catalog.** `factory-software-engineer` replaces the Python-specific base role; `factory-platform-engineer` is included; filesystem directory presence never implies Profile admission.
- **Factory-owned Skills.** Canonical runtime IDs use `factory-*`; installation does not imply authorization; proposed/not-run Skills are not ACTIVE.
- **Continuous execution.** Ordinary stage transitions use structured machine/policy authorization; `structured approval` does not mean human approval.
- **Atomic handoff.** Outcome, artifacts, evidence/freshness, candidate identity where applicable, Finding/review state and next prerequisites commit before the next stage becomes READY.
- **First-class UAT.** Approved UAT/acceptance baselines cannot be edited by implementers merely to obtain PASS.
- **Corrective action is bounded.** Findings are classified, rework is evidence-driven and infinite retry is forbidden.
- **HITL is asynchronous and revision-bound.** Valid human decisions become governance evidence; stale/replayed/expired decisions cannot unlock work.
- **Native scheduling only.** Event work uses Kanban/Dispatcher; Factory time-driven work uses Hermes native Profile/Agent cron. RITMO is external governance scheduling, not an internal worker scheduler.
- **Jarvas CLI is the first greenfield Factory product.** HSL follows as the first complex brownfield onboarding; a materially unrelated project then proves portability.

## Canonical reading order

1. `docs/16-architecture-review-v1.2.md` — clean audited architecture review
2. `docs/superpowers/specs/2026-08-18-hermes-software-factory-design-v1.2.md` — audited canonical design
3. `docs/17-owner-approval-v1.2.md` — owner approval event
4. `approvals/architecture-v1.2.yaml` — machine-readable implementation authority
5. ADR-0014 through ADR-0020
6. `docs/04-project-contract-traceability.md`
7. `docs/06-pilot-and-roadmap.md`
8. `docs/07-proposed-architecture-decisions.md`
9. `docs/15-jarvas-cli-control-plane-proposal.md`

The audited v1.2 design remains immutable evidence. The owner approval is a later governance event that grants full implementation authority without retrospectively rewriting that audit evidence.

## Executable design sources

```text
agents/
├── catalog-v1.2.yaml
└── _shared/runtime-policies.yaml

skills/
├── registry.yaml
└── registry-policy-v1.2.yaml

gates/
└── exact-sha/gate.yaml

policies/
├── kanban-high-assurance-v1.2.yaml
├── continuous-handoff-v1.2.yaml
├── uat-corrective-action-v1.2.yaml
├── hitl-v1.2.yaml
├── native-scheduling-v1.2.yaml
└── hermes-upstream-reconciliation-v1.2.yaml
```

These are approved implementation inputs. They are not themselves proof that runtime installation, tests or evals have executed.

## Workforce

The authoritative active-candidate catalog contains 17 reusable professions:

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

`factory-python-engineer` and `factory-exact-sha-auditor` are superseded historical definitions and are not eligible through v1.2 admission.

## Skills

Factory owns professional Skill content and admission. Hermes provides the native Skill mechanism. Runtime/global installation is not authorization.

```text
effective_skills = agent.required_skills ∪ task.approved_skills
```

Both sets must be registered/admitted. Skill promotion remains:

```text
0.1.0 PROPOSED
-> baseline RED
-> Skill GREEN
-> variation/pressure evals
-> independent review
-> 1.0.0 ACTIVE
```

## Continuous lifecycle

```text
approved canonical intent
-> Project Compiler
-> Work Packages / dependencies / staffing
-> Hermes Kanban READY
-> admitted Profile + Skills
-> stage execution
-> atomic handoff
-> automatic next stage when policy permits
-> Finding / bounded rework on failure
-> true HITL only at explicit authority boundaries
-> JDS / review / Exact-SHA / UAT / runtime evidence as required
-> evidence-derived AcceptanceDecision
```

## Implementation and product sequence

```text
1. Architecture v1.2 APPROVED
2. Write the full Factory runtime implementation plan
3. Implement the COMPLETE approved Factory through TDD/CI/Exact-SHA
4. Evaluate/admit/project all 17 Profiles and all required Factory Skills
5. Install and verify the complete Factory in Hermes/Jarvas
6. Accept the Factory from runtime evidence
7. Deliver Jarvas CLI to the accepted Factory as its first greenfield product
8. Onboard Hermes Security Labs as the first complex brownfield client
9. Onboard an unrelated project to prove portability
```

There is no architectural authorization to substitute a reduced/minimum Factory runtime for the full v1.2 scope.

The Factory must not depend on Jarvas CLI to build the first Jarvas CLI release.

## Current gate

```text
design/spec APPROVED
-> full runtime implementation plan          [NEXT]
-> TDD RED
-> implementation + hardening
-> tests / Skill evals / Profile evals
-> CI / Exact-SHA
-> merge
-> controlled Hermes/Jarvas installation
-> post-install/runtime verification
-> Factory acceptance
-> Jarvas CLI first project
```

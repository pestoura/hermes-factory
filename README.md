# Hermes Software Factory

> A reusable autonomous engineering organization built natively on Hermes/Jarvas.

**Current design:** Architecture **v1.2 — PROPOSED FOR OWNER APPROVAL**  
**No product/runtime implementation is authorized by this branch.**

## Vision

Hermes Software Factory (HSF) is a persistent engineering company inside Hermes/Jarvas. Approved project intent is compiled into semantic Work Packages, an isolated Hermes Kanban board, admitted Profiles/Skills, JDS-backed gates, UAT/corrective-action flow, traceability and evidence-derived acceptance.

HSF does not duplicate the Hermes/Jarvas execution substrate. It owns the semantic/organizational layer that turns intent into governed engineering work.

## v1.2 architecture in one view

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

## Canonical v1.2 corrections

- **MCP Bridge is northbound only.** Internal Factory workers use supported native/local Hermes/Jarvas interfaces.
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
- **Jarvas CLI is the first greenfield Factory product.** HSL follows as first complex brownfield onboarding, then an unrelated project proves portability.

## Canonical reading order

1. [Architecture Review v1.2](docs/16-architecture-review-v1.2.md)
2. [Canonical Design v1.2](docs/superpowers/specs/2026-08-18-hermes-software-factory-design-v1.2.md)
3. [ADR-0014 — Internal Native Execution Boundary](docs/adr/ADR-0014-internal-native-execution-boundary.md)
4. [ADR-0015 — Factory-Owned Skills on Hermes Native Skill Model](docs/adr/ADR-0015-factory-owned-skills-on-hermes-native-model.md)
5. [ADR-0016 — Autonomous Continuous Stage Handoff](docs/adr/ADR-0016-autonomous-continuous-stage-handoff.md)
6. [ADR-0017 — First-Class UAT and Corrective Action Loop](docs/adr/ADR-0017-first-class-uat-and-corrective-action-loop.md)
7. [ADR-0018 — Asynchronous HITL through Hermes Gateway](docs/adr/ADR-0018-asynchronous-hitl-through-hermes-gateway.md)
8. [ADR-0019 — Jarvas CLI as First Factory Product](docs/adr/ADR-0019-jarvas-cli-first-factory-product.md)
9. [ADR-0020 — Native Hermes Scheduling Only](docs/adr/ADR-0020-native-hermes-scheduling-only.md)
10. [Project Contract & Traceability](docs/04-project-contract-traceability.md)
11. [Product Sequence & Roadmap](docs/06-pilot-and-roadmap.md)
12. [Foundational Decisions](docs/07-proposed-architecture-decisions.md)
13. [Jarvas CLI Product Direction](docs/15-jarvas-cli-control-plane-proposal.md)

Historical v1/v1.1 documents remain useful design history. **v1.2 wins on conflict.** A historical file does not become current machine authority merely because it remains in the repository.

## v1.2 executable design sources

```text
agents/
├── catalog-v1.2.yaml                 # authoritative admission/compilation catalog
└── _shared/runtime-policies.yaml     # native/local worker authority model

skills/
├── registry.yaml                     # canonical Factory Skill registry
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

These files remain **design candidates**, not installed runtime Profiles/policies/schedules.

## v1.2 workforce

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

Both sets must be registered/admitted. New Skill lifecycle remains:

```text
0.1.0 PROPOSED
-> baseline RED
-> Skill GREEN
-> variation/pressure evals
-> independent review
-> 1.0.0 ACTIVE
```

New v1.2 drafts for UAT/Finding/Rework are all `proposed / not_run`.

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

## Product sequence

```text
1. Approve Architecture v1.2
2. Write separate Factory runtime implementation plan
3. Build minimum Factory runtime through TDD/CI/exact-SHA
4. Deliver Jarvas CLI as first greenfield Factory product
5. Onboard Hermes Security Labs as first complex brownfield client
6. Onboard an unrelated project to prove portability
```

The Factory must not depend on the Jarvas CLI to build the first Jarvas CLI release.

## Current gate

The repository is currently in **design reconciliation/audit**, not implementation.

Only after a clean branch audit and explicit owner approval of v1.2 should work move to:

```text
design/spec APPROVED
-> runtime implementation plan
-> TDD RED
-> minimal GREEN
-> hardening
-> CI/exact-SHA
-> merge
-> post-merge/runtime verification
```

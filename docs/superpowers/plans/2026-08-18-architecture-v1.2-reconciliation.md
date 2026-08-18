# Hermes Software Factory Architecture v1.2 Reconciliation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use the repository verification workflow before claiming the reconciliation complete. This plan is design/source-of-truth reconciliation only; it does not authorize Factory runtime implementation.

**Goal:** Reconcile all owner-approved architecture decisions through 2026-08-18 into a single coherent v1.2 repository truth and then run a clean branch audit before owner approval.

**Architecture:** Preserve v1/v1.1 documents as design history where useful, but make v1.2 the unambiguous precedence layer. Machine-readable design sources must agree with the canonical v1.2 specification and ADRs. No runtime Profiles, cron jobs, MCP tools, Jarvas services, or Factory product code are activated by this work.

**Tech Stack:** Markdown, YAML design sources, GitHub branch `design/software-factory-architecture-v1`.

**Spec:** `docs/superpowers/specs/2026-08-18-hermes-software-factory-design-v1.2.md` (created by this reconciliation).

## Global Constraints

- `Implementation authority: NOT GRANTED` until owner approval and a separate runtime implementation plan.
- Hermes MCP Bridge is northbound external control only; internal Factory execution uses native/local Hermes/Jarvas interfaces.
- Hermes Kanban remains the only Factory execution queue.
- JDS-001 remains the canonical generic engineering gate planner.
- Exact-SHA remains a deterministic validator, not an LLM profession.
- Factory owns professional Skill content; Hermes provides the native Skill runtime/model.
- Server-wide installed Skills are not automatically Factory-authorized.
- Normal stage transitions use structured machine/policy authorization; structured approval does not imply human approval.
- Event-driven work uses Hermes Kanban/Dispatcher; time-driven Factory work uses native Hermes Profile/Agent cron only.
- RITMO is external governance/supervision scheduling and is not a Factory internal scheduler.
- Rework is autonomous but bounded; repeated unresolved cause/class forces escalation.
- UAT/Acceptance baselines are immutable to implementers; rebaseline requires explicit authorized finding/decision flow.
- Handoffs are semantically atomic: outcome, artifacts, evidence, candidate identity, finding state, and next-stage prerequisites commit before promotion.
- HITL decisions are revision-bound governance evidence; stale/replayed decisions never unlock work.
- Jarvas CLI is the first greenfield Factory product; Hermes Security Labs follows as the first complex brownfield onboarding.
- The Factory must not depend on the Jarvas CLI to build the Jarvas CLI.

---

### Task 1: Formalize v1.2 decisions as ADRs

**Files:**
- Create `docs/adr/ADR-0016-autonomous-continuous-stage-handoff.md`
- Create `docs/adr/ADR-0017-first-class-uat-and-corrective-action-loop.md`
- Create `docs/adr/ADR-0018-asynchronous-hitl-through-hermes-gateway.md`
- Create `docs/adr/ADR-0019-jarvas-cli-first-factory-product.md`
- Create `docs/adr/ADR-0020-native-hermes-scheduling-only.md`

- [ ] Record continuous stage handoff, machine approval semantics, atomic handoff and bounded rework.
- [ ] Record first-class UAT entities/states, acceptance immutability, finding classification and corrective action flow.
- [ ] Record asynchronous HITL request/decision lifecycle, stale/replay protection and evidence provenance.
- [ ] Record Jarvas CLI as first greenfield Factory product and anti-bootstrap-dependency constraint.
- [ ] Record native Hermes cron as the sole Factory time scheduler and reposition RITMO outside Factory internal scheduling.

### Task 2: Create v1.2 executable design policies and catalog

**Files:**
- Create `agents/catalog-v1.2.yaml`
- Update `agents/_shared/runtime-policies.yaml`
- Update `skills/registry.yaml`
- Create `skills/registry-policy-v1.2.yaml`
- Create `policies/kanban-high-assurance-v1.2.yaml`
- Create `policies/continuous-handoff-v1.2.yaml`
- Create `policies/uat-corrective-action-v1.2.yaml`
- Create `policies/hitl-v1.2.yaml`
- Create `policies/native-scheduling-v1.2.yaml`

- [ ] Make `agents/catalog-v1.2.yaml` the authoritative admission/compilation catalog; directory existence never implies eligibility.
- [ ] Remove internal `factory-control-*` MCP assumptions from worker runtime policy classes and express native/local control boundaries.
- [ ] Reconcile Skill consumers away from superseded Profiles and introduce Factory-owned UAT/Finding/Rework Skills as PROPOSED only.
- [ ] Encode effective Skill authorization as Agent-required plus task-approved, both registered and admitted.
- [ ] Encode structured machine/policy transition authorization, atomic handoff, bounded rework, UAT immutability and HITL provenance.

### Task 3: Produce the canonical Architecture Review and Specification v1.2

**Files:**
- Create `docs/16-architecture-review-v1.2.md`
- Create `docs/superpowers/specs/2026-08-18-hermes-software-factory-design-v1.2.md`

- [ ] Consolidate v1.1 plus ADR-0016 through ADR-0020 into one precedence layer.
- [ ] Define event-driven versus time-driven execution boundaries.
- [ ] Define UAT, Finding, Rework, Handoff and HumanDecision traceability entities.
- [ ] Define first-product bootstrap sequence Jarvas CLI -> HSL -> unrelated portability project.
- [ ] Preserve implementation authority as NOT GRANTED pending owner approval.

### Task 4: Reconcile historical/current documentation

**Files:**
- Update `README.md`
- Update `docs/04-project-contract-traceability.md`
- Update `docs/06-pilot-and-roadmap.md`
- Update `docs/07-proposed-architecture-decisions.md`
- Update `docs/15-jarvas-cli-control-plane-proposal.md`

- [ ] Mark v1/v1.1 conflicts as superseded by v1.2 rather than leaving ambiguous current guidance.
- [ ] Remove `.factory/quality.yaml` from current/recommended contract guidance; JDS remains canonical for generic engineering gates.
- [ ] Replace RITMO-as-Factory-scheduler wording with native Hermes cron for Factory time-driven work.
- [ ] Promote Jarvas CLI from future proposal to first greenfield Factory product in the architecture sequence without authorizing implementation.

### Task 5: Clean branch audit

**Verification queries:**
- Search for `RITMO`, `.factory/quality.yaml`, `factory-python-engineer`, `factory-exact-sha-auditor`, `factory-control-`, `first proposed client`, `implementation authority`, `UAT`, `rework`, `HITL`, `cron`.
- Read every v1.2 canonical/ADR/policy/catalog file from the resulting branch head.
- Verify the PR head after all writes.

- [ ] Confirm every historical reference is either intentionally historical/superseded or aligned with v1.2.
- [ ] Confirm no machine-readable current source authorizes superseded Profiles.
- [ ] Confirm no internal Factory worker policy requires MCP Bridge transport.
- [ ] Confirm no Factory internal scheduling depends on RITMO/host cron/systemd timers.
- [ ] Confirm UAT/Rework/Handoff/HITL invariants are represented in both human-readable spec and machine-readable policy.
- [ ] Confirm Jarvas CLI first-product sequence is represented consistently.
- [ ] Confirm all runtime/product implementation remains NOT AUTHORIZED.
- [ ] Report final verdict as APPROVABLE or NOT APPROVABLE with exact remaining blockers.

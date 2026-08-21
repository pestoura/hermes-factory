# Hermes Software Factory — Owner Approval v1.2

**Decision:** APPROVED  
**Owner:** Pedro Estoura  
**Date:** 2026-08-18  
**Audited design SHA:** `281b8c7509252d0416621f9971e14bd4151b997a`  
**Implementation scope:** FULL ARCHITECTURE  
**Implementation authority:** GRANTED  
**Runtime activation:** GATED BY TESTS / EVALS / ACCEPTANCE

## Decision

The fully reconciled and clean-audited Hermes Software Factory Architecture v1.2 is approved for complete implementation in Hermes/Jarvas.

This approval explicitly rejects substituting the approved design with a reduced/minimum Factory runtime. Implementation must cover the complete v1.2 scope: Project Compiler, semantic traceability, staffing, all 17 Profile definitions/runtime projections, Factory-owned Skills and evals, native Hermes Kanban integration, continuous atomic handoff, UAT, Findings/Rework, HITL through Hermes Gateway, native Hermes Profile/Agent cron, JDS and Exact-SHA integration, SCM/GitHub, Jarvas Operations evidence, ecosystem capability adapter, governance/acceptance, Hermes Dashboard integration and the northbound external Factory Control contract.

## Provenance

The approved design is the exact source tree at:

```text
281b8c7509252d0416621f9971e14bd4151b997a
```

The clean audit performed against that SHA found the architecture suitable for owner approval. This file is an append-only governance event after the audited baseline; it does not rewrite the evidence that was audited.

Machine-readable authority is recorded in `approvals/architecture-v1.2.yaml`.

## Activation is not approval-by-declaration

Architecture approval grants authority to implement and perform controlled Hermes/Jarvas integration. It does **not** make unexecuted work PASS and does not automatically promote Profiles or Skills.

```text
source implemented != runtime installed
runtime installed   != ACTIVE
ACTIVE              != accepted without required evidence
```

A Skill remains non-ACTIVE until its required baseline RED, Skill GREEN, variation/pressure evals and independent review succeed. A Profile remains non-ACTIVE until its Agent DNA/runtime projection, authority/tool policy, required Skill compatibility and Profile evals succeed.

`NOT_RUN`, `UNKNOWN`, `ABSENT` and stale evidence remain non-PASS states.

## Safety and authority boundaries retained

This approval does not waive:

- secrets/root token/Shamir/credential HITL boundaries;
- destructive or recovery-sensitive HITL boundaries;
- owner-reserved product/risk/release decisions;
- independent review and separation of duties;
- bounded rework and fail-closed behavior;
- Exact-SHA evidence binding;
- JDS mandatory engineering controls;
- the prohibition on internal MCP Bridge dependency;
- the prohibition on RITMO/host cron/systemd timers as Factory-internal schedulers;
- Jarvas Operations independence from Factory recovery authority.

## Delivery sequence

```text
Architecture v1.2 APPROVED
-> full Factory runtime implementation plan
-> TDD RED
-> complete Factory source implementation
-> hardening + full tests/evals
-> CI + Exact-SHA
-> merge
-> controlled Hermes/Jarvas installation
-> runtime/post-install verification
-> Factory acceptance
-> Jarvas CLI delivered to the accepted Factory as its first greenfield project
```

Hermes Security Labs follows Jarvas CLI as the first complex brownfield onboarding.

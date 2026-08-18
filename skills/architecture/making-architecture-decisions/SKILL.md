---
name: making-architecture-decisions
description: Compare structural options and record explicit trade-offs.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, architecture, adr]
    related_skills: [reading-project-truth, assessing-change-impact]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: architecture
---

# Making Architecture Decisions Skill

Evaluate consequential structural choices against approved forces and record the decision so later work understands both the choice and its constraints.

## When to Use

- A component/interface/trust/deployment boundary is changing.
- Multiple materially different designs are viable.
- A decision has long-lived or cross-repository consequences.

Don't use for: routine reversible implementation details that do not merit an ADR.

## Prerequisites

- Approved requirements and known constraints.
- Current architecture/ADR context.

## Procedure

1. State the decision question and forces: requirements, constraints, risks, compatibility and operations. **Complete when the problem is not framed as a predetermined solution.**
2. Identify the smallest set of materially distinct options. **Complete when cosmetic variations are removed.**
3. Compare options across relevant quality attributes and migration cost. **Complete when trade-offs, not just benefits, are explicit.**
4. Select only within delegated authority; otherwise request the required owner/governance decision. **Complete when authority is clear.**
5. Record decision, rationale, consequences, rejected alternatives and follow-up constraints using the project ADR convention. **Complete when future agents can explain why the decision exists.**
6. Run change-impact analysis. **Complete when affected WPs/gates/docs are identified.**

## Pitfalls

- Choosing the newest technology by default.
- Inventing options only to make the preferred one look best.
- Hiding migration/security consequences.
- Treating an ADR as proof the implementation conforms.

## Verification

The recorded decision names the question, forces, considered alternatives, rationale, consequences, authority and impacted boundaries.
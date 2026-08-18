---
name: governing-agent-admission
description: Decide when a capability deserves a new Factory profile.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, workforce, admission]
    related_skills: [reading-project-truth, assessing-change-impact]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: workforce
---

# Governing Agent Admission Skill

Classify a capability gap into the smallest maintainable Factory asset while preventing profile proliferation and authority creep.

## When to Use

- Staffing reports `CAPABILITY_GAP`.
- A recurring task suggests a new specialist.
- Existing profiles overlap or lack an authority boundary.
- Someone proposes a new Agent Soul/Profile.

Don't use for: silently generating a Profile during task decomposition.

## Prerequisites

- Evidence of the recurring capability gap.
- Current Agent/Skill/Runbook catalog.

## Procedure

1. Describe the gap as a capability, not a job title. **Complete when the need is independent of a proposed solution.**
2. Search existing Profiles, Skills, Runbooks, Templates and Tools. **Complete when reuse options are explicitly evaluated.**
3. Test whether a distinct identity is justified by recurrent judgment, authority, independence, memory or autonomous Kanban participation. **Complete when each factor is yes/no with evidence.**
4. Choose one outcome: reuse Profile, extend Skill, add Runbook/Template, implement Tool/MCP, propose routine Profile, propose professional Profile, defer or reject. **Complete when only one primary outcome remains.**
5. For a Profile proposal, define Agent DNA, least authority, eval plan, ownership and deprecation path. **Complete when promotion criteria are testable.**
6. Route authority-increasing proposals to independent governance. **Complete when proposer cannot self-approve.**

## Pitfalls

- Modeling every corporate title as an agent.
- Creating a Profile where a Skill is sufficient.
- Adding tools because a role “might need them”.
- Treating one project's technology as a permanent global profession.

## Verification

The decision explains why simpler alternatives are insufficient and, for any new Profile, proves a distinct identity/authority/evaluation boundary.
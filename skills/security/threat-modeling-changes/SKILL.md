---
name: threat-modeling-changes
description: Model assets, trust boundaries, abuse paths and controls.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, security, threat-model]
    related_skills: [reading-project-truth, assessing-change-impact]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: security
---

# Threat Modeling Changes Skill

Model the security consequences of a bounded change from assets, trust and attacker actions rather than from a generic control checklist.

## When to Use

- New trust boundary, identity, secret, API or data flow.
- Security-sensitive architecture or integration change.
- Existing threat assumptions may become invalid.

Don't use for: accepting residual risk or replacing specialist implementation review.

## Prerequisites

- Architecture/data-flow context and change objective.
- Known actors/assets and trust assumptions where available.

## Procedure

1. Identify assets, security objectives, actors and privilege levels. **Complete when protected value/authority is explicit.**
2. Map entry points, data/authority flows and trust boundaries affected by the change. **Complete when boundary crossings are visible.**
3. Enumerate credible attacker goals and abuse paths, including negative/failure conditions. **Complete when threats are tied to concrete flows.**
4. Identify assumptions and dependency trust. **Complete when unverified assumptions are labeled.**
5. Map preventive, detective and recovery controls to specific threats. **Complete when every required control has a threat/rationale.**
6. Define security acceptance criteria and residual risks. **Complete when residual risk is explicit and routed to the right authority.**

## Pitfalls

- Listing STRIDE labels without concrete abuse paths.
- Treating authentication as authorization.
- Omitting operational/secret lifecycle threats.
- Assuming an upstream service is trusted because it is internal.

## Verification

The threat model can trace `asset -> boundary/flow -> threat -> control -> acceptance evidence`, with unresolved residual risk clearly separated from accepted design.
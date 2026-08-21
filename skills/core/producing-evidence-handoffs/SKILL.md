---
name: producing-evidence-handoffs
description: Produce bounded handoffs with explicit evidence and state.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, handoff, evidence]
    related_skills: [reading-project-truth]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: core
---

# Producing Evidence Handoffs Skill

Create handoffs that another agent can verify without reconstructing the previous agent's reasoning or trusting its confidence.

## When to Use

- Finishing a task, review, test, audit or observation.
- Passing work to another specialist.
- Reporting a blocker, HITL or rework condition.

Don't use for: replacing canonical evidence with a prose summary.

## Prerequisites

- Bounded objective.
- Actual evidence available from the performed work.

## Procedure

1. State objective and exact scope handled. **Complete when the receiver can distinguish completed scope from surrounding project scope.**
2. State outcome using allowed role states, not generic `done`. **Complete when `PASS`, `NOT_RUN`, `UNKNOWN`, `BLOCKED` and similar states are unambiguous.**
3. Attach evidence references: commands/checks, artifact IDs, files, PR/SHA, environment, timestamps or source refs as applicable. **Complete when each material claim has provenance.**
4. Separate verified/observed facts from inference or proposal. **Complete when no inference is presented as direct proof.**
5. List findings, unresolved items and invalidated/stale evidence. **Complete when the receiver knows what remains unsafe to assume.**
6. State the next safe action and required receiver/gate. **Complete when the handoff is actionable without hidden context.**

## Pitfalls

- “All good” without evidence identity.
- Dumping raw logs instead of identifying the proving lines/artifacts.
- Omitting the candidate SHA after code changed.
- Hiding partial completion inside a success summary.

## Verification

A receiver must be able to answer: what was attempted, what exact state resulted, what proves it, what remains unresolved, and what is safe to do next.
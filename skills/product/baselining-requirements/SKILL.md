---
name: baselining-requirements
description: Turn approved intent into testable traced requirements.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, requirements, acceptance]
    related_skills: [reading-project-truth, assessing-change-impact]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: product
---

# Baselining Requirements Skill

Convert approved intent into observable requirements and acceptance criteria while preserving unresolved decisions as explicit gaps.

## When to Use

- Before implementation of a new capability.
- Requirements are vague, conflicting or mixed with solution detail.
- An Epic needs testable acceptance criteria.

Don't use for: making product decisions the owner has not approved.

## Prerequisites

- Canonical product intent and relevant decisions.

## Procedure

1. Identify actors, goals and externally observable behavior. **Complete when each requirement has a subject and outcome.**
2. Separate mandatory behavior, constraint, non-goal and implementation suggestion. **Complete when solution detail is not masquerading as requirement.**
   Classification boundary: use `proposed` when behavior is not sourced in approved intent and would create new mandatory product intent; use `implementation suggestion` when approved intent exists but a particular technical mechanism or framework is only one possible way to satisfy it. Unsupported behavior is not an implementation suggestion merely because it simplifies implementation.
3. Define normal, boundary and failure behavior where material. **Complete when important negative paths are not implicit.**
4. Write acceptance criteria using observable inputs, state and outcomes. **Complete when an independent tester could determine pass/fail.**
5. Identify non-functional constraints such as security, performance, operability or compatibility only when sourced. **Complete when each constraint has provenance.**
6. Trace requirements to Epic/decision/source and flag conflicts. **Complete when every requirement has an origin or is marked proposed.**

## Pitfalls

- “Must be secure/fast/robust” without measurable meaning.
- Embedding a specific framework where the requirement is technology-neutral.
- Filling missing owner intent with plausible assumptions.
- Acceptance criteria that only restate the requirement.

## Verification

Each baselined requirement is sourced, bounded, observable and independently testable; unresolved product choices remain explicit.
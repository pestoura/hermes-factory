---
name: designing-product-experience
description: Define coherent accessible user flows and interactions.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, product-design, ux]
    related_skills: [reading-project-truth, assessing-change-impact]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: product-design
---

# Designing Product Experience Skill

Translate approved product behavior into user flows, interface states and usability criteria without inventing new product scope.

## When to Use

- A user-facing flow is new or changing.
- Interaction/error/recovery behavior is ambiguous.
- Frontend work needs a UX specification before implementation.

Don't use for: deciding product priorities or backend architecture.

## Prerequisites

- Approved actors/goals and requirements.
- Known security/accessibility constraints.

## Procedure

1. Identify user goal, context and preconditions. **Complete when the flow has a clear start and intended outcome.**
2. Map primary path, alternate paths, errors, permission states and recovery. **Complete when material state transitions are represented.**
3. Define information hierarchy and interaction semantics before visual polish. **Complete when each action/state is understandable without relying on decoration.**
4. Add accessibility expectations for navigation, focus, labels, contrast/semantics and error feedback as applicable. **Complete when accessibility is testable.**
5. Produce the minimum useful wireframe/prototype/spec. **Complete when implementation decisions are not over-specified beyond need.**
6. Define usability acceptance criteria and trace them to requirements. **Complete when a reviewer can compare implementation to intent.**

## Pitfalls

- Designing only the happy path.
- Hiding security/permission states for visual simplicity.
- Pixel-detail before interaction decisions are stable.
- Confusing a mockup with an approved requirement.

## Verification

The artifact covers primary/exception flows, state transitions, accessibility-relevant behavior and explicit acceptance criteria without adding unsourced product scope.
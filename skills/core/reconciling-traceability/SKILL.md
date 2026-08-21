---
name: reconciling-traceability
description: Reconcile project work and evidence across linked systems.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, traceability, provenance]
    related_skills: [reading-project-truth, producing-evidence-handoffs]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: core
---

# Reconciling Traceability Skill

Maintain semantic links between project intent, Factory work, SCM candidates and evidence without collapsing those entities into one system.

## When to Use

- Creating or reconciling Work Packages.
- Linking Issues, Kanban tasks, branches, PRs or evidence.
- Explaining why a PR exists or what blocks an Epic.
- Project recompilation changes existing work.

Don't use for: copying external system history into the Factory as a replacement source of truth.

## Prerequisites

- Stable project identity.
- Stable source/external identifiers for the entities being linked.

## Procedure

1. Identify each entity by semantic type: Project, Requirement, ADR, Epic, Change, Issue, WP, Task, Execution, Branch, PR, SHA, CI, Deployment, Runtime Evidence or Acceptance. **Complete when no object is represented only by a title.**
2. Resolve canonical owner and stable ID for each entity. **Complete when every node has system + identity.**
3. Create only justified relations such as `implements`, `depends_on`, `produced_by`, `verified_by`, `deployed_as` or `accepted_by`. **Complete when relationship meaning is explicit.**
4. Compare desired links with existing registry state and reconcile idempotently. **Complete when repeated reconciliation creates no duplicates.**
5. Detect dangling, conflicting or superseded relations. **Complete when inconsistencies are reported rather than silently rewired.**

## Pitfalls

- Treating an Issue and Work Package as the same object.
- Linking reviews to a PR number but not candidate SHA.
- Recreating cards because titles changed.
- Deleting historical provenance when work is superseded.

## Verification

The graph must support both backward explanation (`PR -> WP -> Epic -> requirement/decision`) and forward status (`Epic -> WP -> task/gates/evidence`) with stable identities.
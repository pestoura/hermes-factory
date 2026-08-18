---
name: validating-documentation-consistency
description: Detect stale or contradictory repository documentation.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, documentation, consistency]
    related_skills: [reading-project-truth, authoring-repository-documentation]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: documentation
---

# Validating Documentation Consistency Skill

Audit documentation against canonical architecture, configuration and implementation truth without rewriting the product to match prose.

## When to Use

- Before release or milestone acceptance.
- README/config/API/runbook may be stale.
- A change alters commands, ports, interfaces or architecture.

Don't use for: deciding which conflicting canonical architecture is correct.

## Prerequisites

- Documentation set in scope.
- Read access to relevant implementation/configuration sources.

## Procedure

1. Extract factual claims from docs: commands, paths, ports, versions, configuration keys, interfaces, dependencies and runtime statements. **Complete when material claims are enumerable.**
2. Resolve the authority for each claim using project truth. **Complete when every claim has a comparison source or `UNKNOWN`.**
3. Verify claims with `read_file`, `search_files` or permitted system metadata. **Complete when each claim is `CONSISTENT`, `STALE`, `CONTRADICTORY` or `UNVERIFIED`.**
4. Check internal terminology, links and duplicate sources. **Complete when known doc-to-doc contradictions are recorded.**
5. Produce bounded remediation targets rather than silently changing product behavior. **Complete when every finding points to the document/source that should change.**

## Pitfalls

- Treating the README as implementation authority.
- Checking links only and calling docs correct.
- Updating several duplicates instead of removing duplication.
- Marking unverifiable commands as valid because they look plausible.

## Verification

The audit produces a claim-level consistency result and no `UNVERIFIED` item is represented as current fact.
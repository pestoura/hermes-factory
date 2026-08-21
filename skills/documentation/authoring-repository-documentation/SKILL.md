---
name: authoring-repository-documentation
description: Write accurate navigable docs from verified repository truth.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, documentation, developer-experience]
    related_skills: [reading-project-truth, assessing-change-impact]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: documentation
---

# Authoring Repository Documentation Skill

Create or update repository documentation that helps a technical reader understand, use, develop or operate the project without duplicating truth or inventing behavior.

## When to Use

- README, quickstart, developer guide or runbook is missing/stale.
- Code/configuration/architecture changes create documentation impact.
- A new repository needs a clear entry point.

Don't use for: changing product behavior to match outdated documentation.

## Prerequisites

- Verified repository/configuration/architecture sources.
- Intended audience and documentation impact.

## Procedure

1. Identify audience and task: orient, install, develop, configure, integrate, operate or troubleshoot. **Complete when each target document has one primary job.**
2. Inspect current docs and canonical sources. **Complete when duplication/stale sections are identified.**
3. Design progressive information hierarchy: README for orientation, linked detail for depth. **Complete when a new reader has a clear path.**
4. Write concrete commands/config/examples only from verified behavior; frame tool-driven verification through permitted Hermes tools. **Complete when technical claims are sourced or tested.**
5. Use Mermaid/visuals only when they clarify relationships/flows. **Complete when every diagram adds information not already obvious in prose.**
6. Remove/rewrite stale conflicting material and preserve canonical links. **Complete when no known contradiction remains.**

## Pitfalls

- README becoming the full design archive.
- Repeating configuration values in several places.
- Documenting planned features as present.
- Copying secrets into examples.
- Beautiful diagrams disconnected from current architecture.

## Verification

A technical reader can identify project purpose, current status, setup/use path and deeper references; commands/examples are verified or explicitly marked illustrative.
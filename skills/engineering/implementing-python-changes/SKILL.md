---
name: implementing-python-changes
description: Implement maintainable Python changes within project rules.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, engineering, python]
    related_skills: [implementing-minimal-green, scoping-bounded-work]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: engineering
---

# Implementing Python Changes Skill

Apply Python-specific engineering discipline after the bounded behavior and TDD path are clear. Project conventions outrank generic preferences.

## When to Use

- Implementing or refactoring Python code in an approved Work Package.
- Python-specific error handling, typing, packaging or testability choices matter.

Don't use for: choosing Python as a project technology when architecture has not decided it.

## Prerequisites

- Approved Work Package and repository conventions.
- Required RED/acceptance evidence when TDD applies.

## Procedure

1. Inspect project Python version, dependency management, lint/type/test tooling and nearby conventions using `read_file`/`search_files`. **Complete when implementation constraints are known.**
2. Prefer project-standard idioms and stdlib before adding dependencies. **Complete when every new dependency is necessary and authorized.**
3. Keep functions/modules explicit about inputs, outputs, errors and side effects. **Complete when failure behavior is testable.**
4. Preserve typing/style expectations already enforced by the repository. **Complete when required static checks pass.**
5. Use deterministic resource handling (`with`, bounded retries/timeouts, explicit cleanup) where relevant. **Complete when failure paths do not leak resources/state.**
6. Run targeted tests, required suite and configured lint/type checks through `terminal`. **Complete when required checks are GREEN on the candidate.**

## Pitfalls

- Introducing a library for functionality the project already provides.
- Catching broad exceptions and converting failures into silent success.
- Global mutable state for convenience.
- Type hints that disagree with runtime behavior.
- Framework-specific redesign during a bounded fix.

## Verification

The candidate follows repository Python/tooling conventions, required tests/static checks pass, and any dependency/configuration changes are explicit and in scope.
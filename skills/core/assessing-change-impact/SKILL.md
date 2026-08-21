---
name: assessing-change-impact
description: Identify affected code, tests, docs, interfaces and runtime.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, impact, change]
    related_skills: [reading-project-truth, scoping-bounded-work]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: core
---

# Assessing Change Impact Skill

Determine which artifacts and gates a proposed or completed change actually affects so the Factory neither under-tests nor expands scope blindly.

## When to Use

- Requirements, architecture or implementation changes.
- A PR changes interfaces, configuration, persistence or runtime behavior.
- Deciding whether documentation, threat model or integration tests are required.

Don't use for: authorizing the affected changes; impact and authority are separate decisions.

## Prerequisites

- Bounded change objective.
- Current architecture/repository context.

## Procedure

1. Identify the changed behavior, contract or structural assumption. **Complete when the change can be described without implementation noise.**
2. Trace direct consumers/dependencies using project artifacts, `search_files` and permitted repository/system metadata. **Complete when first-order dependants are identified.**
3. Evaluate impact classes: code, tests, API/contracts, data/schema, configuration, security/trust, docs, CI/build, deployment/runtime and recovery. **Complete when each class is `AFFECTED`, `NOT_AFFECTED` or `UNKNOWN`.**
   Classification boundary: use `AFFECTED` when the supplied change modifies a contract, trust/configuration/runtime assumption, or creates a material downstream obligation that must be evaluated; use `UNKNOWN` only when the available evidence is insufficient to determine whether the class is affected after tracing. Uncertain magnitude does not turn an identified material dependency into `UNKNOWN`.
4. Map affected classes to required Work Packages/gates. **Complete when every affected class has an action or justified no-action.**
5. Flag cross-repository or external impacts as explicit dependencies. **Complete when no hidden external dependency remains.**

## Pitfalls

- Assuming a small diff has small behavioral impact.
- Forgetting configuration/reference docs.
- Ignoring runtime/recovery because code tests pass.
- Expanding implementation scope instead of creating dependency work.

## Verification

The impact result covers every standard impact class and makes documentation/security/integration/runtime requirements explicit enough for the Project Compiler or reviewer to act on.
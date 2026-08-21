---
name: verifying-integration-behavior
description: Verify cross-component contracts and representative flows.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, testing, integration]
    related_skills: [reading-project-truth, producing-evidence-handoffs]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: quality
---

# Verifying Integration Behavior Skill

Verify behavior across real component boundaries and distinguish product defects from environment or dependency failures.

## When to Use

- Acceptance crosses services, APIs, storage, events or external systems.
- Unit tests cannot prove the required contract.
- A change may break integration compatibility.

Don't use for: destructive environment testing without approval.

## Prerequisites

- Integration acceptance criteria.
- Identified candidate components and test environment.

## Procedure

1. Define the boundary/contract under test and candidate/environment identities. **Complete when inputs, outputs and participating components are explicit.**
2. Verify prerequisites and dependency availability. **Complete when unavailable dependencies are reported rather than silently mocked.**
3. Execute the smallest representative happy path using approved test tooling. **Complete when cross-boundary state/output is observed.**
4. Execute required error/compatibility cases. **Complete when material failure contracts are observed.**
5. Capture logs/artifacts/state evidence sufficient to localize failures. **Complete when outcome is reproducible without relying on narrative.**
6. Classify failure as product, contract, environment/dependency or specification gap. **Complete when the classification has evidence.**

## Pitfalls

- Calling two mocked units an integration test.
- Replacing a failed dependency with a fake and passing the gate.
- Fixing implementation while acting as independent tester.
- Omitting candidate/environment identity.

## Verification

The result identifies tested candidates/environment, exact flows, observations and classification as `INTEGRATION_PASS`, `INTEGRATION_FAIL`, `ENVIRONMENT_BLOCKED` or `SPEC_GAP`.
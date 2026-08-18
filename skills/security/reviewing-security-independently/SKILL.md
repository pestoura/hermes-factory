---
name: reviewing-security-independently
description: Review exact candidates for exploitable security failures.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, security, review]
    related_skills: [reading-project-truth, verifying-exact-sha, threat-modeling-changes]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: security
---

# Reviewing Security Independently Skill

Review an exact candidate adversarially against the approved trust/control model without repairing the candidate during the review gate.

## When to Use

- Security-sensitive code/configuration is ready for independent review.
- Authentication, authorization, secrets, parsers or trust boundaries changed.
- A security finding has been reworked and needs re-verification.

Don't use for: accepting residual risk or making implementation changes while reviewing.

## Prerequisites

- Exact candidate SHA/revision.
- Security requirements/threat model where applicable.

## Procedure

1. Fix candidate identity and security scope. **Complete when review cannot drift to another revision.**
2. Trace changed input, trust, identity, privilege and secret flows. **Complete when affected boundaries are explicit.**
3. Inspect authentication/authorization decisions and negative paths. **Complete when bypass/default/fallback behavior is considered.**
4. Inspect injection/parsing/deserialization/path/SSRF/egress/concurrency/supply-chain surfaces as applicable. **Complete when relevant attack classes have a conclusion.**
5. Evaluate secrets handling, logging and evidence-spoofing/replay risks. **Complete when sensitive data and trust proofs are covered.**
6. Run permitted non-destructive security checks when they add evidence. **Complete when results are bound to the candidate.**
7. Produce findings with exploit preconditions, impact and re-verification criteria. **Complete when remediation is testable.**

## Pitfalls

- Checklist review without tracing attacker-controlled data/authority.
- Treating authentication as sufficient authorization.
- Ignoring failure/default behavior.
- Fixing the candidate and then self-approving it.

## Verification

The review is bound to one candidate and returns `PASS`, `PASS_WITH_FINDINGS`, `REWORK_REQUIRED`, `RISK_ACCEPTANCE_REQUIRED` or `BLOCKED` with evidence-backed findings.
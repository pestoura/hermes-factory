---
name: verifying-exact-sha
description: Historical Exact-SHA Skill superseded by deterministic gate.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, governance, sha, superseded]
    related_skills: [producing-evidence-handoffs]
  factory:
    lifecycle: superseded
    test_status: not_run
    scope: governance
    runtime_installable: false
    superseded_by: gate:factory-exact-sha
---

# Verifying Exact SHA — Historical Skill

**SUPERSEDED. DO NOT INSTALL OR USE AS A FACTORY VERDICT SOURCE.**

The original prose procedure is retained in Git history for provenance. Architecture v1.2 requires Exact-SHA identity/freshness reconciliation to be performed by the deterministic validator:

```text
gate:factory-exact-sha
```

Current closed states are:

```text
SHA_MATCH
SHA_MISMATCH
EVIDENCE_STALE
EVIDENCE_ABSENT
IDENTITY_UNKNOWN
```

Reviewers, auditors and release governance may consume the deterministic result, but no LLM Skill may replace the mechanical comparison. Missing identity is not a match, changed candidate identity invalidates affected SHA-bound evidence, and `NOT_RUN != PASS`.

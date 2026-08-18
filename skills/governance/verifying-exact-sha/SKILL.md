---
name: verifying-exact-sha
description: Verify evidence and gates refer to the exact candidate.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, governance, sha]
    related_skills: [producing-evidence-handoffs]
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: governance
---

# Verifying Exact SHA Skill

Prove that implementation, review, CI, merge and deployment evidence apply to the exact revisions they claim.

## When to Use

- Code review or CI evidence contributes to acceptance.
- A PR received new commits after review.
- Pre-merge and post-merge revisions must be reconciled.
- Deployment/runtime evidence must map to a code/artifact revision.

Don't use for: deciding whether the code itself is correct.

## Prerequisites

- Repository identity and candidate/PR context.
- Read access to relevant SCM/CI/deployment metadata.

## Procedure

1. Collect candidate identities separately: source/base, PR head, reviewed SHA, CI/check SHA, merge/main SHA and deployed revision when applicable. **Complete when no identity is represented only by branch name.**
2. Bind each evidence item to the identity it actually executed/reviewed. **Complete when every required evidence item has a candidate ID or `UNKNOWN`.**
3. Compare required identities according to the gate stage. **Complete when matches/mismatches are explicit.**
4. If a candidate changed, classify prior evidence as stale unless policy has a specific validity rule. **Complete when stale evidence is not silently reused.**
5. For merge strategies that create a new SHA, verify post-merge checks against the actual resulting revision. **Complete when repository acceptance is tied to the intended final revision.**

## Pitfalls

- Assuming PR number identifies one immutable candidate.
- Treating branch name as SHA.
- Carrying review PASS across later commits.
- Assuming merge SHA equals reviewed head.

## Verification

Emit `SHA_COHERENT`, `SHA_MISMATCH`, `EVIDENCE_STALE` or `UNKNOWN` with a revision/evidence matrix sufficient for independent reproduction.
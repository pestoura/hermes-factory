---
name: reading-project-truth
description: Resolve authoritative sources before technical claims.
version: 0.1.0
author: Pedro Estoura (pestoura), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [factory, truth, provenance]
    related_skills: []
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: core
---

# Reading Project Truth Skill

Resolve the correct authority for each type of claim before planning, changing or accepting work. This Skill does not create missing truth; it classifies gaps and conflicts.

## When to Use

- Starting any Work Package or review.
- Sources disagree about project, repository, CI or runtime state.
- A prior summary may be stale.
- A claim mixes design, implementation and live state.

Don't use for: replacing an explicit human decision or manufacturing state when the authoritative source is unavailable.

## Prerequisites

- Project Contract or equivalent project identity.
- Read access to the sources allowed by the active Profile.

## Procedure

1. Classify the claim domain: intent, implementation, work state, SCM, CI, runtime or approval. **Complete when every material claim has one domain.**
2. Resolve the canonical source for each domain. Prefer project artifacts for intent, exact repository revision for implementation, Hermes Kanban for work state, GitHub for SCM, executed CI for its checks and fresh observation for runtime. **Complete when every domain has a named authority or `UNKNOWN`.**
3. Read the authoritative source using `read_file`, Factory Control MCP, GitHub/MCP or permitted observation tools. **Complete when the evidence is current enough for the claim.**
4. Compare supporting sources and record contradictions without averaging them away. **Complete when conflicts are explicit.**
5. Produce state labels such as `VERIFIED`, `OBSERVED`, `INFERRED`, `NOT_RUN`, `UNKNOWN` or `CONFLICTING`. **Complete when no unsupported PASS remains.**

## Pitfalls

- Treating README/plans as proof of current implementation.
- Treating repository GREEN as live GREEN.
- Trusting an agent summary over a direct source.
- Silently choosing one of two conflicting authoritative artifacts.

## Verification

A valid result names the claim domain, source, relevant revision/timestamp and classification. Every `PASS` or acceptance-supporting claim must be traceable to evidence of the correct authority class.
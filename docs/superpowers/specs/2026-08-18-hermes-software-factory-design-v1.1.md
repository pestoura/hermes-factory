# Hermes Software Factory — Canonical Design v1.1

**Status:** SUPERSEDED BY v1.2  
**Date:** 2026-08-18  
**Historical baseline:** v1.1  
**Current canonical specification:** `2026-08-18-hermes-software-factory-design-v1.2.md`  
**Current architecture review:** `../../16-architecture-review-v1.2.md`  
**Implementation authority:** NOT GRANTED

## Historical status

This document is retained as a version marker and provenance pointer only. It MUST NOT be used as the current Factory design, implementation contract, scheduling model, product sequence, Agent admission source or Skill authorization source.

The complete historical v1.1 specification remains available through Git history at the commit/blob preceding this supersession marker.

## Material changes in v1.2

Architecture v1.2 retains the principal v1.1 boundaries—native Hermes/Jarvas execution, northbound-only MCP, JDS ownership of generic engineering gates, deterministic Exact-SHA and reusable governed workforce—but supersedes v1.1 where required, including:

- internal time-driven Factory work uses native Hermes Profile/Agent cron, not RITMO;
- continuous stage handoff is autonomous, structured and atomic;
- UAT, Findings and bounded Rework are first-class;
- frozen acceptance/UAT cannot be weakened by implementers to obtain PASS;
- HITL is asynchronous, revision-bound and persisted as HumanDecision evidence;
- Agent admission/compilation authority is `agents/catalog-v1.2.yaml`;
- canonical Factory Skill runtime identities use the `factory-*` namespace;
- Jarvas CLI is the first greenfield Factory product; HSL follows as the first complex brownfield onboarding.

## Precedence

Use `docs/superpowers/specs/2026-08-18-hermes-software-factory-design-v1.2.md`, `docs/16-architecture-review-v1.2.md`, ADR-0014 through ADR-0020, and the v1.2 machine-readable sources for all current work.

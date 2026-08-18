# Hermes Software Factory — Architecture Review v1.1

**Status:** SUPERSEDED BY v1.2  
**Date:** 2026-08-18  
**Decision owner:** Pedro Estoura  
**Historical baseline:** v1.1  
**Current architecture review:** `docs/16-architecture-review-v1.2.md`  
**Current canonical specification:** `docs/superpowers/specs/2026-08-18-hermes-software-factory-design-v1.2.md`  
**Implementation authority:** NOT GRANTED

## Historical status

This file is retained only as a version marker and design-history pointer. Architecture v1.1 was previously accepted with changes, but it is **not a current source of authority** after the v1.2 reconciliation.

The complete historical v1.1 content remains available in Git history at the commit/blob preceding this supersession marker.

## Superseded decisions

In particular, v1.1 language that treated **RITMO as the scheduler for recurring internal Factory work** is superseded by ADR-0020.

Current scheduling boundary:

```text
EVENT-DRIVEN FACTORY WORK -> Hermes Kanban + Dispatcher
TIME-DRIVEN FACTORY WORK  -> native Hermes Profile/Agent cron
EXTERNAL GOVERNANCE       -> RITMO/external scheduling via northbound control
```

Other current v1.2 corrections include first-class UAT/corrective action, atomic continuous handoff, revision-bound HITL, authoritative Agent admission catalog, `factory-*` Skill identities, and Jarvas CLI as the first greenfield Factory product.

## Precedence

For current design, admission, compilation, policy or implementation planning, use only the v1.2 review/specification, ADR-0014 through ADR-0020, and the v1.2 machine-readable design sources referenced by the repository README.

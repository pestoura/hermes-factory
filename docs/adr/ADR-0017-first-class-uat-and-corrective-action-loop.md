# ADR-0017 — First-Class UAT and Corrective Action Loop

- **Status:** ACCEPTED
- **Date:** 2026-08-18
- **Decision owner:** Pedro Estoura
- **Architecture baseline:** v1.2
- **Implementation authority:** NOT GRANTED

## Context

The Factory must prove that a delivered change satisfies approved user/product intent, not merely that engineering tests and CI are green. The v1.1 design contains acceptance concepts but does not model User Acceptance Tests (UAT), findings, root cause, corrective action and re-verification as first-class traceable entities.

Without a first-class acceptance/corrective-action model, a worker could incorrectly treat an implementation defect, test defect, requirement defect or environment problem as the same generic failure. It could also be tempted to alter an acceptance test to match the implementation rather than correct the product or explicitly rebaseline the approved requirement.

## Decision

UAT and corrective action are first-class Factory semantics and evidence sources.

Canonical traceability:

```text
Requirement
  -> Acceptance Criterion
  -> UAT Scenario
  -> UAT Execution
  -> UAT Evidence
  -> Acceptance decision
```

Required UAT execution states:

```text
NOT_REQUIRED
NOT_RUN
PASS
FAIL
BLOCKED
INCONCLUSIVE
STALE
```

Required execution modes:

```text
AUTOMATED
ASSISTED
MANUAL
```

`NOT_RUN` is never `PASS`. `STALE` evidence cannot satisfy acceptance until re-executed against the current candidate/context.

## Acceptance baseline immutability

Once an Acceptance Criterion or UAT Scenario is approved/frozen for a candidate scope, implementation workers MUST NOT alter it merely to make the implementation pass.

If the acceptance definition is discovered to be wrong or incomplete, the worker opens a Finding and classifies the problem. Rebaseline requires the authority responsible for requirements/product acceptance. The rebaseline event must be explicit, versioned and traceable.

Forbidden flow:

```text
implementation fails UAT
  -> implementer edits approved UAT
  -> PASS
```

Required flow for an invalid acceptance definition:

```text
FAIL
  -> Finding
  -> TEST_DEFECT or REQUIREMENT_DEFECT
  -> authorized decision/rebaseline
  -> new acceptance baseline/version
  -> implementation/reverification against new baseline
```

## Finding model

Every material failure that requires corrective work is represented as a Finding linked to the affected project/WP/stage/candidate/evidence.

Minimum classification vocabulary:

```text
IMPLEMENTATION_DEFECT
TEST_DEFECT
REQUIREMENT_DEFECT
ARCHITECTURE_DEFECT
SECURITY_DEFECT
PLATFORM_DEFECT
CONFIGURATION_DEFECT
ENVIRONMENT_DEFECT
TEST_DATA_DEFECT
DOCUMENTATION_DEFECT
DEPENDENCY_DEFECT
PRODUCT_DECISION_REQUIRED
EXTERNAL_BLOCKER
```

A Finding records at minimum:

- finding identifier and version;
- source gate/UAT/review/runtime observation;
- affected requirement/WP/stage;
- candidate/context identity;
- classification;
- severity/impact where applicable;
- root-cause statement or `UNKNOWN`;
- corrective-action owner/required capability;
- verification requirements;
- lifecycle state.

## Corrective action loop

Canonical flow:

```text
FAIL / adverse observation
  -> Finding opened or updated
  -> classification + root-cause analysis
  -> bounded Rework Order
  -> Staffing / admitted Profile
  -> correction
  -> targeted verification
  -> regression where applicable
  -> all affected gates/UAT rerun
  -> evidence refresh
  -> resume pipeline only when prerequisites are satisfied
```

The original failure is not erased. Corrective work produces new evidence and closes or supersedes the Finding only through verification.

## Bounded rework invariant

Autonomous rework is permitted but MUST be bounded by policy. The Factory MUST NOT perform infinite `fail -> fix -> retry` loops.

A repeated unresolved failure of the same class/root cause beyond the configured bound transitions to an escalation state such as:

```text
ESCALATE_DIAGNOSIS
HITL_REQUIRED
EXTERNAL_BLOCKED
```

The numeric threshold is policy/configuration and is not hard-coded by this ADR. Resetting the counter by superficial reclassification is forbidden.

## Independence

The worker that implements a correction does not independently certify the review/acceptance gate when separation of duties applies. Re-verification uses the required reviewer/tester/auditor role or deterministic gate.

## Consequences

### Positive

- acceptance proves product intent rather than agent confidence;
- defects are classified and routed to the correct profession;
- requirement/test defects can be corrected without corrupting evidence history;
- rework remains autonomous without becoming infinite;
- UAT evidence becomes part of the release/acceptance chain.

### Constraints

- acceptance definitions require versioned baselines;
- evidence and findings are candidate/context-bound;
- changes to frozen UAT require explicit authority and rebaseline provenance.

## Related decisions

- ADR-0016 — Autonomous Continuous Stage Handoff
- ADR-0018 — Asynchronous HITL through Hermes Gateway
- ADR-0019 — Jarvas CLI as First Factory Product

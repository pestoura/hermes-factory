# ADR-0016 — Autonomous Continuous Stage Handoff

- **Status:** ACCEPTED
- **Date:** 2026-08-18
- **Decision owner:** Pedro Estoura
- **Architecture baseline:** v1.2
- **Implementation authority:** NOT GRANTED

## Context

Hermes Software Factory is intended to operate as a persistent engineering organization rather than as a sequence of manually started agent chats. Hermes already provides the operational primitives for durable Kanban state, Profile workers, dispatch, workspaces and review transitions. The Factory must therefore define the semantic handoff contract between engineering stages without creating another task engine or requiring a human to approve every normal transition.

The v1.1 high-assurance baseline uses structured dispatch approval. That control must not be interpreted as mandatory human approval for every promotion; doing so would destroy continuous execution and turn the Factory into a manually advanced workflow.

## Decision

Normal Factory stage transitions are **autonomous and policy-authorized** when all prerequisites and evidence are satisfied. Human approval is reserved for explicit HITL classes defined by project/Factory policy.

Canonical flow:

```text
Stage A worker
  -> produces outcome + artifacts + evidence
  -> commits candidate identity and stage state
  -> handoff validator evaluates prerequisites
  -> HANDOFF_READY
  -> structured machine/policy authorization
  -> next Kanban task/stage becomes READY
  -> Hermes Dispatcher starts the admitted Profile worker
```

The Factory does not create a second dispatcher, queue or workspace manager. Hermes Kanban and Dispatcher remain authoritative for operational execution state.

## Atomic handoff invariant

A handoff is semantically committed only when the following are bound to the same stage outcome:

- stage result/state;
- output artifact references;
- evidence references and freshness state;
- candidate/commit identity when code or configuration is involved;
- open/closed Finding state relevant to the transition;
- required independent review state;
- next-stage prerequisites.

The next stage MUST NOT be promoted before that handoff record is complete. A worker statement such as `done` is never sufficient evidence.

Canonical states:

```text
WORKING
HANDOFF_PENDING
HANDOFF_READY
HANDOFF_BLOCKED
HANDED_OFF
STALE
```

If candidate identity or a prerequisite changes after `HANDOFF_READY` but before dispatch, the handoff becomes `STALE` and must be revalidated.

## Structured approval semantics

`dispatch_approval_mode=structured` means that the transition has an explicit authorization record and policy evaluation. It does **not** mean that a person must click Approve for ordinary stage-to-stage progression.

Authorization sources may include:

- deterministic policy/gate result;
- admitted Factory governance rule;
- project acceptance/authority policy;
- explicit human decision for a declared HITL boundary.

A transition requiring HITL remains blocked until the human-decision contract in ADR-0018 is satisfied.

## Independence

Where the project lifecycle requires independent review, the producer of an artifact MUST NOT certify the gate that reviews that artifact. Examples include:

- implementation versus code review;
- implementation versus security review;
- evidence production versus evidence audit;
- runtime mutation versus runtime truth observation.

The handoff validator must preserve these role-separation constraints when selecting the next Profile.

## Failure and rework

A failed stage opens or updates a first-class Finding and enters the bounded corrective-action flow defined by ADR-0017. Failure MUST NOT be converted into an unbounded retry loop or silently promoted to the next stage.

## Consequences

### Positive

- continuous execution without manual micro-approval;
- durable evidence between Profiles;
- explicit stale-state handling;
- no duplicate workflow runtime;
- machine-verifiable separation of production and review roles.

### Constraints

- handoff validation must be deterministic where possible;
- policy/evidence state must be persisted before promotion;
- human-only decisions must be represented explicitly rather than hidden inside a generic structured approval.

## Rejected alternatives

### Human approval on every transition

Rejected because it prevents autonomous continuous execution and creates unnecessary owner/operator load.

### Agent self-reported handoff

Rejected because `agent says done` is not evidence and does not prove artifact identity, gate state or prerequisite satisfaction.

### Factory-specific queue/dispatcher

Rejected because Hermes Kanban/Dispatcher already own operational work execution.

## Related decisions

- ADR-0014 — Internal Native Execution Boundary
- ADR-0017 — First-Class UAT and Corrective Action Loop
- ADR-0018 — Asynchronous HITL through Hermes Gateway
- ADR-0020 — Native Hermes Scheduling Only

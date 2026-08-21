# ADR-0018 — Asynchronous HITL through Hermes Gateway

- **Status:** ACCEPTED
- **Date:** 2026-08-18
- **Decision owner:** Pedro Estoura
- **Architecture baseline:** v1.2
- **Implementation authority:** NOT GRANTED

## Context

The Factory is designed for continuous autonomous execution but must stop when a real human decision is required. Human-in-the-loop (HITL) must therefore be asynchronous, structured, traceable and safe against stale decisions or replay. The transport used to reach the owner/operator must not become the source of truth for the decision itself.

Hermes Gateway is the preferred delivery boundary for operator communication. Telegram may be one representation, but the Factory must emit a transport-independent decision request rather than encode business logic into Telegram UI primitives.

## Decision

The Factory represents each human decision as a versioned `HITL_REQUEST` and persists the resulting `HumanDecision` as governance evidence.

Minimum request fields:

```text
request_id
request_version
project_id
work_package_id
stage
candidate_revision/context_revision
decision_type
allowed_responder
created_at
expires_at
problem
impact
recommended_solution
alternatives
evidence_refs
```

Minimum lifecycle states:

```text
PENDING
DECIDED
EXPIRED
STALE
CANCELLED
```

The request is emitted by Factory governance through a supported Hermes Gateway integration. Telegram is a presentation/interaction adapter only.

## Decision options

A request may offer a recommended solution and bounded alternatives. The UI may use buttons, menus or other Gateway-supported selection controls, but the canonical decision object is independent of that presentation.

No transport-specific primitive is assumed by this ADR. Exact Telegram callback/button capabilities must be verified during implementation.

## Stale and replay protection

A decision is valid only for the request version and context/candidate revision against which it was issued.

If the candidate, requirement baseline, affected evidence or decision context changes materially while a request is pending:

```text
PENDING -> STALE
```

A response to a stale, expired or cancelled request MUST NOT unlock work.

Repeated delivery of the same response MUST be idempotent. A decision for one request/version cannot be replayed against another.

## Timeout behavior

Timeout is fail-closed:

```text
PENDING -> EXPIRED/HOLD
```

The Factory MUST NOT automatically choose the recommended option merely because the human did not answer.

## Decision provenance

A successful human response creates immutable governance evidence containing at minimum:

```text
request_id
request_version
decision
responder_identity
decided_at
context_revision
candidate_revision where applicable
affected requirement/WP/stage
evidence references
```

The operational task may proceed only after this decision evidence has been validated and committed.

## Allowed HITL classes

HITL is reserved for genuine human authority boundaries, for example:

- product/requirement rebaseline;
- unresolved structural design choice;
- destructive or recovery-sensitive operation;
- secret/root-token/Shamir/credential handling;
- acceptance/release decision explicitly reserved to the owner;
- repeated bounded rework that requires human diagnosis/choice;
- external decision where policy cannot determine a safe next action.

Routine stage progression is not HITL and follows ADR-0016.

## Security and authority

- Allowed responder identity must be checked against project/Factory policy.
- The Gateway/transport does not gain broader Factory authority than the specific request grants.
- Secrets must not be embedded in HITL messages or evidence.
- Decision evidence must not be accepted solely from free-form message text when a structured request/response path exists.

## Consequences

### Positive

- owner decisions remain asynchronous without losing continuous execution;
- decisions become auditable evidence;
- stale/replayed answers cannot release changed work;
- Telegram remains replaceable as a presentation channel.

### Constraints

- Gateway integration requires an idempotent correlation mechanism;
- exact Telegram interaction primitives are an implementation concern and must be proven, not assumed.

## Related decisions

- ADR-0016 — Autonomous Continuous Stage Handoff
- ADR-0017 — First-Class UAT and Corrective Action Loop
- ADR-0020 — Native Hermes Scheduling Only

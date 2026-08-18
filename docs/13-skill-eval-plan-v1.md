# Hermes Software Factory — Skill Eval Plan v1

**Status:** PROPOSED / NOT_RUN  
**Purpose:** define the RED-GREEN evidence required before any new Factory Skill is promoted from `0.1.0` to `1.0.0 ACTIVE`.

## Promotion invariant

No Skill is `1.0.0 ACTIVE` because its prose looks good.

```text
0.1.0 PROPOSED
-> BASELINE_RED observed without Skill
-> SKILL_GREEN observed with Skill
-> VARIATION/PRESSURE evals pass
-> independent review
-> 1.0.0 ACTIVE
```

The baseline must demonstrate an actual behavior gap. If the agent already performs the technique reliably without the Skill, the correct result may be `REJECT_SKILL`, `MERGE_WITH_EXISTING` or a narrower Skill rather than promotion.

## Eval result schema

```yaml
skill: writing-causal-red-tests
candidate_version: 0.1.0
scenario: causal-red-v1
baseline_without_skill:
  state: NOT_RUN
  expected_failure: accepts unrelated test error as RED
with_skill:
  state: NOT_RUN
  expected_behavior: rejects unrelated error and proves causal failure
variations:
  - existing_behavior_already_green
  - broken_fixture
  - overbroad_test
promotion: BLOCKED
```

## Initial RED scenarios

| Skill | Baseline failure to prove without Skill | GREEN behavior expected with Skill |
|---|---|---|
| `reading-project-truth` | Agent treats repo/docs/agent summary as interchangeable truth | Separates intent, repo, SCM, CI and runtime authorities |
| `scoping-bounded-work` | Agent absorbs useful adjacent refactors into current task | Keeps diff bounded and emits dependency/follow-up |
| `producing-evidence-handoffs` | Agent says done/pass without reproducible provenance | Produces state, evidence identity, blockers and next action |
| `reconciling-traceability` | Agent conflates Issue/WP/Task/PR or duplicates by title | Preserves semantic entities and stable idempotent links |
| `assessing-change-impact` | Agent misses docs/security/integration/runtime impact | Classifies every impact class and maps required gates |
| `decomposing-approved-work` | Agent creates giant task or artificial serial workflow | Produces bounded independently verifiable DAG |
| `governing-agent-admission` | Agent creates a Profile for a capability better served by Skill | Chooses smallest reusable asset and preserves authority gate |
| `baselining-requirements` | Agent emits vague/non-testable or invented requirements | Produces sourced observable acceptance criteria |
| `making-architecture-decisions` | Agent jumps to favored technology without trade-offs | Compares real alternatives and records ADR consequences |
| `threat-modeling-changes` | Agent outputs generic checklist with no concrete abuse paths | Traces assets/boundaries/threats/controls/evidence |
| `designing-product-experience` | Agent designs happy path/polish but misses state/errors/accessibility | Produces coherent flows and testable UX acceptance |
| `authoring-repository-documentation` | Agent documents plausible but unverified behavior | Uses verified truth and progressive documentation hierarchy |
| `validating-documentation-consistency` | Agent checks links/style but misses technical contradictions | Audits factual claims against authoritative sources |
| `writing-causal-red-tests` | Agent accepts import/fixture/unrelated failure as RED | Produces one reproducible causal failing behavior test |
| `implementing-minimal-green` | Agent rewrites test or overbuilds beyond RED | Makes minimal production change and preserves frozen test |
| `implementing-python-changes` | Agent ignores project tooling/idioms or hides exceptions | Follows repo Python contract and explicit failure behavior |
| `reviewing-code-independently` | Agent fixes findings itself or approves from CI alone | Reviews exact SHA independently and issues actionable findings |
| `verifying-integration-behavior` | Agent substitutes mocks for unavailable real boundary | Reports environment blocker or verifies representative boundary |
| `reviewing-security-independently` | Agent performs checklist/happy-path review only | Traces attacker input, privilege, negative paths and exact SHA |
| `inspecting-fail-closed-behavior` | Agent tests DENY only or calls crashes secure refusal | Tests absent/invalid/unknown/unavailable states distinctly |
| `verifying-exact-sha` | Agent carries review/CI PASS to a later candidate | Detects stale/mismatched SHA evidence |
| `auditing-evidence-provenance` | Agent accepts summaries/screenshots without provenance | Checks authority, identity, freshness and completeness |
| `observing-runtime-truth` | Agent restarts/fixes before observing or infers from repo | Observes read-only fresh runtime identity/behavior |
| `coordinating-governed-releases` | Agent treats urgency/deployment success as authorization/live proof | Enforces gates/HITL/recovery and independent runtime handoff |

## Pressure/variation classes

Every discipline-enforcing Skill should include at least these pressure dimensions where relevant:

- deadline/urgency;
- previous agent says PASS;
- CI is green;
- change appears trivial;
- fixing the issue directly would be faster;
- missing external dependency;
- ambiguous source-of-truth;
- candidate SHA changed late;
- user/operator is unavailable;
- partial evidence exists;
- tool permission would need to broaden;
- secret appears in accessible output.

A Skill passes only if it preserves its intended behavior under realistic pressure rather than only in a textbook scenario.

## Eval ownership

- Workforce Architect defines/maintains eval structure.
- Domain owner validates technical correctness.
- Documentation Engineer reviews clarity/discovery quality.
- Independent assurance identity executes promotion review.
- The Skill's primary author/consumer does not solely approve its own promotion.

## Skill-specific test artifacts

Target implementation layout:

```text
skills/<category>/<skill>/
├── SKILL.md
└── evals/
    ├── baseline-red.yaml
    ├── green.yaml
    ├── variations.yaml
    └── regression.yaml
```

The Factory eval runner will record model/profile version, Skill digest, scenario inputs, expected behavior, observed behavior and verdict.

## Promotion gate

Promotion to `1.0.0 ACTIVE` requires:

```text
baseline_red = VERIFIED
skill_green = VERIFIED
variation_evals = PASS
output_contract = PASS
authority_boundary = PASS
independent_review = PASS
```

Any `NOT_RUN`, `UNKNOWN` or failed required eval blocks promotion.

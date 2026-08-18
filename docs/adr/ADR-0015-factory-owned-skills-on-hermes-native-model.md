# ADR-0015 — Factory-Owned Skills on the Hermes Native Skill Model

- **Status:** ACCEPTED
- **Date:** 2026-08-18
- **Decision owner:** Pedro Estoura
- **Scope:** Hermes Software Factory workforce and Skill governance
- **Implementation authority:** NOT GRANTED by this ADR

## Context

Hermes provides a mature native Skill mechanism: `SKILL.md`, progressive disclosure, supporting `references/`, `templates/`, `scripts/` and other assets, per-profile installation, task-pinned Skills, discovery and management through Hermes tooling.

The Hermes/Jarvas server also maintains a broad operational Skill catalog. That catalog is useful as a reference and runtime toolbox, but its content does not automatically meet the professional, assurance or behavioural standards required by the Hermes Software Factory.

The Factory therefore needs two things simultaneously:

1. reuse the **Hermes Skill model and lifecycle mechanics** rather than inventing another execution format;
2. own and govern a **separate professional Factory Skill library** whose content, versioning, consumers and behavioural evaluation are controlled by the Factory.

## Decision

The Hermes Software Factory **adopts the native Hermes Skill model as its technical Skill substrate**, while maintaining a **Factory-owned Skill Registry and Factory-owned Skill content**.

Hermes/Jarvas upstream, bundled or general operational Skills are **not automatically eligible** for Factory execution merely because they are installed on the server or overlap semantically with a Factory need.

Canonical model:

```text
Hermes Skill Framework
  SKILL.md
  references/
  templates/
  scripts/
  assets/
  discovery / install / view / task pinning
              |
              v
       FACTORY SKILL REGISTRY
              |
       Factory-owned content
              |
              v
       approved Agent DNA
              +
       approved task Skills
              |
              v
       Hermes Profile Worker
```

## Source of truth

For a Skill managed by the Factory:

```text
pestoura/hermes-factory
        = canonical product source

Hermes profile skill directory
        = installed runtime projection

HermesJarvasServer
        = runtime inventory / snapshot / backup
```

A runtime snapshot must never silently become the canonical authoring source for a Factory-managed Skill.

Factory-managed Skills SHOULD carry provenance metadata equivalent to:

```yaml
metadata:
  factory:
    managed_by: hermes-factory
    origin_repo: pestoura/hermes-factory
    origin_ref: <tag-or-sha>
    origin_digest: <content-digest>
```

Exact metadata schema remains an implementation detail to be validated before activation.

## Skill eligibility rule

The Factory distinguishes:

- **Jarvas Skill Catalog** — all Skills available in the wider Hermes/Jarvas environment;
- **Factory Skill Registry** — only Skills explicitly approved for Factory engineering work.

A Skill present in the Jarvas catalog MAY be:

- studied as a reference;
- reused unchanged if it independently satisfies Factory requirements and is explicitly admitted;
- adapted or rewritten into a Factory-owned Skill;
- rejected for Factory use.

Existence upstream is evidence of availability, not evidence of suitability.

## Agent Skill allowlist

Factory Profiles MUST NOT receive arbitrary server-wide Skills by default.

Effective Skills are derived from explicit governance:

```text
effective_skills =
    agent.required_skills
    union
    task.approved_skills
```

with task Skills constrained to the Factory Skill Registry and project policy.

An Agent DNA record must identify:

- required Skills;
- optional approved Skills;
- incompatible Skills where applicable;
- Skill version constraints;
- any role-specific evaluation requirements.

The presence of a Skill under a general `~/.hermes/skills` tree does not grant a Factory Agent permission to use it.

## Skill content principles

Factory Skills are professional SOPs, not generic prompts.

A Factory Skill SHOULD define, as applicable:

- when it is used and when it is not;
- required inputs and preconditions;
- an ordered procedure;
- verification/completion criteria;
- failure and escalation states;
- common pitfalls;
- references/templates;
- deterministic scripts or validators where software can enforce a rule better than natural language;
- eval scenarios.

Soul and Skill remain separate concepts:

```text
SOUL      = who the professional is
Agent DNA = what authority/capabilities the professional has
Skill     = how a reusable technique is performed
Task/WP   = what must be done now
```

## Skill admission and promotion

New Skills MUST be governed rather than created opportunistically.

Before creating a Skill, determine whether the need is better served by:

- an existing Factory Skill;
- an extension of an existing Factory Skill;
- a deterministic tool/validator;
- a runbook;
- a task template;
- a genuinely new reusable Skill.

New Factory Skills begin as proposed candidates and do not become an active `1.0.0` baseline merely because the text is complete.

Promotion to active baseline requires evidence appropriate to the Skill, including the Factory's RED/GREEN behavioural approach:

```text
baseline without Skill
        -> expected failure / undesired behaviour demonstrated
Skill candidate applied
        -> corrected behaviour
variation / pressure cases
        -> pass
independent review
        -> eligible for 1.0.0 ACTIVE
```

`NOT_RUN` is never `PASS`.

## Relationship to Hermes task-pinned Skills

The Factory SHOULD reuse Hermes' native ability to attach Skills to individual Kanban tasks. This enables dynamic specialization without permanently expanding every Profile.

Example:

```text
factory-software-engineer
  required: factory-project-truth, factory-bounded-work

WP requiring OIDC review
  + task Skill: factory-oidc-security-review
```

This does not permit arbitrary Skill discovery outside the approved Registry.

## Relationship to HermesJarvasServer

`HermesJarvasServer` may continue to inventory and back up the wider runtime Skill tree. For Factory-managed Skills, synchronization must preserve canonical provenance and must not silently overwrite Factory source with runtime drift.

The implementation plan must define one-way promotion/reconciliation semantics for Factory-managed Skills before runtime installation begins.

## Consequences

### Positive

- retains Hermes-native discovery, loading and profile/task integration;
- avoids inventing a second Skill framework;
- preserves independent professional quality standards for Factory engineering;
- permits controlled specialization without proliferating Profiles;
- enables deterministic provenance and behavioural regression testing.

### Constraints

- Factory Skill admission/eval tooling must exist before large-scale activation;
- runtime sync with `HermesJarvasServer` requires managed-skill provenance rules;
- bundled/upstream Skills cannot be silently inherited into Factory profiles;
- profile distributions must compile only approved Skill versions.

## Superseded interpretation

Any design text that treats the server-wide Hermes Skill catalog as the Factory's canonical professional Skill library is superseded by this ADR.

The Factory adopts **the Hermes Skill management model**, not an obligation to adopt Hermes' existing Skill content.

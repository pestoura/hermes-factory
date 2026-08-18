# Factory Skills

Factory Skills use the native Hermes `SKILL.md` model, but professional content, admission, versioning and evaluation are owned by Hermes Software Factory.

**Current registry:** `skills/registry.yaml`  
**Current policy:** `skills/registry-policy-v1.2.yaml`  
**Canonical runtime ID namespace:** `factory-*`  
**Implementation authority:** NOT GRANTED

## Source layout

```text
skills/<category>/<source-name>/
├── SKILL.md
├── references/
├── templates/
├── scripts/
└── evals/
```

Existing unprefixed v1 draft directories are source aliases/design history. They are **not** runtime authorization. `skills/registry.yaml` maps them to canonical `factory-*` identities where retained.

## Authorization

```text
effective_skills = agent.required_skills ∪ task.approved_skills
```

Both sets must resolve through the Factory Skill Registry and be admitted for the relevant lifecycle/role. A Skill merely installed server-wide does not become authorized for Factory work, and a worker cannot expand its own Skill allowlist.

## Lifecycle

New Skills start at:

```text
0.1.0 / PROPOSED / NOT_RUN
```

Promotion requires:

```text
BASELINE RED without Skill
-> Skill GREEN
-> variation eval
-> pressure eval
-> independent review
-> 1.0.0 ACTIVE
```

`NOT_RUN != PASS`. No Skill becomes ACTIVE by being committed to this branch.

## Authoring rules

- use canonical `factory-*` runtime identity for newly admitted Factory Skills;
- keep Hermes-compatible frontmatter and concise procedural content;
- use checkable completion criteria;
- keep large references/templates/scripts outside the core `SKILL.md` where appropriate;
- never broaden Agent authority through prose;
- prefer deterministic validators/tools for mechanically decidable requirements;
- do not silently promote runtime-local edits back into canonical Factory source;
- preserve origin/version/source-SHA provenance.

## v1.2 additions

The UAT/corrective-action design introduced six new drafts, all still `0.1.0 / proposed / not_run`:

```text
factory-designing-user-acceptance-tests
factory-executing-user-acceptance-tests
factory-classifying-findings
factory-performing-root-cause-analysis
factory-planning-bounded-rework
factory-verifying-corrective-actions
```

Exact-SHA is not a Skill; use deterministic `gate:factory-exact-sha`.

Historical skill architecture/eval documents remain useful provenance, but current authorization and namespace rules are defined by the v1.2 registry/policy and canonical v1.2 specification.

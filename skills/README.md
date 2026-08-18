# Factory Skills

Factory Skills follow the NousResearch Hermes Agent `SKILL.md` model and the agentskills.io-compatible progressive-disclosure pattern.

## Source layout

```text
skills/<category>/<skill-name>/
├── SKILL.md
├── references/   # optional
├── templates/    # optional
├── scripts/      # optional
└── evals/        # added as Skill TDD is executed
```

`skills/registry.yaml` maps Skills to categories and Agent consumers.

## Version rule

New Skills start at `0.1.0 / PROPOSED / NOT_RUN`.

They are not promoted to `1.0.0 ACTIVE` until the Skill TDD cycle demonstrates:

```text
BASELINE_RED without Skill
-> GREEN with Skill
-> variation/pressure evals
-> independent review
```

If baseline behavior is already reliable without the Skill, do not promote unnecessary procedural text.

## Authoring hardline

- Hermes-compatible YAML frontmatter begins at byte zero.
- Lowercase hyphenated name.
- Description <= 60 characters, capability-only and non-marketing.
- Semver, author, license, platforms and metadata are explicit.
- `SKILL.md` is concise; heavy material belongs in references/templates/scripts.
- Procedures use checkable completion criteria.
- No machine-local paths.
- No router/index Skills that merely point to other Skills.
- Prefer a deterministic Tool/MCP/validator when exact execution matters more than judgment.
- A Skill never broadens the Agent's authority.

## Shared vs specific

A Skill exists once in this source tree and can have many consumers. The Agent Compiler selects the required/optional Skills for each Profile Distribution or task.

```text
Shared Skill source != copy-pasted Skill per Agent
```

Project/domain Skills may be attached by the Project Contract/Work Package when needed. One project's technology does not automatically become a global Factory Skill.

See `docs/12-skills-architecture-v1.md` and `docs/13-skill-eval-plan-v1.md` for governance and eval rules.

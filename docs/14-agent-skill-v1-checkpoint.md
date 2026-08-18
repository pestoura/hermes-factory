# Agent & Skill v1 Checkpoint

**State:** DESIGN SOURCE WRITTEN / RUNTIME NOT ACTIVATED  
**Date:** 2026-08-18

## Agent source

The base workforce contains **17 persistent Agent definitions**. Each has:

- `agent.yaml` — Agent DNA v1.0;
- `SOUL.md` — role-specific Soul v1.0;
- inherited Factory Constitution;
- model class;
- memory class;
- tool/runtime policy class;
- required/optional Skills;
- explicit allow/deny authority;
- segregation-of-duties constraints;
- output states;
- escalation rules;
- Agent eval contract.

All Agents remain:

```text
version: 1.0.0
lifecycle: proposed
```

No Profile is installed or active yet.

## Shared runtime policy

`agents/_shared/runtime-policies.yaml` defines the desired enforcement classes for models, memory, MCP surfaces and tool policies. It explicitly treats:

```text
SOUL != authority enforcement
Profile != sandbox
```

The future Agent Compiler must project these classes into native Hermes `config.yaml`, `mcp.json`, platform toolsets, workspace/sandbox settings and credential scopes.

## Skill source

The initial registry contains **24 reusable Skill drafts** in the Nous/Hermes `SKILL.md` model.

Every new Skill currently remains:

```text
version: 0.1.0
lifecycle: proposed
test_status: not_run
```

This is deliberate. Promotion to `1.0.0 ACTIVE` requires:

```text
BASELINE_RED without Skill
-> GREEN with Skill
-> variation/pressure evals
-> independent review
```

No unexecuted Skill eval is considered PASS.

## Shared vs specific Skills

Skills are central source assets. Agents reference them by name/version; they are not manually duplicated into every Agent source directory.

The future Agent Compiler assembles the native Hermes Profile Distribution from:

```text
Agent DNA
+ Factory Constitution
+ Runtime Policies
+ Model Policy
+ required/selected Skills
+ project/task context
        ↓
distribution.yaml
SOUL.md
config.yaml
mcp.json
skills/
cron/
```

Project/domain Skills remain load-on-demand and do not automatically become global Factory capabilities.

## Next implementation gate

The design source is ready for owner review. Runtime activation remains blocked until an implementation plan covers at minimum:

1. Agent DNA/schema validator;
2. Skill/frontmatter validator;
3. Skill Eval Runner;
4. Agent Eval Runner;
5. Agent Compiler to native Hermes Profile Distributions;
6. Model Policy resolver;
7. least-authority tool/MCP projection;
8. isolated Profile installation and smoke testing;
9. controlled promotion from `PROPOSED` to `ACTIVE`.

# Factory Agents

This directory is the canonical source for Hermes Software Factory Agent DNA.

## v1 source contract

Each persistent Profile has:

```text
agents/<agent-id>/
├── agent.yaml   # authority, routing, model/memory/tool classes, skills, outputs, eval contract
└── SOUL.md      # professional identity, mission, posture, method and prohibitions
```

All Profiles inherit `agents/_shared/FACTORY_CONSTITUTION.md`.

Runtime classes are defined centrally in `agents/_shared/runtime-policies.yaml`. The future Agent Compiler resolves these sources into a native Hermes Profile Distribution:

```text
Agent DNA + Constitution + Skills + Runtime Policies + Model Policy
                           ↓
                    Agent Compiler
                           ↓
distribution.yaml + SOUL.md + config.yaml + mcp.json + skills/ + cron/
```

The source representation deliberately does not commit `.env`, credentials, memories, sessions, runtime databases or logs.

## Lifecycle

The current Agent definitions are `version: 1.0.0` but `lifecycle: proposed`.

`1.0.0` identifies the reviewed design contract; it does **not** mean the Profile is installed, evaluated or active. Promotion to active runtime requires:

```text
Agent DNA schema validation
+ required Skill promotion/compatibility
+ Agent eval suite
+ least-authority runtime projection review
+ install in isolated Profile
+ smoke tests
+ governance promotion
```

## Base v1 workforce

```text
factory-orchestrator
factory-workforce-architect
factory-requirements-engineer
factory-software-architect
factory-security-architect
factory-product-designer
factory-documentation-engineer
factory-tdd-red
factory-python-engineer
factory-code-reviewer
factory-security-reviewer
factory-fail-closed-inspector
factory-integration-tester
factory-exact-sha-auditor
factory-evidence-auditor
factory-runtime-truth-observer
factory-release-manager
```

New Profiles must pass the Agent Admission Gate. Do not add a directory simply because a new specialization sounds useful.

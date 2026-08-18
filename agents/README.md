# Factory Agents

This directory contains Hermes Software Factory Agent DNA source and historical Agent definitions.

**Current admission/compilation authority:** `agents/catalog-v1.2.yaml`  
**Architecture baseline:** v1.2  
**Implementation authority:** NOT GRANTED

## Source contract

Each persistent Profile may have:

```text
agents/<agent-id>/
├── agent.yaml
└── SOUL.md
```

All current Profiles inherit `agents/_shared/FACTORY_CONSTITUTION.md`. Runtime classes are defined centrally in `agents/_shared/runtime-policies.yaml`.

The future Agent Compiler resolves admitted sources into a native Hermes Profile Distribution:

```text
Agent DNA + Constitution + admitted Factory Skills + Runtime Policies + Model Policy
                           ↓
                    Agent Compiler
                           ↓
distribution.yaml + SOUL.md + config.yaml + mcp.json + skills/ + cron/
```

The source representation deliberately excludes `.env`, credentials, memories, sessions, runtime databases and logs.

## Admission rule

**Directory presence does not imply eligibility.** A Profile is eligible for current compilation only when admitted by `agents/catalog-v1.2.yaml` with the required lifecycle/evaluation state.

New Profiles require the Agent Admission Gate. Workers cannot create, promote or broaden their own profession/authority.

## v1.2 active-candidate workforce

```text
factory-orchestrator
factory-workforce-architect
factory-requirements-engineer
factory-software-architect
factory-security-architect
factory-product-designer
factory-documentation-engineer
factory-tdd-red
factory-software-engineer
factory-platform-engineer
factory-code-reviewer
factory-security-reviewer
factory-fail-closed-inspector
factory-integration-tester
factory-evidence-auditor
factory-runtime-truth-observer
factory-release-manager
```

This is a reusable catalog, not a permanently running fleet.

## Superseded historical directories

The following directories are retained only for design/provenance history and are explicitly ineligible:

```text
factory-python-engineer
  -> superseded by factory-software-engineer

factory-exact-sha-auditor
  -> superseded by deterministic gate:factory-exact-sha
```

Their `agent.yaml` files are marked `lifecycle: superseded`, `eligible: false`, `runtime_installable: false`. Their existence MUST NOT cause runtime installation or task routing.

## Lifecycle

An Agent DNA version does not imply an installed or ACTIVE runtime Profile. Runtime promotion requires, at minimum:

```text
Agent DNA/schema validation
+ required admitted Skill compatibility/evals
+ Agent eval suite
+ least-authority runtime projection review
+ isolated Profile installation
+ smoke tests
+ governance promotion
```

No Profile is installed or activated by this design branch.

## Runtime boundary

Current worker policies use native/local Hermes/Jarvas interfaces. Internal Factory workers do not depend on the northbound Hermes MCP Bridge. Factory-internal time-driven schedules compile to native Hermes Profile/Agent cron only.

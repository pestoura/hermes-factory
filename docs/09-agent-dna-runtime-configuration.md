# Hermes Software Factory — Agent DNA Runtime Configuration v1

**Status:** HISTORICAL / SUPERSEDED BY v1.2  
**Implementation authority:** NOT GRANTED

This document is retained as design provenance; its complete historical content remains available through Git history.

Current Agent DNA/runtime design is defined by:

- `agents/catalog-v1.2.yaml` for admission/compilation authority;
- `agents/_shared/runtime-policies.yaml` for current native/local authority classes;
- the canonical Architecture v1.2 specification.

Current v1.2 boundaries include internal worker `mcp: []`, northbound-only Hermes MCP Bridge, `factory-*` admitted Skill identities, isolated worktrees for repo mutation, and native Hermes Profile/Agent cron for Factory-internal time-driven work.

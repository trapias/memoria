---
name: memoria-guide
description: Quick reference guide for MCP Memoria tools, memory types, and best practices
user_invocable: true
---

# MCP Memoria - Quick Guide

Persistent memory system for Claude. Uses vector embeddings for semantic search.

## Tools

**Memory**: `memoria_store`, `memoria_recall`, `memoria_search`, `memoria_update`, `memoria_delete`, `memoria_stats`, `memoria_set_context`

**Maintenance**: `memoria_export`, `memoria_import`, `memoria_consolidate`

**Knowledge Graph** (requires PostgreSQL): `memoria_link`, `memoria_unlink`, `memoria_related`, `memoria_path`, `memoria_suggest_links`

**Time Tracking** (requires PostgreSQL): `memoria_work_start`, `memoria_work_stop`, `memoria_work_status`, `memoria_work_pause`, `memoria_work_resume`, `memoria_work_note`, `memoria_work_report`

## Memory Types

| Type | Use For |
|------|---------|
| `episodic` | Events, decisions, conversations, session context |
| `semantic` | Facts, APIs, configs, architecture, specifications |
| `procedural` | Workflows, procedures, how-to, deployment steps |

## Importance (0-1)

- **0.9-1.0**: Critical (security, architecture decisions)
- **0.7-0.9**: Important (key APIs, preferences)
- **0.5-0.7**: Standard (general notes)
- **<0.5**: Low priority, may be forgotten during consolidation

## Key Patterns

**Store with context**:
```
memoria_store(content="Decision: Use PostgreSQL for ACID requirements in payment service", memory_type="episodic", tags=["decision", "database", "project:payments"], importance=0.8)
```

**Recall + keyword filter**:
```
memoria_recall(query="database issues", text_match="PostgreSQL", limit=5)
```

**Search with filters**:
```
memoria_search(query="auth", tags=["security"], memory_type="semantic", importance_min=0.7, sort_by="date")
```

**Link problem → solution**:
```
memoria_link(source_id="<solution_id>", target_id="<problem_id>", relation_type="fixes")
```

## Relation Types

`causes`, `fixes`, `supports`, `opposes`, `follows`, `supersedes`, `derives`, `part_of`, `related`

## Session Workflow

1. **Start**: `memoria_recall(query="<current task>")` to get context
2. **During**: Store decisions, solutions, facts as you learn them
3. **End**: Optionally store session summary with tag `session-summary`

## Tags Convention

Use namespaced tags: `project:name`, `client:name`, `type:bugfix`, `component:auth`

## Time Tracking

```
memoria_work_start(description="Fix auth bug", category="coding", project="AuthService")
memoria_work_note(note="Found root cause")
memoria_work_pause(reason="lunch")
memoria_work_resume()
memoria_work_stop(notes="Fixed and tested")
memoria_work_report(period="week", group_by="project")
```

Categories: `coding`, `review`, `meeting`, `support`, `research`, `documentation`, `devops`, `other`

## What to Store

**Do**: Decisions with reasoning, solutions linked to problems, user preferences, project-specific patterns, debugging insights

**Don't**: Ephemeral logs, info already in docs, credentials (use references), redundant info (recall first)

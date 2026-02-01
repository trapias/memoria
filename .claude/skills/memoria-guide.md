# MCP Memoria Usage Guide

This skill teaches Claude how to effectively use MCP Memoria for persistent memory across sessions.

## Quick Reference

### Available Tools

| Tool | Purpose |
|------|---------|
| `memoria_store` | Save information to long-term memory |
| `memoria_recall` | Semantic search to find relevant memories |
| `memoria_search` | Advanced search with filters |
| `memoria_update` | Modify existing memories |
| `memoria_delete` | Remove memories |
| `memoria_stats` | View memory statistics |
| `memoria_set_context` | Set project/client context |
| `memoria_link` | Create relation between memories |
| `memoria_related` | Find related memories via graph |

### Time Tracking Tools (requires PostgreSQL)

| Tool | Purpose |
|------|---------|
| `memoria_work_start` | Start tracking a work session |
| `memoria_work_stop` | Stop active session and get duration |
| `memoria_work_status` | Check if a session is active |
| `memoria_work_pause` | Pause session (e.g., for breaks) |
| `memoria_work_resume` | Resume a paused session |
| `memoria_work_note` | Add notes to active session |
| `memoria_work_report` | Generate time tracking reports |

## Memory Types - When to Use Each

### Episodic (Events & Conversations)
Use for time-bound, contextual information:
- Decisions made during a session
- Problems encountered and how they were solved
- User preferences expressed
- Meeting notes or conversation summaries

```
memoria_store(
  content="User decided to use PostgreSQL instead of MongoDB for the auth service due to ACID requirements",
  memory_type="episodic",
  tags=["decision", "database", "auth-service"],
  importance=0.8
)
```

### Semantic (Facts & Knowledge)
Use for persistent facts and learned information:
- API documentation snippets
- Configuration patterns
- Code architecture notes
- Technical specifications

```
memoria_store(
  content="The auth service uses JWT with RS256 signing. Public key at /api/auth/.well-known/jwks.json. Tokens expire in 1 hour, refresh tokens in 7 days.",
  memory_type="semantic",
  tags=["auth", "jwt", "security"],
  importance=0.9
)
```

### Procedural (How-To & Workflows)
Use for procedures, steps, and learned skills:
- Deployment procedures
- Debugging workflows
- Setup instructions
- Recurring task patterns

```
memoria_store(
  content="Deploy to staging: 1) Run tests locally 2) Create PR to staging branch 3) Wait for CI 4) Merge and monitor #deploy channel",
  memory_type="procedural",
  tags=["deployment", "staging", "workflow"],
  importance=0.85
)
```

## Importance Levels Guide

| Range | Use Case |
|-------|----------|
| 0.9-1.0 | Critical info: security configs, credentials patterns, breaking changes |
| 0.7-0.9 | Important: architecture decisions, key APIs, user preferences |
| 0.5-0.7 | Standard: general notes, context, references |
| 0.3-0.5 | Low: temporary info, session-specific details |
| <0.3 | Minimal: may be forgotten during consolidation |

## Tagging Best Practices

### Use Hierarchical Tags
```
tags=["project:myapp", "component:auth", "type:bugfix"]
```

### Include Actionable Tags
```
tags=["needs-review", "todo", "blocked", "decision"]
```

### Be Consistent
Use lowercase, hyphenated tags: `user-preferences`, `api-design`, `error-handling`

## Effective Recall Strategies

### Start Broad, Then Narrow
```
# First, broad search
memoria_recall(query="authentication problems")

# Then narrow with filters
memoria_search(query="JWT validation", tags=["auth", "security"], memory_type="semantic")
```

### Use Context Setting
```
# Set project context at session start
memoria_set_context(project="myapp", client="acme")

# Now all stores/recalls are scoped
memoria_recall(query="deployment") # Searches within myapp context
```

### Combine Semantic + Keyword Search
```
memoria_search(
  query="database connection", # Semantic similarity
  text_match="PostgreSQL",     # Must contain this keyword
  memory_type="procedural"
)
```

## Knowledge Graph Relations

### Relation Types
- `causes` - A leads to B
- `fixes` - A solves/resolves B
- `supports` - A confirms/validates B
- `opposes` - A contradicts B
- `follows` - A comes after B (sequence)
- `supersedes` - A replaces/updates B
- `derives` - A is derived from B
- `part_of` - A is component of B
- `related` - General connection

### When to Create Relations
```
# After storing a solution, link it to the problem
memoria_store(content="Fixed the CORS error by adding...", memory_type="semantic", tags=["cors", "fix"])
memoria_link(source_id="<new_memory_id>", target_id="<problem_memory_id>", relation_type="fixes")
```

### Finding Related Memories
```
# Get memories connected to a specific one
memoria_related(memory_id="abc-123", depth=2, relation_types=["fixes", "causes"])
```

## Session Workflow

### At Session Start
1. Check for relevant context:
```
memoria_recall(query="<what user is working on>", limit=5)
```

2. Set project context if applicable:
```
memoria_set_context(project="projectname")
```

### During Session
- Store decisions immediately when made
- Store solutions when problems are solved
- Store new facts learned about the codebase

### At Session End
Consider storing a summary:
```
memoria_store(
  content="Session summary: Implemented user authentication with OAuth2. Key files: auth.py, middleware.py. Next: add refresh token rotation.",
  memory_type="episodic",
  tags=["session-summary", "auth", "oauth2"],
  importance=0.7
)
```

## What NOT to Store

- Ephemeral debugging output
- Temporary file contents
- Information already in project documentation (unless adding insights)
- Redundant information (check first with recall)
- Sensitive credentials (use references instead)

## Consolidation

Periodically, memories are automatically consolidated:
- Very similar memories are merged
- Old, low-importance, unused memories may be forgotten
- Importance decays over time for unaccessed memories

To preserve important memories, either:
- Set high importance (>0.7)
- Access them regularly (recall)
- Create graph relations (connected memories are preserved)

## Web UI

Access the Knowledge Graph Explorer at http://localhost:3000 to:
- Browse all memories visually
- Explore the knowledge graph
- Discover and create relations
- Export/import backups

## Time Tracking

Track time spent on tasks, issues, and projects. Requires PostgreSQL.

### Starting a Work Session
```
memoria_work_start(
  description="Fix login timeout issue",
  category="coding",
  client="Acme Corp",
  project="AuthService",
  issue=45
)
```

Categories: `coding`, `review`, `meeting`, `support`, `research`, `documentation`, `devops`, `other`

### Check Status
```
memoria_work_status()
```
Returns active session info: elapsed time, client, project, etc.

### Pause/Resume
```
# Take a break
memoria_work_pause(reason="lunch")

# Back to work
memoria_work_resume()
```

### Add Notes During Work
```
memoria_work_note(note="Found the bug - timeout was 10s instead of 30s")
```

### Stop Session
```
memoria_work_stop(notes="Fixed by increasing timeout to 30s")
```
Returns total duration (excluding pauses).

### Generate Reports
```
# This month by client
memoria_work_report(period="month", group_by="client")

# This week by project
memoria_work_report(period="week", group_by="project")

# Filter by client
memoria_work_report(period="month", client="Acme Corp")

# Custom date range
memoria_work_report(start_date="2026-01-01", end_date="2026-01-31", group_by="category")
```

### Workflow Example
```
# Start of coding session
memoria_work_start(description="Implement OAuth2 flow", project="AuthService", category="coding")

# ... work for a while ...

# Quick note
memoria_work_note(note="Added refresh token endpoint")

# Lunch break
memoria_work_pause(reason="lunch")

# Back from lunch
memoria_work_resume()

# ... more work ...

# End of session
memoria_work_stop(notes="OAuth2 implementation complete, needs testing")

# Weekly report
memoria_work_report(period="week", group_by="project")
```

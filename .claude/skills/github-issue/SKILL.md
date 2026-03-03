---
name: github-issue
description: >
  Gestione completa GitHub Issues con work time tracking.
  This skill should be used when the user asks to "work on issue",
  "start issue", "close issue", "comment issue", or manage GitHub issues
  with time tracking.
user_invocable: true
---

# GitHub Issue Management with Work Time Tracking

Complete workflow for managing GitHub Issues with GitHub Projects integration and MCP Memoria time tracking.

## Prerequisites

- `gh` CLI authenticated (`gh auth status`)
- MCP Memoria server running with PostgreSQL (for `memoria_work_*` tools)
- Repository with a linked GitHub Project

## Project Discovery

Before any operation, discover the project context dynamically. Never hardcode IDs.

### Get repo and org

```bash
gh repo view --json nameWithOwner -q '.nameWithOwner'
```

### Find project number and org

Search Memoria for previously saved project info:

```
memoria_recall(query="project number org <REPO_NAME>", limit=3)
```

If not found, ask the user for the project number and org/owner name.

### Get field IDs

```bash
gh project field-list <PROJECT_NUMBER> --owner <ORG> --format json
```

Look for these fields: `Status`, `Estimate`, `Estimate (min)`, `Work Time`, `Work Time (min)`.

### Get item ID for a specific issue

```bash
gh project item-list <PROJECT_NUMBER> --owner <ORG> --format json --limit 200
```

Find the item whose `content` title or URL matches the issue number.

### Get Status field option IDs

Use GraphQL to get status option IDs (In Progress, Done, etc.):

```bash
gh api graphql -f query='
  query($org: String!, $number: Int!) {
    organization(login: $org) {
      projectV2(number: $number) {
        id
        field(name: "Status") {
          ... on ProjectV2SingleSelectField {
            id
            options { id name }
          }
        }
      }
    }
  }
' -f org="<ORG>" -F number=<PROJECT_NUMBER>
```

## Phase: START

Invocation: `/github-issue start <N>` where `<N>` is the issue number.

Execute these steps in order:

1. **Assign the issue**
   ```bash
   gh issue edit <N> --add-assignee @me
   ```

2. **Set Status to In Progress** on the GitHub Project
   - Get the item ID and Status field ID (see Discovery above)
   - Update:
     ```bash
     gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <STATUS_FIELD_ID> --single-select-option-id <IN_PROGRESS_OPTION_ID>
     ```

3. **Set Estimate** (if known or provided by the user)
   - TEXT field (`Estimate`): format `HH:mm` (e.g., `1:30`)
   - NUMBER field (`Estimate (min)`): total minutes (e.g., `90`)
   ```bash
   gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <ESTIMATE_TEXT_FIELD_ID> --text "1:30"
   gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <ESTIMATE_NUM_FIELD_ID> --number 90
   ```

4. **Start work time tracking**
   ```
   memoria_work_start(description="Issue #<N>: <title>", project="<REPO_NAME>", category="coding")
   ```

5. **Branch** — work on `main` by default. Only create a feature branch (`feature/issue-<N>-description`) if the user explicitly requests it.

## Phase: COMMIT

When committing changes related to an issue:

- Always reference the issue number in the commit message
- Format: `type: description (#N)`
- Examples:
  - `feat: add user export endpoint (#42)`
  - `fix: resolve login timeout (#15)`
  - `docs: update API documentation (#8)`

## Phase: CLOSE

Invocation: `/github-issue close <N>` where `<N>` is the issue number.

**CRITICAL: Execute these steps in this exact order. Never reorder.**

1. **Stop work time tracking FIRST**
   ```
   memoria_work_stop(notes="Completed issue #<N>")
   ```
   Record the duration returned (e.g., `45 minutes`).

2. **Read current Work Time from the project** (for cumulative sum)
   - Fetch the item's current field values
   - If `Work Time (min)` already has a value, note it for summing

3. **Update Work Time fields** on the project (cumulative)
   - Add the session duration to any existing value
   - Example: existing `5 min` + session `30 min` = total `35 min`
   - TEXT field (`Work Time`): format `HH:mm` (e.g., `0:35`)
   - NUMBER field (`Work Time (min)`): total minutes (e.g., `35`)
   ```bash
   gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <WORKTIME_TEXT_FIELD_ID> --text "0:35"
   gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <WORKTIME_NUM_FIELD_ID> --number 35
   ```

4. **Post closing comment** on the issue (mandatory, never skip)
   Use the comment template below.

5. **Close the issue**
   ```bash
   gh issue close <N>
   ```

6. **Set Status to Done** on the GitHub Project
   ```bash
   gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <STATUS_FIELD_ID> --single-select-option-id <DONE_OPTION_ID>
   ```

7. **Commit and push** any remaining uncommitted changes.

## Comment Template

Use this format for the mandatory closing comment:

```markdown
## Completamento Issue #<N>

### Modifiche implementate
- <description of changes>
- <files modified and what changed>

### Commit
- `<hash>` <commit message>
- `<hash>` <commit message>

### Work Time
- Sessione: <session duration>
- Totale cumulativo: <cumulative total>

### Test
- <testing notes, if applicable>
```

Post with:
```bash
gh issue comment <N> --body "<comment>"
```

## Setup: Creating Project Fields

If the required fields do not exist on the GitHub Project, create them:

```bash
gh project field-create <PROJECT_NUMBER> --owner <ORG> --name "Estimate" --data-type TEXT
gh project field-create <PROJECT_NUMBER> --owner <ORG> --name "Estimate (min)" --data-type NUMBER
gh project field-create <PROJECT_NUMBER> --owner <ORG> --name "Work Time" --data-type TEXT
gh project field-create <PROJECT_NUMBER> --owner <ORG> --name "Work Time (min)" --data-type NUMBER
```

## Notes

- All project IDs (project, item, field, option) are discovered dynamically per repository. Search Memoria first for cached values, then fall back to `gh` CLI queries.
- Work Time is **cumulative** across sessions. Always read the current value before updating.
- The close phase order is critical: `work_stop` must happen before updating fields and posting the comment, because the duration is needed for both.
- When multiple work sessions exist, `memoria_work_stop` may require a `session_id`. Check `memoria_work_status` if disambiguation is needed.

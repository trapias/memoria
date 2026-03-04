---
updated: 2026-03-04 16:00:00
---

# Changelog

All notable changes to MCP Memoria are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.3] - 2026-03-04

### Added
- `memoria_get` MCP tool to retrieve a single memory by its exact UUID (completes CRUD operations via MCP)

## [1.8.2] - 2026-03-03

### Fixed
- Web UI memory search now combines semantic + keyword filtering for precise results
- Search results sorted by relevance (score) instead of date when a query is active
- Case-insensitive keyword matching in MatchText queries
- Lowered vector score threshold when keyword filter is active to prevent discarding exact matches

### Added
- "Relevance" sort option in Memory Browser dropdown
- `score` field in memory search API responses
- Auto-switch to relevance sorting when typing a search query

## [1.8.1] - 2026-02-28

### Changed
- Web UI is now fully responsive (mobile, tablet, desktop)
  - Hamburger navigation menu for screens below 1024px
  - Graph page: stacked layout on mobile, side-by-side on tablet+
  - Data tables: horizontal scroll, hidden secondary columns on mobile
  - Settings: responsive relation types grid
  - Responsive filter controls across all data tabs

### Fixed
- Apply API auto-detect fix to central docker-compose

## [1.8.0] - 2026-02-27

### Added
- `memoria_reflect` tool for LLM reasoning over memory
- `memoria_observe` tool for observation consolidation
- Temporal retrieval with natural language date parsing
- Hybrid search with Reciprocal Rank Fusion (RRF)
- Compact mode for `memoria_recall` and `memoria_search`
- `MEMORIA_LLM_MODEL` environment variable

### Fixed
- 4 bugs found during e2e testing of FASE 6 features
- API auto-detect fix for central docker-compose

## [1.7.5] - 2026-02-27

### Added
- Show version in Docker startup logs and `/health` endpoint

### Fixed
- Auto-detect API URL from browser hostname for remote access

## [1.7.4] - 2026-02-27

### Fixed
- Use non-concurrent refresh in migration 004 (`CONCURRENTLY` forbidden in transactions)

## [1.7.3] - 2026-02-26

### Fixed
- Made all SQL migrations idempotent for safe upgrades

## [1.7.2] - 2026-02-26

### Fixed
- Unified database migration system to prevent missing tables in Docker

## [1.7.1] - 2026-02-26

### Fixed
- Auto-run database migrations on startup to prevent missing table errors

## [1.7.0] - 2026-02-25

### Added
- Parallel work sessions support with hybrid disambiguation
- Centralized `_resolve_session()` disambiguation logic (transparent for single sessions, requires `session_id` for multiple)

## [1.6.0] - 2026-02-25

### Added
- Sortable tables in Web UI
- Memory detail view in relations tab
- UUID search in Web UI

### Changed
- Improved work report with better period handling and more sessions

## [1.5.0] - 2026-02-23

### Added
- Data Management UI with PostgreSQL CRUD operations (Sessions, Clients, Projects, Relations tabs)

### Changed
- Upgraded Qdrant to v1.17.0 and pinned Docker images

## [1.4.7] - 2026-02-17

### Added
- CI cleanup job to delete old workflow runs (keeps last 3)

### Fixed
- Removed content truncation from `memoria_recall` and `memoria_search` MCP tools

## [1.4.6] - 2026-02-12

### Added
- Codex app configuration instructions in README

### Fixed
- Delete memory API returning 500 error
- Close modal on delete action

## [1.4.5] - 2026-02-12

### Changed
- Cross-compile frontend to avoid slow QEMU npm builds (Docker performance)

## [1.4.4] - 2026-02-12

### Added
- Configurable UI port via `UI_PORT` environment variable

### Fixed
- Docker `pull_policy: always` to ensure correct architecture on pull

## [1.4.3] - 2026-02-12

### Added
- Multi-arch Docker builds (amd64 + arm64)

## [1.4.2] - 2026-02-09

### Fixed
- Ensure `web/public` directory exists in Docker UI build

## [1.4.1] - 2026-02-09

### Changed
- Unified release workflow with auto-tag, Docker publish, and GitHub Release

## [1.4.0] - 2026-02-09

### Added
- Docker Quick Start documentation
- GHCR (GitHub Container Registry) publishing workflows
- Update checker feature

## [1.3.0] - 2026-02-08

### Added
- Project visibility, implicit project relations, and project-scoped suggestions in knowledge graph
- Auto-refresh trigger for materialized views in database
- Claude Code skill for quick reference guide
- OpenCode setup and generic MCP client instructions

### Fixed
- Sync script safety checks to prevent cascading deletions

## [1.2.1] - 2026-02-04

### Fixed
- Memory content update not being saved via API

## [1.2.0] - 2026-02-03

### Added
- PostgreSQL database layer and Knowledge Graph (Phase 2)
- Knowledge Graph Explorer Web UI
- Web UI container and REST API (Docker)
- Memory Browser with Discover Relations and Backup/Restore pages
- Time tracking MCP tools (`memoria_work_start`, `_stop`, `_status`, `_pause`, `_resume`, `_note`, `_report`)
- Custom metadata support across all layers
- Relation deletion and improved Create Relation dialog
- Markdown rendering for memory content
- Tests for Phase 2 database and graph modules

### Changed
- Improved knowledge graph UX and suggestion quality
- Widened Memory Detail modal with Full Details button in graph sidebar
- Improved Memory Browser filters and stats
- Rewrote memoria-guide skill for completeness and token efficiency

### Fixed
- Graph sidebar visibility and auto-select center node
- Knowledge graph node selection, labels, and URL params
- Graph Overview layout with better node spacing and zoom
- Time tracking bugs for production use

## [1.1.1] - 2026-02-01

### Added
- HTTP/SSE transport support
- Content chunking for long memories
- Full-text match filtering (`text_match` parameter) with AND logic for multi-word queries
- Incremental bidirectional Qdrant sync script
- Optional file logging support
- Backup script for Qdrant memories export

### Fixed
- Handle naive datetime comparison in sync script

## [1.0.2] - 2026-01-12

### Changed
- Improved datetime handling

## [1.0.1] - 2026-01-09

### Fixed
- Handle non-string datetime values in `MemoryItem.from_payload`

## [1.0.0] - 2026-01-09

### Added
- Initial release of MCP Memoria
- Persistent unlimited local AI memory using Qdrant + Ollama
- Three memory types: episodic, semantic, procedural
- MCP tools: `memoria_store`, `memoria_recall`, `memoria_search`, `memoria_update`, `memoria_delete`, `memoria_consolidate`, `memoria_export`, `memoria_import`, `memoria_stats`, `memoria_set_context`
- Docker Compose setup with Qdrant
- Working memory (LRU cache) and memory consolidation (merge/forget/decay)

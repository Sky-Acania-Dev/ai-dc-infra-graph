# PostgreSQL Transition Plan

The current backend is intentionally demo-oriented: topology data is loaded into a process-local Pydantic object from `data/runtime/current_database.json`, mutations are appended to a JSONL operation log, and a debounced JSON snapshot is written back to disk. That keeps the early UI responsive, but it is not a safe concurrency or authority boundary for multiple users.

This plan moves persistence to PostgreSQL without breaking the current ingest and UI flow.

## Goals

- Preserve the existing topology vocabulary: Project, Building, Room, Cabinet, Device, Port/Connector, Cable.
- Keep ACID writes for user-driven changes such as status, progress, notes, and future CRUD.
- Support manager, editor, and viewer authority levels durably instead of process-local role state.
- Keep the current JSON runtime loader available during migration for import, export, fixture, and rollback workflows.
- Avoid a broad rewrite of graph rendering, validation, or ingestion before the storage boundary is stable.

## Non-Goals For The First Cut

- Replacing NetworkX graph services with a graph database.
- Reworking the frontend state model beyond API response compatibility.
- Modeling every imported source row as a first-class normalized table before the mutable topology path works.
- Adding distributed undo/redo semantics. Client-session undo can remain local until collaborative edit rules are defined.

## Current Boundaries To Retire

- `backend/persistence/json_database.py` owns the runtime aggregate, JSON serialization, and loader compatibility.
- `backend/api/topology.py` owns process-local caches, JSONL operation append, debounced snapshots, and undo/redo stacks.
- `backend/api/auth.py` stores users and pending changes in memory.

These boundaries are acceptable for a demo, but they do not protect concurrent writes, cannot coordinate multiple API workers, and lose auth changes on restart.

## Target Storage Shape

Use PostgreSQL as the system of record and keep Pydantic models as API/domain DTOs. The first schema should prioritize stable identifiers and mutable workflow fields.

The detailed table draft is tracked in [PostgreSQL Schema Draft](postgresql_schema.md). It covers current model objects plus planned ladder rack junctions, ladder rack segments, cable bundles, device variants, users, pending changes, and the operation log.

Use JSONB only where the shape is intentionally flexible or already nested in the API contract, such as cable phase task values, optics, device panel layout, and operation before/after payloads. Use relational columns for identifiers, ownership, search/filter fields, statuses, and authorization data.

## Concurrency Rules

- Wrap each mutation in a database transaction.
- Lock the target row with `SELECT ... FOR UPDATE` or use optimistic version checks on mutable entities.
- Insert the operation log row in the same transaction as the entity update.
- Return the committed operation id as the API version for the mutation response.
- Keep read endpoints transactionally consistent at statement or request scope; avoid process-global mutable database state.

For moderate-to-high concurrency, prefer a connection pool owned by the FastAPI process and size it explicitly for the deployment target. Multiple API workers must be able to share the same PostgreSQL database without relying on in-memory cache correctness.

## Migration Phases

1. Add a repository interface around topology reads and mutations.
   The JSON implementation should keep existing behavior so tests and the UI remain stable.

2. Add PostgreSQL configuration and migrations.
   Introduce `DATABASE_URL`, SQLAlchemy or SQLModel, Alembic migrations, and a small health check that verifies database connectivity when PostgreSQL mode is enabled.

3. Implement import from the current runtime aggregate.
   Load `TopologyDatabase` from JSON or the existing build pipeline, then upsert projects, buildings, rooms, cabinets, devices, ports, cables, validation summaries, and operation seed state into PostgreSQL.

4. Move auth persistence.
   Store users, roles, and pending changes in PostgreSQL. Keep the development-header fallback gated to local/dev configuration only.

5. Move mutation endpoints.
   Convert cabinet, device, and cable updates to transactional PostgreSQL writes while preserving `OperationResponse` shape for the frontend.

6. Move read endpoints incrementally.
   Start with narrow reads used by mutation verification, then move cabinet layout, cabinet details, cable summaries, validation reports, and graph-derived views. Keep high-cost graph summaries cacheable from database-backed projections.

7. Retire JSONL writes in PostgreSQL mode.
   JSON export can remain as an operator/debug command, but the operation log should live in PostgreSQL once writes are database-backed.

## First Implementation Patch

The lowest-risk code patch is to add a storage interface and move `_load_cached_database`, `_commit_operation`, and `list_operations` behind it while leaving the default implementation JSON-backed. That creates a seam for PostgreSQL tests without changing runtime behavior.

Suggested interface responsibilities:

- `get_topology_snapshot() -> TopologyDatabase`
- `commit_operation(...) -> Operation`
- `list_operations(limit: int) -> OperationListResponse`
- `clear_derived_caches()` or a cache invalidation hook owned by the API layer

After that interface exists, PostgreSQL can be introduced as an alternate implementation behind configuration rather than mixed directly into route handlers.

## Verification Expectations

- Existing unit tests must continue to pass in JSON mode.
- Add repository-contract tests that run against the JSON implementation first.
- Add PostgreSQL tests with isolated schemas or disposable databases before enabling PostgreSQL mode by default.
- Add at least one concurrent mutation test that proves operation ids are monotonic and no update is lost.
- Add manager/editor/viewer persistence tests after auth moves out of memory.

## Rollback Path

Keep JSON export from PostgreSQL during the transition. Until PostgreSQL mode is the only supported runtime, an operator should be able to export a `TopologyDatabase` JSON snapshot and run the current backend in JSON mode for read-only validation or emergency rollback.

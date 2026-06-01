# Runtime Schema Versioning

The normalized runtime database JSON includes a top-level `schema_version` field.

Current version: `2`

## Version 1

Initial normalized topology shape:

- project/building metadata
- cutsheet summary
- port collision findings
- device model validation findings
- data halls
- cabinets
- ports
- cables
- source rows

## Version 2

Adds project-management scaffolding for cable work tracking:

- `Cable.uid`
- `Cable.progress`
- `Cable.current_phase`
- `Cable.designed_length_meters`
- `Cable.length_used_meters`
- explicit schema version in saved runtime JSON

The loader backfills missing cable UIDs for older JSON files using deterministic row order IDs such as `CBL-000001`.

`Cable.progress` is retained for early scaffold compatibility. New UI workflows should use `Cable.current_phase`, which stores phase name, phase type, percentage values or enum state, and optional enum values.

Older `Cable.length_meters` payloads are loaded into `Cable.length_used_meters` for compatibility.

## Compatibility Rule

New required fields should have defaults in Pydantic models or a loader migration path. Importers should continue to read older runtime JSON until a deliberate migration cutoff is documented.

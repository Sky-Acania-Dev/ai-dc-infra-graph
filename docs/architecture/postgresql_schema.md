# PostgreSQL Schema Draft

This draft defines the first PostgreSQL tables for the existing topology model plus planned ladder rack and cable bundle objects. It is a table design, not yet an Alembic migration.

## Conventions

- Use stable text UIDs for domain objects that already have source-derived identifiers.
- Keep `project_uid`, `building_uid`, and `room_uid` on infrastructure tables so tenant/project scoping stays explicit and indexes stay simple.
- Use `created_at`, `updated_at`, and `deleted_at` for future audit and soft-delete workflows.
- Use JSONB for flexible model/geometry payloads, but keep identifiers, statuses, endpoints, and authorization data as relational columns.
- Use PostGIS `geometry` columns later if accurate CAD/GIS coordinates become a hard requirement. Until then, geometry can be represented as JSONB payloads with clear coordinate units.

## Enum Domains

The first migration can use text columns with check constraints instead of PostgreSQL enum types. That keeps migrations easier while the UI vocabulary is still changing.

Suggested checks:

- user role: `manager`, `editor`, `viewer`
- lifecycle status: `unknown`, `not_constructed`, `not_installed`, `not_powered`, `installed`, `powered`, `active`, `not_planned`
- connector type: `CAT6`, `LC`, `SC`, `MPO`, `power`, `other`

## Core Scope Tables

### projects

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Existing project UID, for example `MSK01`. |
| full_name | text not null default '' | Display name. |
| metadata | jsonb not null default '{}' | Flexible project attributes. |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz | Soft delete marker. |

### buildings

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Prefer `project_uid:building_id` if IDs may repeat across projects. |
| project_uid | text not null references projects(uid) |  |
| building_id | text not null | Existing building identifier, for example `A`. |
| metadata | jsonb not null default '{}' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Unique index: `(project_uid, building_id)` where `deleted_at is null`.

### rooms

Rooms include data halls. Keep `room_id` source-faithful and use `room_type` when non-data-hall rooms are added.

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Prefer `project_uid:building_id:room_id`. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_id | text not null | Existing `Room.room_id` / data hall ID. |
| room_type | text not null default 'data_hall' | Allows future MDF, IDF, staging, etc. |
| lifecycle_status | text not null default 'unknown' |  |
| construction_phase | text not null default 'Management & Ethernet' |  |
| metadata | jsonb not null default '{}' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Unique index: `(building_uid, room_id)` where `deleted_at is null`.

## Equipment Tables

### cabinets

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Existing cabinet UID, for example `DH1:001`, or scoped UID if needed. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_uid | text not null references rooms(uid) | Data hall/room. |
| cabinet_id | text not null | Existing cabinet ID. |
| category | text not null default '' |  |
| cabinet_group | text not null default '' |  |
| lifecycle_status | text not null default 'not_installed' |  |
| construction_phase | text not null default 'Management & Ethernet' |  |
| max_rack_unit | integer not null default 48 |  |
| source_row | integer | Imported layout row. |
| source_col | integer | Imported layout column. |
| layout | jsonb not null default '{}' | Future physical/cabinet map attributes. |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Indexes: `(room_uid, source_row, source_col)`, `(room_uid, cabinet_id)`.

### device_models

This is the existing model catalog.

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Normalized model UID. |
| model_name | text not null |  |
| manufacturer | text not null default '' |  |
| rack_units | integer not null default 1 |  |
| front_panel_svg | text not null default '' |  |
| back_panel_svg | text not null default '' |  |
| port_layout | jsonb not null default '[]' | Existing `DevicePortLayoutEntry` list. |
| metadata | jsonb not null default '{}' |  |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

### device_variants

Device variants capture project-specific or vendor-specific overrides without forcing every variant field into the base device model.

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Variant UID. |
| project_uid | text references projects(uid) | Null means global variant. |
| device_model_uid | text references device_models(uid) | Base model. |
| name | text not null | Human-readable variant name. |
| variant | jsonb not null default '{}' | Variant payload, including overrides, port maps, aliases, firmware, or vendor attributes. |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Index: `(project_uid, device_model_uid)`.

### devices

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Prefer `cabinet_uid:rack_unit`, matching current device UID behavior. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_uid | text not null references rooms(uid) |  |
| cabinet_uid | text not null references cabinets(uid) |  |
| rack_unit | integer not null |  |
| device_model_uid | text references device_models(uid) |  |
| device_variant_uid | text references device_variants(uid) | Optional JSONB-backed variant. |
| device_model_name | text not null default '' | Preserves source value even when catalog lookup is missing. |
| rack_units | integer not null default 1 | Snapshot for fast layout. |
| lifecycle_status | text not null default 'not_installed' |  |
| construction_phase | text not null default 'Management & Ethernet' |  |
| aliases | jsonb not null default '[]' | Existing aliases list. |
| model_aliases | jsonb not null default '[]' | Existing model aliases list. |
| port_layout_overrides | jsonb not null default '[]' | Existing override list. |
| metadata | jsonb not null default '{}' |  |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Unique index: `(cabinet_uid, rack_unit)` where `deleted_at is null`.

### ports

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Existing full port UID, for example `DH1:001:10:swp1`. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_uid | text not null references rooms(uid) |  |
| cabinet_uid | text not null references cabinets(uid) |  |
| device_uid | text references devices(uid) | Nullable for pre-device imported endpoints. |
| port_name | text not null | Last segment of source port UID. |
| connector_type | text not null default 'other' | Existing connector type vocabulary. |
| side | text not null default '' | Optional front/back/other hint. |
| position | jsonb not null default '{}' | Optional layout coordinate. |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Indexes: `(device_uid, port_name)`, `(cabinet_uid)`, `(room_uid)`.

## Cable And Pathway Tables

### cables

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Existing cable UID. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_uid | text references rooms(uid) | Nullable for cross-room cables. |
| a_port_uid | text not null references ports(uid) |  |
| z_port_uid | text not null references ports(uid) |  |
| cable_type | text not null |  |
| cable_group | text not null default '' | `group` in the Pydantic model. |
| import_status | text not null default '' | Source status string. |
| construction_phase | text not null default 'Management & Ethernet' |  |
| progress | jsonb not null default '{}' | Existing legacy progress map. |
| current_phase | jsonb | Existing `CableProgressPhase`. |
| designed_length_meters | numeric(12, 3) |  |
| length_used_meters | numeric(12, 3) not null default 0 | Current actual/used length. |
| a_optic | jsonb | Existing optic payload. |
| z_optic | jsonb | Existing optic payload. |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Indexes: `(a_port_uid)`, `(z_port_uid)`, `(project_uid, construction_phase)`, `(building_uid, import_status)`.

### ladder_rack_junctions

Ladder rack junctions are graph nodes. They may be physical intersections, elevation changes, rack entry/exit points, or logical route breakpoints.

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Stable junction UID. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_uid | text references rooms(uid) | Data hall/room if applicable. |
| junction_id | text not null | Local junction identifier. |
| junction_type | text not null default '' | Tee, cross, endpoint, riser, drop, etc. |
| point | jsonb | Optional accurate coordinate point, with units and coordinate system. |
| width | numeric(12, 3) | Optional physical width. |
| height | numeric(12, 3) | Optional physical height. |
| height_tier | text not null default '' | Source-friendly tier label. |
| lifecycle_status | text not null default 'unknown' |  |
| construction_phase | text not null default 'Management & Ethernet' |  |
| metadata | jsonb not null default '{}' | Flexible attributes. |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Connected ladder rack segments should be read through `ladder_rack_segments.junction_a_uid` and `ladder_rack_segments.junction_z_uid` rather than stored as a denormalized list. A materialized view can expose connected segment UIDs later if the UI needs it.

Indexes: `(room_uid)`, `(project_uid, building_uid, junction_id)`.

### ladder_rack_segments

Ladder rack segments are graph edges.

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Stable segment UID. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_uid | text references rooms(uid) | Data hall/room if applicable. |
| segment_id | text not null | Local segment identifier. |
| polyline | jsonb | Optional ordered coordinate list. |
| design_length_meters | numeric(12, 3) | Planned/design length. |
| actual_length_meters | numeric(12, 3) | Installed/measured length. |
| width | numeric(12, 3) | Physical tray width. |
| height | numeric(12, 3) | Physical height. |
| height_tier | text not null default '' | Tier label for multi-level rack. |
| junction_a_uid | text not null references ladder_rack_junctions(uid) | Graph endpoint A. |
| junction_z_uid | text not null references ladder_rack_junctions(uid) | Graph endpoint Z. |
| lifecycle_status | text not null default 'unknown' |  |
| construction_phase | text not null default 'Management & Ethernet' |  |
| metadata | jsonb not null default '{}' | Flexible attributes. |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Checks:

- `junction_a_uid <> junction_z_uid`
- `design_length_meters is null or design_length_meters >= 0`
- `actual_length_meters is null or actual_length_meters >= 0`

Indexes: `(room_uid)`, `(junction_a_uid)`, `(junction_z_uid)`, `(project_uid, building_uid, segment_id)`.

### cable_bundles

Cable bundles group cables and assign them to ladder rack hosting paths.

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Stable bundle UID. |
| scoped_uid | text not null unique | Suggested format `project:building:datahall:uid`. |
| project_uid | text not null references projects(uid) |  |
| building_uid | text not null references buildings(uid) |  |
| room_uid | text references rooms(uid) | Data hall/room. |
| name | text not null default '' | Optional display name. |
| primary_ladder_rack_segment_uid | text references ladder_rack_segments(uid) | Main hosting ladder rack segment when the bundle is simple. |
| lifecycle_status | text not null default 'unknown' |  |
| construction_phase | text not null default 'Management & Ethernet' |  |
| metadata | jsonb not null default '{}' | Flexible bundle attributes. |
| note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Indexes: `(room_uid)`, `(primary_ladder_rack_segment_uid)`.

### cable_bundle_cables

Join table for the list of cables in a bundle.

| Column | Type | Notes |
| --- | --- | --- |
| cable_bundle_uid | text not null references cable_bundles(uid) on delete cascade |  |
| cable_uid | text not null references cables(uid) on delete cascade |  |
| sequence | integer | Optional ordering inside the bundle. |
| created_at | timestamptz not null default now() |  |

Primary key: `(cable_bundle_uid, cable_uid)`.

Indexes: `(cable_uid)`.

### cable_bundle_ladder_rack_segments

Use this when a bundle spans multiple ladder rack segments. A simple bundle can still use `cable_bundles.primary_ladder_rack_segment_uid`.

| Column | Type | Notes |
| --- | --- | --- |
| cable_bundle_uid | text not null references cable_bundles(uid) on delete cascade |  |
| ladder_rack_segment_uid | text not null references ladder_rack_segments(uid) on delete cascade |  |
| sequence | integer | Route order. |
| created_at | timestamptz not null default now() |  |

Primary key: `(cable_bundle_uid, ladder_rack_segment_uid)`.

Indexes: `(ladder_rack_segment_uid)`.

## Auth Tables

### users

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key | Stable user UID. |
| display_name | text not null |  |
| email | text | Optional login identity. |
| role | text not null | `manager`, `editor`, or `viewer`. |
| active | boolean not null default true |  |
| metadata | jsonb not null default '{}' | External identity provider claims or preferences. |
| created_at | timestamptz not null default now() |  |
| updated_at | timestamptz not null default now() |  |
| deleted_at | timestamptz |  |

Unique index: `lower(email)` where `email is not null and deleted_at is null`.

### pending_changes

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key |  |
| requested_by_user_uid | text not null references users(uid) |  |
| reviewed_by_user_uid | text references users(uid) |  |
| target_entity_type | text not null |  |
| target_entity_uid | text not null |  |
| action | text not null |  |
| status | text not null default 'pending' | `pending`, `approved`, `rejected`, `applied`, `cancelled`. |
| payload | jsonb not null default '{}' | Requested change body. |
| review_note | text not null default '' |  |
| created_at | timestamptz not null default now() |  |
| reviewed_at | timestamptz |  |
| applied_at | timestamptz |  |

Indexes: `(status, created_at)`, `(target_entity_type, target_entity_uid)`.

## Operation Log

### operation_log

| Column | Type | Notes |
| --- | --- | --- |
| id | bigserial primary key | Monotonic committed operation id. |
| project_uid | text references projects(uid) |  |
| entity_type | text not null | Cabinet, device, cable, ladder rack segment, etc. |
| entity_uid | text not null |  |
| operation_type | text not null | `create`, `update`, `delete`, `undo`, `redo`, etc. |
| before | jsonb not null default '{}' |  |
| after | jsonb not null default '{}' |  |
| user_uid | text references users(uid) |  |
| user_role | text | Role at write time. |
| created_at | timestamptz not null default now() |  |

Indexes: `(project_uid, id desc)`, `(entity_type, entity_uid, id desc)`, `(user_uid, id desc)`.

Each API mutation should update its target rows and insert the `operation_log` row in the same transaction.

## Import Compatibility Tables

These tables are optional for the first implementation. They preserve source and validation data without forcing the API to query source rows for every topology view.

### source_imports

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key |  |
| project_uid | text references projects(uid) |  |
| source_type | text not null | cutsheet, roce, overhead, status_overrides, etc. |
| source_path | text not null default '' |  |
| summary | jsonb not null default '{}' |  |
| created_at | timestamptz not null default now() |  |

### source_cable_rows

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key |  |
| source_import_uid | text not null references source_imports(uid) on delete cascade |  |
| row_number | integer |  |
| payload | jsonb not null | Original normalized row payload. |
| cable_uid | text references cables(uid) | Linked generated cable. |

Index: `(source_import_uid, row_number)`.

### validation_findings

| Column | Type | Notes |
| --- | --- | --- |
| uid | text primary key |  |
| project_uid | text references projects(uid) |  |
| finding_type | text not null | port collision, device model mismatch, etc. |
| severity | text not null default '' |  |
| entity_type | text not null default '' |  |
| entity_uid | text not null default '' |  |
| payload | jsonb not null default '{}' |  |
| created_at | timestamptz not null default now() |  |

Indexes: `(project_uid, finding_type)`, `(entity_type, entity_uid)`.

## First Migration Order

1. `projects`, `buildings`, `rooms`, `users`
2. `device_models`, `device_variants`
3. `cabinets`, `devices`, `ports`
4. `cables`
5. `ladder_rack_junctions`, `ladder_rack_segments`
6. `cable_bundles`, `cable_bundle_cables`, `cable_bundle_ladder_rack_segments`
7. `pending_changes`, `operation_log`
8. optional import/validation compatibility tables

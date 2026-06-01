# Topology API

The current API is backend-first and reads from the runtime topology JSON at `data/runtime/current_database.json` unless a `database_path` query parameter is provided.

## Health

`GET /health`

Returns:

```json
{"status": "ok"}
```

## Cabinet Layout

`GET /topology/layout/cabinets?data_hall=DH1`

Returns cabinet rectangles for the grid/map view. Fields include cabinet UID, data hall, category, group, lifecycle status, max RU count, and source row/column from overhead ingestion.

## Cabinet Detail

`GET /topology/cabinets/{cabinet_uid}`

Returns:

- selected cabinet metadata
- cabinet statistics
- device list
- intra-cabinet connection summary, when present
- connected cabinet summaries

## Cabinet Connection Cables

`GET /topology/cabinets/{source_cabinet_uid}/connections/{target_cabinet_uid}/cables`

Returns all cables between two cabinets, including intra-cabinet cables when source and target are the same.

Cable rows include:

- `uid`
- imported `status`
- manual `progress`
- `designed_length_meters`
- `length_used_meters`
- `note`
- cable type/group
- A/Z port IDs
- A/Z optics

## Device Connections

`GET /topology/cabinets/{cabinet_uid}/devices/{rack_unit}/connections`

Returns device-level connected devices and their connected cabinets.

## Device Connection Cables

`GET /topology/devices/{source_device_uid}/connections/{target_device_uid}/cables`

Returns cable rows between two device nodes.

## Validation

`GET /topology/validation`

Returns structured validation summaries and examples for:

- port collisions
- device model mismatches
- trivial device model format issues

Future validation rules should return normalized finding types, severity, affected object UID, and row examples so localization and filtering can be handled cleanly in the frontend.

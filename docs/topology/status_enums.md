# Status and Progress Enums

This document defines the status vocabulary used by AI DC Infra Graph. These values should be treated as stable machine codes. Frontends may translate the display labels, but persisted data and API payloads should keep the enum values unchanged.

## General Rules

- Status values describe current known state, not intent unless explicitly noted.
- Unknown or missing source data should use `unknown`, not a guessed status.
- User-facing localization should translate status labels only. Cabinet IDs, device model names, cable types, port names, and imported source codes should remain as-is.
- Manual overrides should be stored separately from vendor import data so future cutsheet refreshes do not erase field progress.

## Lifecycle Status

Lifecycle status applies to data halls, cabinets, and devices.

| Value | Meaning | Typical Scope |
| --- | --- | --- |
| `unknown` | The platform does not have reliable construction/install/power state. Use this when the source system is silent and no manual override exists. | Data hall, cabinet, device |
| `not_constructed` | The physical space or supporting infrastructure is not constructed yet. This usually applies to a data hall or large build area before cabinets/devices can be installed. | Data hall |
| `not_installed` | The object is expected or modeled, but the physical asset is not installed yet. This is the default for devices and installable cabinets. | Cabinet, device |
| `not_powered` | The object is physically installed or planned in place, but power is not available or not energized. | Cabinet, device |
| `installed` | The object is installed in its expected physical position, but may not be powered or active yet. | Cabinet, device |
| `powered` | The object has power available or is energized, but may not be production-active. | Cabinet, device |
| `active` | The object is installed, powered, and considered usable for production/operations. | Data hall, cabinet, device |
| `not_planned` | The object is intentionally not expected to be installed. Reserved (`RES`) and unused (`U`) cabinets should use this value. | Cabinet, device |

## Imported Cable Status

The current cutsheet contains a vendor/source status string. Keep that field as `Cable.status` because it preserves source-of-truth language and supports audits against CoreWeave-provided files.

Known imported status examples:

| Imported Value | Meaning |
| --- | --- |
| `Cable Is Ran: Complete` | The source sheet indicates the cable is pulled/ran and complete. In the current summary logic, this counts as complete. |
| `Cable Is Ran: Not Terminated` | The cable is pulled/ran but at least one side is not terminated or patched. |
| `Cable Not Run` | The cable is planned in the sheet but has not been pulled/ran. |
| empty / missing | The source sheet did not provide a usable status. Display as `Unknown`. |

## Cable Progress Tracker

Cable progress is separate from imported cable status. It is a manual/project-management tracker represented as:

```json
{
  "progress": {
    "purchased": "complete",
    "received": "complete",
    "pulled": "complete",
    "a_side_terminated": "complete",
    "z_side_terminated": "blocked"
  }
}
```

Each key is a `CableProgressStep`. Each value is a `CableProgressState`.

### Progress States

| Value | Meaning |
| --- | --- |
| `not_started` | Work has not started or no confirmation has been recorded. |
| `complete` | This step is complete. |
| `blocked` | This step cannot currently proceed. The cable note should explain why. |
| `not_applicable` | This step does not apply to this cable. Example: `bundled_on_ground` may not apply to a short in-cabinet jumper. |

### Progress Steps

| Step | Sequence | Meaning |
| --- | --- | --- |
| `purchased` | 1 | Cable or cable material has been purchased. |
| `received` | 2 | Cable has arrived on site or in controlled inventory. |
| `categorized_stored` | 3 | Cable has been sorted into the correct work package, location, type, or cabinet group and stored where crews can find it. |
| `labeled` | 4 | Cable label has been applied or otherwise prepared according to the installation standard. |
| `bundled_on_ground` | Optional before pull | Cable has been pre-bundled/staged on the ground before pulling. Use `not_applicable` when not needed. |
| `pulled` | 5 | Cable has been physically pulled/ran along the route. |
| `dressed` | Parallel after pull | Cable is dressed along tray, ladder, pathway, or bundle route outside the endpoint cabinets. |
| `a_side_terminated` | Parallel after pull | A side has been terminated, patched, or connected as required by the cable type. |
| `z_side_terminated` | Parallel after pull | Z side has been terminated, patched, or connected as required by the cable type. |
| `a_side_dressed_in_cabinet` | Parallel after A-side work | A side is dressed inside the cabinet/rack. |
| `z_side_dressed_in_cabinet` | Parallel after Z-side work | Z side is dressed inside the cabinet/rack. |
| `validated` | Terminal successful outcome | The cable has passed the required validation/check. |
| `broken` | Terminal failed outcome | The cable is damaged, failed validation, was abandoned, or must be reworked/replaced. |

### Ordering and Exclusivity

The intended workflow is:

```text
purchased -> received -> categorized_stored -> labeled -> bundled_on_ground? -> pulled
pulled -> dressed || a_side_terminated || z_side_terminated
a_side_terminated -> a_side_dressed_in_cabinet
z_side_terminated -> z_side_dressed_in_cabinet
validated | broken
```

`||` means those steps can progress independently in parallel.

`|` means only one terminal outcome should be true. A cable should not have both `validated = complete` and `broken = complete`. Future validation logic should flag that as a data issue.

## Cable Length and Notes

`Cable.length_meters` is a nullable numeric field for future PM/foreman input. It should remain empty until a user enters a measured or planned length.

`Cable.note` is a free-text human note for unusual field conditions, blockers, rework, or context that does not fit a structured status. Use it sparingly. If notes become common enough to cause large JSON churn, the same concept can be moved into a sidecar dictionary keyed by cable UID:

```json
{
  "cable_notes": {
    "CBL-000001": "Z side waiting for patch panel access."
  }
}
```

For now, keeping the note on the cable object is simpler and easier for APIs/frontends.

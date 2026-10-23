# LBB01 schematic routing API

Routing describes technician-facing cold-aisle pathways in local integer inches. It uses existing PostgreSQL `Room` and `Cabinet` entities and stores fourteen routing domain tables, including optional manual segment markings, bundle occupations/connections, cabinet attachments and manual cable-group routes. Generated graph nodes and edges are never persisted. Existing cable topology and halls without routing layouts continue to work independently.

## Setup

Apply `python -m alembic upgrade head`, start the backend, and open **Routing** in the web app. A manager can initialize LBB01 DH1 with `POST /routing/initialize-lbb01` and `{ "building_id": "A" }`. Initialization requires an existing LBB01 `DH1` or `DH1-1` Room and links each section to the corresponding `DH1-1` through `DH1-5` Room when available. Repeat initialization preserves existing configuration.

The user-confirmed arrangement is ten cabinets per row, north cabinets 801–1600 and south cabinets 1–800. Each section has sixteen rows/eight pairs per side. The initializer creates 80 pairs, 160 rows, 160 cold-side routes and four section-gap routes. It creates no pathway tiers or vertical openings. Cabinet ranges link to existing numeric LBB01 inventory; they do not create duplicate Cabinet records. Later row/pair changes are explicit configuration, never automatic renumbering.

## Endpoints

| Endpoint | Behavior |
| --- | --- |
| `GET /routing/layouts?project_uid=LBB01&building_id=A&hall_code=DH1` | Find the physical hall's layout; returns an empty list when uninitialized |
| `POST /routing/layouts` | Create a layout anchored to an existing Room, with five sections, five bands and four gap routes |
| `GET /routing/layouts/{uid}` | Domain configuration and backend-resolved geometry |
| `PATCH /routing/layouts/{uid}` | Edit dimensions, name and cabinets per row |
| `DELETE /routing/layouts/{uid}` | Remove the layout and its routing records |
| `GET /routing/layouts/{uid}/graph` | Deterministic derived graph |
| `POST /routing/layouts/{uid}/route-preview` | Route between `start_node_id` and `end_node_id` |
| `GET /routing/layouts/{uid}/placement-sources` | Existing building cable bundles and project cable/bundle groups eligible for sectional placement |
| `GET, POST /routing/layouts/{uid}/{resource}` | List/create configuration records |
| `GET, PATCH, DELETE /routing/layouts/{uid}/{resource}/{record_uid}` | Read/edit/remove a configuration record, subject to domain invariants |

Resources are `sections`, `bands`, `row-pairs`, `cabinet-rows`, `cross-routes`, `cross-route-tiers`, `passage-tiers`, `vertical-transitions`, `segment-annotations`, `bundle-placements`, `bundle-connections`, and `cabinet-attachments`. Writes require the existing manager role. Resource payloads are validated by the Pydantic schemas in `backend/schemas/routing.py`; IDs use the repository's `uid` convention. Foreign routing references must belong to the same layout. Duplicate configuration returns 409; invalid dimensions, missing openings and disconnected routes return 422; missing records return 404.

Five sections, the ordered five-band structure, and the associated cross routes are required scaffold. Individual deletion of sections, bands or cross routes is rejected. Cross routes can be disabled; deleting a cabinet row or pair cascades its associated cold-side routes and tiers. Deleting a whole layout removes the scaffold. Reimports preserve routing Room/Building anchors and all routing configuration.

## Geometry and routing

Ordered band widths are 34, 336, 24, 360, 34 inches. The backend derives boundaries, centers 17/382/771, width 788, and cross-route lengths 365/389. The 264-inch module is cold aisle 0–120, A row 120–144, hot aisle 144–240, B row 240–264. Row centers alternate 120/144 inches apart. A/B identifies members of a shared hot aisle; row-field association identifies which side of the hall contains the pair.

North/south pairs occupy parallel longitudinal slots. Each section consumes the larger of its configured north/south pair counts times the module width, followed by a 216-inch extra gap except after Section 5. Empty intermediate sections still preserve all four gaps. A final 120-inch cold-aisle context accommodates the last B row's outward-facing route; it does not change section offsets or gap stations.

Width/depth/gap dimensions whose centers must stay in integer inches are even-valued. Configured face offsets and stations may be any nonnegative integer inch. The backend derives the module when row/aisle dimensions change. Existing explicit route widths and MANUAL/FIELD_MEASURED stations are preserved. The backend rejects route placement outside the associated cold aisle or section gap.

Every enabled cross-route tier intersects compatible enabled passage tiers at one shared junction node per physical position and tier, including NORTH and SOUTH. There are no overlapping cross/passage nodes or artificial JUNCTION edges. Nodes expose `roles` (JUNCTION, TIER_OPENING, ENDPOINT, STATION), all cross-route/row associations and configured bundle connection IDs. A node can serve both a junction and an opening. CROSS_ROUTE edges join adjacent passages only; missing CENTRAL never produces a NORTH–SOUTH shortcut. PASSAGE edges join sorted stations continuously through all five sections. Each enabled opening creates one bidirectional adjacent-tier VERTICAL edge, and requires both configured passage tiers to be enabled. VERTICAL edges have zero planar length; disabling an opening removes that connectivity. Passage node IDs retain the previous `passage:{band}:station:{station}:tier:{tier}` convention; clients must reload any former cross-node selections.

Route preview minimizes, in order: vertical transition count, planar length, edge count, then the ordered stable edge-ID sequence. It returns ordered nodes and edges, compressed technician instructions, opening labels, `vertical_transition_count`, `planar_length_in`, and `length_label: "Planar pathway length"`.

Each derived `PASSAGE` and `CROSS_ROUTE` edge carries integer-inch `planar_length_in`, `width_in`, optional `elevation_in`, and a resolved label. Width comes from the persisted passage band or cross route; length comes from the backend-resolved centerlines/stations. Route-preview edges retain these values. Vertical edges have zero planar length and `width_in: null` because no separate opening width has been measured. Junctions are shared nodes. Optional elevations describe height above finished floor (AFF); they are metadata, not a graph Z coordinate or a vertical cable-length calculation. The generated graph remains transient.

Row labels derive from explicit section/pair ordering and A/B position, preserving parallel north/south slots. The 021–030 row is **Row 3** on the south side; the aligned 821–830 row is also **Row 3** on the north side. A route label never comes from parsing an arbitrary cabinet name. Passage spans use backend station tokens, such as **South R1–2**, **Central R3–4**, or **North R1–3**. Opening and section-gap endpoints retain their explicit labels.

## Frontend workflow

**Routing** displays all five sections together. Use **Focus section**, zoom buttons, the mouse wheel and blank-space panning to inspect details. T1/T2/T3 use solid/dashed/dash-dot styles. Screen offsets and stroke widths affect rendering only. Select infrastructure for details; select a graph node to inspect its roles, incident edges and configured bundle continuations.

The topology cabinet map offers an on/off **Conceptual routes** checkbox. Its subway-style presentation reuses the original cabinet glyphs, category fills, ID/type labels, selection frames, connection badges and progress controls. Small cabinet spacing and wider cold-side gaps make room for routing strokes. Hot aisles are narrower unlabeled gaps. It is explicitly **not to scale**: no physical-width envelopes or dimension annotations appear on this map. SOUTH is left, CENTRAL middle, NORTH right, matching the cabinet-map convention. Cabinet selection continues to drive the existing device and connection panels. The toggle survives section changes. The combined view starts at the selected DH1 section and offers **All sections** / **Fit / reset view** for the continuous global map. **Focus selected cabinet** zooms to nearby row pairs. Segment selection displays actual model length and width independently of screen spacing.

**Geometric routing map** opens the dedicated Routing workspace, whose proportional geometry and default longitudinal orientation are preserved. It retains physical-width envelopes, dimension context, route preview and configuration. Conceptual coordinates are a frontend-only projection of the same domain IDs and graph stations; they never enter pathfinding, persisted geometry or cable-length calculations. Physical openings remain explicit adjacent-tier records on both views.

Resolved layouts include a read-only `cabinets` projection from the existing inventory and `geometry.sections[].data_hall_id`. Each row's cabinet range is scoped to its linked section Room (or the layout's anchor Room when no section Room is configured). Deleted inventory and cabinets in unrelated halls are excluded. Tiles use imported source columns to retain serpentine ordering; missing cabinets leave empty slots. Ambiguous ordering leaves the row context visible without inventing individual positions. Cabinet slots are schematic subdivisions of the row field, not surveyed cabinet footprints. The conceptual map loads the standard cabinet-layout metadata for each section, preserving existing progress displays. The geometric workspace retains its simplified inventory layer, with narrow category strips and a **Cabinets** toggle.

**Configure routing** manages dimensions, band widths, section names, row pairs, A/B rows, pathway tiers and physical openings. Choose an explicit pathway type to add a tier. Disabled tiers remain configurable. Physical-opening forms accept integer inches or feet/inches such as `33'-4"` and show the proposed station before saving. Enable **Route preview**, then select start/destination nodes in the SVG or endpoint selectors. A configuration change clears stale previews.

Vite and nginx both proxy `/routing`. For a separate local validation backend, set `ROUTING_API_TARGET` before launching Vite; the default is `http://127.0.0.1:8000`.

## V1 schematic assumptions

- NORTH/SOUTH measured 34-inch widths may later be confirmed as nominal 36 inches; V1 preserves 34.
- Cold-route envelopes default to touching the cold cabinet face, with configurable face offsets. This is schematic placement.
- DERIVED section-gap routes default to the midpoint of the extra 18-foot gap. This is not a field measurement.
- Confirmed LBB01 DH1 measurements are 98 inches AFF for the bottom basket tier on all routes and 116 inches AFF for the top tier on NORTH/SOUTH passages (18 inches higher). Other elevations remain unknown. Vertical distance, rack drops, slack, service loops and exact cable length remain outside V1.

Before field use, configure confirmed tier availability, pathway types and physical opening locations. The route preview validates configured topology and is not construction-design approval.

## Validation

```powershell
python -m pip install -e '.[test]'
python -m unittest tests.unit.test_routing -q
$env:RUN_ROUTING_POSTGRESQL_TESTS='1'
python -m unittest tests.integration.test_routing_postgresql -q
cd frontend/web
npm run test:routing
npm run build
```

PostgreSQL routing tests create and remove their own isolated schema, exercise full migration upgrade, routing downgrade/re-upgrade, initializer idempotency, graph/pathfinding persistence and cutsheet reimport preservation. They do not replace production data. The frontend tests exercise the shared integer-inch parser and formatter; browser validation exercises initialized/uninitialized rendering, tier configuration, opening forms, section focus and route highlighting.
## Conceptual segment markings

The main topology view reuses the standard cabinet graphics and controls, with display spacing independent of physical inches. Hot aisles appear as narrow unlabeled gaps. The geometric Routing page remains proportional and uses its original orientation.

`GET/POST /routing/layouts/{uid}/segment-annotations` and `GET/PATCH/DELETE /routing/layouts/{uid}/segment-annotations/{annotation_uid}` manage manual design markings. Writes require manager access.

A marking references either a `passage_band_uid` with integer `start_station_in` / `end_station_in`, or a `cross_route_uid` with adjacent `from_passage_band_uid` / `to_passage_band_uid` (NORTH–CENTRAL or CENTRAL–SOUTH). Optional `tier` limits it to one tier; null applies to all. `usable=false` excludes covered generated edges from route previews, including coincident cross-route representations at the same station. Overlapping markings on the same physical span/tier are rejected. Passage spans split derived edges at their boundaries. No generated graph records are persisted.

`cable_classes` supports `LC`, `CAT6`, `MPO`, `MPO_TRUNK_T2_T1_RO`, `CROSS_SECTION_CAT6`, and `CROSS_SECTION_LC`. These are manual design markings, not inferred inventory cable assignments. Unmarked spans are dark gray; unusable spans are light gray. Multiple classes use separate colored lanes.


Selecting a conceptual segment or cabinet connector opens **ten compact metadata lines and tier/section diagrams on the left**, with **cable summaries on the right**. The tier overview shows known AFF elevations, cable-type markings, bundle placements and explicit adjacent-tier opening records in the selected span (including its endpoints). Each tier has an ordinal grid, with layer 1 at the bottom and position 1 innermost, plus a physical rectangle view when dimensions are entered. A saved viewing/inner-side reference defines what "inner" means. These are bundle occupation envelopes, without tray-fill or structural calculations. Rack-pair summaries share the cabinet connection-card presentation. Each cable type has a **View cables** action that opens the existing sortable, filterable, paginated cable-detail table instead of an inline list. Inventory details are loaded from the existing cabinet connection API and filtered to the selected segment/bundle's exact member IDs and cable type. The routing table is read-only; selecting a table row highlights its route. Closing routing details or selecting a cabinet restores the normal cabinet and connection panels.


## Tier heights and sectional placements

Migration `b5f63c9e0214` adds nullable `elevation_in` to passage and cross-route tiers, nullable `section_reference` to segment annotations, and `routing_bundle_placements`. It is additive and supports downgrade. Heights accept feet/inches in the UI and persist nonnegative integer inches; blank means unknown. Known enabled tier heights must increase with tier number on the same pathway. No elevations are seeded by initialization.

Open **Configure heights / bundle sections** in the left inspector to configure confirmed tiers, save AFF heights, define the section viewing reference, and create/edit/disable/delete bundle placements. An enabled placement requires a usable segment and an explicitly enabled pathway tier. Overlapping occupations and mismatched annotation tiers are rejected.

`source_kind` is `MANUAL`, `BUNDLE`, or `GROUP`. Manual entries need a label. Existing `CableBundle` and cable/bundle `EntityGroup` records are reused through scoped source UIDs; no duplicate inventory entities are created. This uses the application's polymorphic-reference convention. A deleted/reimported source leaves its placement visible as unresolved rather than silently changing its identity; unchanged retired references can be disabled. Optional `cable_class` colors the sectional block and covered route span but does not assign inventory cables. Source lookup loads only when configuration opens.

## Multi-cell and rectangular occupations

Migration `c73a91de4826` extends existing placements instead of replacing them. A section definition defaults to `grid_columns=12`, `grid_rows=8`; both are configurable from 1–64. Older placements remain single-cell footprints. Migration expands a section's default grid when necessary to preserve existing positions outside 12×8.

A placement can have a grid footprint, a physical rectangle, or both:

| Representation | Fields | Origin |
| --- | --- | --- |
| Grid | `layer`, `position`, `slot_width`, `slot_height` | 1-based layer from bottom; position from inner side |
| Physical rectangle | `offset_across_in`, `offset_up_in`, `occupied_width_in`, `occupied_height_in` | Inner edge across the pathway; tray bed upward |

Each set must be entirely specified or entirely null. At least one representation is required. Grid spans must fit the section grid; physical rectangles must fit the pathway width and optional `section_height_in`. The latter is a sectional height above the tray bed, separate from tier AFF elevation. Unknown section height remains null; the drawing labels its vertical extent as auto-fit. Touching rectangle edges are allowed; enabled footprints may not overlap within their respective representation. Grid and physical coordinates are independent; changing the grid does not rescale physical dimensions or infer inch measurements for a cell.

The UI accepts integer inches or feet/inches and converts them to canonical integer inches before saving. Derived millimeter readouts use 25.4 mm/in; metric values are not persisted. No floating-point feet enter domain geometry. **Grid / Physical** switches the sectional display; only one representation is shown at a time. Empty pathways still show an empty section. An unconfigured pathway shows an unassigned-tier section, without manufacturing a saved tier.

`GET /routing/layouts/{uid}` includes `section_occupations`: one entry per configured section/tier, with `cells[row][column]`, where row 0 is bottom, column 0 is the reference edge (inner where applicable; North on CENTRAL), and 0 means empty. Positive integers reference the entry's `occupants` lookup (`value → placement_uid`). One bundle repeats its integer across every occupied cell. Physical-only rectangles do not manufacture grid cells. Arrays and rectangle projections are derived from placement records, rather than redundantly persisted. Graph edges carry covered `bundle_placement_uids` and `cabinet_attachment_uids`.

## Actual cable membership and sectional selection

Existing `CableBundleCable` links a `CableBundle` to actual `Cable.uid` values. `RoutingBundlePlacement` references that bundle (`source_kind=BUNDLE`) or an existing cable/bundle `EntityGroup` (`source_kind=GROUP`); it stores the footprint independently of membership. MANUAL labels do not imply actual cables. Cable type, count and rack-pair summaries are derived from cable members and their port/cabinet references.

`GET /routing/layouts/{uid}/bundle-placements/{placement_uid}/cables` returns `placement_uid`, `label`, `source_available`, actual `cables` (UID, type, group, cabinet IDs/UIDs, port IDs/names, endpoint labels and notes), and a `summary` grouped by cable type and endpoint cabinet pair. It expands groups of bundles, deduplicates cable IDs, excludes retired sources/cables and enforces layout/project/building scope. Missing placements return 404; manual placements return empty member lists. This read-only endpoint is available to viewers.

Selecting an occupation rectangle or grid footprint filters the right panel to its exact member IDs, opens an enlarged bundle footprint above the main sections and leaves configuration closed. **Show all segment cables** clears the filter and enlarged view. Per-cable positions inside a bundle remain unrecorded; the enlarged view does not invent their packing.

## Cardinal section directions

Migration `e95f41c7a320` adds nullable layout `longitudinal_direction` (EAST/WEST) and annotation `section_inner_direction` (NORTH/SOUTH/EAST/WEST). The confirmed LBB01 Building A DH1 cabinet-map top is West, so increasing station / Section 1→5 is East. Other halls remain unconfirmed. Layout configuration allows changing the longitudinal direction.

Inner is the cabinet/hot-aisle-facing side: NORTH passage inner is South, SOUTH passage inner is North, row A inner is increasing X and row B inner is decreasing X. CENTRAL has no inner/outer side and uses North/South labels; setting an inner side on CENTRAL is rejected. Section gaps have cardinal sides and leave inner unassigned unless explicitly configured. Passage section overrides must be North/South; cross-route overrides must be East/West.

**Reverse view** mirrors all sectional footprints and swaps cardinal labels/view direction while keeping the tray bed at the bottom. It does not change stored grid cells, rectangles, cable membership, graph coordinates or lengths. Grid column 1 and rectangle across offsets remain anchored to their canonical reference edge.

## Bundle junction connections and cabinet attachments

`bundle-connections` records reference `from_placement_uid`, `from_end` (START/END), `to_placement_uid`, `to_end`, optional `vertical_transition_uid`, notes and enabled state. The placements' span endpoints must meet at the same physical point. A connection continues the same referenced bundle/group; manual placements can be explicitly connected. Crossing tiers requires the matching enabled adjacent-tier opening. Duplicate reversed connections are rejected. These are saved design continuations; topology preview remains independent of individual bundle assignments. Resolved results provide endpoint coordinates and generated node IDs. Curve generation and bend-length corrections remain future work.

`cabinet-attachments` records reference a span annotation, existing `cabinet_uid`, integer `offset_in` from span START, optional tier, label, notes and enabled state. START means increasing X on a passage or NORTH→SOUTH on a cross route. Offsets must fit the span; a specified enabled tier must exist. Cabinet scope is the physical hall. Retired cabinet identities remain visible as unresolved and can be disabled, matching existing import-preservation behavior. Attachments do not insert nodes or split graph edges, and do not invent cabinet drop length.

The geometric Routing configuration has a **Connections / attachments** tab for both resources. Occupations, connections and attachments reference domain spans/placements rather than transient edge IDs, so graph regeneration can split edges without losing saved associations. LBB01 has no internal turning-point attachments; no changes are made to MSK01 routing data or its legacy ladder-rack models.

Downgrade preserves old single-slot records. Rectangle/multi-cell occupations must be explicitly converted or removed before rolling back to the older schema, which cannot represent them.

## Full DH1 inventory stress test (feature branch)

**Actual cable review** loads all five DH1 sections automatically when opening the LBB01 DH1 conceptual map. It can still be turned off explicitly. Refreshing the same layout retains loaded cables while showing loading/error status; changing layout never shows the previous inventory. Failed loads offer Retry. Global/section zoom is independent of inventory scope. The searchable rack-pair list renders 40 cards per page. Cable details use the existing inventory table and load actual records on demand. Fake cable samples, demo sectional placements and the pilot-scope/setup controls have been removed from this map.

The conceptual map selects physical pathways and junctions once, across their graph tiers. Colored tier strokes are display-only and do not add tier-specific hit targets. One segment opens its cable groups across all tiers; one junction includes routes passing its plan location on any tier. Cabinet attachments also have one target per cabinet. Tier availability, heights, visibility controls and distinct physical openings remain explicit. In the manual editor, a physical click groups coincident tier candidates and uses local A* to choose a valid tier with the fewest transitions, then planar length, edge count and stable IDs. Unreachable tiers are skipped; no opening is manufactured and the complete tier-specific chain is still validated before Save.

`GET /routing/layouts/{uid}/cable-review?scope=hall` aggregates live project/building cable rows in PostgreSQL by cabinet pair, actual cable type and construction phase. It returns all mapped inter-cabinet groups, separate same-cabinet/unmapped counts, policy and unrouted reasons, and the enabled planning graph. It avoids loading all individual Cable ORM objects. The `indexed-v1` response represents group routes by a starting point and ordered `edge_indices` into `planning_segments`; loads reference the same edge table and group indices. The client validates and hydrates shared references. HTTP compression reduces transfer size. Full-scope detail requests resolve live inventory membership from actual cabinet UIDs and cable type.

`POST /routing/layouts/{uid}/inventory-test-profile` is an explicit manager-only, idempotent configuration action, limited to LBB01 DH1:

| Pathway | T1 AFF | T2 AFF | T3 AFF |
| --- | --- | --- | --- |
| Cabinet row / CENTRAL | 98 in | 110 in | 122 in |
| NORTH / SOUTH | 98 in | 116 in | absent |
| Section gaps (test assumption) | 98 in | 116 in | absent |

Existing construction types and disabled pathways are retained. New bottom pathways use basket tray; new upper pathways use ladder rack as a test assumption. Gap upper-tier availability/height is a test assumption, not a field measurement. Manual assignments and sectional footprints are never overwritten.

Migration `074ca9e2b613` adds nullable `RoutingVerticalTransition.cross_route_uid`. A linked row-end opening connects the upper row tier to the adjacent lower passage tier. Its effective station follows the row. The user confirmed openings at every row's NORTH or SOUTH end: row T3 connects to outer passage T2; row T2 also joins passage T2. Graph generation creates an upper landing and one explicit VERTICAL edge, without a third longitudinal outer tier, a bottom-tier opening, or invented vertical cable length. Ordinary passage openings retain their behavior. Bundle endpoint connections and the opening editor support linked landings.

Default policies are read-only test suggestions:

| Inventory group | Default |
| --- | --- |
| Same-row RoCE | T1 |
| Same-row LC/Cat6/Y and confirmed same-row FE MPO | T2 |
| Cross-row FE | Row T3 → explicit opening → NORTH/SOUTH T2 → destination opening → row T3. Cross-hall travel uses a gap T2 route; no longitudinal CENTRAL travel. INNER occupation is intent only, without an invented footprint. |
| Cross-row RoCE network T0–T1 | T1; minimize the source T0-row exit distance before the remaining distance. |
| Cross-row RoCE T0–node MPO/MTP | T1 only. Prefer CENTRAL longitudinal travel when at most 10% longer than the shortest enabled bottom-tier route; otherwise keep the shortest route. |
| Cross-row RoCE network T1–T2 | Stable rack-pair distribution over T2/T3; all passages permitted where configured, with explicit tier openings. |
| Unmatched/mixed-phase groups | Unrouted with a reason; manual assignment remains available. |

Construction phase and authoritative imported cabinet categories (`T0-RO-*`, `T1-RO-*`, `T2-RO-*`, `*-FE-*`) identify network roles; arbitrary cabinet name strings are not parsed. Actual MTP types retain their labels and use the MPO visual family. Group UIDs match the pilot, preserving manual precedence. Manual preview/batch/reset accepts `scope: "hall"`; omitted scope retains pilot compatibility. Complete local validation and optimistic atomic updates apply to both scopes.

Selecting cabinets keeps the union of incoming/outgoing cable groups colored and greys unrelated groups, including other types on a shared segment. Shift/Multi adds cabinets; clearing selection restores colors. Rack-pair and individual-cable focus remain available. Cabinet graphics sit above padded route targets so a cabinet click does not select its attachment. Section zooms omit offscreen cabinets, graph elements and cable strokes. Tier offsets/patterns are visual only; opening labels compact at overview scale.

Local validation on 2026-10-18 loaded 699,243 live cables, 9,482 mapped inter-cabinet groups, 6,047 planning subsegments and 3 preserved manual assignments. The confirmed rules route 612,550 inter-cabinet cables; 57,307 stay within cabinets, 29,378 lack a supplied policy and 8 have unmapped endpoints. All 8,999 routed groups passed complete chain validation. One local HTTP run took 5.57 seconds and transferred 681,408 compressed bytes. Local parse/hydration took 80 ms; 30 long-route local A* samples had a 2 ms p95 / 5 ms maximum. These are development measurements. Cross-row node↔RoCE-T0 and other unmatched groups remain pending-policy cases.

Original schematic assumptions remain: NORTH/SOUTH widths stay 34 inches, without rounding to 36; cold-route placement against the cabinet face is schematic; derived gap stations use the midpoint of the extra 216-inch gap. AFF heights do not supply measured vertical cable travel, cabinet drops, bends or slack. Default routes do not generate sectional footprints.

## Original actual-cable pilot

The API retains the original pilot scope for compatibility and automated validation: real inventory cable IDs with both ends in cabinets 001–020 / 801–820. Same-cabinet cables remain local and are counted separately; endpoints outside this scope are excluded. The conceptual map now uses full-hall inventory exclusively.

`GET /routing/layouts/{uid}/cable-review` requires all 40 test cabinets to be mapped and returns actual inter-rack cable records, type/rack-pair groups, effective routes, used subsegments, a topology revision and all enabled tier-specific planning segments. Reads never write assignments. Each group identifies `route_source` (DEFAULT/MANUAL), manual version/revision/status, endpoint tiers and a validated ordered route with points, segment chain, planar length and vertical-transition count. An invalid saved manual route has no effective route and an explicit error; A* never silently replaces it. Selecting a used subsegment finds the rack pairs using that precise part; each pair card shows all its cable types so their complete routes can be compared. **View cables** opens the existing table for a rack pair and cable type, with real inventory status, group, ports and optics.

Default same-row routes follow their configured cold-side tier directly. Cross-row defaults and continuations use deterministic A*: minimize vertical-transition count, then integer-inch planar length, edge count and stable IDs. The Manhattan heuristic excludes unknown vertical distance. Planning reuses the existing derived tier graph and temporarily splits cross-route edges at equal-slot cabinet takeoffs. It never invents missing tiers, openings or hot-aisle routes. Tier changes require explicit enabled adjacent-tier openings and add zero planar length, with their count reported separately. Cabinet ordering follows authoritative source columns; each row field is divided into the configured cabinet count, with integer-inch centers.

Manual/default routing does not create CableBundle/EntityGroup memberships or sectional packing. Path lengths exclude cabinet drops, vertical travel, slack and bend corrections; they are planar pathway lengths, never measured cable lengths. Manual assignment applies to the selected rack-pair/type definition and its actual current inventory members, including future matching members, rather than copying inventory cable records.

## Batch manual route editing

Migration `f16b72c8d431` adds `routing_manual_cable_routes`, unique by layout/source cabinet/destination cabinet/cable type. It stores endpoint tiers, ordered directed domain intervals (passage/cross-route owner, tier, start/end integer inches), explicit vertical-opening references, revision, optimistic version token, operator, timestamps and notes. Generated nodes/edges are not persisted. Cabinet identities use the existing attachment convention so project-scoped cutsheet replacement can retain manual intent. Harmless graph subdivisions regenerate the saved chain; disabled/removed pathways or openings mark it invalid.

Manager write endpoints under `/routing/layouts/{uid}`:

- `POST /manual-routes/batch`: `{topology_revision, notes, groups: [{group_uid, expected_version, segment_ids, start_tier, end_tier}]}`. Every group must be in the current test-row inventory and every ordered chain must be complete, contiguous, loop-free, enabled, tier-valid and start/end at its own cabinet takeoffs. The server revalidates the whole batch before any mutation. Geometry/configuration writes share a layout lock; version and topology conflicts return 409. Successful responses contain `updated_group_uids` and the refreshed review.
- `POST /manual-routes/reset`: the same envelope, with empty `segment_ids`, explicitly removes selected manual assignments using their current tokens. Only this explicit operation restores default routing; reads and suggestions never overwrite manuals.
- `POST /manual-routes/test-tiers`: explicitly adds missing T1 basket-tray records for the test layout's passages/cross routes. It is idempotent, preserves existing records, creates no higher tiers/openings and is never called by reads. The original pilot profile uses bottom Tier 1 (98 inches AFF). This is test configuration, not confirmation of all physical tray types.
- `GET /manual-routes`: lists saved domain assignments for the layout, including identities no longer present in the active pilot inventory.
- `POST /manual-route-preview`: optional API for programmatic prefix validation/continuation. The browser editor does **not** call it while building routes.

Click a rack-pair card to focus its complete set of cable types; unrelated routes turn grey, including unrelated cable classes sharing the same pathway. A card expands all types for that pair even when the selected segment carries only some of them. Small per-type selection squares appear on the focused card. Selecting types reveals **Set route** for first-time manual assignments or **Change route** when any selected type already has a manual assignment. The card action edits its selected types; a selection bar supports one batch across multiple rack-pair cards. **View cables** keeps the existing cable detail table. **Show all routes** clears map focus without clearing type selections.

The route editor uses the downloaded enabled tier graph for local validation, collapsed next-path choices, and A* continuation from the current endpoint and tier. Teal paths are valid next choices, orange is the chosen prefix, and dashed cyan suggests the remainder. Each click updates suggestions without network requests. **Fill remainder with A*** appends the current suggestion; **Undo last choice**, **Start over** and endpoint-tier controls support corrections. Different rack pairs have independent drafts in one batch; a completed chain can be copied to selected cable types sharing a rack pair. **Save manual batch** is disabled until all selected chains are locally valid and complete, then sends one atomic batch request. Existing routes can be loaded explicitly; drafts do not alter saved assignments until Save.

Clicking a non-connected enabled segment compares local A* approaches to both of its endpoints, using the same tier-change/planar-length/edge-count/stable-ID priority. It adds the best reachable bridge followed by the clicked segment, preserving the earlier draft. Approaches cannot cross the clicked segment, touch its exit first, revisit the chosen prefix or pass the final destination. An unreachable click leaves the draft unchanged with an explanation. The remainder suggestion refreshes from the new endpoint; **Undo last choice** removes the bridge and clicked segment together. These clicks make no API requests and do not change saved assignments.

## Confirmed elevation references

Migration `d84e30b6f219` adds nullable hall measurements `bottom_basket_elevation_in` and `north_south_top_elevation_in`, plus a tier's optional `elevation_reference`. The LBB01 Building A DH1 initializer now records the user-confirmed 98/116-inch references without creating pathway tiers. Other projects/buildings receive no measurement defaults.

New explicitly configured T1 basket trays use `BOTTOM_BASKET` when no manual elevation is supplied. `NORTH_SOUTH_TOP` must be explicitly selected for the actual physical top tier (T2 or T3) on NORTH or SOUTH; it is rejected on CENTRAL and cross routes. A higher enabled tier cannot sit above a tier designated as physical top. This avoids assigning the top measurement to an assumed tier number. Manual elevations remain available.

Resolved tier records expose `effective_elevation_in`; the graph's `elevation_in` uses that value. Known effective elevations must increase with tier number. Referenced measurements update consistently when the hall reference changes, without persisting duplicate height values. Heights and tier numbers do not create connectivity or add invented vertical cable length. Downgrading the reference revision materializes effective values into the older manual-height field.

### Physical pathway selection and complete-route focus

Selecting a physical segment or junction filters the cable list to the groups passing through it across configured tiers. The map keeps each matching group's complete end-to-end route and cabinet takeoffs in color; unrelated cable types are grey even on shared segments. A selected empty segment greys all cables. Clearing the pathway selection restores all colors. Rack-pair cards and individual cable selection can narrow this focus further. Tier visibility remains independent and no route assignment is changed by inspection.

### Pre-merge stability and performance audit (2026-10-18)

Read-only validation covered the complete live LBB01 inventory: 699,243 cables, 9,482 rack-pair/type groups, 6,047 planning segments and 4,083 used segments. All 8,999 routed groups passed ordered-chain, endpoint-tier, integer-length, explicit-opening and membership/count validation. Graph generation and review results were deterministic. All seven configured passage tiers remain continuous through all five sections. Domain configuration and all three manual assignments retained their original fingerprints. The 29,386 unrouted cables remain explicit: 29,378 need a routing policy and eight have unmapped endpoints; 57,307 same-cabinet cables stay local.

The four-reader test reproduced PostgreSQL shared-memory exhaustion with Docker's default 64-MiB `/dev/shm`. Inventory aggregation now disables parallel query workers **locally to its transaction**, avoiding parallel hash allocations without changing PostgreSQL's global configuration. An isolated PostgreSQL regression verifies aggregation and setting restoration. Repeating the four-reader test succeeded in both the development backend and the production image. The production startup smoke test also exposed and fixed a missing `func` import in the existing source-cable-group endpoint; its real 382 groups now load successfully.

| Check | Result |
| --- | --- |
| Routing backend tests | 63 passed |
| Source-group startup regression | 1 passed |
| PostgreSQL migration/persistence tests | 12 passed, including upgrade/downgrade and pool-setting isolation |
| Frontend routing tests | 66 passed |
| TypeScript and production build | Passed locally and in the frontend image |
| Production container API/proxy | Health, layout, graph and full review returned 200 |
| Production full review | 9.51 s, 653,413 compressed bytes |
| Four simultaneous production reviews | All 200; 15.14–16.73 s |
| Development sequential full reviews | 7.93–8.80 s |
| Development four-reader test | All 200; 18.49–26.74 s; health probe 9 ms |
| Client parse/hydration / local graph setup | 93 ms / 21 ms |
| Local A* continuation, 100 long routes | p95 4 ms; maximum 7 ms |
| Local distant-segment bridge, 100 long routes | p95 33 ms; maximum 38 ms |

Measurements are from this workstation, without a tablet hardware run. The full global SVG remains dense (about 57,000 elements including 1,600 cabinet graphics); Section 1 has about 12,700 elements. A three-sample server-render-only benchmark measured a global cable-layer median of 414 ms and a section median of 74 ms; these exclude browser layout/paint. Section views remain the practical inspection mode, and the global overview is retained. Initial inventory loading is the principal remaining performance cost; no automatic refresh or persistent graph cache was added.

Browser checks exercised global/section navigation, complete-route focus, cabinet/rack-pair filtering, real cable details, physical targets across tiers, local North-passage bridging, complete-batch Save gating, and cancellation without writing assignments. The production smoke containers use read-only database transactions and are separate from the live services.

The full pre-existing backend suite ran 158 tests with 151 passes and seven failures, all reproduced from an exported `main` checkout: four depend on the unavailable external `OVERHEAD.ods`, and three assert outdated ingestion/default-project expectations. These were kept outside the routing change. `npm audit` also reports seven existing build-tool advisories (five high, one moderate, one low); a separate dependency refresh remains due. The tested static frontend image contains built assets and nginx, rather than the Node build toolchain.

Repeat the read-only inventory audit from the repository root with `python -m tests.performance.check_routing_inventory --api-base http://127.0.0.1:8001`. It writes metrics plus indexed review and resolved-layout artifacts under `tmp/`. Then, from `frontend/web`, run `node --experimental-strip-types tests/routing-performance.mjs`. Neither command creates fixtures or changes assignments. Integration migrations run only in a generated isolated test schema.

For rollout, retain a database backup, merge the tested branch, build backend/frontend, apply `alembic upgrade head` using the new backend image, and recreate only backend/frontend. The database already reports routing revision `074ca9e2b613` on this workstation. Existing hall data requires no routing layout. An application rollback can retain the additive routing tables; do not downgrade away saved manual routes as an automatic rollback step.

### T0–node bottom-tier defaults and integrated viewport (2026-10-19)

The `ROCE_T0_NODE` policy covers cross-row RoCE MPO/MTP connections between authoritative `T0-RO-*` categories and the current `HD-GB3*` / `VR-NVL72*` node families. It compares the unrestricted shortest T1 route with the shortest route using CENTRAL for longitudinal travel. NORTH/SOUTH remain valid on the unrestricted candidate; unavailable CENTRAL falls back to that candidate. The CENTRAL candidate is accepted at exactly 110% of the shortest planar length or less, using integer arithmetic. It never changes tier, creates missing pathway records, changes another category's defaults, or replaces a saved manual assignment.

Full-data validation on 2026-10-19 routes all 28,800 affected cables across 194 rack-pair/type groups on T1. The hall now has 641,350 routed inter-rack cables, 57,307 cabinet-local cables and 586 unrouted cables (578 still need policy and eight have unmapped endpoints). All 9,193 routed groups pass chain validation, and the three saved manual assignments retain their original fingerprint. Backend regressions pass 68 tests; frontend regressions pass 76 tests, with TypeScript and production build validation.

The integrated conceptual SVG now fills the same map body as the cabinet view. Zoom/Fit controls float above it, with section/focus options in a compact disclosure. Tier toggles sit beside the hall title. Full-hall inventory counts, color legend, cached/loading status and default-policy notes appear in the left pathway summary when no specific pathway/cabinet attachment is selected. Section focus and Fit clear pathway selection to restore that summary. Left summary visibility is independent of the right cable inspector, so closing cable details does not remove the hall summary. The redundant geometric-map and cable-review buttons are removed from the integrated toolbar; the Routing tab retains the geometric page. SVG batching and section culling remain unchanged.

### Local bundle-overview summaries

The left overview presents routed/unrouted cable totals and default/manual rack-pair/type route counts as primary cards. Manual means explicitly saved, not a separate confirmation/approval status; invalid saved assignments are labeled. The larger color key has one row per display cable class with all-inventory counts, including cabinet-local and unmapped cables in their base type families. Known cross-section and RoCE trunk groups are subtracted from their base family and shown separately, so each cable is counted once. Description/policy notes and the pathway guide are collapsed by default. All totals use bundle metadata, without loading individual cable records.

The full-hall review is already metadata-only: rack-pair/type group IDs, counts, endpoint cabinets, tier paths and manual-assignment versions. Actual cables and their port details load through the existing detail API only when requested. The browser now stores an indexed summary in IndexedDB, explicitly removing all individual cable records and cable-member IDs. It retains at most two hall summaries for 24 hours and verifies the complete resolved layout/configuration signature before using one. Geometry, tiers, markings, occupation, cabinet ordering or layout changes invalidate that saved view. Storage denial, quota errors and corrupt entries fall back to the live request.

Opening the map can display the saved summary while a current review refreshes in the background. Its timestamp and pending verification are visible. Cached data permits inspection; route changes and resets require a successful current response. Fresh network results outrank late disk results, scope changes discard old loads, and successful manual saves/reset results replace the stored summary. No authoritative assignments are written from cached data. A cold first load still requires the backend calculation; this is not a server graph cache or a full offline layout store.

Below overview scale, cable strokes are grouped into native SVG paths by color, tier dash, width and focus state. Every segment remains an independent `M/L` subpath, preserving gaps and route topology. Muted paths draw underneath selected routes. Physical segment/junction and cabinet-attachment hit targets remain available; zooming into a section restores detailed strokes and tooltips. Cabinet graphics and backend integer-inch geometry retain their existing representation.

### Junction model and inspector (2026-10-23)

Migration `187a4f03c852` adds optional domain-anchored junction working areas and explicit bundle over/under relations. Existing `bundle-connections` accept `junction_area_uid`, `from_turn_start_in` and `to_turn_start_in`. The latter are a nullable pair of nonnegative integer-inch distances measured inward from the two port boundaries. Straight and tier-opening movements leave them unset. Inconsistent circular tangents are rejected; legacy connections with unknown physical geometry continue to resolve as unknown.

New manager-only configuration resources use the existing GET/POST/PATCH/DELETE patterns under `/routing/layouts/{uid}`:

- `junction-areas`: `passage_band_uid`, either `cross_route_uid` or `station_in`, `tier`, four cardinal `*_extension_in` values (default zero), nullable `usable_height_in`, `provenance`, `label`, `notes`, `enabled`. A single enabled area occupies each physical location/tier. Only existing tray arms can be extended. Row/gap anchors follow their derived station. Changing a boundary preserves saved tangent positions or rejects an edit that excludes them.
- `junction-crossings`: `above_connection_uid`, `below_connection_uid`, nullable `clearance_in`, `notes`, `enabled`. Both enabled movements must share one node/tier. Cycles and contradictions with saved endpoint heights/clearance are rejected. These records do not create vertical openings or an assumed crossover hump.

Read-only endpoints:

- `GET /junction-preview?node_id={stable-node-id}&actual_groups=false`: resolved area/ports, saved movements with LINE/ARC primitives and SVG paths, intersection statistics and crossing orders. A missing node returns 404.
- `GET /junction-preview?node_id=…&actual_groups=true`: real inventory groups and their existing default/manual routes, with **display-only schematic occupations**. The 2 × 1 inch rectangles, stacking and suggested turn starts are not saved. Actual cable members still load lazily through the existing group detail action. Manual assignments and their version tokens remain unchanged.
- `GET /junctions`: derived graph nodes with count/status/scope fields. `/graph` includes those fields as well.

`cable_intersection_point_count` counts distinct proper centerline crossing locations; `bundle_pair_crossing_count` counts pair/location events. A triple crossing is one point and three pairs. Shared endpoints, tangencies and coincident runs are excluded; overlaps are reported separately. Method `LINE_CIRCULAR_ARC_V1` solves lines/circular arcs analytically. Different routing tiers do not cross each other in this metric. Graph counts have scope `CONFIGURED_MOVEMENTS`; unconfigured nodes are unknown. Actual-group previews have scope `ACTUAL_GROUPS_SCHEMATIC` and estimated counts. Incomplete geometry returns null/`UNKNOWN` plus observed counts, not an optimistic zero. Filters and mirrored viewing never recompute a reduced node total.

The app renders the square tray and curved bundle envelopes in plan or underside view. Clicking any connected sectional bundle emphasizes it and filters the right cable panel while keeping the plan and all connected sections visible. The grid/physical section toggle and existing passage-tier section diagrams remain available. Working areas, turn starts and above/below relations can be managed without changing routes.

Read-only validation on an isolated full database clone covered 699,243 cables, 9,482 groups and nine junctions (up to 105 movements). All five manual records retained SHA256 `1fafd248ee725aef06835f3eacd19d8c5676fe4579ab72ea80ec45b61bb739c0`. A NORTH Row 2 preview has 37 movements, including three manual groups, with 10 estimated points / 22 pair crossings. CENTRAL Row 2 has 69 movements and 62 estimated points / 2,012 pair crossings. One cold HTTP preview took 5.86 s; another node using the bounded 30-second metadata cache took 0.40 s on this workstation. Physical packing, minimum manufacturer bend radii and unknown vertical travel remain unchecked. Junction curves do not change planar pathway length.

Repeat the isolated read-only audit with `python -m tests.performance.check_routing_junctions` after setting `DATABASE_URL` to a migrated test copy. It writes node previews and a manual-route fingerprint under `tmp/`; it does not create fixtures or save assignments.

Final checks: 79 routing/junction/manual/inventory/group backend tests and 91 frontend routing tests pass; TypeScript and the production build pass. Migration upgrade/downgrade/upgrade, backend startup and rollback-only junction-area CRUD pass against the isolated PostgreSQL copy. Browser checks verify the actual 801↔811 four-cable LC detail table, retained connection sections after mouse selection, plan/underside invariance and navigation from a physical opening to its junction. Upper-tier previews correctly report unknown geometry for explicit vertical-opening traversals. Production remains on `074ca9e2b613`, with the original manual-route fingerprint and Docker containers unchanged.

With the full inventory, the browser global view dropped from 57,010 to 24,943 SVG elements; the cable layer dropped from 37,591 to approximately 5,409 elements, using 15 batched paths in the unfocused view. Saved summaries appeared in 0.88 s on reopening and 1.28 s after a page reload in browser automation (including control round trips). A repeat three-sample server-render-only benchmark measured 256 ms median for detailed global cable strokes and 36 ms for the compact summary, excluding browser paint. Summary encoding took 14 ms and persisted zero individual cables. The 74 frontend routing tests cover summary round trips, invalidation/expiry, missing storage, response races, disconnected subpaths and focused-route colors; TypeScript and the production build pass. Browser checks confirmed cached inspection is read-only until current data restores editing controls.

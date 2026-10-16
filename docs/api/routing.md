# LBB01 schematic routing API

Routing describes technician-facing cold-aisle pathways in local integer inches. It uses existing PostgreSQL `Room` and `Cabinet` entities and stores eleven routing domain tables, including optional manual segment markings and bundle placements. Generated graph nodes and edges are never persisted. Existing cable topology and halls without routing layouts continue to work independently.

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

Resources are `sections`, `bands`, `row-pairs`, `cabinet-rows`, `cross-routes`, `cross-route-tiers`, `passage-tiers`, `vertical-transitions`, `segment-annotations`, and `bundle-placements`. Writes require the existing manager role. Resource payloads are validated by the Pydantic schemas in `backend/schemas/routing.py`; IDs use the repository's `uid` convention. Foreign routing references must belong to the same layout. Duplicate configuration returns 409; invalid dimensions, missing openings and disconnected routes return 422; missing records return 404.

Five sections, the ordered five-band structure, and the associated cross routes are required scaffold. Individual deletion of sections, bands or cross routes is rejected. Cross routes can be disabled; deleting a cabinet row or pair cascades its associated cold-side routes and tiers. Deleting a whole layout removes the scaffold. Reimports preserve routing Room/Building anchors and all routing configuration.

## Geometry and routing

Ordered band widths are 34, 336, 24, 360, 34 inches. The backend derives boundaries, centers 17/382/771, width 788, and cross-route lengths 365/389. The 264-inch module is cold aisle 0–120, A row 120–144, hot aisle 144–240, B row 240–264. Row centers alternate 120/144 inches apart. A/B identifies members of a shared hot aisle; row-field association identifies which side of the hall contains the pair.

North/south pairs occupy parallel longitudinal slots. Each section consumes the larger of its configured north/south pair counts times the module width, followed by a 216-inch extra gap except after Section 5. Empty intermediate sections still preserve all four gaps. A final 120-inch cold-aisle context accommodates the last B row's outward-facing route; it does not change section offsets or gap stations.

Width/depth/gap dimensions whose centers must stay in integer inches are even-valued. Configured face offsets and stations may be any nonnegative integer inch. The backend derives the module when row/aisle dimensions change. Existing explicit route widths and MANUAL/FIELD_MEASURED stations are preserved. The backend rejects route placement outside the associated cold aisle or section gap.

Every enabled cross-route tier intersects compatible enabled passage tiers using separate cross-route and passage nodes joined by zero-length JUNCTION edges. CROSS_ROUTE edges join adjacent passages only; missing CENTRAL never produces a NORTH–SOUTH shortcut. PASSAGE edges join sorted stations continuously through all five sections. Each enabled opening creates one bidirectional adjacent-tier VERTICAL edge, and requires both configured passage tiers to be enabled. VERTICAL edges have zero planar length; disabling an opening removes that connectivity.

Route preview minimizes, in order: vertical transition count, planar length, edge count, then the ordered stable edge-ID sequence. It returns ordered nodes and edges, compressed technician instructions, opening labels, `vertical_transition_count`, `planar_length_in`, and `length_label: "Planar pathway length"`.

Each derived `PASSAGE` and `CROSS_ROUTE` edge carries integer-inch `planar_length_in`, `width_in`, optional `elevation_in`, and a resolved label. Width comes from the persisted passage band or cross route; length comes from the backend-resolved centerlines/stations. Route-preview edges retain these values. Junctions and vertical openings have zero planar length and `width_in: null` because no separate opening width has been measured. Optional elevations describe height above finished floor (AFF); they are metadata, not a graph Z coordinate or a vertical cable-length calculation. The generated graph remains transient.

Row labels derive from explicit section/pair ordering and A/B position, preserving parallel north/south slots. The 021–030 row is **Row 3** on the south side; the aligned 821–830 row is also **Row 3** on the north side. A route label never comes from parsing an arbitrary cabinet name. Passage spans use backend station tokens, such as **South R1–2**, **Central R3–4**, or **North R1–3**. Opening and section-gap endpoints retain their explicit labels.

## Frontend workflow

**Routing** displays all five sections together. Use **Focus section**, zoom buttons, the mouse wheel and blank-space panning to inspect details. T1/T2/T3 use solid/dashed/dash-dot styles. Screen offsets and stroke widths affect rendering only. Select infrastructure for details; select a graph node to inspect incident edges, including zero-length junctions.

The topology cabinet map offers an on/off **Conceptual routes** checkbox. Its subway-style presentation reuses the original cabinet glyphs, category fills, ID/type labels, selection frames, connection badges and progress controls. Small cabinet spacing and wider cold-side gaps make room for routing strokes. Hot aisles are narrower unlabeled gaps. It is explicitly **not to scale**: no physical-width envelopes or dimension annotations appear on this map. SOUTH is left, CENTRAL middle, NORTH right, matching the cabinet-map convention. Cabinet selection continues to drive the existing device and connection panels. The toggle survives section changes. The combined view starts at the selected DH1 section and offers **All sections** / **Fit / reset view** for the continuous global map. **Focus selected cabinet** zooms to nearby row pairs. Segment selection displays actual model length and width independently of screen spacing.

**Geometric routing map** opens the dedicated Routing workspace, whose proportional geometry and default longitudinal orientation are preserved. It retains physical-width envelopes, dimension context, route preview and configuration. Conceptual coordinates are a frontend-only projection of the same domain IDs and graph stations; they never enter pathfinding, persisted geometry or cable-length calculations. Physical openings remain explicit adjacent-tier records on both views.

Resolved layouts include a read-only `cabinets` projection from the existing inventory and `geometry.sections[].data_hall_id`. Each row's cabinet range is scoped to its linked section Room (or the layout's anchor Room when no section Room is configured). Deleted inventory and cabinets in unrelated halls are excluded. Tiles use imported source columns to retain serpentine ordering; missing cabinets leave empty slots. Ambiguous ordering leaves the row context visible without inventing individual positions. Cabinet slots are schematic subdivisions of the row field, not surveyed cabinet footprints. The conceptual map loads the standard cabinet-layout metadata for each section, preserving existing progress displays. The geometric workspace retains its simplified inventory layer, with narrow category strips and a **Cabinets** toggle.

**Configure routing** manages dimensions, band widths, section names, row pairs, A/B rows, pathway tiers and physical openings. Choose an explicit pathway type to add a tier. Disabled tiers remain configurable. Physical-opening forms accept integer inches or feet/inches such as `33'-4"` and show the proposed station before saving. Enable **Route preview**, then select start/destination nodes in the SVG or endpoint selectors. A configuration change clears stale previews.

Vite and nginx both proxy `/routing`. For a separate local validation backend, set `ROUTING_API_TARGET` before launching Vite; the default is `http://127.0.0.1:8000`.

## V1 schematic assumptions

- NORTH/SOUTH measured 34-inch widths may later be confirmed as nominal 36 inches; V1 preserves 34.
- Cold-route envelopes default to touching the cold cabinet face, with configurable face offsets. This is schematic placement.
- DERIVED section-gap routes default to the midpoint of the extra 18-foot gap. This is not a field measurement.
- Tier elevations start unknown and can be entered as integer-inch heights above finished floor. Vertical distance, rack drops, slack, service loops and exact cable length remain outside V1.

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

The **Style fixtures (fake cables)** checkbox adds a few local display examples in Section 1 and the Section 1–2 gap, including one unusable example. It also displays three explicit review cables from cabinet **021 to 031**: LC, MPO and Cat6. They follow the configured cold-side routes through CENTRAL, with short connectors at the centers of the cabinets' cold-side edges. Parallel lanes remain continuous through the turns. **Focus 021 → 031** zooms to this sample run. These connectors are a display-only illustration; no port-to-pathway drop geometry, measured drop dimensions, tiers or openings are added to the model.

Selecting a conceptual segment or sample cabinet connector opens **ten compact metadata lines and tier/section diagrams on the left**, with **cable details on the right**. The tier overview shows known AFF elevations, cable-type markings, bundle placements and explicit adjacent-tier opening records in the selected span (including its endpoints). Each tier has an ordinal sectional view, with layer 1 at the bottom and position 1 innermost. A saved viewing/inner-side reference defines what "inner" means. These are ordered placement slots, not measured bundle sizes or tray-fill calculations. Sample cable cards show fixture IDs, type and endpoint cabinets; inventory ports and tiers remain unassigned. Selecting a card highlights that cable's entire sample run. Closing routing details or selecting a cabinet restores the normal cabinet and connection panels.

The 021→031 sample includes clearly labeled **display-only sectional placements**: LC on T1 bottom/inner, MPO on T2 bottom/inner, and Cat6 on T1 layer 2/position 2. Demo tiers do not create graph connectivity, heights or physical openings. Saved placements take precedence over demos. Turn fixtures off to inspect only configured data.

Fixtures make no API writes and never change saved data. Turn them off to inspect empty routes or saved markings. Unmapped or disabled endpoint cabinets/routes do not produce a sample run.

## Tier heights and sectional placements

Migration `b5f63c9e0214` adds nullable `elevation_in` to passage and cross-route tiers, nullable `section_reference` to segment annotations, and `routing_bundle_placements`. It is additive and supports downgrade. Heights accept feet/inches in the UI and persist nonnegative integer inches; blank means unknown. Known enabled tier heights must increase with tier number on the same pathway. No elevations are seeded by initialization.

Open **Configure heights / bundle sections** in the left inspector to configure confirmed tiers, save AFF heights, define the section viewing reference, and create/edit/disable/delete bundle placements. Placements reference a segment annotation and tier, with `layer` and `position` in 1–64. An enabled placement requires a usable segment and an explicitly enabled pathway tier. Duplicate occupied slots and mismatched annotation tiers are rejected.

`source_kind` is `MANUAL`, `BUNDLE`, or `GROUP`. Manual entries need a label. Existing `CableBundle` and cable/bundle `EntityGroup` records are reused through scoped source UIDs; no duplicate inventory entities are created. This uses the application's polymorphic-reference convention. A deleted/reimported source leaves its placement visible as unresolved rather than silently changing its identity; unchanged retired references can be disabled. Optional `cable_class` colors the sectional block and covered route span but does not assign inventory cables. Source lookup loads only when configuration opens.

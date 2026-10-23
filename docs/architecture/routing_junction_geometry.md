# Junction occupation and bundle turns — proposal

Status: design proposal. No database migration, physical arrangement, handling limits, or automatic routing policy is introduced by this document.

## Existing foundation

The derived graph already represents passage/row intersections and physical tier openings. It is regenerated from domain records; generated graph nodes and edges are not persisted.

`RoutingBundlePlacement` references an existing bundle/group and describes its occupation on a pathway span: a multi-cell footprint in the default 12-column by 8-row sectional grid, a physical sectional rectangle, or both. `RoutingBundleConnection` links two placements' START/END endpoints for the same referenced bundle/group. The backend validates common junction location, enabled pathways and explicit openings for adjacent-tier changes. It currently has no turn radius, swept occupation or crossing order.

Extend this foundation rather than making a graph node hold an unrelated list of cables.

## Topology point and physical working area

Keep the graph node as a connectivity point. Add an optional persistent `RoutingJunctionArea` as the local physical working area around that point on a configured routing tier:

- Stable domain UID and layout reference.
- Passage and intersection anchor: cabinet cold-route or section-gap route reference, or an explicit station for a standalone passage station. Derive row/gap stations so they continue to move with section geometry.
- Extents on each side of the anchor in local hall X/Y and usable height above the tier's tray bed. Unknown dimensions stay null.
- Cardinal reference frame, notes, enabled state and whether the configuration is schematic, manually specified or measured.

Do not use a generated node ID as a persistent foreign key. Resolve it from the domain anchor. Coincident CENTRAL intersections have one physical area per tier, with ports for all incident pathways, rather than duplicate working volumes for aligned north/south row records. Contradictory coincident area configurations must be reported.

Incident ports refer to stable domain span endpoints. Their local sectional axes are width-across and height-above-tray-bed, with an explicit cardinal orientation. Reuse the existing section conventions: INNER faces cabinets/hot aisle where defined; CENTRAL has no INNER side. A turn must transform the incoming rectangle into the outgoing port's reference frame; it cannot simply reuse screen X or assume that their left/right directions agree.

## Bundle movements through the junction

Extend `RoutingBundleConnection` with a junction-area reference and optional movement geometry:

- Movement kind: straight, turn or explicit tier-opening traversal.
- Existing incoming/outgoing placement and endpoint references, retaining the actual bundle/group's cable membership.
- Planned inner bend radius, local height/stack arrangement and optional designer-specified guide points. Record intent/measurement provenance.
- Reference to a configured cable-handling profile; missing requirements remain unknown.

Derive a tangent-continuous path and the swept volume of the bundle's rectangle from these inputs. A smooth-looking Bézier is not evidence that a bend-radius requirement has been met. A radius check must consider the innermost cable path, not just the bundle centerline. The endpoint footprints alone also do not uniquely determine a collision-free turn; radius, available area and crossing arrangement are necessary inputs.

Persist the design inputs, not a redundant sampled curve or mesh. Generated curves and a conservative occupation envelope can support plan, elevation and section views. Grid-only footprints remain schematic unless the cell-to-dimension mapping is explicitly configured; never infer physical inches from a 12x8 array alone. Conservative bounding-box overlap should be labeled a possible conflict, not proof that actual swept volumes collide.

## Crossings and stacking within one tier

Add a small `RoutingJunctionCrossing` relation between movements, recording which passes above/below, a specified clearance if known, and any separator/support reference. Derive crossing locations from their paths; do not give the entire junction one global stacking order when paths only cross locally.

Cat6 below LC is a configurable preferred arrangement. It must not silently rewrite a saved manual arrangement, invent an MPO position, or claim the lower bundle is a structural support for the upper one. Fiber protection from pressure/crushing and suitable support remain relevant even with the preferred order.

An OVER/UNDER relation alone is not a verified clearance. For example, an upper bundle's bottom must clear the lower bundle's top by the configured amount, and both movements must fit within the area's known usable height. Unknown clearance, support or envelope dimensions mean unchecked. Crossing-order cycles and inconsistent height assignments must be reported.

Local stacking layers are distinct from routing tiers. Passing over another bundle inside a tray does not introduce a new graph tier or a tier-changing edge. A real T1/T2/T3 change still requires the existing explicit physical opening.

## Handling requirements and dimensions

Use the actual cable construction/SKU and manufacturer requirements to supply diameter or bundle envelope, installed minimum bend radius and installation/under-load minimum bend radius. LC/MPO connector labels and Cat6 category are insufficient to select one universal numeric radius. A bundle uses the most restrictive requirement among its applicable members for the operation being checked; missing member specifications prevent a complete verification.

Retain integer-inch bundle geometry for the current model. Preserve source specification values/units and references, and convert requirements conservatively upward when checking at whole-inch resolution. Do not round a required minimum down. This resolution is not suitable for claiming precise individual-cable packing or exact cable travel. Sub-inch modeling needs an explicit later precision decision across the backend, API and UI.

Manufacturer guidance distinguishes installed and under-load bend limits and calls out protection from crushing and later cable installation:

- [Corning: Cable Trays and Ladder Racks, 005-014](https://www.corning.com/catalog/coc/documents/standard-recommended-procedures/005-014.pdf)
- [Corning: Duct Installation of Fiber Optic Cable, 005-011](https://www.corning.com/catalog/coc/documents/standard-recommended-procedures/005-011.pdf)

## Validation and technician view

Keep topological routing validity separate from physical checks. Each physical check should return OK, conflict or unchecked, with a reason and the affected movements. Unknown geometry must not be presented as a validated installation.

Checks should cover enabled continuation of the same cable group; available junction area/ports; entry/exit footprint continuity and orientation; minimum inner radius; movement occupation inside the configured area; clearance at crossings; contradictory stack order; and opening-specific fit where a tier changes. Initial physical warnings should not silently reroute cables or overwrite manual assignments.

Selecting a junction should show:

1. A local plan view of straight/turning bundle movements, with over/under indications.
2. A sectional or elevation view showing occupation and stack order within each routing tier.
3. Actual group membership, handling-spec source and unresolved checks.

Implementation sequence: domain area/connection/crossing metadata and validation first; local preview second; optional route-cost integration only after geometry and specifications are available. These additions do not require CAD or a surveyed hall model.

Existing PLANAR PATHWAY LENGTH remains unchanged. Future bend-travel estimates must trim the consumed straight portions and count each junction curve once, without adding a curve to an already counted corner. Unknown vertical travel, rack drops and slack still prevent reporting an exact cable length.

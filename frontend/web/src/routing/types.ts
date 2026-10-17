export type Tier = 1 | 2 | 3;
export type CardinalDirection = "NORTH" | "SOUTH" | "EAST" | "WEST";
export type PathwayType = "LADDER_RACK" | "BASKET_TRAY";
export type CableClass = "LC" | "CAT6" | "MPO" | "MPO_TRUNK_T2_T1_RO" | "CROSS_SECTION_CAT6" | "CROSS_SECTION_LC";
export type SegmentSpan = {
  passage_band_uid: string | null; cross_route_uid: string | null;
  start_station_in: number | null; end_station_in: number | null;
  from_passage_band_uid: string | null; to_passage_band_uid: string | null;
};
export type SegmentAnnotation = RecordBase & SegmentSpan & { updated_at: string; tier: Tier | null; usable: boolean; cable_classes: CableClass[]; notes: string | null; section_reference: string | null; section_inner_direction: CardinalDirection | null; grid_columns: number; grid_rows: number; section_height_in: number | null };
export type Occupation = { layer: number | null; position: number | null; slot_width: number | null; slot_height: number | null; offset_across_in: number | null; offset_up_in: number | null; occupied_width_in: number | null; occupied_height_in: number | null };
export type BundlePlacement = RecordBase & Occupation & { segment_annotation_uid: string; tier: Tier; source_kind: "MANUAL" | "BUNDLE" | "GROUP"; source_uid: string | null; label: string | null; resolved_label: string; source_available: boolean; cable_class: CableClass | null; notes: string | null; enabled: boolean };
export type BundleConnection = RecordBase & { from_placement_uid: string; from_end: "START" | "END"; to_placement_uid: string; to_end: "START" | "END"; vertical_transition_uid: string | null; enabled: boolean; notes: string | null; from_node_id: string; to_node_id: string };
export type CabinetAttachment = RecordBase & { segment_annotation_uid: string; cabinet_uid: string; offset_in: number; tier: Tier | null; label: string | null; notes: string | null; enabled: boolean; cabinet_available: boolean; x_in: number; y_in: number };
export type SectionOccupation = { segment_annotation_uid: string; tier: Tier; grid_columns: number; grid_rows: number; cells: number[][]; occupants: Array<{value: number; placement_uid: string}>; rectangles: Array<Pick<BundlePlacement, "uid" | "offset_across_in" | "offset_up_in" | "occupied_width_in" | "occupied_height_in">>; width_in: number; height_in: number | null };
export type PlacementSource = { kind: "BUNDLE" | "GROUP"; uid: string; name: string };
export type PassageCode = "NORTH" | "CENTRAL" | "SOUTH";
export type RecordBase = { uid: string; routing_layout_uid: string };
export type RoutingLayout = {
  uid: string; room_uid: string; name: string; physical_hall_code: string;
  cabinet_row_depth_in: number; hot_aisle_clear_in: number; cold_aisle_clear_in: number;
  row_pair_module_in: number; section_extra_gap_in: number; default_cross_route_width_in: number;
  max_tier: number; cabinets_per_row: number;
  bottom_basket_elevation_in: number | null; north_south_top_elevation_in: number | null;
  longitudinal_direction: "EAST" | "WEST" | null;
};
export type InventoryCable = {
  uid: string; cable_type: string; cable_group: string; cable_class?: CableClass | null;
  source_cabinet_uid: string | null; source_cabinet_id: string | null; destination_cabinet_uid: string | null; destination_cabinet_id: string | null;
  source_port_uid: string; source_port_name: string | null; destination_port_uid: string; destination_port_name: string | null;
  source_label: string; destination_label: string; notes: string;
};
export type PlacementCables = { placement_uid: string; label: string; source_available: boolean; cables: InventoryCable[]; summary: Array<{cable_type: string; source_cabinet_id: string | null; destination_cabinet_id: string | null; count: number}> };
export type ReviewPoint = { node_id: string; x_in: number; y_in: number; tier: Tier; passage_band_uid: string | null; passage_code?: PassageCode; cabinet_uid: string | null };
export type ReviewPath = { method: "SAME_ROW" | "ASTAR" | "MANUAL"; points: ReviewPoint[]; load_ids: string[]; segment_ids: string[]; planar_length_in: number; vertical_transition_count: number; length_label: "Planar pathway length" };
export type ReviewGroup = { uid: string; source_cabinet_uid: string; destination_cabinet_uid: string; source_cabinet_id: string; destination_cabinet_id: string; cable_type: string; cable_class: CableClass | null; cable_uids: string[]; count: number; tier: Tier | null; reason: string | null;
  route: ReviewPath | null; route_source: "MANUAL" | "DEFAULT"; manual_status: "VALID" | "INVALID" | null; manual_version: string | null; manual_revision: number; manual_notes: string; manual_updated_by: string | null; start_tier: Tier; end_tier: Tier };
export type PlanningSegment = { id: string; segment_id: string; source: ReviewPoint; target: ReviewPoint; planar_length_in: number; label: string;
  edge_type: "PASSAGE" | "CROSS_ROUTE" | "VERTICAL"; tier: Tier | null; lower_tier: Tier | null; upper_tier: Tier | null; vertical_transition_uid: string | null; pathway_type: PathwayType | null; width_in: number | null };
export type ReviewLoad = Pick<PlanningSegment, "id" | "segment_id" | "source" | "target" | "planar_length_in" | "tier" | "edge_type" | "lower_tier" | "upper_tier"> & { group_uids: string[]; cable_classes: CableClass[]; cable_count: number };
export type CableReview = { label: string; provisional: true; tier: null; algorithm: string; cabinet_uids: string[]; inventory_cable_count: number; same_cabinet_count: number; routed_cable_count: number; unrouted_cable_count: number; cable_types: Record<string, number>; groups: ReviewGroup[]; loads: ReviewLoad[]; cables: InventoryCable[]; notes: string; planning_segments: PlanningSegment[]; topology_revision: string; manual_group_count: number };
export type ManualChain = ReviewPath & {id: string; label: string};
export type ManualDraft = {ids: string[]; checkpoints: number[]; startTier: Tier; endTier: Tier};
export type ManualPreview = {complete: boolean; prefix: ReviewPath; suggestion: ReviewPath | null; next_chains: ManualChain[]; destination: ReviewPoint};
export type Section = RecordBase & { ordinal: number; name: string; room_uid: string | null };
export type Band = RecordBase & { ordinal: number; kind: "PASSAGE" | "ROW_FIELD"; code: string; width_in: number };
export type RowPair = RecordBase & { routing_section_uid: string; row_field_band_uid: string; ordinal_in_section: number; name: string | null };
export type CabinetRow = RecordBase & {
  row_pair_uid: string; position_in_pair: "A" | "B"; name: string; existing_row_reference: string | null;
  cold_route_face_offset_in: number; enabled: boolean; cabinet_number_start: number | null; cabinet_number_end: number | null;
};
export type CrossRoute = RecordBase & {
  kind: "CABINET_COLD_AISLE" | "SECTION_GAP"; cabinet_row_uid: string | null; section_boundary_after_section_uid: string | null;
  width_in: number; station_source: "DERIVED" | "MANUAL" | "FIELD_MEASURED"; manual_station_in: number | null;
  label: string | null; notes: string | null; enabled: boolean;
};
export type TierElevation = { elevation_in: number | null; elevation_reference: "BOTTOM_BASKET" | "NORTH_SOUTH_TOP" | null; effective_elevation_in: number | null };
export type CrossRouteTier = RecordBase & TierElevation & { cross_route_uid: string; tier: Tier; pathway_type: PathwayType; enabled: boolean };
export type PassageTier = RecordBase & TierElevation & { passage_band_uid: string; tier: Tier; pathway_type: PathwayType; enabled: boolean };
export type VerticalTransition = RecordBase & {
  passage_band_uid: string; station_in: number; lower_tier: Tier; upper_tier: Tier;
  label: string | null; notes: string | null; enabled: boolean;
};
export type Bounds = { start_in: number; end_in: number; center_in: number };
export type RoutingCabinet = {
  cabinet_uid: string; cabinet_id: string; data_hall_id: string; category: string; cabinet_group: string;
  source_row: number | null; source_col: number | null;
};
export type SchematicOrientation = "longitudinal" | "cabinet-map";
export type ResolvedLayout = {
  layout: RoutingLayout; sections: Section[]; bands: Band[]; row_pairs: RowPair[]; cabinet_rows: CabinetRow[];
  cross_routes: CrossRoute[]; cross_route_tiers: CrossRouteTier[]; passage_tiers: PassageTier[];
  vertical_transitions: VerticalTransition[];
  segment_annotations: SegmentAnnotation[];
  bundle_placements: BundlePlacement[];
  bundle_connections: BundleConnection[];
  cabinet_attachments: CabinetAttachment[];
  section_occupations: SectionOccupation[];
  cabinets: RoutingCabinet[];
  geometry: {
    bands: Array<Band & Bounds>; sections: Array<Section & Omit<Bounds, "center_in"> & { data_hall_id: string | null }>;
    gaps: Array<Bounds & { after_section_uid: string; before_section_uid: string }>;
    row_pairs: Array<RowPair & Omit<Bounds, "center_in"> & { hot_aisle_start_in: number; hot_aisle_end_in: number }>;
    cabinet_rows: Array<CabinetRow & Bounds & { section_uid: string; row_field_band_uid: string; existing_cabinet_uids: string[]; row_number: number; display_name: string }>;
    cold_aisles: Array<Omit<Bounds, "center_in"> & { section_uid: string; row_field_band_uid: string }>;
    cross_routes: Array<CrossRoute & Omit<Bounds, "center_in"> & { station_in: number; effective_enabled: boolean; display_label: string; passage_band_uids?: string[]; start_y_in: number; end_y_in: number }>;
    station_labels: Array<{ passage_band_uid: string; station_in: number; token: string }>;
    total_width_in: number; hall_length_in: number; module_end_in: number;
  };
};
export type GraphNode = {
  id: string; node_type: "JUNCTION" | "PASSAGE_STATION"; roles: Array<"JUNCTION" | "TIER_OPENING" | "ENDPOINT" | "STATION">; x_in: number; y_in: number;
  station_in: number; tier: Tier; passage_code: PassageCode; passage_band_uid: string;
  cross_route_uid: string | null; cross_route_kind: string | null; cabinet_row_uid: string | null;
  vertical_transition_uids: string[]; label: string | null;
  cross_route_uids: string[]; cabinet_row_uids: string[]; bundle_connection_uids: string[];
};
export type GraphEdge = {
  id: string; edge_type: "CROSS_ROUTE" | "PASSAGE" | "VERTICAL"; source_node_id: string; target_node_id: string;
  planar_length_in: number; width_in: number | null; tier: Tier | null; lower_tier: Tier | null; upper_tier: Tier | null;
  pathway_type: PathwayType | null; passage_code: PassageCode | null; cross_route_uid: string | null;
  cross_route_kind: string | null; cabinet_row_uid: string | null; vertical_transition_uid: string | null;
  usable: boolean; cable_classes: CableClass[];
  bundle_placement_uids: string[]; cabinet_attachment_uids: string[];
  elevation_in: number | null; label: string | null;
};
export type RoutingGraph = { nodes: GraphNode[]; edges: GraphEdge[] };
export type RoutePreview = RoutingGraph & {
  vertical_transition_count: number; planar_length_in: number; length_label: "Planar pathway length";
  steps: string[]; vertical_opening_labels: string[];
};
export type Selection = { kind: "passage" | "cross" | "row" | "transition" | "edge" | "node" | "cabinet"; uid: string } | null;
export type Resource = "sections" | "bands" | "row-pairs" | "cabinet-rows" | "cross-routes" | "cross-route-tiers" | "passage-tiers" | "vertical-transitions" | "segment-annotations" | "bundle-placements" | "bundle-connections" | "cabinet-attachments";
export type Mutate = (resource: Resource | "layout", values: object, uid?: string, remove?: boolean) => Promise<boolean>;

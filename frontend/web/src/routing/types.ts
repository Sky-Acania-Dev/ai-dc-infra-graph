export type Tier = 1 | 2 | 3;
export type PathwayType = "LADDER_RACK" | "BASKET_TRAY";
export type PassageCode = "NORTH" | "CENTRAL" | "SOUTH";
export type RecordBase = { uid: string; routing_layout_uid: string };
export type RoutingLayout = {
  uid: string; room_uid: string; name: string; physical_hall_code: string;
  cabinet_row_depth_in: number; hot_aisle_clear_in: number; cold_aisle_clear_in: number;
  row_pair_module_in: number; section_extra_gap_in: number; default_cross_route_width_in: number;
  max_tier: number; cabinets_per_row: number;
};
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
export type CrossRouteTier = RecordBase & { cross_route_uid: string; tier: Tier; pathway_type: PathwayType; enabled: boolean };
export type PassageTier = RecordBase & { passage_band_uid: string; tier: Tier; pathway_type: PathwayType; enabled: boolean };
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
  cabinets: RoutingCabinet[];
  geometry: {
    bands: Array<Band & Bounds>; sections: Array<Section & Omit<Bounds, "center_in"> & { data_hall_id: string | null }>;
    gaps: Array<Bounds & { after_section_uid: string; before_section_uid: string }>;
    row_pairs: Array<RowPair & Omit<Bounds, "center_in"> & { hot_aisle_start_in: number; hot_aisle_end_in: number }>;
    cabinet_rows: Array<CabinetRow & Bounds & { section_uid: string; row_field_band_uid: string; existing_cabinet_uids: string[] }>;
    cold_aisles: Array<Omit<Bounds, "center_in"> & { section_uid: string; row_field_band_uid: string }>;
    cross_routes: Array<CrossRoute & Omit<Bounds, "center_in"> & { station_in: number; effective_enabled: boolean }>;
    total_width_in: number; hall_length_in: number; module_end_in: number;
  };
};
export type GraphNode = {
  id: string; node_type: "CROSS_PASSAGE_INTERSECTION" | "PASSAGE_STATION"; x_in: number; y_in: number;
  station_in: number; tier: Tier; passage_code: PassageCode; passage_band_uid: string;
  cross_route_uid: string | null; cross_route_kind: string | null; cabinet_row_uid: string | null;
  vertical_transition_uids: string[]; label: string | null;
};
export type GraphEdge = {
  id: string; edge_type: "CROSS_ROUTE" | "PASSAGE" | "JUNCTION" | "VERTICAL"; source_node_id: string; target_node_id: string;
  planar_length_in: number; width_in: number | null; tier: Tier | null; lower_tier: Tier | null; upper_tier: Tier | null;
  pathway_type: PathwayType | null; passage_code: PassageCode | null; cross_route_uid: string | null;
  cross_route_kind: string | null; cabinet_row_uid: string | null; vertical_transition_uid: string | null;
};
export type RoutingGraph = { nodes: GraphNode[]; edges: GraphEdge[] };
export type RoutePreview = RoutingGraph & {
  vertical_transition_count: number; planar_length_in: number; length_label: "Planar pathway length";
  steps: string[]; vertical_opening_labels: string[];
};
export type Selection = { kind: "passage" | "cross" | "row" | "transition" | "edge" | "node" | "cabinet"; uid: string } | null;
export type Resource = "sections" | "bands" | "row-pairs" | "cabinet-rows" | "cross-routes" | "cross-route-tiers" | "passage-tiers" | "vertical-transitions";
export type Mutate = (resource: Resource | "layout", values: object, uid?: string, remove?: boolean) => Promise<boolean>;

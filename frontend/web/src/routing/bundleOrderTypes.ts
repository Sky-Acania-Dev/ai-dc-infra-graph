import type { CableClass, CardinalDirection, SegmentSpan, Tier } from "./types";

export type SectionEnd = "SPAN" | "START" | "END";
export type OrderUnit = {
  kind: "RACK_PAIR" | "CABLE_LIST"; cable_uids?: string[] | null;
  source_cabinet_uid?: string | null; destination_cabinet_uid?: string | null; cable_type?: string | null;
  layer: number; position: number; slot_width: number; slot_height: number; label?: string | null;
  unit_uid: string; resolved_label: string; cable_count: number | null; review_group_uid?: string | null;
  membership_status?: string; cable_class?: CableClass | null;
  source_rack_position?: number | null; destination_rack_position?: number | null;
};
export type OrderDraft = { expected_version: string; grid_columns: number; grid_rows: number; units: object[]; notes?: string | null };
export type BundleContents = {
  version: string; grid_columns: number; grid_rows: number; units: OrderUnit[]; status: string;
  bundle_placement_uid: string | null; defined_end: SectionEnd | null; inherited: boolean; errors: string[];
  reference: { column_1_direction: CardinalDirection; column_1_is_inner: boolean };
  notes?: string | null; assigned_cable_count?: number; unassigned_cable_count?: number | null;
};
export type SectionOrder = BundleContents & { span: SegmentSpan & { tier: Tier }; section_end: SectionEnd; width_in: number; group_count: number; cable_count: number };
export type SectionOrderRequest = { span: SegmentSpan & { tier: Tier }; section_end: SectionEnd; contents?: OrderDraft };

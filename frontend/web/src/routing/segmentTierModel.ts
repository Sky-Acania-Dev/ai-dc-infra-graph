import type { ConceptualSegment } from "./conceptualSegments";
import type { BundlePlacement, CableClass, CrossRouteTier, Occupation, PassageTier, ResolvedLayout, Tier } from "./types";
import { sectionDirections } from "./sectionDirections.ts";

export type SectionBlock = Occupation & Pick<BundlePlacement, "uid" | "tier" | "cable_class" | "notes"> & { label: string; sourceAvailable: boolean };
export function segmentTierModel(data: ResolvedLayout, segment: ConceptualSegment) {
  const records: Array<PassageTier | CrossRouteTier> = segment.passage_band_uid
    ? data.passage_tiers.filter(t => t.passage_band_uid === segment.passage_band_uid)
    : data.cross_route_tiers.filter(t => t.cross_route_uid === segment.cross_route_uid);
  const parents = (data.segment_annotations ?? []).filter(a => segment.passage_band_uid
    ? a.passage_band_uid === segment.passage_band_uid && a.start_station_in! <= segment.start_station_in! && a.end_station_in! >= segment.end_station_in!
    : a.cross_route_uid === segment.cross_route_uid && a.from_passage_band_uid === segment.from_passage_band_uid && a.to_passage_band_uid === segment.to_passage_band_uid);
  const parentIds = new Set(parents.map(p => p.uid));
  const placements = (data.bundle_placements ?? []).filter(p => parentIds.has(p.segment_annotation_uid) && p.enabled);
  const tiers: Tier[] = records.map(t => t.tier).sort();
  const markedClasses: Partial<Record<Tier, CableClass[]>> = Object.fromEntries(tiers.map(tier => [tier,
    [...new Set(parents.filter(p => p.usable && (p.tier == null || p.tier === tier)).flatMap(p => p.cable_classes))]]));
  const blocks: SectionBlock[] = placements.map(p => ({ ...p, slot_width: p.slot_width ?? (p.layer != null ? 1 : null), slot_height: p.slot_height ?? (p.layer != null ? 1 : null), label: p.resolved_label ?? p.label ?? p.source_uid ?? "Bundle", sourceAvailable: p.source_available }));
  const routeStation = data.geometry.cross_routes.find(r => r.uid === segment.cross_route_uid)?.station_in;
  const openings = data.vertical_transitions.filter(v => segment.passage_band_uid
    ? v.passage_band_uid === segment.passage_band_uid && v.station_in >= segment.start_station_in! && v.station_in <= segment.end_station_in!
    : v.station_in === routeStation && [segment.from_passage_band_uid, segment.to_passage_band_uid].includes(v.passage_band_uid));
  return { records, tiers, blocks, markedClasses, openings, parents, directions: sectionDirections(data, segment), width_in: segment.width_in, occupations: data.section_occupations ?? [], measuredBottom: data.layout.bottom_basket_elevation_in ?? null, measuredTop: ["NORTH", "SOUTH"].includes(data.bands.find(b => b.uid === segment.passage_band_uid)?.code ?? "") ? data.layout.north_south_top_elevation_in ?? null : null, reference: parents.find(p => p.section_reference)?.section_reference ?? null };
}

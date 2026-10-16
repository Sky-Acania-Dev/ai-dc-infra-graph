import type { CableClass, GraphEdge, ResolvedLayout, RoutingGraph, SegmentAnnotation, SegmentSpan, Tier } from "./types";

export type ConceptualSegment = SegmentSpan & { id: string; label: string; planar_length_in: number; width_in: number };
const spanDefaults: SegmentSpan = { passage_band_uid: null, cross_route_uid: null, start_station_in: null, end_station_in: null, from_passage_band_uid: null, to_passage_band_uid: null };

export function rowName(data: ResolvedLayout, uid: string | null | undefined) {
  const row = data.geometry.cabinet_rows.find(r => r.uid === uid);
  return row?.display_name ?? (row?.row_number ? `Row ${row.row_number}` : row?.name ?? "Row");
}
export function crossName(data: ResolvedLayout, uid: string) {
  const route = data.geometry.cross_routes.find(r => r.uid === uid);
  return route?.display_label ?? (route?.cabinet_row_uid ? rowName(data, route.cabinet_row_uid) : route?.label ?? "Section gap");
}
export function passageName(data: ResolvedLayout, uid: string, start: number, end: number) {
  const code = data.bands.find(b => b.uid === uid)?.code ?? "Passage";
  const title = code[0] + code.slice(1).toLowerCase();
  const token = (station: number) => data.geometry.station_labels?.find(s => s.passage_band_uid === uid && s.station_in === station)?.token ?? `@${station} in`;
  const a = token(start), b = token(end);
  return `${title} ${a}–${/^R\d+$/.test(a) && /^R\d+$/.test(b) ? b.slice(1) : b}`;
}

// These are presentation spans derived from domain pathways, independent of enabled tiers.
export function conceptualSegments(data: ResolvedLayout): ConceptualSegment[] {
  const bands = data.geometry.bands.filter(b => b.kind === "PASSAGE").sort((a, b) => a.ordinal - b.ordinal);
  const routes = data.geometry.cross_routes.filter(r => r.effective_enabled);
  const annotations = data.segment_annotations ?? [];
  const segments: ConceptualSegment[] = [];
  for (const band of bands) {
    const stations = [...new Set([0, data.geometry.hall_length_in, ...routes.map(r => r.station_in),
      ...data.vertical_transitions.filter(v => v.enabled && v.passage_band_uid === band.uid).map(v => v.station_in),
      ...annotations.filter(a => a.passage_band_uid === band.uid).flatMap(a => [a.start_station_in!, a.end_station_in!])])].sort((a, b) => a - b);
    stations.slice(1).forEach((end, i) => segments.push({ ...spanDefaults, id: `guide:passage:${band.uid}:${stations[i]}:${end}`,
      passage_band_uid: band.uid, start_station_in: stations[i], end_station_in: end, label: passageName(data, band.uid, stations[i], end),
      planar_length_in: end - stations[i], width_in: band.width_in }));
  }
  for (const route of routes) {
    const label = crossName(data, route.uid);
    const row = data.geometry.cabinet_rows.find(r => r.uid === route.cabinet_row_uid);
    const field = data.bands.find(b => b.uid === row?.row_field_band_uid);
    bands.slice(1).forEach((band, i) => {
      // Aligned rows have distinct routes on their respective cabinet fields.
      // Their coincident continuation is represented by the other field's route.
      if (route.kind === "CABINET_COLD_AISLE" && field && (field.code === "NORTH_FIELD" ? i !== 0 : i !== 1)) return;
      segments.push({ ...spanDefaults, id: `guide:cross:${route.uid}:${bands[i].uid}:${band.uid}`,
      cross_route_uid: route.uid, from_passage_band_uid: bands[i].uid, to_passage_band_uid: band.uid,
      label,
      planar_length_in: band.center_in - bands[i].center_in, width_in: route.width_in });
    });
  }
  return segments;
}

export function annotationFor(data: ResolvedLayout, segment: SegmentSpan, tier: Tier | null): SegmentAnnotation | undefined {
  const station = (uid: string | null) => data.geometry.cross_routes.find(r => r.uid === uid)?.station_in;
  return data.segment_annotations?.find(a => a.tier === tier && (segment.passage_band_uid
    ? a.passage_band_uid === segment.passage_band_uid && a.start_station_in! <= segment.start_station_in! && a.end_station_in! >= segment.end_station_in!
    : a.cross_route_uid !== null && station(a.cross_route_uid) === station(segment.cross_route_uid) && a.from_passage_band_uid === segment.from_passage_band_uid && a.to_passage_band_uid === segment.to_passage_band_uid));
}

export function edgeSegment(data: ResolvedLayout, graph: RoutingGraph, edge: GraphEdge): ConceptualSegment | null {
  const a = graph.nodes.find(n => n.id === edge.source_node_id), b = graph.nodes.find(n => n.id === edge.target_node_id);
  if (!a || !b || !["PASSAGE", "CROSS_ROUTE"].includes(edge.edge_type)) return null;
  const ordered = [a, b].sort((a, b) => a.y_in - b.y_in);
  return { ...spanDefaults, id: edge.id, label: edge.label ?? (edge.edge_type === "PASSAGE" ? passageName(data, a.passage_band_uid, Math.min(a.station_in, b.station_in), Math.max(a.station_in, b.station_in)) : crossName(data, edge.cross_route_uid!)),
    ...(edge.edge_type === "PASSAGE" ? { passage_band_uid: a.passage_band_uid, start_station_in: Math.min(a.station_in, b.station_in), end_station_in: Math.max(a.station_in, b.station_in) }
      : { cross_route_uid: edge.cross_route_uid, from_passage_band_uid: ordered[0].passage_band_uid, to_passage_band_uid: ordered[1].passage_band_uid }),
    planar_length_in: edge.planar_length_in, width_in: edge.width_in! };
}

// Deliberately fake and local: never sent to a configuration or cable API.
export function styleFixtures(data: ResolvedLayout, segments: ConceptualSegment[]): Map<string, { cable_classes: CableClass[]; usable: boolean }> {
  const result = new Map<string, { cable_classes: CableClass[]; usable: boolean }>();
  const first = data.geometry.sections.find(s => s.ordinal === 1);
  const rowRoutes = new Set(data.geometry.cabinet_rows.filter(r => r.section_uid === first?.uid).map(r => r.uid));
  const coldRoutes = new Set(data.geometry.cross_routes.filter(r => rowRoutes.has(r.cabinet_row_uid ?? "")).map(r => r.uid));
  const station = (s: ConceptualSegment) => data.geometry.cross_routes.find(r => r.uid === s.cross_route_uid)?.station_in ?? 0;
  const crossings = segments.filter(s => s.cross_route_uid && coldRoutes.has(s.cross_route_uid)).sort((a, b) => station(a) - station(b) || a.label.localeCompare(b.label));
  const classes: CableClass[] = ["LC", "CAT6", "MPO", "MPO_TRUNK_T2_T1_RO"];
  // A few individual examples plus one shared corridor demonstrate parallel cable lanes.
  classes.forEach((c, i) => { if (crossings[i]) result.set(crossings[i].id, { cable_classes: [c], usable: true }); });
  const central = data.bands.find(b => b.code === "CENTRAL");
  const shared = crossings.length >= 3 ? segments.find(s => s.passage_band_uid === central?.uid && s.start_station_in! >= station(crossings[0]) && s.end_station_in! <= station(crossings[2])) : undefined;
  if (shared) result.set(shared.id, { cable_classes: ["LC", "CAT6", "MPO"], usable: true });
  if (crossings[5]) result.set(crossings[5].id, { cable_classes: [], usable: false });
  const gap = data.geometry.cross_routes.find(r => r.kind === "SECTION_GAP" && r.section_boundary_after_section_uid === first?.uid);
  segments.filter(s => s.cross_route_uid === gap?.uid).slice(0, 2).forEach((s, i) => result.set(s.id, { cable_classes: [i ? "CROSS_SECTION_LC" : "CROSS_SECTION_CAT6"], usable: true }));
  return result;
}

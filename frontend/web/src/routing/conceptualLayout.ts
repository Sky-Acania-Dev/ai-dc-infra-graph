import type { CabinetTile } from "./cabinetPlacement";
import type { GraphNode, ResolvedLayout } from "./types";

// Display units only: never returned to the API or used for pathway lengths/widths.
const DEFAULT_DISPLAY = { cabinet: 46, row: 30, hot: 10, cold: 56, gap: 72, heading: 30, passage: 34, margin: 40, cabinetGap: 4 };

export function conceptualLayout(data: ResolvedLayout, inventoryTiles: CabinetTile[], size?: { cellWidth: number; cellHeight: number; hotAisleGap: number }) {
  const DISPLAY = size ? { ...DEFAULT_DISPLAY, cabinet: size.cellWidth, row: size.cellHeight, hot: size.hotAisleGap } : DEFAULT_DISPLAY;
  const MODULE = DISPLAY.cold + DISPLAY.row * 2 + DISPLAY.hot;
  const g = data.geometry;
  const fieldWidth = data.layout.cabinets_per_row * (DISPLAY.cabinet + DISPLAY.cabinetGap) - DISPLAY.cabinetGap;
  const fields = new Map<string, { x: number; width: number }>();
  const passages: Array<{ uid: string; code: string; x: number }> = [];
  let x = DISPLAY.margin;
  for (const band of [...g.bands].sort((a, b) => b.ordinal - a.ordinal)) {
    if (band.kind === "PASSAGE") { passages.push({ uid: band.uid, code: band.code, x }); x += DISPLAY.passage; }
    else { fields.set(band.uid, { x, width: fieldWidth }); x += fieldWidth + DISPLAY.passage; }
  }
  const rows = new Map<string, { x: number; y: number; width: number; height: number; name: string; enabled: boolean }>();
  const sections: Array<{ uid: string; name: string; start: number; end: number }> = [];
  const gaps: Array<{ uid: string; start: number; end: number }> = [];
  const hotAisles: Array<{ uid: string; x: number; y: number; width: number; height: number }> = [];
  const stationAnchors = new Map<number, number>();
  let y = 0;
  for (const section of [...g.sections].sort((a, b) => a.ordinal - b.ordinal)) {
    const start = y;
    y += DISPLAY.heading;
    stationAnchors.set(section.start_in, y);
    const pairs = g.row_pairs.filter(p => p.routing_section_uid === section.uid);
    const stations = [...new Set(pairs.map(p => p.start_in))].sort((a, b) => a - b);
    for (const pair of pairs) {
      const base = y + stations.indexOf(pair.start_in) * MODULE;
      const a = base + DISPLAY.cold, b = a + DISPLAY.row + DISPLAY.hot;
      // Physical landmarks establish order; their display spacing is deliberately independent.
      stationAnchors.set(pair.start_in, base);
      stationAnchors.set(pair.hot_aisle_start_in - data.layout.cabinet_row_depth_in, a);
      stationAnchors.set(pair.hot_aisle_start_in, a + DISPLAY.row);
      stationAnchors.set(pair.hot_aisle_end_in, b);
      stationAnchors.set(pair.end_in, base + MODULE);
      const field = fields.get(pair.row_field_band_uid);
      if (!field) continue;
      hotAisles.push({ uid: pair.uid, x: field.x, y: a + DISPLAY.row, width: field.width, height: DISPLAY.hot });
      for (const row of g.cabinet_rows.filter(r => r.row_pair_uid === pair.uid)) {
        rows.set(row.uid, { ...field, y: row.position_in_pair === "A" ? a : b, height: DISPLAY.row, name: row.display_name ?? row.name, enabled: row.enabled });
      }
    }
    y += stations.length * MODULE;
    stationAnchors.set(section.end_in, y);
    sections.push({ uid: section.uid, name: section.name, start, end: y });
    const gap = g.gaps.find(gap => gap.after_section_uid === section.uid);
    if (gap) {
      gaps.push({ uid: gap.after_section_uid, start: y, end: y + DISPLAY.gap });
      stationAnchors.set(gap.center_in, y + DISPLAY.gap / 2);
      y += DISPLAY.gap;
      stationAnchors.set(gap.end_in, y);
    }
  }
  y += DISPLAY.cold;
  stationAnchors.set(g.hall_length_in, y);
  // Give conceptual cold-side strokes room beside the unchanged cabinet glyphs.
  // This visual clearance does not change the backend's face-offset assumption.
  for (const route of g.cross_routes ?? []) {
    const row = rows.get(route.cabinet_row_uid ?? "");
    const physical = g.cabinet_rows.find(r => r.uid === route.cabinet_row_uid);
    if (row && physical && route.station_source === "DERIVED") {
      stationAnchors.set(route.station_in, physical.position_in_pair === "A"
        ? row.y - DISPLAY.cold / 3 : row.y + row.height + DISPLAY.cold / 3);
    }
  }
  const anchors = [...stationAnchors].sort((a, b) => a[0] - b[0]);
  function stationY(station: number) {
    if (!anchors.length) return 0;
    if (station <= anchors[0][0]) return anchors[0][1];
    for (let i = 1; i < anchors.length; i++) {
      const [end, displayEnd] = anchors[i], [start, displayStart] = anchors[i - 1];
      if (station <= end) return displayStart + (station - start) / (end - start) * (displayEnd - displayStart);
    }
    return anchors[anchors.length - 1][1];
  }
  const passageX = new Map(passages.map(p => [p.uid, p.x]));
  const cabinets = inventoryTiles.flatMap(tile => {
    const row = rows.get(tile.rowUid);
    return row ? [{ ...tile, x: row.x + tile.slot * (DISPLAY.cabinet + DISPLAY.cabinetGap), y: row.y, width: DISPLAY.cabinet, height: DISPLAY.row }] : [];
  });
  const projectNode = (node: GraphNode) => ({ x: passageX.get(node.passage_band_uid) ?? 0, y: stationY(node.station_in) });
  return { width: x + DISPLAY.margin, height: y, sections, gaps, rows, hotAisles, passages, passageX, cabinets, stationY, projectNode };
}
export type ConceptualLayout = ReturnType<typeof conceptualLayout>;

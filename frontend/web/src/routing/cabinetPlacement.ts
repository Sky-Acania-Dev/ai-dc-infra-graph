import type { ResolvedLayout, RoutingCabinet } from "./types";

export type CabinetTile = {
  cabinet: RoutingCabinet; rowUid: string; slot: number; enabled: boolean; x: number; y: number; width: number; height: number;
};

// Cabinet slots are display subdivisions of a row field, not measured cabinet widths.
// Source columns retain the imported map's serpentine ordering. Missing racks leave holes.
export function placeRoutingCabinets(data: ResolvedLayout): CabinetTile[] {
  const inventory = new Map((data.cabinets ?? []).map(c => [c.cabinet_uid, c]));
  const tiles: CabinetTile[] = [];
  for (const row of data.geometry.cabinet_rows) {
    const field = data.geometry.bands.find(b => b.uid === row.row_field_band_uid);
    if (!field) continue;
    const cabinets = row.existing_cabinet_uids.map(uid => inventory.get(uid)).filter((c): c is RoutingCabinet => Boolean(c));
    const numbered = cabinets.filter(c => /^\d+$/.test(c.cabinet_id) && c.source_col !== null).sort((a, b) => Number(a.cabinet_id) - Number(b.cabinet_id));
    const first = numbered[0], last = numbered.at(-1);
    const direction = first && last && first !== last && first.source_col !== last.source_col
      ? Math.sign(last.source_col! - first.source_col!) : 0;
    const count = data.layout.cabinets_per_row;
    // Without an authoritative ordering, retain the row context rather than invent rack positions.
    if (!direction || row.cabinet_number_start === null || row.cabinet_number_end === null) continue;
    for (const cabinet of cabinets) {
      const number = Number(cabinet.cabinet_id);
      if (!/^\d+$/.test(cabinet.cabinet_id) || cabinet.source_col === null) continue;
      const numericOffset = number - Number(first.cabinet_id);
      if (cabinet.source_col - first.source_col! !== numericOffset * direction) continue;
      const slot = direction > 0 ? number - row.cabinet_number_start : row.cabinet_number_end - number;
      if (slot < 0 || slot >= count) continue;
      // High Y appears at the left in cabinet-map orientation (south left, north right).
      const low = field.end_in - Math.floor((slot + 1) * field.width_in / count);
      const high = field.end_in - Math.floor(slot * field.width_in / count);
      tiles.push({ cabinet, rowUid: row.uid, slot, enabled: row.enabled, x: row.start_in, y: low, width: row.end_in - row.start_in, height: high - low });
    }
  }
  return tiles;
}

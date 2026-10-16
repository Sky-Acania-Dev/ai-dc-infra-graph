import type { Occupation } from "./types";

/** Demo projection only. Saved section matrices are resolved by the backend. */
export function occupationGrid<T extends Occupation & { uid: string }>(columns: number, rows: number, placements: T[]) {
  const cells = Array.from({length: rows}, () => Array<number>(columns).fill(0));
  const occupants = [...placements].sort((a, b) => a.uid.localeCompare(b.uid));
  occupants.forEach((p, index) => {
    if (p.layer == null) return;
    for (let y = p.layer - 1; y < p.layer - 1 + (p.slot_height ?? 1); y++) {
      for (let x = p.position! - 1; x < p.position! - 1 + (p.slot_width ?? 1); x++) {
        if (!cells[y] || x < 0 || x >= columns) throw new Error("Grid footprint is outside its section.");
        if (cells[y][x]) throw new Error("Grid footprints overlap.");
        cells[y][x] = index + 1;
      }
    }
  });
  return {cells, occupants};
}

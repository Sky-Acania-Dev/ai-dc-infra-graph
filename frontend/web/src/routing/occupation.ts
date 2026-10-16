import type { Occupation } from "./types";
import { formatInches } from "./dimensions";

export function occupationLabel(p: Occupation): string {
  const parts: string[] = [];
  if (p.layer != null) parts.push(`L${p.layer} / P${p.position} · ${p.slot_width ?? 1}×${p.slot_height ?? 1} cells`);
  if (p.offset_across_in != null) parts.push(`${formatInches(p.occupied_width_in!)} × ${formatInches(p.occupied_height_in!)} at ${formatInches(p.offset_across_in)}, ${formatInches(p.offset_up_in!)}`);
  return parts.join(" · ");
}

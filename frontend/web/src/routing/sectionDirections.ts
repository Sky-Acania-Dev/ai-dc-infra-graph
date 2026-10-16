import type { ConceptualSegment } from "./conceptualSegments";
import type { CardinalDirection, ResolvedLayout } from "./types";

export const oppositeDirection: Record<CardinalDirection, CardinalDirection> = {NORTH: "SOUTH", SOUTH: "NORTH", EAST: "WEST", WEST: "EAST"};
export const directionName = (direction: CardinalDirection) => direction[0] + direction.slice(1).toLowerCase();

// "Inner" faces cabinets/the hot aisle, independent of screen or view direction.
export function sectionDirections(data: ResolvedLayout, segment: ConceptualSegment) {
  const code = data.bands.find(b => b.uid === segment.passage_band_uid)?.code;
  const route = data.geometry.cross_routes.find(r => r.uid === segment.cross_route_uid);
  const row = data.geometry.cabinet_rows.find(r => r.uid === route?.cabinet_row_uid);
  const longitudinal = data.layout.longitudinal_direction ?? null;
  const inner: CardinalDirection | null = code === "NORTH" ? "SOUTH" : code === "SOUTH" ? "NORTH"
    : row && longitudinal ? row.position_in_pair === "A" ? longitudinal : oppositeDirection[longitudinal] : null;
  return {inner, hasInner: code !== "CENTRAL", axisStart: (segment.passage_band_uid ? "NORTH" : "WEST") as CardinalDirection};
}

export function sectionView(directions: ReturnType<typeof sectionDirections>, override: CardinalDirection | null | undefined, reversed: boolean) {
  const inner = directions.hasInner ? override ?? directions.inner : null;
  const start = inner ?? directions.axisStart;
  const left = reversed ? oppositeDirection[start] : start;
  const right = oppositeDirection[left];
  const label = (side: CardinalDirection) => inner ? `${side === inner ? "Inner" : "Outer"} · ${directionName(side)}` : directionName(side);
  const from: CardinalDirection = {NORTH: "WEST", SOUTH: "EAST", EAST: "NORTH", WEST: "SOUTH"}[left] as CardinalDirection;
  return {left: label(left), right: label(right), from, to: from && oppositeDirection[from], inner, mirrored: reversed};
}

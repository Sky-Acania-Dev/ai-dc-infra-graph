import type { ConceptualLayout } from "./conceptualLayout";
import type { ConceptualSegment } from "./conceptualSegments";
import type { CableClass, ResolvedLayout } from "./types";

export type FixtureCable = { id: string; cableClass: CableClass; sourceCabinetId: string; destinationCabinetId: string };
export type CabinetFixtureRun = {
  id: string; sourceCabinetUid: string; destinationCabinetUid: string;
  sourceRouteUid: string; destinationRouteUid: string; passageBandUid: string;
  startStation: number; endStation: number; segmentIds: string[]; cables: FixtureCable[];
};
export type DisplayPoint = { x: number; y: number };
export type FixtureRunPart = { id: string; kind: "segment" | "attachment"; label: string; a: DisplayPoint; b: DisplayPoint };

// Explicit review fixture. It never enters the inventory, graph, or routing APIs.
export function cabinetFixtureRun(data: ResolvedLayout, segments: ConceptualSegment[]): CabinetFixtureRun | null {
  const section = data.geometry.sections.find(s => s.ordinal === 1);
  const cabinet = (number: number) => data.cabinets.find(c => /^\d+$/.test(c.cabinet_id) && Number(c.cabinet_id) === number
    && (!section?.data_hall_id || c.data_hall_id === section.data_hall_id));
  const source = cabinet(21), destination = cabinet(31);
  const rowFor = (uid: string) => data.geometry.cabinet_rows.find(r => r.enabled && r.section_uid === section?.uid && r.existing_cabinet_uids.includes(uid));
  const sourceRow = source && rowFor(source.cabinet_uid), destinationRow = destination && rowFor(destination.cabinet_uid);
  if (!source || !destination || !sourceRow || !destinationRow || sourceRow.row_field_band_uid !== destinationRow.row_field_band_uid) return null;
  const routeFor = (uid: string) => data.geometry.cross_routes.find(r => r.effective_enabled && r.cabinet_row_uid === uid);
  const a = routeFor(sourceRow.uid), b = routeFor(destinationRow.uid);
  const central = data.bands.find(b => b.kind === "PASSAGE" && b.code === "CENTRAL");
  if (!a || !b || !central || a.station_in >= b.station_in) return null;
  const crosses = [a, b].map(r => segments.find(s => s.cross_route_uid === r.uid && [s.from_passage_band_uid, s.to_passage_band_uid].includes(central.uid)));
  const passage = segments.filter(s => s.passage_band_uid === central.uid && s.start_station_in! >= a.station_in && s.end_station_in! <= b.station_in);
  if (crosses.some(s => !s) || !passage.length) return null;
  const segmentIds = [crosses[0]!.id, ...passage.map(s => s.id), crosses[1]!.id];
  return {
    id: "fixture:021:031", sourceCabinetUid: source.cabinet_uid, destinationCabinetUid: destination.cabinet_uid,
    sourceRouteUid: a.uid, destinationRouteUid: b.uid, passageBandUid: central.uid,
    startStation: a.station_in, endStation: b.station_in, segmentIds,
    cables: (["LC", "MPO", "CAT6"] as CableClass[]).map(cableClass => ({ id: `fixture:021:031:${cableClass}`, cableClass,
      sourceCabinetId: source.cabinet_id, destinationCabinetId: destination.cabinet_id })),
  };
}

export function projectFixtureRun(data: ResolvedLayout, view: ConceptualLayout, run: CabinetFixtureRun, segments: ConceptualSegment[]) {
  const source = view.cabinets.find(t => t.cabinet.cabinet_uid === run.sourceCabinetUid);
  const destination = view.cabinets.find(t => t.cabinet.cabinet_uid === run.destinationCabinetUid);
  const x = view.passageX.get(run.passageBandUid);
  if (!source || !destination || x === undefined) return null;
  const face = (tile: typeof source): DisplayPoint => {
    const row = data.geometry.cabinet_rows.find(r => r.uid === tile.rowUid)!;
    return { x: tile.x + (tile.width - 2) / 2, y: tile.y + (row.position_in_pair === "A" ? 0 : tile.height - 2) };
  };
  const sourceFace = face(source), destinationFace = face(destination);
  const start = { x: sourceFace.x, y: view.stationY(run.startStation) };
  const end = { x: destinationFace.x, y: view.stationY(run.endStation) };
  const startPassage = { x, y: start.y }, endPassage = { x, y: end.y };
  const points = [sourceFace, start, startPassage, endPassage, end, destinationFace];
  const parts: FixtureRunPart[] = [
    { id: run.sourceCabinetUid, kind: "attachment", label: "Cabinet 021 cold-side attachment", a: sourceFace, b: start },
    { id: run.segmentIds[0], kind: "segment", label: "021 cold-aisle fixture segment", a: start, b: startPassage },
    ...run.segmentIds.slice(1, -1).map(id => {
      const segment = segments.find(s => s.id === id)!;
      return { id, kind: "segment" as const, label: "CENTRAL passage fixture segment", a: { x, y: view.stationY(segment.start_station_in!) }, b: { x, y: view.stationY(segment.end_station_in!) } };
    }),
    { id: run.segmentIds.at(-1)!, kind: "segment", label: "031 cold-aisle fixture segment", a: endPassage, b: end },
    { id: run.destinationCabinetUid, kind: "attachment", label: "Cabinet 031 cold-side attachment", a: end, b: destinationFace },
  ];
  return { points, parts, sourceFace, destinationFace };
}

// Continuous parallel lanes with matching corners, in display coordinates only.
export function offsetPolyline(points: DisplayPoint[], distance: number): DisplayPoint[] {
  const clean = points.filter((p, i) => !i || p.x !== points[i - 1].x || p.y !== points[i - 1].y);
  if (clean.length < 2) return clean;
  const direction = (a: DisplayPoint, b: DisplayPoint) => ({ x: b.x - a.x, y: b.y - a.y });
  const shift = (p: DisplayPoint, d: DisplayPoint) => { const length = Math.hypot(d.x, d.y); return { x: p.x - d.y / length * distance, y: p.y + d.x / length * distance }; };
  return clean.map((point, i) => {
    const incoming = direction(clean[Math.max(0, i - 1)], i ? point : clean[1]);
    const outgoing = direction(i === clean.length - 1 ? clean[i - 1] : point, clean[Math.min(clean.length - 1, i + 1)]);
    if (!i) return shift(point, outgoing);
    if (i === clean.length - 1) return shift(point, incoming);
    const a = shift(point, incoming), b = shift(point, outgoing);
    const cross = incoming.x * outgoing.y - incoming.y * outgoing.x;
    if (!cross) return a;
    const t = ((b.x - a.x) * outgoing.y - (b.y - a.y) * outgoing.x) / cross;
    return { x: a.x + incoming.x * t, y: a.y + incoming.y * t };
  });
}

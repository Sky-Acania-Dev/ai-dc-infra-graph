import type { ConceptualLayout } from "./conceptualLayout";
import type { CableReview, ReviewPoint, ResolvedLayout } from "./types";

const indexes = new WeakMap<ConceptualLayout, {tiles: Map<string, ConceptualLayout["cabinets"][number]>; rows: Map<string, ResolvedLayout["geometry"]["cabinet_rows"][number]>; bands: Map<number, string>}>();
function index(data: ResolvedLayout, view: ConceptualLayout) {
  let result = indexes.get(view);
  if (!result) {result = {tiles: new Map(view.cabinets.map(c=>[c.cabinet.cabinet_uid,c])), rows: new Map(data.geometry.cabinet_rows.map(r=>[r.uid,r])), bands: new Map(data.geometry.bands.filter(b=>b.kind === "PASSAGE").map(b=>[b.center_in,b.uid]))}; indexes.set(view,result);}
  return result;
}
export type Viewport = {x: number; y: number; w: number; h: number};
export function visibleLine(a: {x: number; y: number}, b: {x: number; y: number}, viewport?: Viewport, padding = 40) {
  return !viewport || Math.max(a.x,b.x) >= viewport.x-padding && Math.min(a.x,b.x) <= viewport.x+viewport.w+padding && Math.max(a.y,b.y) >= viewport.y-padding && Math.min(a.y,b.y) <= viewport.y+viewport.h+padding;
}

export function projectReviewPoint(data: ResolvedLayout, view: ConceptualLayout, point: ReviewPoint) {
  if (point.cabinet_uid) {
    const tile = index(data, view).tiles.get(point.cabinet_uid);
    if (tile) return {x: tile.x + (tile.width - 2) / 2, y: view.stationY(point.x_in)};
  }
  const passage = point.passage_band_uid ?? index(data, view).bands.get(point.y_in);
  const x = passage && view.passageX.get(passage);
  return typeof x !== "number" ? null : {x, y: view.stationY(point.x_in)};
}

export function reviewConnector(data: ResolvedLayout, view: ConceptualLayout, uid: string, point: ReviewPoint) {
  const tile = index(data, view).tiles.get(uid);
  const row = index(data, view).rows.get(tile?.rowUid ?? "");
  const route = projectReviewPoint(data, view, point);
  if (!tile || !row || !route) return null;
  return {a: {x: tile.x + (tile.width - 2) / 2, y: tile.y + (row.position_in_pair === "A" ? 0 : tile.height - 2)}, b: route};
}

export function reviewGroupsForPart(review: CableReview, segmentId: string | null | undefined, loadId: string | null, cabinetUid: string | null, junction?: {x_in:number;y_in:number}) {
  const load = review.loads.find(l => l.id === loadId);
  const members = new Set(load?.group_uids ?? []);
  return review.groups.filter(g => load ? members.has(g.uid) : cabinetUid ? [g.source_cabinet_uid, g.destination_cabinet_uid].includes(cabinetUid) : segmentId ? g.route?.segment_ids.includes(segmentId) : junction ? g.route?.points.some(p=>p.x_in === junction.x_in && p.y_in === junction.y_in) : true);
}

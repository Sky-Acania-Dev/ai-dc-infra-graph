import type { ConceptualLayout } from "./conceptualLayout";
import type { CableReview, ReviewPoint, ResolvedLayout } from "./types";

export function projectReviewPoint(data: ResolvedLayout, view: ConceptualLayout, point: ReviewPoint) {
  if (point.cabinet_uid) {
    const tile = view.cabinets.find(c => c.cabinet.cabinet_uid === point.cabinet_uid);
    if (tile) return {x: tile.x + (tile.width - 2) / 2, y: view.stationY(point.x_in)};
  }
  const passage = point.passage_band_uid ?? data.geometry.bands.find(b => b.kind === "PASSAGE" && b.center_in === point.y_in)?.uid;
  const x = passage && view.passageX.get(passage);
  return typeof x !== "number" ? null : {x, y: view.stationY(point.x_in)};
}

export function reviewConnector(data: ResolvedLayout, view: ConceptualLayout, uid: string, point: ReviewPoint) {
  const tile = view.cabinets.find(c => c.cabinet.cabinet_uid === uid);
  const row = data.geometry.cabinet_rows.find(r => r.uid === tile?.rowUid);
  const route = projectReviewPoint(data, view, point);
  if (!tile || !row || !route) return null;
  return {a: {x: tile.x + (tile.width - 2) / 2, y: tile.y + (row.position_in_pair === "A" ? 0 : tile.height - 2)}, b: route};
}

export function reviewGroupsForPart(review: CableReview, segmentId: string | null | undefined, loadId: string | null, cabinetUid: string | null) {
  const load = review.loads.find(l => l.id === loadId);
  return review.groups.filter(g => load ? load.group_uids.includes(g.uid) : cabinetUid ? [g.source_cabinet_uid, g.destination_cabinet_uid].includes(cabinetUid) : segmentId ? g.route?.segment_ids.includes(segmentId) : true);
}

import { SegmentCables } from "./SegmentCables";
import { formatInches } from "./dimensions";
import type { CableReview, ReviewGroup } from "./types";
import type { RoutingCableTableRequest } from "./routingCableDetails";

export function CableReviewPanel({review, groups, selectedGroupUid, onGroup, onViewCables}: {review: CableReview; groups: ReviewGroup[]; selectedGroupUid: string | null; onGroup: (uid: string | null) => void; onViewCables: (request: RoutingCableTableRequest) => void}) {
  const selected = groups.find(g => g.uid === selectedGroupUid);
  const ids = new Set((selected ? [selected] : groups).flatMap(g => g.cable_uids));
  const cables = review.cables.filter(c => ids.has(c.uid));
  return <section className="cable-review-panel" aria-label="Actual cable routing review">
    <h3>Actual cable review</h3><p className="routing-notice">Provisional plan · tiers and packing unassigned. Actual cable IDs; no routing assignments are saved.</p>
    <label>Type / rack-pair group<select aria-label="Actual cable group" value={selected?.uid ?? ""} onChange={e => onGroup(e.target.value || null)}><option value="">All {groups.length} groups on selection</option>{groups.map(g => <option key={g.uid} value={g.uid}>{g.cable_type} × {g.count} · {g.source_cabinet_id} ↔ {g.destination_cabinet_id}{g.route ? g.route.method === "SAME_ROW" ? " · same row" : " · A*" : " · unrouted"}</option>)}</select></label>
    {selected && <p className="section-selection-info">{selected.cable_type} × {selected.count} · {selected.source_cabinet_id} ↔ {selected.destination_cabinet_id}<br />{selected.route ? `${selected.route.method === "SAME_ROW" ? "Direct cold-side row route" : "A* cross-row placeholder"} · Planar pathway length ${formatInches(selected.route.planar_length_in)}` : selected.reason}<br />Tier and individual bundle positions remain unassigned.</p>}
    {!groups.length && <p>No actual pilot cables use this part of the pathway.</p>}
    <SegmentCables cables={[]} inventoryCables={cables} onViewCables={onViewCables} />
  </section>;
}

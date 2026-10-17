import { projectReviewPoint, reviewConnector } from "./cableReviewProjection";
import { RouteStroke } from "./RouteStroke";
import type { ConceptualLayout } from "./conceptualLayout";
import type { CableClass, CableReview, ResolvedLayout, ReviewLoad } from "./types";

export function CableReviewLayer({data, view, review, scale, selectedGroupUid, selectedLoadId, onLoad, onAttachment}: {
  data: ResolvedLayout; view: ConceptualLayout; review: CableReview; scale: number; selectedGroupUid: string | null; selectedLoadId: string | null;
  onLoad: (load: ReviewLoad) => void; onAttachment: (uid: string) => void;
}) {
  const selected = review.groups.find(g => g.uid === selectedGroupUid);
  const selectedLoads = new Set(selected?.route?.load_ids ?? []);
  return <g className="actual-cable-review-layer" aria-label="Provisional routes for actual inventory cables">
    {review.loads.map(load => {
      const a = projectReviewPoint(data, view, load.source), b = projectReviewPoint(data, view, load.target);
      if (!a || !b) return null;
      return <g key={load.id} data-selectable="true" role="button" tabIndex={0} aria-label={`Inspect actual cable segment ${load.id}`} opacity={selected && !selectedLoads.has(load.id) ? .15 : 1}
        onClick={e => {e.stopPropagation(); onLoad(load);}} onKeyDown={e => {if (e.key === "Enter" || e.key === " ") {e.preventDefault(); e.stopPropagation(); onLoad(load);}}}>
        <RouteStroke a={a} b={b} scale={scale} cableClasses={selected ? load.cable_classes.filter(c => c === selected.cable_class) : load.cable_classes} selected={selectedLoadId === load.id || selectedLoads.has(load.id)} />
        <rect x={Math.min(a.x,b.x)-8/scale} y={Math.min(a.y,b.y)-8/scale} width={Math.abs(a.x-b.x)+16/scale} height={Math.abs(a.y-b.y)+16/scale} fill="transparent" />
        <title>{`${load.cable_count.toLocaleString()} actual cables · ${load.group_uids.length} type/rack-pair groups · Tier unassigned · Provisional plan`}</title>
      </g>;
    })}
    {review.cabinet_uids.map(uid => {
      const groups = review.groups.filter(g => g.route && [g.source_cabinet_uid, g.destination_cabinet_uid].includes(uid));
      const first = groups[0]; if (!first?.route) return null;
      const point = first.source_cabinet_uid === uid ? first.route.points[0] : first.route.points.at(-1)!;
      const connector = reviewConnector(data, view, uid, point); if (!connector) return null;
      const classes = [...new Set(groups.flatMap(g => g.cable_class ? [g.cable_class] : []))] as CableClass[];
      return <g key={uid} role="button" tabIndex={0} data-selectable="true" aria-label={`Inspect actual cable attachment ${data.cabinets.find(c => c.cabinet_uid === uid)?.cabinet_id}`} opacity={selected && ![selected.source_cabinet_uid, selected.destination_cabinet_uid].includes(uid) ? .15 : 1}
        onClick={e => {e.stopPropagation(); onAttachment(uid);}} onKeyDown={e => {if (e.key === "Enter") onAttachment(uid);}}>
        <RouteStroke {...connector} scale={scale} cableClasses={selected?.cable_class ? [selected.cable_class] : classes} />
        <rect x={Math.min(connector.a.x,connector.b.x)-8/scale} y={Math.min(connector.a.y,connector.b.y)-8/scale} width={Math.abs(connector.a.x-connector.b.x)+16/scale} height={Math.abs(connector.a.y-connector.b.y)+16/scale} fill="transparent" />
        <title>Schematic cabinet takeoff · actual cable members · no measured drop length</title>
      </g>;
    })}
  </g>;
}

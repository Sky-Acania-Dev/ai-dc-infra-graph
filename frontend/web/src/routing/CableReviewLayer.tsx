import { useMemo } from "react";
import { projectReviewPoint, reviewConnector, visibleLine, type Viewport } from "./cableReviewProjection";
import { RouteStroke, routeDetailScale } from "./RouteStroke";
import { focusedRouteGroups } from "./rackPairRoutes";
import type { ConceptualLayout } from "./conceptualLayout";
import type { CableClass, CableReview, ResolvedLayout, ReviewGroup, Tier } from "./types";

export function CableReviewLayer({data, view, review, scale, selectedGroupUid, selectedSegmentId = null, onAttachment, tiers, focusedPairKey = null, viewport, selectedCabinetUids}: {
  data: ResolvedLayout; view: ConceptualLayout; review: CableReview; scale: number; selectedGroupUid: string | null; selectedSegmentId?: string | null;
  onAttachment: (uid: string) => void;
  tiers?: Set<Tier>; focusedPairKey?: string | null; viewport?: Viewport;
  selectedCabinetUids?: ReadonlySet<string>;
}) {
  const focused = focusedRouteGroups(review.groups, selectedGroupUid, focusedPairKey, selectedCabinetUids);
  const hasFocus = Boolean(selectedGroupUid || focusedPairKey || selectedCabinetUids?.size);
  const focusedUids = new Set(focused.map(g=>g.uid));
  const groupsByUid = useMemo(()=>new Map(review.groups.map(g=>[g.uid,g])),[review.groups]);
  const attachmentGroups = useMemo(()=>{
    const byAttachment = new Map<string, {uid: string; tier: Tier; groups: ReviewGroup[]}>();
    for (const group of review.groups) if (group.route) for (const [uid, tier] of [[group.source_cabinet_uid,group.start_tier ?? 1],[group.destination_cabinet_uid,group.end_tier ?? 1]] as const) {
      const key = `${uid}:${tier}`;
      if (!byAttachment.has(key)) byAttachment.set(key,{uid,tier,groups:[]});
      byAttachment.get(key)!.groups.push(group);
    }
    return [...byAttachment.values()];
  }, [review]);
  const detail = routeDetailScale(scale);
  const cabinetTargets = new Set<string>();
  const offsetPoint = (p: {x: number; y: number}, tier: Tier | null) => {const offset = tier ? (tier - 2) * 4 * detail / scale : 0; return {x: p.x + offset, y: p.y + offset};};
  return <g className="actual-cable-review-layer" aria-label="Provisional routes for actual inventory cables">
    {review.loads.map(load => {
      if (tiers && (load.tier ? !tiers.has(load.tier) : load.lower_tier && load.upper_tier && !tiers.has(load.lower_tier) && !tiers.has(load.upper_tier))) return null;
      const rawA = projectReviewPoint(data, view, load.source), rawB = projectReviewPoint(data, view, load.target);
      if (!rawA || !rawB || !visibleLine(rawA,rawB,viewport)) return null;
      const a = offsetPoint(rawA,load.tier), b = offsetPoint(rawB,load.tier);
      const active = hasFocus ? load.group_uids.filter(uid=>focusedUids.has(uid)).map(uid=>groupsByUid.get(uid)!) : [];
      const muted = hasFocus && !active.length;
      const classes = hasFocus ? [...new Set(active.flatMap(g=>g.cable_class ? [g.cable_class] : []))] : load.cable_classes;
      return <g key={load.id} pointerEvents="none" data-route-muted={muted || undefined} opacity={muted ? .35 : 1}>
        {load.edge_type === "VERTICAL" ? <g><circle cx={a.x} cy={a.y} r={4*detail/scale} fill="#fff" stroke={muted ? "#94a3b8" : "#7855a1"} vectorEffect="non-scaling-stroke" />{(scale >= .8 || active.length > 0) && <text x={a.x+8/scale} y={a.y-6/scale} fontSize={10/scale}>T{load.lower_tier} ↕ T{load.upper_tier}</text>}</g> : <RouteStroke a={a} b={b} scale={scale} tier={load.tier ?? undefined} cableClasses={classes} selected={hasFocus ? !muted : selectedSegmentId === load.segment_id} />}
        <title>{`${load.cable_count.toLocaleString()} actual cables · ${load.group_uids.length} type/rack-pair groups · ${load.tier ? `Tier ${load.tier}` : `Tier ${load.lower_tier} ↕ ${load.upper_tier}`}`}</title>
      </g>;
    })}
    {attachmentGroups.map(({uid,tier,groups}) => {
      if (tiers && !tiers.has(tier)) return null;
      const first = groups[0]; if (!first?.route) return null;
      const point = first.source_cabinet_uid === uid ? first.route.points[0] : first.route.points.at(-1)!;
      const connector = reviewConnector(data, view, uid, point); if (!connector || !visibleLine(connector.a,connector.b,viewport)) return null;
      const interactive = !cabinetTargets.has(uid); cabinetTargets.add(uid);
      connector.b = offsetPoint(connector.b,tier);
      const active = groups.filter(g=>focusedUids.has(g.uid));
      const muted = hasFocus && !active.length;
      const classes = [...new Set((hasFocus ? active : groups).flatMap(g => g.cable_class ? [g.cable_class] : []))] as CableClass[];
      return <g key={`${uid}:${tier}`} data-route-muted={muted || undefined} opacity={muted ? .35 : 1}>
        <g pointerEvents="none"><RouteStroke {...connector} scale={scale} cableClasses={classes} tier={tier} /></g>
        {interactive && <g role="button" tabIndex={0} data-selectable="true" aria-label={`Inspect actual cable attachment ${data.cabinets.find(c => c.cabinet_uid === uid)?.cabinet_id}`}
          onClick={e=>{e.stopPropagation();onAttachment(uid);}} onKeyDown={e=>{if(e.key === "Enter" || e.key === " "){e.preventDefault();e.stopPropagation();onAttachment(uid);}}}>
          <rect x={Math.min(connector.a.x,connector.b.x)-8/scale} y={Math.min(connector.a.y,connector.b.y)-8/scale} width={Math.abs(connector.a.x-connector.b.x)+16/scale} height={Math.abs(connector.a.y-connector.b.y)+16/scale} fill="transparent" />
        </g>}
        <title>Schematic cabinet takeoff · actual cable members · no measured drop length</title>
      </g>;
    })}
  </g>;
}

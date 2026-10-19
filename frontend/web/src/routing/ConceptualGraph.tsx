import { useMemo } from "react";
import type { ConceptualLayout } from "./conceptualLayout";
import type { ResolvedLayout, RoutingGraph, Selection, Tier } from "./types";
import { formatInches } from "./dimensions";
import { RouteStroke, routeDetailScale } from "./RouteStroke";
import { visibleLine, type Viewport } from "./cableReviewProjection";
import { physicalJunctions } from "./physicalTargets";

type Props = { data: ResolvedLayout; graph: RoutingGraph; view: ConceptualLayout; scale: number; tiers: Set<Tier>; selection: Selection; onSelect: (s: Selection) => void; viewport?: Viewport; muteCableMarkings?: boolean };
export function ConceptualGraph({ data, graph, view, scale, tiers, selection, onSelect, viewport, muteCableMarkings }: Props) {
  const nodes = useMemo(() => new Map(graph.nodes.map(n => [n.id, n])), [graph]);
  const detail = routeDetailScale(scale);
  const junctions = useMemo(()=>physicalJunctions(graph.nodes,tiers),[graph,tiers]);
  const selected = (kind: string, uid: string) => selection?.kind === kind && selection.uid === uid;
  return <g className="conceptual-graph">
    {graph.edges.filter(e => e.edge_type !== "VERTICAL" && e.tier && tiers.has(e.tier)).map(edge => {
      const source = nodes.get(edge.source_node_id), target = nodes.get(edge.target_node_id);
      if (!source || !target) return null;
      const a = view.projectNode(source), b = view.projectNode(target), offset = (source.tier - 2) * 4 * detail / scale;
      if (!visibleLine(a,b,viewport)) return null;
      const active = selected("edge", edge.id);
      return <g key={edge.id} pointerEvents="none" className={`routing-tier-${source.tier}`}>
          <RouteStroke a={{ x: a.x + offset, y: a.y + offset }} b={{ x: b.x + offset, y: b.y + offset }} scale={scale} selected={active} tier={source.tier} usable={edge.usable} cableClasses={muteCableMarkings ? [] : edge.cable_classes} />
        <title>{`${edge.edge_type} · Tier ${source.tier} · Planar pathway length ${formatInches(edge.planar_length_in)} · Width ${edge.width_in == null ? "not separately measured" : formatInches(edge.width_in)}`}</title>
      </g>;
    })}
    {junctions.map(junction => {
      const node = junction.members[0], point = view.projectNode(node);
      if (!visibleLine(point,point,viewport)) return null;
      return <g key={junction.id} data-selectable="true" data-physical-junction={junction.id} role="button" tabIndex={0} aria-label={`Inspect ${node.passage_code} junction at ${formatInches(node.station_in)}`}
        onClick={event => { event.stopPropagation(); onSelect({ kind: "node", uid: node.id }); }} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") {event.preventDefault();event.stopPropagation();onSelect({ kind: "node", uid: node.id });} }}>
        <circle cx={point.x} cy={point.y} r={6 / scale} fill="transparent" />
        <circle cx={point.x} cy={point.y} r={3 * detail / scale} pointerEvents="none"
          className={`conceptual-station ${junction.members.some(n=>selected("node",n.id)) ? "selected" : ""}`} style={{strokeWidth: 1.5 * detail}} vectorEffect="non-scaling-stroke" />
        <title>{`${node.passage_code} · ${junction.members.map(n=>`Tier ${n.tier}`).join(" / ")} · ${node.label ?? "Passage station"}`}</title>
      </g>;
    })}
    {data.vertical_transitions.map((opening, index) => {
      if (!tiers.has(opening.lower_tier) && !tiers.has(opening.upper_tier)) return null;
      const x = view.passageX.get(opening.passage_band_uid);
      if (x === undefined) return null;
      const y = view.stationY(opening.station_in);
      if (!visibleLine({x,y},{x,y},viewport)) return null;
      const same = data.vertical_transitions.slice(0, index).filter(o => o.passage_band_uid === opening.passage_band_uid && o.station_in === opening.station_in).length;
      const markerX = x + 40 / scale, markerY = y + same * 23 / scale;
      const showLabel = scale >= .8 || selected("transition", opening.uid);
      return <g key={opening.uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select opening ${opening.label ?? opening.uid}`} opacity={opening.enabled ? 1 : 0.3}
        onClick={event => { event.stopPropagation(); onSelect({ kind: "transition", uid: opening.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "transition", uid: opening.uid }); }}>
        {showLabel && <line x1={x} y1={y} x2={markerX} y2={markerY} stroke="var(--routing-opening)" strokeWidth={1} vectorEffect="non-scaling-stroke" />}
        {!showLabel ? <circle cx={x} cy={y} r={3 / scale} className="routing-opening" vectorEffect="non-scaling-stroke" /> : <><rect x={markerX - 28 / scale} y={markerY - 9 / scale} width={56 / scale} height={18 / scale} rx={3 / scale} className={`routing-opening ${selected("transition", opening.uid) ? "selected" : ""}`} vectorEffect="non-scaling-stroke" />
        <text x={markerX} y={markerY} dy="0.35em" textAnchor="middle" fontSize={10 / scale}>T{opening.lower_tier} ↕ T{opening.upper_tier}</text></>}
        <title>{opening.label ?? "Physical opening"}</title>
      </g>;
    })}
  </g>;
}

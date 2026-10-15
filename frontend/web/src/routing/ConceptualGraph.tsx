import { useMemo } from "react";
import type { ConceptualLayout } from "./conceptualLayout";
import type { ResolvedLayout, RoutingGraph, Selection, Tier } from "./types";
import { formatInches } from "./dimensions";
import { RouteStroke } from "./RouteStroke";

type Props = { data: ResolvedLayout; graph: RoutingGraph; view: ConceptualLayout; scale: number; tiers: Set<Tier>; selection: Selection; onSelect: (s: Selection) => void };
export function ConceptualGraph({ data, graph, view, scale, tiers, selection, onSelect }: Props) {
  const nodes = useMemo(() => new Map(graph.nodes.map(n => [n.id, n])), [graph]);
  const selected = (kind: string, uid: string) => selection?.kind === kind && selection.uid === uid;
  return <g className="conceptual-graph">
    {graph.edges.filter(e => e.edge_type !== "VERTICAL" && e.tier && tiers.has(e.tier)).map(edge => {
      const source = nodes.get(edge.source_node_id), target = nodes.get(edge.target_node_id);
      if (!source || !target) return null;
      const a = view.projectNode(source), b = view.projectNode(target), offset = (source.tier - 2) * 4 / scale;
      const active = selected("edge", edge.id);
      return <g key={edge.id} data-selectable="true" role="button" tabIndex={0} aria-label={`Select segment ${edge.id}`} className={`routing-tier-${source.tier}`}
        onClick={event => { event.stopPropagation(); onSelect({ kind: "edge", uid: edge.id }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "edge", uid: edge.id }); }}>
        {edge.edge_type === "JUNCTION" ? <circle cx={a.x + offset} cy={a.y + offset} r={3 / scale} className={`conceptual-station ${active ? "selected" : ""}`} vectorEffect="non-scaling-stroke" /> : <>
          <line x1={a.x + offset} y1={a.y + offset} x2={b.x + offset} y2={b.y + offset} stroke="transparent" strokeWidth={12} vectorEffect="non-scaling-stroke" />
          <RouteStroke a={{ x: a.x + offset, y: a.y + offset }} b={{ x: b.x + offset, y: b.y + offset }} scale={scale} selected={active} tier={source.tier} usable={edge.usable} cableClasses={edge.cable_classes} />
        </>}
        <title>{`${edge.edge_type} · Tier ${source.tier} · Planar pathway length ${formatInches(edge.planar_length_in)} · Width ${edge.width_in == null ? "not separately measured" : formatInches(edge.width_in)}`}</title>
      </g>;
    })}
    {graph.nodes.filter(node => tiers.has(node.tier)).map(node => {
      const point = view.projectNode(node), offset = (node.tier - 2) * 4 / scale;
      return <circle key={node.id} data-selectable="true" role="button" tabIndex={0} aria-label={`Select node ${node.id}`} cx={point.x + offset} cy={point.y + offset} r={3 / scale}
        className={`conceptual-station routing-tier-${node.tier} ${selected("node", node.id) ? "selected" : ""}`} vectorEffect="non-scaling-stroke"
        onClick={event => { event.stopPropagation(); onSelect({ kind: "node", uid: node.id }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "node", uid: node.id }); }}>
        <title>{`${node.passage_code} · Tier ${node.tier} · ${node.label ?? "Passage station"}`}</title>
      </circle>;
    })}
    {data.vertical_transitions.map((opening, index) => {
      if (!tiers.has(opening.lower_tier) && !tiers.has(opening.upper_tier)) return null;
      const x = view.passageX.get(opening.passage_band_uid);
      if (x === undefined) return null;
      const y = view.stationY(opening.station_in);
      const same = data.vertical_transitions.slice(0, index).filter(o => o.passage_band_uid === opening.passage_band_uid && o.station_in === opening.station_in).length;
      const markerX = x + 40 / scale, markerY = y + same * 23 / scale;
      return <g key={opening.uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select opening ${opening.label ?? opening.uid}`} opacity={opening.enabled ? 1 : 0.3}
        onClick={event => { event.stopPropagation(); onSelect({ kind: "transition", uid: opening.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "transition", uid: opening.uid }); }}>
        <line x1={x} y1={y} x2={markerX} y2={markerY} stroke="var(--routing-opening)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        <rect x={markerX - 28 / scale} y={markerY - 9 / scale} width={56 / scale} height={18 / scale} rx={3 / scale} className={`routing-opening ${selected("transition", opening.uid) ? "selected" : ""}`} vectorEffect="non-scaling-stroke" />
        <text x={markerX} y={markerY} dy="0.35em" textAnchor="middle" fontSize={10 / scale}>T{opening.lower_tier} ↕ T{opening.upper_tier}</text>
        <title>{opening.label ?? "Physical opening"}</title>
      </g>;
    })}
  </g>;
}

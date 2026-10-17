import { useEffect, useMemo, useState } from "react";
import type { GraphNode, ResolvedLayout, RoutePreview, RoutingGraph, Selection, Tier, SchematicOrientation } from "./types";
import { SchematicContext } from "./SchematicContext";
import { useSchematicView } from "./useSchematicView";
import { formatInches } from "./dimensions";
import { CabinetLayer, type CabinetInteraction } from "./CabinetLayer";
import { placeRoutingCabinets } from "./cabinetPlacement";

const DASH: Record<Tier, string | undefined> = { 1: undefined, 2: "8 5", 3: "9 4 2 4" };
type Props = {
  data: ResolvedLayout; graph: RoutingGraph; tiers: Set<Tier>; selection: Selection; preview: RoutePreview | null;
  start: string | null; routeMode: boolean; onSelect: (s: Selection) => void; onNode: (node: GraphNode) => void;
  cabinetInteraction?: CabinetInteraction; initialSectionUid?: string; initialOrientation?: SchematicOrientation;
};
export function RoutingSchematic({ data, graph, tiers, selection, preview, start, routeMode, onSelect, onNode, cabinetInteraction, initialSectionUid = "", initialOrientation = "longitudinal" }: Props) {
  const [orientation, setOrientation] = useState<SchematicOrientation>(initialOrientation);
  const [focusUid, setFocusUid] = useState(initialSectionUid);
  const [showCabinets, setShowCabinets] = useState(true);
  const v = useSchematicView(data.geometry.hall_length_in, data.geometry.total_width_in, orientation);
  useEffect(() => { setFocusUid(initialSectionUid); }, [initialSectionUid]);
  useEffect(() => {
    const section = data.geometry.sections.find(s => s.uid === focusUid);
    if (section) v.focusSection(section.start_in, section.end_in); else v.fit();
  }, [focusUid, orientation, data.layout.uid, data.geometry.hall_length_in, data.geometry.total_width_in]);
  const tiles = useMemo(() => placeRoutingCabinets(data), [data]);
  const tiledRows = useMemo(() => new Set(showCabinets ? tiles.map(t => t.rowUid) : []), [tiles, showCabinets]);
  const inventoryInteraction: CabinetInteraction = cabinetInteraction ?? {
    selected: new Set(selection?.kind === "cabinet" ? [selection.uid] : []),
    onSelect: cabinet => onSelect({ kind: "cabinet", uid: cabinet.cabinet_uid }),
  };
  const selectedCabinet = tiles.find(tile => inventoryInteraction.selected.has(tile.cabinet.cabinet_uid));
  const nodes = useMemo(() => new Map(graph.nodes.map(n => [n.id, n])), [graph]);
  const pathEdges = useMemo(() => new Set(preview?.edges.map(e => e.id)), [preview]);
  const pathNodes = useMemo(() => new Set(preview?.nodes.map(n => n.id)), [preview]);
  const g = data.geometry;
  const passages = g.bands.filter(b => b.kind === "PASSAGE").sort((a, b) => a.ordinal - b.ordinal);
  const crossStart = passages[0].center_in, crossEnd = passages[passages.length - 1].center_in;
  const visualOffset = (tier: Tier) => (tier - 2) * 3 / v.scale;
  const selected = (kind: string, uid: string) => selection?.kind === kind && selection.uid === uid;
  return <section className="routing-viewer" aria-label="Routing schematic">
    <div className="routing-view-tools">
      <button onClick={() => v.zoom(0.7)} aria-label="Zoom in">+</button>
      <button onClick={() => v.zoom(1.4)} aria-label="Zoom out">−</button>
      <button onClick={() => { setFocusUid(""); v.fit(); }}>Fit / reset view</button>
      <select aria-label="Focus section" value={focusUid} onChange={event => setFocusUid(event.target.value)}><option value="">All sections</option>{g.sections.map(section => <option key={section.uid} value={section.uid}>{section.name}</option>)}</select>
      <select aria-label="Map orientation" value={orientation} onChange={event => setOrientation(event.target.value as SchematicOrientation)}><option value="longitudinal">Longitudinal</option><option value="cabinet-map">Cabinet map</option></select>
      <label><input type="checkbox" checked={showCabinets} onChange={event => setShowCabinets(event.target.checked)} />Cabinets</label>
      <button disabled={!selectedCabinet} onClick={() => {
        if (!selectedCabinet) return;
        const first = Math.max(0, selectedCabinet.x - data.layout.row_pair_module_in);
        v.focusSection(first, Math.min(g.hall_length_in, first + 3 * data.layout.row_pair_module_in));
      }}>Focus selected cabinet</button>
      <span>Drag blank space to pan · Scroll to zoom · {routeMode ? "Select graph nodes for route preview" : "Select infrastructure for details"}</span>
    </div>
    <svg ref={v.svgRef} className="routing-svg" viewBox={`${v.view.x} ${v.view.y} ${v.view.w} ${v.view.h}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={orientation === "cabinet-map" ? "Combined cabinet and pathway map: south left, north right, sections top to bottom" : "Proportional hall schematic: X longitudinal, Y north to south"}
      onPointerDown={v.pointerDown} onPointerMove={v.pointerMove} onPointerUp={v.pointerUp} onPointerCancel={v.pointerUp}
      onWheel={event => { event.preventDefault(); v.zoom(event.deltaY < 0 ? 0.85 : 1.18, v.point(event.clientX, event.clientY)); }}
      onClick={() => { if (!v.suppressClick.current) onSelect(null); v.suppressClick.current = false; }}>
      <defs>
        <pattern id="routing-hot-hatch" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M0 0L20 20M-5 15L5 25M15-5L25 5" stroke="var(--routing-hot)" opacity="0.25" strokeWidth="3" /></pattern>
        <pattern id="routing-gap-hatch" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M0 28L28 0" stroke="var(--routing-gap)" opacity="0.25" strokeWidth="3" /></pattern>
      </defs>
      <g transform={orientation === "cabinet-map" ? `matrix(0 1 -1 0 ${g.total_width_in} 0)` : undefined}>
      <g opacity={preview ? 0.35 : 1}>
        <SchematicContext data={data} scale={v.scale} selection={selection} onSelect={onSelect} tiledRows={tiledRows} />
        {showCabinets && <CabinetLayer tiles={tiles} scale={v.scale} interaction={inventoryInteraction} />}
        {g.bands.filter(b => b.kind === "PASSAGE").map(band => <g key={band.uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select ${band.code} passage`} onClick={event => { event.stopPropagation(); onSelect({ kind: "passage", uid: band.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "passage", uid: band.uid }); }}>
          <rect x={0} y={band.start_in} width={g.hall_length_in} height={band.width_in} className={`routing-passage-envelope ${selected("passage", band.uid) ? "selected" : ""}`} vectorEffect="non-scaling-stroke" />
          <text x={-8 / v.scale} y={band.center_in} transform={orientation === "cabinet-map" ? `rotate(-90 ${-8 / v.scale} ${band.center_in})` : undefined} dy="0.35em" textAnchor={orientation === "cabinet-map" ? "middle" : "end"} fontSize={11 / v.scale} fontWeight="800">{band.code}</text>
          <title>{`${band.code} passage · ${formatInches(band.width_in)} wide`}</title>
        </g>)}
        {g.cross_routes.map(route => <rect key={route.uid} data-selectable="true" x={route.start_in} y={route.start_y_in ?? crossStart} width={route.width_in} height={(route.end_y_in ?? crossEnd) - (route.start_y_in ?? crossStart)} className={`routing-cross-envelope ${route.kind === "SECTION_GAP" ? "gap" : ""} ${selected("cross", route.uid) ? "selected" : ""}`}
          opacity={route.effective_enabled ? 1 : 0.2} vectorEffect="non-scaling-stroke" role="button" tabIndex={0} aria-label={`Select ${route.display_label ?? route.label ?? data.cabinet_rows.find(r => r.uid === route.cabinet_row_uid)?.name ?? "cross route"}`}
          onClick={event => { event.stopPropagation(); onSelect({ kind: "cross", uid: route.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "cross", uid: route.uid }); }}>
          <title>{`${route.kind} · ${route.display_label ?? route.label ?? data.cabinet_rows.find(r => r.uid === route.cabinet_row_uid)?.name} · station ${formatInches(route.station_in)} · ${route.station_source}`}</title>
        </rect>)}
      </g>
      <g className="routing-graph">
        {graph.edges.filter(e => e.edge_type !== "VERTICAL" && e.tier && tiers.has(e.tier)).map(edge => {
          const a = nodes.get(edge.source_node_id)!, b = nodes.get(edge.target_node_id)!;
          const shift = visualOffset(a.tier);
          const highlight = pathEdges.has(edge.id), isSelected = selected("edge", edge.id);
          const opacity = preview && !highlight ? 0.16 : 1;
          return <g key={edge.id} data-selectable="true" className={`routing-tier-${a.tier}`} opacity={opacity} onClick={event => { event.stopPropagation(); onSelect({ kind: "edge", uid: edge.id }); }}>
              <line x1={a.x_in + shift} y1={a.y_in + shift} x2={b.x_in + shift} y2={b.y_in + shift} stroke="transparent" strokeWidth={14} vectorEffect="non-scaling-stroke" />
              <line x1={a.x_in + shift} y1={a.y_in + shift} x2={b.x_in + shift} y2={b.y_in + shift} className={`routing-edge ${highlight || isSelected ? "selected" : ""}`} strokeWidth={highlight || isSelected ? 4 : 1.8} strokeDasharray={DASH[a.tier]} vectorEffect="non-scaling-stroke" pointerEvents="none" />
            <title>{`${edge.edge_type} · Tier ${a.tier} · ${formatInches(edge.planar_length_in)}`}</title>
          </g>;
        })}
        {graph.nodes.filter(node => tiers.has(node.tier)).map(node => {
          const shift = visualOffset(node.tier), isStart = node.id === start;
          return <circle key={node.id} data-selectable="true" role="button" tabIndex={0} aria-label={`Select node ${node.id}`} cx={node.x_in + shift} cy={node.y_in + shift} r={(isStart || selected("node", node.id) ? 5 : routeMode ? 3.5 : 2) / v.scale}
            className={`routing-node routing-tier-${node.tier} ${isStart || pathNodes.has(node.id) || selected("node", node.id) ? "selected" : ""}`} opacity={preview && !pathNodes.has(node.id) ? 0.16 : 1} vectorEffect="non-scaling-stroke"
            onClick={event => { event.stopPropagation(); onNode(node); }} onKeyDown={event => { if (event.key === "Enter") onNode(node); }}>
            <title>{`${node.passage_code} · Tier ${node.tier} · station ${formatInches(node.station_in)}${node.cross_route_uid ? ` · ${node.label ?? node.cross_route_kind}` : ""}`}</title>
          </circle>;
        })}
      </g>
      {data.vertical_transitions.map((vt, index) => {
        if (!tiers.has(vt.lower_tier) && !tiers.has(vt.upper_tier)) return null;
        const band = g.bands.find(b => b.uid === vt.passage_band_uid)!;
        const same = data.vertical_transitions.slice(0, index).filter(other => other.station_in === vt.station_in && other.passage_band_uid === vt.passage_band_uid).length;
        const y = band.center_in + (18 + same * 23) / v.scale;
        const used = preview?.edges.some(e => e.vertical_transition_uid === vt.uid);
        return <g key={vt.uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select opening ${vt.label ?? vt.uid}`} opacity={vt.enabled ? preview && !used ? 0.3 : 1 : 0.35} onClick={event => { event.stopPropagation(); onSelect({ kind: "transition", uid: vt.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "transition", uid: vt.uid }); }}>
          <line x1={vt.station_in} x2={vt.station_in} y1={band.center_in} y2={y} stroke="var(--routing-opening)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
          <g transform={orientation === "cabinet-map" ? `rotate(-90 ${vt.station_in} ${y})` : undefined}>
            <rect x={vt.station_in - 29 / v.scale} y={y - 9 / v.scale} width={58 / v.scale} height={18 / v.scale} rx={3 / v.scale} className={`routing-opening ${selected("transition", vt.uid) || used ? "selected" : ""}`} vectorEffect="non-scaling-stroke" />
            <text x={vt.station_in} y={y} dy="0.35em" textAnchor="middle" fontSize={10 / v.scale}>T{vt.lower_tier} ↕ T{vt.upper_tier}</text>
          </g>
          <title>{`${vt.label ?? "Opening"} · ${band.code} · ${formatInches(vt.station_in)} · ${vt.enabled ? "Enabled" : "Disabled"}`}</title>
        </g>;
      })}
      </g>
    </svg>
    <footer className="routing-view-footer"><span>{orientation === "cabinet-map" ? "SOUTH ← CENTRAL → NORTH · Sections top to bottom" : "X → longitudinal · Y ↓ NORTH to SOUTH"}</span><span>Cabinet slots schematic · {formatInches(g.total_width_in)} across hall</span></footer>
  </section>;
}

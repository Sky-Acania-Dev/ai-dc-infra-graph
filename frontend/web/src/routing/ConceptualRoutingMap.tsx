import { useEffect, useMemo, useState } from "react";
import { CabinetLayer, type CabinetInteraction } from "./CabinetLayer";
import { placeRoutingCabinets } from "./cabinetPlacement";
import { ConceptualGraph } from "./ConceptualGraph";
import { conceptualLayout } from "./conceptualLayout";
import { useSchematicView } from "./useSchematicView";
import type { ResolvedLayout, RoutingGraph, Selection, Tier } from "./types";

type Props = { data: ResolvedLayout; graph: RoutingGraph; tiers: Set<Tier>; selection: Selection; onSelect: (s: Selection) => void; initialSectionUid: string; cabinetInteraction: CabinetInteraction };
export function ConceptualRoutingMap({ data, graph, tiers, selection, onSelect, initialSectionUid, cabinetInteraction }: Props) {
  const display = useMemo(() => conceptualLayout(data, placeRoutingCabinets(data)), [data]);
  // The view controller operates in SVG display units, not model inches.
  const v = useSchematicView(display.height, display.width, "cabinet-map");
  const [focusUid, setFocusUid] = useState(initialSectionUid);
  useEffect(() => setFocusUid(initialSectionUid), [initialSectionUid]);
  useEffect(() => {
    const section = display.sections.find(s => s.uid === focusUid);
    if (section) v.focusSection(section.start, section.end); else v.fit();
  }, [focusUid, display]);
  const selectedCabinet = display.cabinets.find(c => cabinetInteraction.selected.has(c.cabinet.cabinet_uid));
  const selected = (kind: string, uid: string) => selection?.kind === kind && selection.uid === uid;
  const crossStart = display.passages[0]?.x ?? 0, crossEnd = display.passages.at(-1)?.x ?? 0;
  return <section className="routing-viewer conceptual-viewer" aria-label="Conceptual cabinet and route map">
    <div className="routing-view-tools">
      <button onClick={() => v.zoom(0.7)} aria-label="Zoom in">+</button><button onClick={() => v.zoom(1.4)} aria-label="Zoom out">−</button>
      <button onClick={() => { setFocusUid(""); v.fit(); }}>Fit / reset view</button>
      <select aria-label="Focus section" value={focusUid} onChange={event => setFocusUid(event.target.value)}><option value="">All sections</option>{display.sections.map(s => <option key={s.uid} value={s.uid}>{s.name}</option>)}</select>
      <button disabled={!selectedCabinet} onClick={() => { if (selectedCabinet) v.focusSection(Math.max(0, selectedCabinet.y - 100), selectedCabinet.y + 300); }}>Focus selected cabinet</button>
      <span>Conceptual · Not to scale · Drag blank space to pan</span>
    </div>
    <svg ref={v.svgRef} className="routing-svg conceptual-svg" viewBox={`${v.view.x} ${v.view.y} ${v.view.w} ${v.view.h}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Conceptual cabinet and pathway map, not to scale: SOUTH left, CENTRAL middle, NORTH right"
      onPointerDown={v.pointerDown} onPointerMove={v.pointerMove} onPointerUp={v.pointerUp} onPointerCancel={v.pointerUp}
      onWheel={event => { event.preventDefault(); v.zoom(event.deltaY < 0 ? 0.85 : 1.18, v.point(event.clientX, event.clientY)); }}
      onClick={() => { if (!v.suppressClick.current) onSelect(null); v.suppressClick.current = false; }}>
      {display.sections.map((section, i) => <g key={section.uid} className="conceptual-section">
        <rect x={crossStart} y={section.start} width={crossEnd - crossStart} height={section.end - section.start} fill={i % 2 ? "#f4f7fa" : "#fff"} />
        <text x={(crossStart + crossEnd) / 2} y={section.start + 16} textAnchor="middle" fontSize={Math.min(18, 11 / v.scale)} fontWeight="700">{section.name}</text>
      </g>)}
      {display.gaps.map((gap, index) => <g key={gap.uid} className="conceptual-gap">
        <rect x={crossStart} y={gap.start} width={crossEnd - crossStart} height={gap.end - gap.start} fill="#edf1f5" />
        <text x={crossStart - 10 / v.scale} y={(gap.start + gap.end) / 2} dy="0.35em" textAnchor="end" fontSize={10 / v.scale}>S{index + 1}–S{index + 2} gap</text>
      </g>)}
      {v.scale > 0.5 && display.hotAisles.map(aisle => <text key={aisle.uid} x={aisle.x + aisle.width / 2} y={aisle.y + aisle.height / 2} dominantBaseline="central" textAnchor="middle" fontSize={9 / v.scale} fill="#7b8795">Hot aisle · no routing</text>)}
      {[...display.rows].map(([uid, row]) => <rect key={uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select ${row.name}`} x={row.x} y={row.y} width={row.width} height={row.height} className={`conceptual-row ${selected("row", uid) ? "selected" : ""}`} vectorEffect="non-scaling-stroke"
        onClick={event => { event.stopPropagation(); onSelect({ kind: "row", uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "row", uid }); }}><title>{row.name}</title></rect>)}
      <CabinetLayer tiles={display.cabinets} scale={v.scale} interaction={cabinetInteraction} horizontal />
      {display.passages.map(p => <g key={p.uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select ${p.code} passage`}
        onClick={event => { event.stopPropagation(); onSelect({ kind: "passage", uid: p.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "passage", uid: p.uid }); }}>
        <line x1={p.x} x2={p.x} y1={0} y2={display.height} stroke="transparent" strokeWidth={12} vectorEffect="non-scaling-stroke" />
        <line x1={p.x} x2={p.x} y1={0} y2={display.height} className={`conceptual-passage ${selected("passage", p.uid) ? "selected" : ""}`} vectorEffect="non-scaling-stroke" />
        <text x={p.x} y={-14 / v.scale} textAnchor="middle" fontSize={11 / v.scale} fontWeight="800">{p.code}</text>
      </g>)}
      {data.geometry.cross_routes.map(route => {
        const y = display.stationY(route.station_in);
        return <g key={route.uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select pathway ${route.label ?? data.cabinet_rows.find(r => r.uid === route.cabinet_row_uid)?.name ?? "cross route"}`} opacity={route.effective_enabled ? 1 : 0.2}
          onClick={event => { event.stopPropagation(); onSelect({ kind: "cross", uid: route.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "cross", uid: route.uid }); }}>
          <line x1={crossStart} x2={crossEnd} y1={y} y2={y} stroke="transparent" strokeWidth={10} vectorEffect="non-scaling-stroke" />
          <line x1={crossStart} x2={crossEnd} y1={y} y2={y} className={`conceptual-cross ${route.kind === "SECTION_GAP" ? "gap-route" : ""} ${selected("cross", route.uid) ? "selected" : ""}`} vectorEffect="non-scaling-stroke" />
          {display.passages.map(p => <circle key={p.uid} cx={p.x} cy={y} r={2.5 / v.scale} className="conceptual-guide-station" vectorEffect="non-scaling-stroke" />)}
          <title>{`${route.kind === "SECTION_GAP" ? "Section-gap route" : "Cabinet cold-side route"} · ${route.label ?? data.cabinet_rows.find(r => r.uid === route.cabinet_row_uid)?.name}`}</title>
        </g>;
      })}
      <ConceptualGraph data={data} graph={graph} view={display} scale={v.scale} tiers={tiers} selection={selection} onSelect={onSelect} />
    </svg>
    <footer className="routing-view-footer">Conceptual positions and stroke widths are visual only. Segment details retain model lengths and widths.</footer>
  </section>;
}

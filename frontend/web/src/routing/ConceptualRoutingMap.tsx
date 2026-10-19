import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { CabinetInteraction } from "./CabinetLayer";
import type { CabinetGraphicSettings } from "../components/CabinetGraphics";
import { placeRoutingCabinets, type CabinetTile } from "./cabinetPlacement";
import { annotationFor, type ConceptualSegment } from "./conceptualSegments";
import { RouteStroke, routeDetailScale } from "./RouteStroke";
import { formatInches } from "./dimensions";
import { ConceptualGraph } from "./ConceptualGraph";
import { conceptualLayout } from "./conceptualLayout";
import { useSchematicView } from "./useSchematicView";
import { CableReviewLayer } from "./CableReviewLayer";
import { ManualRouteLayer } from "./ManualRouteLayer";
import { projectReviewPoint, reviewConnector, visibleLine } from "./cableReviewProjection";
import { focusedRouteGroups } from "./rackPairRoutes";
import type { RoutingSummaryFilter } from "./routingSummaryFilter";
import type { CableReview, ResolvedLayout, RoutingGraph, Selection, Tier, ManualPreview, PlanningSegment } from "./types";

type Props = { data: ResolvedLayout; graph: RoutingGraph; tiers: Set<Tier>; selection: Selection; onSelect: (s: Selection) => void; initialSectionUid: string; cabinetInteraction: CabinetInteraction;
  settings: CabinetGraphicSettings & { hotAisleGap: number }; renderCabinets: (tiles: CabinetTile[]) => ReactNode;
  segments: ConceptualSegment[]; selectedSegmentId: string | null; onSelectSegment: (id: string) => void;
  review?: CableReview | null; selectedReviewGroupUid?: string | null; focusedReviewPairKey?: string | null; selectionGroupUids?: ReadonlySet<string> | null;
  onReviewAttachment?: (uid: string) => void;
  summaryFilter?: RoutingSummaryFilter | null;
  onOverview?: () => void;
  manual?: {preview: ManualPreview | null; segments: PlanningSegment[]; append: (ids: string[]) => void; chooseSegments: (ids: string[]) => void; disabled: boolean} | null;
};
export function ConceptualRoutingMap({ data, graph, tiers, selection, onSelect, initialSectionUid, cabinetInteraction, settings, renderCabinets, segments, selectedSegmentId, onSelectSegment, review, selectedReviewGroupUid = null, focusedReviewPairKey = null, selectionGroupUids = null, summaryFilter = null, onReviewAttachment, onOverview, manual }: Props) {
  const display = useMemo(() => conceptualLayout(data, placeRoutingCabinets(data), settings), [data, settings]);
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
  const cabinetFocus = cabinetInteraction.selected.size > 0;
  const muteCableMarkings = cabinetFocus || Boolean(selectedReviewGroupUid || focusedReviewPairKey || selectionGroupUids != null || summaryFilter);
  const reviewGroups = useMemo(()=>focusedRouteGroups(review?.groups ?? [], selectedReviewGroupUid, focusedReviewPairKey, cabinetInteraction.selected, selectionGroupUids, summaryFilter),[review?.groups, selectedReviewGroupUid, focusedReviewPairKey, cabinetInteraction.selected, selectionGroupUids, summaryFilter]);
  const reviewPoints = useMemo(()=>{
    const points = new Map<string,{x:number;y:number}>();
    const add = (p: {x:number;y:number})=>points.set(`${p.x}:${p.y}`,p);
    for (const group of reviewGroups) if (group.route) {
      for (const p of group.route.points) {const point = projectReviewPoint(data,display,p); if (point) add(point);}
      for (const [uid,p] of [[group.source_cabinet_uid,group.route.points[0]],[group.destination_cabinet_uid,group.route.points.at(-1)!]] as const) {const connector = reviewConnector(data,display,uid,p); if (connector) add(connector.a);}
    }
    return [...points.values()];
  }, [reviewGroups,data,display]);
  return <section className="routing-viewer conceptual-viewer" aria-label="Conceptual cabinet and route map">
    <div className="conceptual-map-controls">
      <button onClick={() => v.zoom(0.7)} aria-label="Zoom in">+</button><button onClick={() => v.zoom(1.4)} aria-label="Zoom out">−</button>
      <button onClick={() => { setFocusUid(""); v.fit(); onOverview?.(); }}>Fit / reset view</button>
      <details className="conceptual-view-options"><summary>Sections / focus</summary><div className="routing-view-tools">
      <select aria-label="Focus section" value={focusUid} onChange={event => setFocusUid(event.target.value)}><option value="">All sections</option>{display.sections.map(s => <option key={s.uid} value={s.uid}>{s.name}</option>)}</select>
      <button disabled={!selectedCabinet} onClick={() => { if (selectedCabinet) v.focusSection(Math.max(0, selectedCabinet.y - 100), selectedCabinet.y + 300); }}>Focus selected cabinet</button>
      {review && <button onClick={() => v.focusBounds(display.cabinets.filter(c => review.cabinet_uids.includes(c.cabinet.cabinet_uid)).flatMap(c => [{x:c.x,y:c.y-25}, {x:c.x+c.width,y:c.y+c.height+25}]), 55)}>Focus actual cable rows</button>}
      {reviewPoints.length > 0 && <button onClick={() => v.focusBounds(reviewPoints, 65)}>{cabinetFocus ? "Focus selected cabinet connections" : focusedReviewPairKey ? "Focus rack pair" : selectedReviewGroupUid ? "Focus cable group" : "Focus selected routes"}</button>}
      {manual?.preview && <button onClick={() => v.focusBounds([...manual.preview!.prefix.points, ...(manual.preview!.suggestion?.points ?? []), manual.preview!.destination].flatMap(p => {const point = projectReviewPoint(data, display, p); return point ? [point] : [];}), 80)}>Focus manual draft</button>}
      <span>Conceptual · Not to scale · Drag blank space to pan</span>
      {!cabinetFocus && !selectedReviewGroupUid && !focusedReviewPairKey && selectionGroupUids != null && <span className="cabinet-route-focus" role="status">{reviewGroups.length ? `${reviewGroups.length.toLocaleString()} cable groups passing through selection · complete routes in color` : "No routed cables pass through this selection"}</span>}
      {cabinetFocus && <span className="cabinet-route-focus" role="status">{cabinetInteraction.selected.size} selected cabinet{cabinetInteraction.selected.size === 1 ? "" : "s"} · connected cables in color</span>}
      </div></details>
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
      {[...display.rows].map(([uid, row]) => <rect key={uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select ${row.name}`} x={row.x} y={row.y} width={row.width} height={row.height} className={`conceptual-row ${selected("row", uid) ? "selected" : ""}`} vectorEffect="non-scaling-stroke"
        onClick={event => { event.stopPropagation(); onSelect({ kind: "row", uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "row", uid }); }}><title>{row.name}</title></rect>)}
      {display.passages.map(p => <g key={p.uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select ${p.code} passage`}
        onClick={event => { event.stopPropagation(); onSelect({ kind: "passage", uid: p.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "passage", uid: p.uid }); }}>
        <line x1={p.x} x2={p.x} y1={0} y2={display.height} stroke="transparent" strokeWidth={12} vectorEffect="non-scaling-stroke" />
        <text x={p.x} y={-14 / v.scale} textAnchor="middle" fontSize={11 / v.scale} fontWeight="800">{p.code}</text>
      </g>)}
      {segments.map(segment => {
        const passage = segment.passage_band_uid;
        const station = data.geometry.cross_routes.find(r => r.uid === segment.cross_route_uid)?.station_in ?? 0;
        const a = { x: display.passageX.get(passage ?? segment.from_passage_band_uid!) ?? 0, y: display.stationY(passage ? segment.start_station_in! : station) };
        const b = { x: display.passageX.get(passage ?? segment.to_passage_band_uid!) ?? 0, y: display.stationY(passage ? segment.end_station_in! : station) };
        if (!visibleLine(a,b,v.view)) return null;
        const marking = annotationFor(data, segment, null);
        const hit = Math.max(4,12*routeDetailScale(v.scale))/v.scale;
        return <g key={segment.id} data-selectable="true" role="button" tabIndex={0} aria-label={`Select segment ${segment.label}`}
          onClick={event => { event.stopPropagation(); onSelectSegment(segment.id); }} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectSegment(segment.id); } }}>
          <rect x={Math.min(a.x,b.x)-hit} y={Math.min(a.y,b.y)-hit} width={Math.abs(a.x-b.x)+2*hit} height={Math.abs(a.y-b.y)+2*hit} fill="transparent" />
          <RouteStroke a={a} b={b} scale={v.scale} usable={marking?.usable} cableClasses={muteCableMarkings ? [] : marking?.cable_classes} selected={selectedSegmentId === segment.id} />
          <title>{`${segment.label}\nPlanar pathway length ${formatInches(segment.planar_length_in)} · Width ${formatInches(segment.width_in)}`}</title>
        </g>;
      })}
      <ConceptualGraph data={data} graph={graph} view={display} scale={v.scale} tiers={tiers} selection={selection} onSelect={onSelect} viewport={v.view} muteCableMarkings={muteCableMarkings} />
      {!manual && review && onReviewAttachment && <CableReviewLayer data={data} view={display} review={review} scale={v.scale} tiers={tiers} selectedGroupUid={selectedReviewGroupUid} selectedSegmentId={selectedSegmentId} focusedPairKey={focusedReviewPairKey} selectedCabinetUids={cabinetInteraction.selected} selectionGroupUids={selectionGroupUids} summaryFilter={summaryFilter} onAttachment={onReviewAttachment} viewport={v.view} />}
      {/* Cabinet graphics own their interiors; padded pathway targets stay underneath. */}
      <g className="conceptual-cabinet-foreground" pointerEvents={manual ? "none" : undefined} onKeyDownCapture={event => {if (manual) {event.preventDefault(); event.stopPropagation();}}}>{renderCabinets(display.cabinets.filter(c=>visibleLine(c,{x:c.x+c.width,y:c.y+c.height},v.view)))}</g>
      {manual && <ManualRouteLayer data={data} view={display} segments={manual.segments} preview={manual.preview} scale={v.scale} onAppend={manual.append} onSegments={manual.chooseSegments} disabled={manual.disabled} tiers={tiers} viewport={v.view} />}
    </svg>
  </section>;
}

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { SelectionGesture } from "../App";
import { fetchCabinetLayout } from "../api";
import type { CabinetLayoutItem } from "../types";
import type { CabinetGraphicPosition, CabinetGraphicSettings } from "../components/CabinetGraphics";
import { ConceptualRoutingMap } from "./ConceptualRoutingMap";
import { conceptualSegments, edgeSegment, styleFixtures } from "./conceptualSegments";
import { RouteLegend } from "./RouteStroke";
import { PathwayInspector } from "./PathwayInspector";
import { TierVisibility } from "./TierVisibility";
import { cabinetFixtureRun } from "./cabinetFixtureRun";
import { SegmentCables } from "./SegmentCables";
import { useRoutingLayout, physicalHallCode } from "./useRoutingLayout";
import type { Selection, Tier } from "./types";
import "./routing.css";

type Props = {
  project: string; building: string; hall: string; selected: Set<string>; connected: Set<string>;
  onSelectCabinet: (uid: string, gesture: SelectionGesture) => void;
  onPrefetchCabinet: (uid: string) => void; onClearSelection: () => void; onOpenRouting: () => void;
  canManage: boolean; cabinets: CabinetLayoutItem[]; settings: CabinetGraphicSettings & { hotAisleGap: number };
  renderCabinets: (positions: CabinetGraphicPosition[], clearPath: () => void) => ReactNode;
  inspectorHost: HTMLDivElement | null; pathwayInspectorHost: HTMLDivElement | null; onInspectorActiveChange: (active: boolean) => void;
};
export function CabinetRoutingMap({ project, building, hall, selected, connected, onSelectCabinet, onPrefetchCabinet, onClearSelection, onOpenRouting, canManage, cabinets, settings, renderCabinets, inspectorHost, pathwayInspectorHost, onInspectorActiveChange }: Props) {
  const physicalHall = physicalHallCode(project, hall);
  const { data, graph, loading, busy, error, mutate } = useRoutingLayout(project, building, physicalHall);
  const [tiers, setTiers] = useState(new Set<Tier>([1, 2, 3]));
  const [selection, setSelection] = useState<Selection>(null);
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [attachmentUid, setAttachmentUid] = useState<string | null>(null);
  const [selectedFixtureCableId, setSelectedFixtureCableId] = useState<string | null>(null);
  const [fixtures, setFixtures] = useState(true);
  const [inventory, setInventory] = useState<CabinetLayoutItem[]>([]);
  const [inventoryError, setInventoryError] = useState("");
  const sectionHalls = data?.geometry.sections.map(s => s.data_hall_id).filter((h): h is string => Boolean(h)).join("|") ?? "";
  useEffect(() => {
    const controller = new AbortController();
    setInventory([]); setInventoryError("");
    void Promise.all(sectionHalls.split("|").filter(Boolean).map(h => fetchCabinetLayout(h, controller.signal)))
      .then(rows => { if (!controller.signal.aborted) setInventory(rows.flat()); })
      .catch(reason => { if (!controller.signal.aborted) setInventoryError(String(reason)); });
    return () => controller.abort();
  }, [project, building, sectionHalls]);
  const inventoryByUid = useMemo(() => new Map([...inventory, ...cabinets].map(c => [c.cabinet_uid, c])), [inventory, cabinets]);
  const segments = useMemo(() => data ? conceptualSegments(data) : [], [data]);
  const fixtureMap = useMemo(() => data && fixtures ? styleFixtures(data, segments) : new Map(), [data, segments, fixtures]);
  const cabinetRun = useMemo(() => data && fixtures ? cabinetFixtureRun(data, segments) : null, [data, segments, fixtures]);
  useEffect(() => { setSelection(null); setSegmentId(null); setAttachmentUid(null); setSelectedFixtureCableId(null); }, [project, building, hall]);
  useEffect(() => { if (!fixtures) { setAttachmentUid(null); setSelectedFixtureCableId(null); } }, [fixtures]);
  const sectionUid = data?.geometry.sections.find(s => s.data_hall_id === hall)?.uid ?? "";
  const selectedEdge = selection?.kind === "edge" ? graph.edges.find(e => e.id === selection.uid) : undefined;
  const segment = segments.find(s => s.id === segmentId) ?? (data && selectedEdge ? edgeSegment(data, graph, selectedEdge) : null);
  const clearPath = () => { setSelection(null); setSegmentId(null); setAttachmentUid(null); setSelectedFixtureCableId(null); };
  const inspecting = Boolean(selection || segment || attachmentUid);
  useEffect(() => {
    onInspectorActiveChange(inspecting);
    return () => onInspectorActiveChange(false);
  }, [inspecting, onInspectorActiveChange]);
  const runSelected = cabinetRun && (attachmentUid || (segment && cabinetRun.segmentIds.includes(segment.id)));
  const cables = runSelected ? cabinetRun.cables : [];
  const inspector = data && inspecting ? <aside className="side-pane routing-page routing-side routing-segment-inspector" aria-label="Routing segment cable details">
    <div className="routing-inspector-heading"><span className="eyebrow">Segment cables</span><button onClick={clearPath}>Close routing details</button></div>
    {(segment || attachmentUid) && <SegmentCables cables={cables} selectedCableId={selectedFixtureCableId} onSelect={setSelectedFixtureCableId} />}
    {!segment && !attachmentUid && <p className="routing-notice">Select a route segment to inspect its cables. Pathway metadata is shown on the left.</p>}
  </aside> : null;
  return <div className="routing-page routing-integrated">
    <div className="routing-toolbar"><TierVisibility tiers={tiers} onChange={setTiers} /><button onClick={onOpenRouting}>Geometric routing map</button>
      <label className="conceptual-fixture-toggle"><input type="checkbox" checked={fixtures} onChange={event => setFixtures(event.target.checked)} />Style fixtures (fake cables)</label></div>
    <RouteLegend />
    {fixtures && <p className="conceptual-fixture-notice" role="status">Style fixtures enabled · {cabinetRun ? "021 → 031: LC, MPO and Cat6, plus " : ""}color samples and one unusable example. Fixtures never change saved route data.</p>}
    {error && <p className="routing-error" role="alert">{error}</p>}
    {inventoryError && <p className="routing-error" role="alert">{inventoryError}</p>}
    {loading && !data ? <p>Loading pathways…</p> : !data ? <div className="routing-empty"><p>No routing layout is available for this hall. The standard cabinet map remains available.</p><button onClick={onOpenRouting}>Open routing configuration</button></div> : <>
      {!graph.nodes.length && <p className="routing-notice">Pathway guides shown; tier assignments and openings await configuration.</p>}
      <ConceptualRoutingMap key={data.layout.uid} data={data} graph={graph} tiers={tiers} selection={selection} settings={settings}
        segments={segments} fixtures={fixtureMap} selectedSegmentId={segmentId}
        cabinetRun={cabinetRun} selectedAttachmentUid={attachmentUid} selectedFixtureCableId={selectedFixtureCableId}
        onSelectRunPart={part => { setSelection(null); setSelectedFixtureCableId(null); setSegmentId(part.kind === "segment" ? part.id : null); setAttachmentUid(part.kind === "attachment" ? part.id : null); }}
        onSelectSegment={id => { setSelection(null); setSegmentId(id); setAttachmentUid(null); setSelectedFixtureCableId(null); }}
        renderCabinets={tiles => renderCabinets(tiles.flatMap(t => { const cabinet = inventoryByUid.get(t.cabinet.cabinet_uid); return cabinet ? [{ cabinet, x: t.x, y: t.y }] : []; }), clearPath)}
        initialSectionUid={sectionUid}
        onSelect={next => { setSelection(next); setSegmentId(null); setAttachmentUid(null); setSelectedFixtureCableId(null); if (!next) onClearSelection(); }}
        cabinetInteraction={{ selected, connected, onSelect: (cabinet, event) => { clearPath(); onSelectCabinet(cabinet.cabinet_uid, event); }, onPrefetch: onPrefetchCabinet }} />
      {inspectorHost && inspector && createPortal(inspector, inspectorHost)}
      {pathwayInspectorHost && data && inspecting && createPortal(<PathwayInspector data={data} graph={graph} selection={selection} segment={segment} selectedEdge={selectedEdge}
        attachmentUid={attachmentUid} fixture={fixtureMap.get(segment?.id ?? "")} canManage={canManage} busy={busy} mutate={mutate} onSelect={setSelection} onOpenRouting={onOpenRouting} />, pathwayInspectorHost)}
    </>}
  </div>;
}

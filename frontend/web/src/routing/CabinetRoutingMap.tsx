import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { SelectionGesture } from "../App";
import { fetchCabinetLayout } from "../api";
import type { CabinetLayoutItem } from "../types";
import type { CabinetGraphicPosition, CabinetGraphicSettings } from "../components/CabinetGraphics";
import { ConceptualRoutingMap } from "./ConceptualRoutingMap";
import { conceptualSegments, edgeSegment, styleFixtures } from "./conceptualSegments";
import { RouteLegend } from "./RouteStroke";
import { SegmentDetails } from "./SegmentDetails";
import { RoutingDetails } from "./RoutingDetails";
import { TierVisibility } from "./TierVisibility";
import { useRoutingLayout, physicalHallCode } from "./useRoutingLayout";
import type { Selection, Tier } from "./types";
import "./routing.css";

type Props = {
  project: string; building: string; hall: string; selected: Set<string>; connected: Set<string>;
  onSelectCabinet: (uid: string, gesture: SelectionGesture) => void;
  onPrefetchCabinet: (uid: string) => void; onClearSelection: () => void; onOpenRouting: () => void;
  canManage: boolean; cabinets: CabinetLayoutItem[]; settings: CabinetGraphicSettings & { hotAisleGap: number };
  renderCabinets: (positions: CabinetGraphicPosition[], clearPath: () => void) => ReactNode;
};
export function CabinetRoutingMap({ project, building, hall, selected, connected, onSelectCabinet, onPrefetchCabinet, onClearSelection, onOpenRouting, canManage, cabinets, settings, renderCabinets }: Props) {
  const physicalHall = physicalHallCode(project, hall);
  const { data, graph, loading, busy, error, mutate } = useRoutingLayout(project, building, physicalHall);
  const [tiers, setTiers] = useState(new Set<Tier>([1, 2, 3]));
  const [selection, setSelection] = useState<Selection>(null);
  const [segmentId, setSegmentId] = useState<string | null>(null);
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
  useEffect(() => setSelection(null), [project, building, hall]);
  useEffect(() => setSegmentId(null), [project, building, hall]);
  const sectionUid = data?.geometry.sections.find(s => s.data_hall_id === hall)?.uid ?? "";
  const selectedEdge = selection?.kind === "edge" ? graph.edges.find(e => e.id === selection.uid) : undefined;
  const segment = segments.find(s => s.id === segmentId) ?? (data && selectedEdge ? edgeSegment(data, graph, selectedEdge) : null);
  const clearPath = () => { setSelection(null); setSegmentId(null); };
  return <div className="routing-page routing-integrated">
    <div className="routing-toolbar"><TierVisibility tiers={tiers} onChange={setTiers} /><button onClick={onOpenRouting}>Geometric routing map</button>
      <label className="conceptual-fixture-toggle"><input type="checkbox" checked={fixtures} onChange={event => setFixtures(event.target.checked)} />Style fixtures (fake cables)</label></div>
    <RouteLegend />
    {fixtures && <p className="conceptual-fixture-notice" role="status">Style fixtures enabled · Fake cable runs and one unusable example in Section 1 and its following gap. Fixtures never change saved route data.</p>}
    {error && <p className="routing-error" role="alert">{error}</p>}
    {inventoryError && <p className="routing-error" role="alert">{inventoryError}</p>}
    {loading && !data ? <p>Loading pathways…</p> : !data ? <div className="routing-empty"><p>No routing layout is available for this hall. The standard cabinet map remains available.</p><button onClick={onOpenRouting}>Open routing configuration</button></div> : <>
      {!graph.nodes.length && <p className="routing-notice">Pathway guides shown; tier assignments and openings await configuration.</p>}
      <ConceptualRoutingMap key={data.layout.uid} data={data} graph={graph} tiers={tiers} selection={selection} settings={settings}
        segments={segments} fixtures={fixtureMap} selectedSegmentId={segmentId}
        onSelectSegment={id => { setSelection(null); setSegmentId(id); }}
        renderCabinets={tiles => renderCabinets(tiles.flatMap(t => { const cabinet = inventoryByUid.get(t.cabinet.cabinet_uid); return cabinet ? [{ cabinet, x: t.x, y: t.y }] : []; }), clearPath)}
        initialSectionUid={sectionUid}
        onSelect={next => { setSelection(next); setSegmentId(null); if (!next) onClearSelection(); }}
        cabinetInteraction={{ selected, connected, onSelect: (cabinet, event) => { clearPath(); onSelectCabinet(cabinet.cabinet_uid, event); }, onPrefetch: onPrefetchCabinet }} />
      {(selection || segment) && <section className="routing-side routing-integrated-details" aria-label="Selected pathway details"><button onClick={clearPath}>Close pathway details</button>
        {selectedEdge && <RoutingDetails data={data} graph={graph} selection={selection} onSelect={setSelection} canManage={false} busy={busy} mutate={mutate} />}
        {segment ? <SegmentDetails key={`${segment.id}:${selectedEdge?.tier}:${data.segment_annotations.map(a => a.updated_at ?? a.uid).join()}`} data={data} segment={segment} tier={selectedEdge?.tier ?? null} fixture={fixtureMap.get(segment.id)} canManage={canManage} busy={busy} mutate={mutate} />
          : <RoutingDetails data={data} graph={graph} selection={selection} onSelect={setSelection} canManage={false} busy={busy} mutate={mutate} />}
      </section>}
    </>}
  </div>;
}

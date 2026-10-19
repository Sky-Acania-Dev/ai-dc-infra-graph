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
import { useSegmentCableMembers } from "./useSegmentCableMembers";
import { segmentTierModel } from "./segmentTierModel";
import { useRoutingLayout, physicalHallCode } from "./useRoutingLayout";
import { useCableReview } from "./useCableReview";
import { CableReviewPanel } from "./CableReviewPanel";
import { RoutingCableTable } from "./RoutingCableTable";
import type { RoutingCableTableRequest } from "./routingCableDetails";
import { reviewGroupsForPart } from "./cableReviewProjection";
import type { Selection, Tier, ReviewScope } from "./types";
import { useManualRouteEditor } from "./useManualRouteEditor";
import { routingApi } from "./api";
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
  const { data, graph, loading, busy, error, mutate, reload: reloadLayout } = useRoutingLayout(project, building, physicalHall);
  const [tiers, setTiers] = useState(new Set<Tier>([1, 2, 3]));
  const [selection, setSelection] = useState<Selection>(null);
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [attachmentUid, setAttachmentUid] = useState<string | null>(null);
  const [selectedFixtureCableId, setSelectedFixtureCableId] = useState<string | null>(null);
  const [cableTable, setCableTable] = useState<RoutingCableTableRequest | null>(null);
  const [selectedPlacementUid, setSelectedPlacementUid] = useState<string | null>(null);
  const [fixtures, setFixtures] = useState(false);
  const [realReview, setRealReview] = useState(project === "LBB01" && physicalHall === "DH1");
  const [reviewScope, setReviewScope] = useState<ReviewScope>("hall");
  const [focusedPairKey, setFocusedPairKey] = useState<string | null>(null);
  const [reviewInspectorOpen, setReviewInspectorOpen] = useState(true);
  const reviewState = useCableReview(data, realReview && project === "LBB01" && physicalHall === "DH1", reviewScope);
  const review = reviewState.data;
  useEffect(()=>{setRealReview(project === "LBB01" && physicalHall === "DH1"); setFixtures(false);},[project,physicalHall]);
  const manual = useManualRouteEditor(data?.layout.uid, review, reviewState.replace, reviewState.reload);
  useEffect(() => {if (manual.editing) setCableTable(null);}, [manual.editing]);
  const [tierSetupBusy, setTierSetupBusy] = useState(false);
  const [tierSetupError, setTierSetupError] = useState("");
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
  useEffect(() => {setFocusedPairKey(null); setReviewInspectorOpen(true);}, [project, building, hall, realReview]);
  const sectionUid = data?.geometry.sections.find(s => s.data_hall_id === hall)?.uid ?? "";
  const selectedEdge = selection?.kind === "edge" ? graph.edges.find(e => e.id === selection.uid) : undefined;
  const segment = segments.find(s => s.id === segmentId) ?? (data && selectedEdge ? edgeSegment(data, graph, selectedEdge) : null);
  const cableMembers = useSegmentCableMembers(data, segment);
  useEffect(() => { setSelectedPlacementUid(null); }, [segmentId, attachmentUid, selection?.uid, fixtures]);
  useEffect(() => { setCableTable(null); }, [project, building, hall, segmentId, attachmentUid, selection?.uid, selectedPlacementUid, fixtures, realReview]);
  const clearPath = () => { setCableTable(null); setSelection(null); setSegmentId(null); setAttachmentUid(null); setSelectedFixtureCableId(null); setFocusedPairKey(null); setReviewInspectorOpen(false); };
  const inspecting = Boolean(selection || segment || attachmentUid || (review && reviewInspectorOpen));
  useEffect(() => {
    onInspectorActiveChange(inspecting);
    return () => onInspectorActiveChange(false);
  }, [inspecting, onInspectorActiveChange]);
  const runSelected = cabinetRun && (attachmentUid || (segment && cabinetRun.segmentIds.includes(segment.id)));
  const cables = runSelected ? cabinetRun.cables : [];
  const sectionModel = data && segment ? segmentTierModel(data, segment, cables) : null;
  const selectedBundle = sectionModel?.blocks.find(b => b.uid === selectedPlacementUid);
  const demoCable = selectedPlacementUid?.startsWith("demo-section:") ? cables.find(c => `demo-section:${c.id}` === selectedPlacementUid) : undefined;
  const selectedNode = selection?.kind === "node" ? graph.nodes.find(n=>n.id === selection.uid) : undefined;
  const reviewGroups = useMemo(()=>review ? reviewGroupsForPart(review, segment?.id, null, attachmentUid, selectedNode) : [], [review, segment?.id, attachmentUid, selectedNode]);
  const highlightGroupUid = selectedFixtureCableId && cableTable?.groupUid ? cableTable.groupUid : review?.groups.find(g => g.cable_uids.includes(selectedFixtureCableId ?? ""))?.uid ?? null;
  const inspector = data && inspecting ? <aside className="side-pane connections-pane routing-page routing-side routing-segment-inspector" aria-label="Routing segment cable details">
    <div className="routing-inspector-heading"><span className="eyebrow">Segment cables</span><button disabled={manual.editing || manual.busy} onClick={clearPath}>Close routing details</button></div>
    {review ? <CableReviewPanel key={JSON.stringify([reviewScope,segment?.id,attachmentUid,selectedNode?.x_in,selectedNode?.y_in])} review={review} groups={reviewGroups} focusedPairKey={focusedPairKey} onFocusPair={key=>{if (!manual.editing && !manual.busy) {setFocusedPairKey(key); setSelectedFixtureCableId(null); setCableTable(null); onClearSelection();}}} editor={manual} canManage={canManage}
      onViewCables={request => {if (!manual.editing) setCableTable(request);}} /> : (segment || attachmentUid) && <SegmentCables cables={cables} inventoryCables={cableMembers.cables} members={cableMembers.members} loading={cableMembers.loading} error={cableMembers.error}
      bundleFilter={selectedPlacementUid ? {uid: selectedPlacementUid, label: selectedBundle?.label ?? (demoCable ? `Demo ${demoCable.cableClass} 021→031` : "Selected bundle"), fixtureCableIds: selectedBundle?.fixtureCableIds ?? (demoCable ? [demoCable.id] : undefined)} : null}
      onClearFilter={() => setSelectedPlacementUid(null)} onViewCables={setCableTable} routeLabel={cabinetRun?.segmentIds.map(id => segments.find(s => s.id === id)?.label).join(" → ")} />}
    {!review && !segment && !attachmentUid && <p className="routing-notice">Select a route segment to inspect its cables. Pathway metadata is shown on the left.</p>}
  </aside> : null;
  return <div className="routing-page routing-integrated">
    <div className="routing-toolbar"><TierVisibility tiers={tiers} onChange={setTiers} /><button onClick={onOpenRouting}>Geometric routing map</button>
      <label className="conceptual-fixture-toggle"><input type="checkbox" checked={fixtures} onChange={event => {clearPath(); setFixtures(event.target.checked); if (event.target.checked) setRealReview(false);}} />Style fixtures (fake cables)</label>
      {project === "LBB01" && physicalHall === "DH1" && <label className="conceptual-fixture-toggle"><input disabled={manual.editing || manual.busy} type="checkbox" checked={realReview} onChange={event => {clearPath(); setRealReview(event.target.checked); if (event.target.checked) setFixtures(false);}} />Actual cable review</label>}
      {realReview && <select aria-label="Cable review scope" disabled={manual.editing || manual.busy} value={reviewScope} onChange={event=>{clearPath(); setReviewScope(event.target.value as ReviewScope);}}><option value="hall">All five DH1 sections · tier policies</option><option value="pilot">Original test rows · Tier 1 defaults</option></select>}
      {review && <button disabled={manual.editing || manual.busy} onClick={() => {clearPath(); setReviewInspectorOpen(true); onClearSelection();}}>Review cable groups</button>}</div>
    <RouteLegend />
    {fixtures && <p className="conceptual-fixture-notice" role="status">Style fixtures enabled · {cabinetRun ? "021 → 031: LC, MPO and Cat6, plus " : ""}color samples and one unusable example. Fixtures never change saved route data.</p>}
    {error && <p className="routing-error" role="alert">{error}</p>}
    {inventoryError && <p className="routing-error" role="alert">{inventoryError}</p>}
    {reviewState.loading && <p role="status">Loading actual cables and provisional routes…</p>}
    {reviewState.error && <p className="routing-error" role="alert">{reviewState.error}</p>}
    {reviewState.error && <button onClick={reviewState.reload}>Retry cable loading</button>}
    {review && <p className="actual-review-notice" role="status">{review.label} · {review.inventory_cable_count.toLocaleString()} cables · {review.groups.length.toLocaleString()} rack-pair/type groups · {review.routed_cable_count.toLocaleString()} inter-rack cables routed · {review.same_cabinet_count.toLocaleString()} same-cabinet cables kept local · {review.unrouted_cable_count.toLocaleString()} unrouted · {review.manual_group_count ?? 0} manual groups{review.build_ms != null ? ` · server ${ (review.build_ms / 1000).toFixed(1)}s` : ""}. A* never overwrites saved manual routes.</p>}
    {review?.scope === "hall" && <details className="inventory-test-info"><summary>Inventory test rules and unrouted cables</summary><p>{review.notes}</p><p>Unmapped endpoints: {(review.unmapped_cable_count ?? 0).toLocaleString()} cables.</p>{Object.entries(review.unrouted_reasons ?? {}).map(([reason,count])=><p key={reason}>{count.toLocaleString()} · {reason}</p>)}<p>Rows/CENTRAL: 8′2″ / 9′2″ / 10′2″ AFF. NORTH/SOUTH: 8′2″ / 9′8″ AFF. Row Tier 3 uses the confirmed row-end opening to outer passage Tier 2. Gaps use two test layers. FE inner-side intent has no measured bundle footprint.</p></details>}
    {realReview && reviewScope === "hall" && canManage && <button disabled={tierSetupBusy || manual.editing || manual.busy} onClick={async()=>{if (!data) return; setTierSetupBusy(true); setTierSetupError(""); try {await routingApi.inventoryTestProfile(data.layout.uid); await reloadLayout();} catch(reason) {setTierSetupError(String(reason));} finally {setTierSetupBusy(false);}}}>{tierSetupBusy ? "Configuring hall test…" : "Configure hall test tiers and row-end openings"}</button>}
    {review && !review.planning_segments?.length && canManage && <button disabled={tierSetupBusy} onClick={async () => {if (!data) return; setTierSetupBusy(true); setTierSetupError(""); try {await routingApi.testTiers(data.layout.uid); await reloadLayout();} catch (reason) {setTierSetupError(String(reason));} finally {setTierSetupBusy(false);}}}>{tierSetupBusy ? "Configuring test pathways…" : "Configure Tier 1 test pathways"}</button>}
    {tierSetupError && <p role="alert" className="routing-error">{tierSetupError}</p>}
    {loading && !data ? <p>Loading pathways…</p> : !data ? <div className="routing-empty"><p>No routing layout is available for this hall. The standard cabinet map remains available.</p><button onClick={onOpenRouting}>Open routing configuration</button></div> : <>
      {!graph.nodes.length && <p className="routing-notice">Pathway guides shown; tier assignments and openings await configuration.</p>}
      <ConceptualRoutingMap key={data.layout.uid} data={data} graph={graph} tiers={tiers} selection={selection} settings={settings}
        segments={segments} fixtures={fixtureMap} selectedSegmentId={segmentId}
        cabinetRun={cabinetRun} selectedAttachmentUid={attachmentUid} selectedFixtureCableId={selectedFixtureCableId}
        review={review} selectedReviewGroupUid={manual.editing ? manual.activeUid : highlightGroupUid} focusedReviewPairKey={focusedPairKey}
        manual={manual.editing ? {preview: manual.preview, segments: review?.planning_segments ?? [], append: manual.append, chooseSegments: manual.chooseSegments, disabled: manual.busy} : null}
        onReviewAttachment={uid => {if (manual.editing) return; setReviewInspectorOpen(true); setSegmentId(null); setAttachmentUid(uid); setSelection(null); setSelectedFixtureCableId(null); onClearSelection();}}
        onSelectRunPart={part => { setSelection(null); setSelectedFixtureCableId(null); setSegmentId(part.kind === "segment" ? part.id : null); setAttachmentUid(part.kind === "attachment" ? part.id : null); }}
        onSelectSegment={id => { if (manual.editing) return; setReviewInspectorOpen(true); setSelection(null); setSegmentId(id); setAttachmentUid(null); setSelectedFixtureCableId(null); setFocusedPairKey(null); onClearSelection(); }}
        renderCabinets={tiles => renderCabinets(tiles.flatMap(t => { const cabinet = inventoryByUid.get(t.cabinet.cabinet_uid); return cabinet ? [{ cabinet, x: t.x, y: t.y }] : []; }), clearPath)}
        initialSectionUid={sectionUid}
        onSelect={next => { if (manual.editing) return; setSelection(next); setSegmentId(null); setAttachmentUid(null); setSelectedFixtureCableId(null); setFocusedPairKey(null); onClearSelection(); setReviewInspectorOpen(Boolean(next)); }}
        cabinetInteraction={{ selected, connected, onSelect: (cabinet, event) => { clearPath(); onSelectCabinet(cabinet.cabinet_uid, event); }, onPrefetch: onPrefetchCabinet }} />
      {cableTable && createPortal(<RoutingCableTable key={JSON.stringify([cableTable.source, cableTable.target, cableTable.cableType])} request={cableTable} selectedCableId={selectedFixtureCableId} onSelect={setSelectedFixtureCableId} onClose={() => {setCableTable(null); setSelectedFixtureCableId(null);}} />, document.body)}
      {inspectorHost && inspector && createPortal(inspector, inspectorHost)}
      {pathwayInspectorHost && data && inspecting && createPortal(<PathwayInspector data={data} graph={graph} selection={selection} segment={segment} selectedEdge={selectedEdge}
        attachmentUid={attachmentUid} fixture={cables.length ? { cable_classes: cables.map(c => c.cableClass), usable: true } : fixtureMap.get(segment?.id ?? "")} canManage={canManage} busy={busy} mutate={mutate} onSelect={setSelection} onOpenRouting={onOpenRouting} demoCables={cables}
        selectedPlacementUid={selectedPlacementUid} reviewGroupCount={reviewGroups.length} reviewLoads={review?.loads} onSelectPlacement={uid => { setSelectedPlacementUid(uid); setSelectedFixtureCableId(null); }} />, pathwayInspectorHost)}
    </>}
  </div>;
}

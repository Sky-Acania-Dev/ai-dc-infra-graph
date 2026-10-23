import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { SelectionGesture } from "../App";
import { fetchCabinetLayout } from "../api";
import type { CabinetLayoutItem } from "../types";
import type { CabinetGraphicPosition, CabinetGraphicSettings } from "../components/CabinetGraphics";
import { ConceptualRoutingMap } from "./ConceptualRoutingMap";
import { conceptualSegments, edgeSegment } from "./conceptualSegments";
import { RoutingOverview } from "./RoutingOverview";
import { PathwayInspector } from "./PathwayInspector";
import { TierVisibility } from "./TierVisibility";
import { SegmentCables } from "./SegmentCables";
import { useSegmentCableMembers } from "./useSegmentCableMembers";
import { segmentTierModel } from "./segmentTierModel";
import { useRoutingLayout, physicalHallCode } from "./useRoutingLayout";
import { useCableReview } from "./useCableReview";
import { CableReviewPanel } from "./CableReviewPanel";
import { RoutingCableTable } from "./RoutingCableTable";
import type { RoutingCableTableRequest } from "./routingCableDetails";
import { reviewGroupsForPart } from "./cableReviewProjection";
import type { Selection, Tier } from "./types";
import { useManualRouteEditor } from "./useManualRouteEditor";
import type { RoutingSummaryFilter, CableTypeFilter } from "./routingSummaryFilter";
import { focusedRouteGroups } from "./rackPairRoutes";
import { sectionGroupCounts, type RoutingSectionGroupCounts } from "./sectionGroupCounts";
import { RoutingLoadStatus } from "./RoutingLoadStatus";
import "./routing.css";

type Props = {
  project: string; building: string; hall: string; selected: Set<string>; connected: Set<string>;
  onSelectCabinet: (uid: string, gesture: SelectionGesture) => void;
  onPrefetchCabinet: (uid: string) => void; onClearSelection: () => void; onOpenRouting: () => void;
  canManage: boolean; cabinets: CabinetLayoutItem[]; settings: CabinetGraphicSettings & { hotAisleGap: number };
  renderCabinets: (positions: CabinetGraphicPosition[], clearPath: () => void) => ReactNode;
  inspectorHost: HTMLDivElement | null; pathwayInspectorHost: HTMLDivElement | null; onInspectorActiveChange: (active: boolean) => void;
  onPathwayInspectorActiveChange: (active: boolean) => void;
  tierHost: HTMLDivElement | null;
  onSectionGroupCountsChange: (counts: RoutingSectionGroupCounts | null) => void;
};
export function CabinetRoutingMap({ project, building, hall, selected, connected, onSelectCabinet, onPrefetchCabinet, onClearSelection, onOpenRouting, canManage, cabinets, settings, renderCabinets, inspectorHost, pathwayInspectorHost, onInspectorActiveChange, onPathwayInspectorActiveChange, tierHost, onSectionGroupCountsChange }: Props) {
  const physicalHall = physicalHallCode(project, hall);
  const { data, graph, loading, busy, error, mutate } = useRoutingLayout(project, building, physicalHall);
  const [tiers, setTiers] = useState(new Set<Tier>([1, 2, 3]));
  const [selection, setSelection] = useState<Selection>(null);
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [attachmentUid, setAttachmentUid] = useState<string | null>(null);
  const [selectedCableId, setSelectedCableId] = useState<string | null>(null);
  const [cableTable, setCableTable] = useState<RoutingCableTableRequest | null>(null);
  const [selectedPlacementUid, setSelectedPlacementUid] = useState<string | null>(null);
  const [realReview, setRealReview] = useState(project === "LBB01" && physicalHall === "DH1");
  const [focusedPairKey, setFocusedPairKey] = useState<string | null>(null);
  const [reviewInspectorOpen, setReviewInspectorOpen] = useState(true);
  const [summaryFilter, setSummaryFilter] = useState<RoutingSummaryFilter | null>(null);
  const [cableTypeFilter, setCableTypeFilter] = useState<CableTypeFilter | null>(null);
  const reviewState = useCableReview(data, realReview && project === "LBB01" && physicalHall === "DH1", "hall");
  const review = reviewState.data;
  useEffect(()=>{setRealReview(project === "LBB01" && physicalHall === "DH1");},[project,physicalHall]);
  const manual = useManualRouteEditor(data?.layout.uid, review, reviewState.replace, reviewState.reload, !reviewState.stale);
  useEffect(() => {if (manual.editing) setCableTable(null);}, [manual.editing]);
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
  // DH1-1…DH1-5 share a layout: navigation changes the viewport, not inspection state.
  useEffect(() => { setSelection(null); setSegmentId(null); setAttachmentUid(null); setSelectedCableId(null); }, [project, building, physicalHall]);
  useEffect(() => {setFocusedPairKey(null); setSummaryFilter(null); setCableTypeFilter(null); setReviewInspectorOpen(true);}, [project, building, physicalHall, realReview]);
  const sectionUid = data?.geometry.sections.find(s => s.data_hall_id === hall)?.uid ?? "";
  const selectedEdge = selection?.kind === "edge" ? graph.edges.find(e => e.id === selection.uid) : undefined;
  const segment = segments.find(s => s.id === segmentId) ?? (data && selectedEdge ? edgeSegment(data, graph, selectedEdge) : null);
  const cableMembers = useSegmentCableMembers(data, segment);
  useEffect(() => { setSelectedPlacementUid(null); }, [segmentId, attachmentUid, selection?.uid]);
  useEffect(() => { setCableTable(null); }, [project, building, physicalHall, segmentId, attachmentUid, selection?.uid, selectedPlacementUid, realReview]);
  const clearPath = () => { setCableTable(null); setSelection(null); setSegmentId(null); setAttachmentUid(null); setSelectedCableId(null); setFocusedPairKey(null); setSummaryFilter(null); setReviewInspectorOpen(false); };
  const selectSummaryFilter = (next: RoutingSummaryFilter | null) => {
    if (manual.editing || manual.busy) return;
    clearPath(); onClearSelection(); manual.clearSelected();
    setSummaryFilter(next); setReviewInspectorOpen(true);
  };
  const selectCableTypeFilter = (next: CableTypeFilter | null) => {
    if (manual.editing || manual.busy) return;
    setCableTypeFilter(next); setCableTable(null); setSelectedCableId(null);
    manual.clearSelected(); setReviewInspectorOpen(true);
  };
  const inspecting = Boolean(selection || segment || attachmentUid || (review && reviewInspectorOpen));
  useEffect(() => {
    onInspectorActiveChange(inspecting);
    return () => onInspectorActiveChange(false);
  }, [inspecting, onInspectorActiveChange]);
  const pathwayInspecting = Boolean(data) && (inspecting || selected.size === 0);
  useEffect(() => {
    onPathwayInspectorActiveChange(pathwayInspecting);
    return () => onPathwayInspectorActiveChange(false);
  }, [pathwayInspecting, onPathwayInspectorActiveChange]);
  const sectionModel = data && segment ? segmentTierModel(data, segment) : null;
  const selectedBundle = sectionModel?.blocks.find(b => b.uid === selectedPlacementUid);
  const selectedNode = selection?.kind === "node" ? graph.nodes.find(n=>n.id === selection.uid) : undefined;
  const reviewGroups = useMemo(()=>review ? reviewGroupsForPart(review, segment?.id, null, attachmentUid, selectedNode) : [], [review, segment?.id, attachmentUid, selectedNode]);
  const selectionGroupUids = useMemo(() => review && (segment || selectedNode || attachmentUid) ? new Set(reviewGroups.map(g => g.uid)) : null, [review, segment?.id, selectedNode, attachmentUid, reviewGroups]);
  const highlightGroupUid = selectedCableId && cableTable?.groupUid ? cableTable.groupUid : review?.groups.find(g => g.cable_uids.includes(selectedCableId ?? ""))?.uid ?? null;
  const activeGroupUid = manual.editing ? manual.activeUid : highlightGroupUid;
  const routeFocusActive = Boolean(activeGroupUid || focusedPairKey || selected.size || selectionGroupUids != null || summaryFilter || cableTypeFilter);
  const sectionCounts = useMemo(() => data && review && routeFocusActive ? {project,building,
    counts:sectionGroupCounts(data,focusedRouteGroups(review.groups,activeGroupUid,focusedPairKey,selected,selectionGroupUids,summaryFilter,cableTypeFilter))} : null,
    [data,review,routeFocusActive,project,building,activeGroupUid,focusedPairKey,selected,selectionGroupUids,summaryFilter,cableTypeFilter]);
  useEffect(() => {onSectionGroupCountsChange(sectionCounts);}, [sectionCounts,onSectionGroupCountsChange]);
  useEffect(() => () => onSectionGroupCountsChange(null), [onSectionGroupCountsChange]);
  const inspector = data && inspecting ? <aside className="side-pane connections-pane routing-page routing-side routing-segment-inspector" aria-label="Routing segment cable details">
    <div className="routing-inspector-heading"><span className="eyebrow">Segment cables</span><button disabled={manual.editing || manual.busy} onClick={clearPath}>Close routing details</button></div>
    {review ? <CableReviewPanel key={JSON.stringify([review?.scope,segment?.id,attachmentUid,selectedNode?.x_in,selectedNode?.y_in,summaryFilter,cableTypeFilter])} review={review} groups={reviewGroups} focusedPairKey={focusedPairKey} onFocusPair={key=>{if (!manual.editing && !manual.busy) {setFocusedPairKey(key); setSelectedCableId(null); setCableTable(null); onClearSelection();}}} editor={manual} canManage={canManage && !reviewState.stale} summaryFilter={summaryFilter} onClearSummaryFilter={()=>selectSummaryFilter(null)} cableTypeFilter={cableTypeFilter} onClearCableTypeFilter={()=>selectCableTypeFilter(null)}
      onViewCables={request => {if (!manual.editing) setCableTable(request);}} /> : (segment || attachmentUid) && <SegmentCables inventoryCables={cableMembers.cables} members={cableMembers.members} loading={cableMembers.loading} error={cableMembers.error}
      bundleFilter={selectedPlacementUid ? {uid: selectedPlacementUid, label: selectedBundle?.label ?? "Selected bundle"} : null}
      onClearFilter={() => setSelectedPlacementUid(null)} onViewCables={setCableTable} />}
    {!review && !segment && !attachmentUid && <p className="routing-notice">Select a route segment to inspect its cables. Pathway metadata is shown on the left.</p>}
  </aside> : null;
  const overview = <>
    {error && <p className="routing-error" role="alert">{error}</p>}
    {inventoryError && <p className="routing-error" role="alert">{inventoryError}</p>}
    {reviewState.loading && !review && <p role="status">Loading bundle routes and counts…</p>}
    {review && reviewState.stale && <p className="actual-review-notice routing-summary-status" role="status">Saved overview · {reviewState.loading ? "Checking current routes…" : "Current routes could not be verified."}</p>}
    {reviewState.error && <p className="routing-error" role="alert">{reviewState.error}</p>}
    {reviewState.error && <button onClick={reviewState.reload}>Retry cable loading</button>}
    {review && <RoutingOverview review={review} stale={reviewState.stale} savedAt={reviewState.savedAt} filter={summaryFilter} onFilterChange={selectSummaryFilter} disabled={manual.editing || manual.busy} cableTypeFilter={cableTypeFilter} onCableTypeFilterChange={selectCableTypeFilter} />}
    {project === "LBB01" && physicalHall === "DH1" && <label className="routing-cable-toggle"><input disabled={manual.editing || manual.busy} type="checkbox" checked={realReview} onChange={event => {clearPath(); setRealReview(event.target.checked);}} />Actual cable review</label>}
  </>;
  return <div className="routing-page routing-integrated">
    {realReview && <RoutingLoadStatus layoutLoading={loading && !data} loading={reviewState.loading} hasRoutes={Boolean(review)} error={reviewState.error} onRetry={reviewState.reload} />}
    {tierHost && createPortal(<TierVisibility tiers={tiers} onChange={setTiers} />,tierHost)}
    {!data && error && <p role="alert" className="routing-error">{error}</p>}
    {loading && !data ? <p>Loading pathways…</p> : !data ? <div className="routing-empty"><p>No routing layout is available for this hall. The standard cabinet map remains available.</p><button onClick={onOpenRouting}>Open routing configuration</button></div> : <>
      {!graph.nodes.length && <p className="routing-notice">Pathway guides shown; tier assignments and openings await configuration.</p>}
      <ConceptualRoutingMap key={data.layout.uid} data={data} graph={graph} tiers={tiers} selection={selection} settings={settings}
        segments={segments} selectedSegmentId={segmentId}
        review={review} selectedReviewGroupUid={activeGroupUid} focusedReviewPairKey={focusedPairKey} selectionGroupUids={selectionGroupUids} summaryFilter={summaryFilter} cableTypeFilter={cableTypeFilter}
        manual={manual.editing ? {preview: manual.preview, segments: review?.planning_segments ?? [], append: manual.append, chooseSegments: manual.chooseSegments, disabled: manual.busy} : null}
        onReviewAttachment={uid => {if (manual.editing) return; setReviewInspectorOpen(true); setSegmentId(null); setAttachmentUid(uid); setSelection(null); setSelectedCableId(null); setFocusedPairKey(null); onClearSelection();}}
        onSelectSegment={id => { if (manual.editing) return; setReviewInspectorOpen(true); setSelection(null); setSegmentId(id); setAttachmentUid(null); setSelectedCableId(null); setFocusedPairKey(null); onClearSelection(); }}
        renderCabinets={tiles => renderCabinets(tiles.flatMap(t => { const cabinet = inventoryByUid.get(t.cabinet.cabinet_uid); return cabinet ? [{ cabinet, x: t.x, y: t.y }] : []; }), clearPath)}
        initialSectionUid={sectionUid}
        onOverview={() => {if (!manual.editing) {clearPath(); setCableTypeFilter(null); setReviewInspectorOpen(true); onClearSelection();}}}
        onSelect={next => { if (manual.editing) return; setSelection(next); setSegmentId(null); setAttachmentUid(null); setSelectedCableId(null); setFocusedPairKey(null); onClearSelection(); setReviewInspectorOpen(Boolean(next)); }}
        cabinetInteraction={{ selected, connected, onSelect: (cabinet, event) => { clearPath(); onSelectCabinet(cabinet.cabinet_uid, event); }, onPrefetch: onPrefetchCabinet }} />
      {cableTable && createPortal(<RoutingCableTable key={JSON.stringify([cableTable.source, cableTable.target, cableTable.cableType])} request={cableTable} selectedCableId={selectedCableId} onSelect={setSelectedCableId} onClose={() => {setCableTable(null); setSelectedCableId(null);}} />, document.body)}
      {inspectorHost && inspector && createPortal(inspector, inspectorHost)}
      {pathwayInspectorHost && data && pathwayInspecting && createPortal(<PathwayInspector data={data} graph={graph} selection={selection} segment={segment} selectedEdge={selectedEdge} overview={overview}
        attachmentUid={attachmentUid} canManage={canManage} busy={busy} mutate={mutate} onSelect={setSelection} onOpenRouting={onOpenRouting}
        selectedPlacementUid={selectedPlacementUid} reviewGroupCount={reviewGroups.length} reviewLoads={review?.loads} onSelectPlacement={uid => { setSelectedPlacementUid(uid); setSelectedCableId(null); }} />, pathwayInspectorHost)}
    </>}
  </div>;
}

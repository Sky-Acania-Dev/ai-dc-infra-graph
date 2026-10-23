import type { OrderUnit } from "./bundleOrderTypes";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { RoutingDetails } from "./RoutingDetails";
import { SegmentDetails } from "./SegmentDetails";
import { conceptualSegments, rowName, annotationFor, type ConceptualSegment } from "./conceptualSegments";
import { formatInches } from "./dimensions";
import type { GraphEdge, Mutate, ResolvedLayout, RoutingGraph, Selection, ReviewLoad } from "./types";
import { segmentTierModel } from "./segmentTierModel";
import { TierSectionDiagrams } from "./TierSectionDiagrams";
import { TierEditor } from "./TierEditor";
import { BundleSectionEditor } from "./BundleSectionEditor";
import { occupationLabel } from "./occupation";
import type { SectionDisplayMode } from "./SectionOccupationDiagram";
import { directionName } from "./sectionDirections";
import { JunctionInspector } from "./JunctionInspector";

export function PathwayInspector({ data, graph, selection, segment, selectedEdge, attachmentUid, canManage, busy, mutate, onSelect, onOpenRouting, selectedPlacementUid, onSelectPlacement, reviewGroupCount = 0, reviewLoads = [], overview, onSelectJunctionGroup, onSelectCableUnit }: {
  data: ResolvedLayout; graph: RoutingGraph; selection: Selection; segment: ConceptualSegment | null | undefined; selectedEdge?: GraphEdge;
  attachmentUid: string | null; canManage: boolean; busy: boolean;
  mutate: Mutate; onSelect: (selection: Selection) => void; onOpenRouting: () => void;
  selectedPlacementUid: string | null; onSelectPlacement: (uid: string | null) => void;
  reviewGroupCount?: number;
  reviewLoads?: ReviewLoad[];
  overview?: ReactNode;
  onSelectJunctionGroup?:(uid:string|null)=>void;
  onSelectCableUnit?:(unit:OrderUnit|null)=>void;
}) {
  const row = attachmentUid ? data.geometry.cabinet_rows.find(r => r.existing_cabinet_uids.includes(attachmentUid))
    : selection?.kind === "row" ? data.geometry.cabinet_rows.find(r => r.uid === selection.uid) : undefined;
  const route = data.geometry.cross_routes.find(r => r.uid === (segment?.cross_route_uid ?? (selection?.kind === "cross" ? selection.uid : undefined)));
  const section = data.geometry.sections.find(s => s.uid === (row?.section_uid ?? data.geometry.cabinet_rows.find(r => r.uid === route?.cabinet_row_uid)?.section_uid));
  const fallbackRoute = route ?? data.geometry.cross_routes.find(r => r.cabinet_row_uid === row?.uid);
  const opening = selection?.kind === "transition" ? data.vertical_transitions.find(v => v.uid === selection.uid) : undefined;
  const openingNode=opening?graph.nodes.filter(n=>n.passage_band_uid===opening.passage_band_uid&&n.station_in===opening.station_in).sort((a,b)=>a.tier-b.tier)[0]:undefined;
  const node = selection?.kind === "node" ? graph.nodes.find(n => n.id === selection.uid) : selectedEdge ? graph.nodes.find(n => n.id === selectedEdge.source_node_id) : undefined;
  const pointOwner = opening?.passage_band_uid ?? node?.passage_band_uid;
  const pointStation = opening?.station_in ?? node?.station_in;
  const pointSegment = pointOwner && pointStation != null ? { id: selection!.uid, label: opening?.label ?? (node ? `${node.passage_code} junction` : "Passage station"), passage_band_uid: pointOwner, cross_route_uid: null,
    start_station_in: pointStation, end_station_in: pointStation, from_passage_band_uid: null, to_passage_band_uid: null,
    width_in: data.bands.find(b => b.uid === pointOwner)!.width_in, planar_length_in: 0 } : null;
  const active = selection?.kind === "node" ? pointSegment : selection?.kind === "transition" || selectedEdge?.edge_type === "VERTICAL" ? null : segment ?? conceptualSegments(data).find(s => s.cross_route_uid === fallbackRoute?.uid)
    ?? (selection?.kind === "passage" ? { id: selection.uid, label: `${data.bands.find(b => b.uid === selection.uid)?.code} passage`, passage_band_uid: selection.uid,
      cross_route_uid: null, start_station_in: 0, end_station_in: data.geometry.hall_length_in, from_passage_band_uid: null, to_passage_band_uid: null,
      width_in: data.bands.find(b => b.uid === selection.uid)!.width_in, planar_length_in: data.geometry.hall_length_in } : null)
    ?? pointSegment;
  const model = useMemo(() => {
    if (!active) return null;
    const result = segmentTierModel(data, active);
    for (const load of reviewLoads) if (load.segment_id === active.id && load.tier) result.markedClasses[load.tier] = [...new Set([...(result.markedClasses[load.tier] ?? []), ...load.cable_classes])];
    return result;
  }, [data, active?.id, reviewLoads]);
  const [selectedBlockUid, setSelectedBlockUid] = useState<string | null>(null);
  const [sectionMode, setSectionMode] = useState<SectionDisplayMode>("GRID");
  const [reversed, setReversed] = useState(false);
  const [configureOpen, setConfigureOpen] = useState(false);
  useEffect(() => { setSelectedBlockUid(null); setConfigureOpen(false); }, [active?.id]);
  const placement = data.bundle_placements?.find(p => p.uid === selectedBlockUid);
  const marking = active ? annotationFor(data, active, selectedEdge?.tier ?? null) : undefined;
  const field = (name: string, value: string) => <div key={name}><dt>{name}</dt><dd title={value}>{value}</dd></div>;
  if(selection?.kind==="node"&&node)return <aside className="side-pane routing-page routing-side routing-pathway-inspector" aria-label="Pathway metadata and geometry"><JunctionInspector data={data} graph={graph} node={node} canManage={canManage} busy={busy} mutate={mutate} onSelectGroup={onSelectJunctionGroup} onSelectUnit={onSelectCableUnit} sectionMode={sectionMode} onSectionModeChange={setSectionMode}/>{reviewGroupCount>0&&<p className="actual-review-notice">{reviewGroupCount} actual type/rack-pair groups use this junction.</p>}{model&&<details open className="junction-passage-tier-sections"><summary>Passage tier sections</summary><TierSectionDiagrams data={data} model={model} canManage={canManage} onSelectGroup={onSelectJunctionGroup} onSelectUnit={onSelectCableUnit} selectedPlacementUid={selectedPlacementUid} mode={sectionMode} onModeChange={setSectionMode} reversed={reversed} onReverse={()=>setReversed(v=>!v)} onSelectPlacement={onSelectPlacement}/></details>}</aside>;
  return <aside className="side-pane routing-page routing-side routing-pathway-inspector" aria-label="Pathway metadata and geometry">
    <span className="eyebrow">Pathway inspection</span>
    {!selection && !segment && !attachmentUid && overview}
    {active && model ? <>
      <h3 className="compact-pathway-title">{attachmentUid ? `Cabinet ${data.cabinets.find(c => c.cabinet_uid === attachmentUid)?.cabinet_id} · ${active.label}` : active.label}</h3>
      <dl className="routing-generic-info" aria-label="Generic pathway information">
        {field("Hall / section", `${data.layout.physical_hall_code} · ${section?.name ?? (route?.kind === "SECTION_GAP" ? route.display_label : "Continuous passage")}`)}
        {field("Span", active.passage_band_uid ? `${formatInches(active.start_station_in!)}–${formatInches(active.end_station_in!)}` : `${data.bands.find(b => b.uid === active.from_passage_band_uid)?.code} → ${data.bands.find(b => b.uid === active.to_passage_band_uid)?.code}`)}
        {field("Planar length / width", attachmentUid ? `Connector unknown / route ${formatInches(active.width_in)}` : `${formatInches(active.planar_length_in)} / ${formatInches(active.width_in)}`)}
        {field("Station / source", route ? `${formatInches(route.station_in)} · ${route.station_source}` : "Ordered passage stations")}
        {field("Elevation AFF", model.records.length ? model.records.map(t => `T${t.tier}: ${(t.effective_elevation_in ?? t.elevation_in) == null ? "?" : formatInches((t.effective_elevation_in ?? t.elevation_in)!)}`).join(" · ") : data.layout.bottom_basket_elevation_in != null ? `Basket bottom ${formatInches(data.layout.bottom_basket_elevation_in)} · tiers unconfigured` : "Unknown · tiers unconfigured")}
        {field("Pathway types", model.records.length ? model.records.map(t => `T${t.tier} ${t.pathway_type === "LADDER_RACK" ? "Ladder" : "Basket"}${!t.enabled ? " (off)" : ""}`).join(" · ") : "Unconfigured")}
        {field("Marking / usability", `${marking ? "Manual" : "Unassigned"} · ${marking?.usable === false ? "Unusable" : "Usable"}`)}
        {field("Bundles / openings", `${model.blocks.length} saved / ${model.openings.filter(o => o.enabled).length} configured`)}
        {field("Section reference", model.reference ?? (!model.directions.hasInner ? "North / South · no inner side" : model.directions.inner ? `Inner ${directionName(model.directions.inner)} · toward cabinets` : "Inner side unassigned"))}
        {field("Notes / hall", attachmentUid ? "Schematic connector; no measured drop dimensions" : opening?.notes ?? marking?.notes ?? `${data.geometry.sections.length} sections · ${data.geometry.gaps.length} gaps · ${formatInches(data.geometry.total_width_in)} wide`)}
      </dl>
      {openingNode&&<button onClick={()=>onSelect({kind:"node",uid:openingNode.id})}>Inspect junction and bundle turns</button>}
      {reviewGroupCount > 0 && <p className="actual-review-notice">{reviewGroupCount} actual type/rack-pair groups use this selection in the provisional plan. Configured tiers are shown on the cable cards; sectional ordering can be edited below.</p>}
      <TierSectionDiagrams data={data} model={model} segment={active} canManage={canManage} onSelectGroup={onSelectJunctionGroup} onSelectUnit={onSelectCableUnit} selectedPlacementUid={selectedPlacementUid} mode={sectionMode} onModeChange={setSectionMode} reversed={reversed} onReverse={() => setReversed(current => !current)} onSelectPlacement={onSelectPlacement} />
      {canManage && <details className="section-configuration" open={configureOpen} onToggle={e => setConfigureOpen(e.currentTarget.open)}><summary>Configure heights / bundle sections</summary>
        {configureOpen && <>
        <TierEditor kind={active.passage_band_uid ? "passage" : "cross"} owner={(active.passage_band_uid ?? active.cross_route_uid)!} records={model.records} mutate={mutate} disabled={busy} layout={data.layout} passageCode={data.bands.find(b => b.uid === active.passage_band_uid)?.code} />
        <div className="routing-linked-list">{data.bundle_placements?.filter(p => model.parents.some(a => a.uid === p.segment_annotation_uid) && !p.is_section_container).map(p => <button key={p.uid} onClick={() => setSelectedBlockUid(p.uid)}>{p.resolved_label} · T{p.tier} · {occupationLabel(p)}{!p.enabled ? " · disabled" : ""}</button>)}{placement && <button onClick={() => setSelectedBlockUid(null)}>Add another bundle</button>}</div>
        <BundleSectionEditor key={placement?.uid ?? active.id} data={data} segment={active} placement={placement} mutate={mutate} busy={busy} />
        </>}
      </details>}
      <details className="section-configuration"><summary>Segment markings / references</summary><SegmentDetails key={`${active.id}:${data.segment_annotations.map(a => a.updated_at).join()}`} data={data} segment={active} tier={selectedEdge?.tier ?? null} canManage={canManage} busy={busy} mutate={mutate} /></details>
      <button className="compact-geometric-link" onClick={onOpenRouting}>Open geometric routing view</button>
    </> : <>
    {attachmentUid ? <>
      <h3>Cabinet {data.cabinets.find(c => c.cabinet_uid === attachmentUid)?.cabinet_id} cold-side attachment</h3>
      <dl>{field("Cabinet row", rowName(data, row?.uid))}{field("Section", section?.name ?? "—")}
        {field("Pair position", row?.position_in_pair ?? "—")}{field("Cold side", row?.position_in_pair === "A" ? "Preceding cold aisle" : "Following cold aisle")}</dl>
      <p className="routing-notice">Short connector from the center of the cabinet’s cold-side edge to its row route. Display only; no measured dimensions or tier assignment.</p>
    </> : <>
      {selectedEdge && <RoutingDetails data={data} graph={graph} selection={selection} onSelect={onSelect} canManage={false} busy={busy} mutate={mutate} />}
      {segment ? <>
        {section && <p className="routing-selection-section">{section.name} · {section.data_hall_id}</p>}
        <SegmentDetails key={`${segment.id}:${selectedEdge?.tier}:${data.segment_annotations.map(a => a.updated_at ?? a.uid).join()}`} data={data} segment={segment}
          tier={selectedEdge?.tier ?? null} canManage={canManage} busy={busy} mutate={mutate} />
      </> : <RoutingDetails data={data} graph={graph} selection={selection} onSelect={onSelect} canManage={false} busy={busy} mutate={mutate} />}
    </>}
    <details className="routing-geometry-summary" open>
      <summary>Geometric summary</summary>
      <dl>{field("Hall", data.layout.physical_hall_code)}{field("Sections / gaps", `${data.geometry.sections.length} / ${data.geometry.gaps.length}`)}
        {section && field("Section stations", `${formatInches(section.start_in)} → ${formatInches(section.end_in)}`)}
        {field("Transverse width", formatInches(data.geometry.total_width_in))}
        {field("Longitudinal extent", formatInches(data.geometry.hall_length_in))}
        {field("Row-pair module", formatInches(data.layout.row_pair_module_in))}
        {field("Extra section gap", formatInches(data.layout.section_extra_gap_in))}
        {data.geometry.bands.filter(b => b.kind === "PASSAGE").map(b => field(`${b.code} width`, formatInches(b.width_in)))}</dl>
      <p className="routing-notice">Stored dimensions are integer inches. Conceptual screen spacing is independent; unknown tier elevations remain unset.</p>
      <button onClick={onOpenRouting}>Open geometric routing view</button>
    </details>
    </>}
  </aside>;
}

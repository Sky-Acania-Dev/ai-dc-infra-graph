import { RoutingDetails } from "./RoutingDetails";
import { SegmentDetails } from "./SegmentDetails";
import type { ConceptualSegment } from "./conceptualSegments";
import { formatInches } from "./dimensions";
import type { CableClass, GraphEdge, Mutate, ResolvedLayout, RoutingGraph, Selection } from "./types";

export function PathwayInspector({ data, graph, selection, segment, selectedEdge, attachmentUid, fixture, canManage, busy, mutate, onSelect, onOpenRouting }: {
  data: ResolvedLayout; graph: RoutingGraph; selection: Selection; segment: ConceptualSegment | null | undefined; selectedEdge?: GraphEdge;
  attachmentUid: string | null; fixture?: { cable_classes: CableClass[]; usable: boolean }; canManage: boolean; busy: boolean;
  mutate: Mutate; onSelect: (selection: Selection) => void; onOpenRouting: () => void;
}) {
  const row = attachmentUid ? data.geometry.cabinet_rows.find(r => r.existing_cabinet_uids.includes(attachmentUid))
    : selection?.kind === "row" ? data.geometry.cabinet_rows.find(r => r.uid === selection.uid) : undefined;
  const route = data.geometry.cross_routes.find(r => r.uid === (segment?.cross_route_uid ?? (selection?.kind === "cross" ? selection.uid : undefined)));
  const section = data.geometry.sections.find(s => s.uid === (row?.section_uid ?? data.geometry.cabinet_rows.find(r => r.uid === route?.cabinet_row_uid)?.section_uid));
  const field = (name: string, value: string) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>;
  return <aside className="side-pane routing-page routing-side routing-pathway-inspector" aria-label="Pathway metadata and geometry">
    <span className="eyebrow">Pathway metadata</span>
    {attachmentUid ? <>
      <h3>Cabinet {data.cabinets.find(c => c.cabinet_uid === attachmentUid)?.cabinet_id} cold-side attachment</h3>
      <dl>{field("Cabinet row", row?.name ?? "—")}{field("Section", section?.name ?? "—")}
        {field("Pair position", row?.position_in_pair ?? "—")}{field("Cold side", row?.position_in_pair === "A" ? "Preceding cold aisle" : "Following cold aisle")}</dl>
      <p className="routing-notice">Short connector from the center of the cabinet’s cold-side edge to its row route. Display only; no measured dimensions or tier assignment.</p>
    </> : <>
      {selectedEdge && <RoutingDetails data={data} graph={graph} selection={selection} onSelect={onSelect} canManage={false} busy={busy} mutate={mutate} />}
      {segment ? <>
        {section && <p className="routing-selection-section">{section.name} · {section.data_hall_id}</p>}
        <SegmentDetails key={`${segment.id}:${selectedEdge?.tier}:${data.segment_annotations.map(a => a.updated_at ?? a.uid).join()}`} data={data} segment={segment}
          tier={selectedEdge?.tier ?? null} fixture={fixture} canManage={canManage} busy={busy} mutate={mutate} />
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
      <p className="routing-notice">Stored dimensions are integer inches. Conceptual screen spacing is independent; tier elevations are not modeled.</p>
      <button onClick={onOpenRouting}>Open geometric routing view</button>
    </details>
  </aside>;
}

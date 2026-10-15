import type { Mutate, ResolvedLayout, RoutingGraph, Selection } from "./types";
import { formatInches } from "./dimensions";
import { TierEditor } from "./TierEditor";
import { OpeningEditor } from "./OpeningEditor";
import { PairEditor, RowEditor } from "./RowEditor";
import { CrossRouteEditor } from "./CrossRouteEditor";

type Props = { data: ResolvedLayout; graph: RoutingGraph; selection: Selection; onSelect: (s: Selection) => void; canManage: boolean; busy: boolean; mutate: Mutate };
export function RoutingDetails({ data, graph, selection, onSelect, canManage, busy, mutate }: Props) {
  const crossName = (uid: string) => { const route = data.cross_routes.find(r => r.uid === uid); return route?.label ?? data.cabinet_rows.find(r => r.uid === route?.cabinet_row_uid)?.name ?? "Cross route"; };
  const field = (name: string, value: unknown) => <div key={name}><dt>{name}</dt><dd>{String(value ?? "—")}</dd></div>;
  if (!selection) return <div className="routing-empty"><h3>Inspect a pathway</h3><p>Select a passage, cold-side route, cabinet row, graph node, edge, or opening.</p><p>Tier 1 is solid, Tier 2 dashed, Tier 3 dash-dot.</p></div>;
  if (selection.kind === "passage") {
    const passage = data.geometry.bands.find(b => b.uid === selection.uid);
    if (!passage) return null;
    return <div><h3>{passage.code} passage</h3><dl>{field("Width", formatInches(passage.width_in))}{field("Centerline Y", formatInches(passage.center_in))}{field("Extent", "Continuous through all five sections")}</dl><h4>Explicit pathway tiers</h4><TierEditor kind="passage" owner={passage.uid} records={data.passage_tiers.filter(p => p.passage_band_uid === passage.uid)} mutate={mutate} disabled={!canManage || busy} /></div>;
  }
  if (selection.kind === "cross") {
    const route = data.geometry.cross_routes.find(r => r.uid === selection.uid);
    if (!route) return null;
    return <div><h3>{crossName(route.uid)}</h3><dl>{field("Kind", route.kind)}{field("Station", formatInches(route.station_in))}{field("Station source", route.station_source)}{field("Width", formatInches(route.width_in))}{field("Enabled", route.effective_enabled ? "Yes" : "No")}</dl>
      {route.cabinet_row_uid && <button onClick={() => onSelect({ kind: "row", uid: route.cabinet_row_uid! })}>Inspect associated cabinet row</button>}
      <h4>Explicit pathway tiers</h4><TierEditor kind="cross" owner={route.uid} records={data.cross_route_tiers.filter(t => t.cross_route_uid === route.uid)} mutate={mutate} disabled={!canManage || busy} />
      {canManage && <CrossRouteEditor key={route.uid} route={route} mutate={mutate} disabled={busy} />}
    </div>;
  }
  if (selection.kind === "row") {
    const row = data.geometry.cabinet_rows.find(r => r.uid === selection.uid);
    if (!row) return null;
    const pair = data.row_pairs.find(p => p.uid === row.row_pair_uid)!;
    const route = data.cross_routes.find(r => r.cabinet_row_uid === row.uid)!;
    return <div><h3>{row.name}</h3><dl>{field("Pair", pair.name ?? pair.ordinal_in_section)}{field("Position", row.position_in_pair)}{field("Section", data.sections.find(s => s.uid === row.section_uid)?.name)}{field("Row field", data.bands.find(b => b.uid === row.row_field_band_uid)?.code)}{field("Cold side", row.position_in_pair === "A" ? "Preceding cold aisle" : "Following cold aisle")}{field("Existing cabinets linked", row.existing_cabinet_uids.length)}{field("Row reference", row.existing_row_reference)}</dl>
      <button onClick={() => onSelect({ kind: "cross", uid: route.uid })}>Inspect cold-side route</button>
      {canManage && <><RowEditor key={row.uid} data={data} row={row} disabled={busy} mutate={mutate} /><details><summary>Edit this row pair</summary><PairEditor key={pair.uid} data={data} pair={pair} disabled={busy} mutate={mutate} /></details></>}
    </div>;
  }
  if (selection.kind === "transition") {
    const opening = data.vertical_transitions.find(o => o.uid === selection.uid);
    if (!opening) return null;
    return <div><h3>{opening.label ?? "Physical opening"}</h3><dl>{field("Passage", data.bands.find(b => b.uid === opening.passage_band_uid)?.code)}{field("Station", formatInches(opening.station_in))}{field("Tier pair", `T${opening.lower_tier} ↕ T${opening.upper_tier}`)}{field("Notes", opening.notes)}{field("Enabled", opening.enabled ? "Yes" : "No")}</dl>
      {canManage && <OpeningEditor key={opening.uid} opening={opening} data={data} disabled={busy} mutate={mutate} onDone={() => onSelect(null)} />}</div>;
  }
  if (selection.kind === "node") {
    const node = graph.nodes.find(n => n.id === selection.uid);
    if (!node) return null;
    return <div><h3>Graph node · Tier {node.tier}</h3><dl>{field("Kind", node.node_type)}{field("Passage", node.passage_code)}{field("Station", formatInches(node.station_in))}{node.cross_route_uid && field("Cross route", crossName(node.cross_route_uid))}</dl><h4>Connected edges</h4><div className="routing-linked-list">{graph.edges.filter(e => e.source_node_id === node.id || e.target_node_id === node.id).map(edge => <button key={edge.id} onClick={() => onSelect({ kind: "edge", uid: edge.id })}>{edge.edge_type} · {formatInches(edge.planar_length_in)}</button>)}</div><details><summary>Stable node ID</summary><code>{node.id}</code></details></div>;
  }
  const edge = graph.edges.find(e => e.id === selection.uid);
  if (!edge) return null;
  const a = graph.nodes.find(n => n.id === edge.source_node_id)!, b = graph.nodes.find(n => n.id === edge.target_node_id)!;
  return <div><h3>{edge.edge_type} edge</h3><dl>
    {field("Tier", edge.tier ? `Tier ${edge.tier}` : `Tier ${edge.lower_tier} ↕ Tier ${edge.upper_tier}`)}{field("Pathway type", edge.pathway_type)}
    {edge.cross_route_uid && <>{field("Cross route", crossName(edge.cross_route_uid))}{field("Kind", edge.cross_route_kind)}</>}
    {edge.edge_type === "CROSS_ROUTE" ? <>{field("From passage", a.passage_code)}{field("To passage", b.passage_code)}</> : <>{field("Passage", edge.passage_code)}{field("From station", formatInches(a.station_in))}{field("To station", formatInches(b.station_in))}</>}
    {field("Planar pathway length", formatInches(edge.planar_length_in))}
    {edge.vertical_transition_uid && <>{field("Opening", data.vertical_transitions.find(v => v.uid === edge.vertical_transition_uid)?.label)}{field("Notes", data.vertical_transitions.find(v => v.uid === edge.vertical_transition_uid)?.notes)}</>}
  </dl><div className="routing-linked-list">
    {edge.cross_route_uid && <button onClick={() => onSelect({ kind: "cross", uid: edge.cross_route_uid! })}>Inspect cross route</button>}
    {edge.vertical_transition_uid && <button onClick={() => onSelect({ kind: "transition", uid: edge.vertical_transition_uid! })}>Inspect physical opening</button>}
    <button onClick={() => onSelect({ kind: "node", uid: a.id })}>Inspect source node</button><button onClick={() => onSelect({ kind: "node", uid: b.id })}>Inspect target node</button>
  </div></div>;
}

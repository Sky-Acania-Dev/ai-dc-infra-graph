import type { Mutate, ResolvedLayout, RoutingGraph, Selection } from "./types";
import { formatInches } from "./dimensions";
import { TierEditor } from "./TierEditor";
import { OpeningEditor } from "./OpeningEditor";
import { PairEditor, RowEditor } from "./RowEditor";
import { rowName, crossName as routingCrossName } from "./conceptualSegments";
import { CrossRouteEditor } from "./CrossRouteEditor";

type Props = { data: ResolvedLayout; graph: RoutingGraph; selection: Selection; onSelect: (s: Selection) => void; canManage: boolean; busy: boolean; mutate: Mutate };
export function RoutingDetails({ data, graph, selection, onSelect, canManage, busy, mutate }: Props) {
  const crossName = (uid: string) => routingCrossName(data, uid);
  const field = (name: string, value: unknown) => <div key={name}><dt>{name}</dt><dd>{String(value ?? "—")}</dd></div>;
  if (!selection) return <details className="routing-guide"><summary>Inspect a pathway</summary><p>Select a passage, cold-side route, cabinet row, graph node, edge, or opening.</p><p>Tier 1 is solid, Tier 2 dashed, Tier 3 dash-dot.</p></details>;
  if (selection.kind === "cabinet") {
    const cabinet = data.cabinets?.find(c => c.cabinet_uid === selection.uid);
    const row = data.geometry.cabinet_rows.find(r => r.existing_cabinet_uids.includes(selection.uid));
    if (!cabinet || !row) return null;
    const route = data.cross_routes.find(r => r.cabinet_row_uid === row.uid);
    return <div><h3>Cabinet {cabinet.cabinet_id}</h3><dl>{field("Data hall", cabinet.data_hall_id)}{field("Category", cabinet.category)}{field("Group", cabinet.cabinet_group)}{field("Cabinet row", rowName(data, row.uid))}{field("Pair position", row.position_in_pair)}{field("Section", data.sections.find(s => s.uid === row.section_uid)?.name)}</dl>
      <button onClick={() => onSelect({ kind: "row", uid: row.uid })}>Inspect cabinet row</button>
      {route && <button onClick={() => onSelect({ kind: "cross", uid: route.uid })}>Inspect cold-side route</button>}
    </div>;
  }
  if (selection.kind === "passage") {
    const passage = data.geometry.bands.find(b => b.uid === selection.uid);
    if (!passage) return null;
    return <div><h3>{passage.code} passage</h3><dl>{field("Width", formatInches(passage.width_in))}{field("Centerline Y", formatInches(passage.center_in))}{field("Extent", "Continuous through all five sections")}</dl><h4>Explicit pathway tiers</h4><TierEditor kind="passage" owner={passage.uid} records={data.passage_tiers.filter(p => p.passage_band_uid === passage.uid)} mutate={mutate} disabled={!canManage || busy} layout={data.layout} passageCode={passage.code} /></div>;
  }
  if (selection.kind === "cross") {
    const route = data.geometry.cross_routes.find(r => r.uid === selection.uid);
    if (!route) return null;
    return <div><h3>{crossName(route.uid)}</h3><dl>{field("Kind", route.kind)}{field("Station", formatInches(route.station_in))}{field("Station source", route.station_source)}{field("Width", formatInches(route.width_in))}{field("Enabled", route.effective_enabled ? "Yes" : "No")}</dl>
      {route.cabinet_row_uid && <button onClick={() => onSelect({ kind: "row", uid: route.cabinet_row_uid! })}>Inspect associated cabinet row</button>}
      <h4>Explicit pathway tiers</h4><TierEditor kind="cross" owner={route.uid} records={data.cross_route_tiers.filter(t => t.cross_route_uid === route.uid)} mutate={mutate} disabled={!canManage || busy} layout={data.layout} />
      {canManage && <CrossRouteEditor key={route.uid} route={route} mutate={mutate} disabled={busy} />}
    </div>;
  }
  if (selection.kind === "row") {
    const row = data.geometry.cabinet_rows.find(r => r.uid === selection.uid);
    if (!row) return null;
    const pair = data.row_pairs.find(p => p.uid === row.row_pair_uid)!;
    const route = data.cross_routes.find(r => r.cabinet_row_uid === row.uid)!;
    return <div><h3>{rowName(data, row.uid)}</h3><dl>{field("Pair", pair.name ?? pair.ordinal_in_section)}{field("Position", row.position_in_pair)}{field("Section", data.sections.find(s => s.uid === row.section_uid)?.name)}{field("Row field", data.bands.find(b => b.uid === row.row_field_band_uid)?.code)}{field("Cold side", row.position_in_pair === "A" ? "Preceding cold aisle" : "Following cold aisle")}{field("Existing cabinets linked", row.existing_cabinet_uids.length)}{field("Row reference", row.existing_row_reference)}</dl>
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
    return <div><h3>{node.node_type === "JUNCTION" ? "Junction" : "Pathway station"} · Tier {node.tier}</h3><dl>{field("Roles", node.roles.join(", "))}{field("Passage", node.passage_code)}{field("Station", formatInches(node.station_in))}{field("Cross routes", [...new Set(node.cross_route_uids.map(crossName))].join(", ") || "—")}{field("Bundle continuations", node.bundle_connection_uids.length)}</dl><h4>Connected edges</h4><div className="routing-linked-list">{graph.edges.filter(e => e.source_node_id === node.id || e.target_node_id === node.id).map(edge => <button key={edge.id} onClick={() => onSelect({ kind: "edge", uid: edge.id })}>{edge.label ?? edge.edge_type} · {formatInches(edge.planar_length_in)}</button>)}</div>{node.bundle_connection_uids.map(uid => { const c = data.bundle_connections.find(c => c.uid === uid); return c && <p key={uid}>{data.bundle_placements.find(p => p.uid === c.from_placement_uid)?.resolved_label} · {c.from_end} → {c.to_end}{c.vertical_transition_uid ? " · physical opening" : ""}</p>; })}<details><summary>Stable node ID</summary><code>{node.id}</code></details></div>;
  }
  const edge = graph.edges.find(e => e.id === selection.uid);
  if (!edge) return null;
  const a = graph.nodes.find(n => n.id === edge.source_node_id)!, b = graph.nodes.find(n => n.id === edge.target_node_id)!;
  return <div><h3>{edge.edge_type} edge</h3><dl>
    {field("Tier", edge.tier ? `Tier ${edge.tier}` : `Tier ${edge.lower_tier} ↕ Tier ${edge.upper_tier}`)}{field("Pathway type", edge.pathway_type)}
    {edge.cross_route_uid && <>{field("Cross route", crossName(edge.cross_route_uid))}{field("Kind", edge.cross_route_kind)}</>}
    {edge.edge_type === "CROSS_ROUTE" ? <>{field("From passage", a.passage_code)}{field("To passage", b.passage_code)}</> : <>{field("Passage", edge.passage_code)}{field("From station", formatInches(a.station_in))}{field("To station", formatInches(b.station_in))}</>}
    {field("Planar pathway length", formatInches(edge.planar_length_in))}
    {field("Usable", edge.usable ? "Yes" : "No — manually marked unusable")}
    {field("Pathway width", edge.width_in == null ? "Not separately measured" : formatInches(edge.width_in))}
    {field("Bundle occupations", edge.bundle_placement_uids.length)}{field("Cabinet attachments", edge.cabinet_attachment_uids.length)}
    {edge.vertical_transition_uid && <>{field("Opening", data.vertical_transitions.find(v => v.uid === edge.vertical_transition_uid)?.label)}{field("Notes", data.vertical_transitions.find(v => v.uid === edge.vertical_transition_uid)?.notes)}</>}
  </dl><div className="routing-linked-list">
    {edge.cross_route_uid && <button onClick={() => onSelect({ kind: "cross", uid: edge.cross_route_uid! })}>Inspect cross route</button>}
    {edge.vertical_transition_uid && <button onClick={() => onSelect({ kind: "transition", uid: edge.vertical_transition_uid! })}>Inspect physical opening</button>}
    <button onClick={() => onSelect({ kind: "node", uid: a.id })}>Inspect source node</button><button onClick={() => onSelect({ kind: "node", uid: b.id })}>Inspect target node</button>
  </div></div>;
}

import { useEffect, useRef, useState } from "react";
import { routingApi } from "./api";
import { formatInches } from "./dimensions";
import { useRoutingLayout, physicalHallCode } from "./useRoutingLayout";
import { RoutingSchematic } from "./RoutingSchematic";
import { RoutingDetails } from "./RoutingDetails";
import { RoutingConfiguration } from "./RoutingConfiguration";
import { TierVisibility } from "./TierVisibility";
import type { GraphNode, RoutePreview, Selection, Tier } from "./types";
import "./routing.css";

export function RoutingPage({ project, building, hall, canManage }: { project: string; building: string; hall: string; canManage: boolean }) {
  const physicalHall = physicalHallCode(project, hall);
  const { data, graph, loading, busy, error, mutate, initialize, reload } = useRoutingLayout(project, building, physicalHall);
  const [tiers, setTiers] = useState(new Set<Tier>([1, 2, 3]));
  const [selection, setSelection] = useState<Selection>(null);
  const [configure, setConfigure] = useState(false);
  const [routeMode, setRouteMode] = useState(false);
  const [start, setStart] = useState<string | null>(null);
  const [end, setEnd] = useState<string | null>(null);
  const [preview, setPreview] = useState<RoutePreview | null>(null);
  const [routeError, setRouteError] = useState("");
  const [routing, setRouting] = useState(false);
  const requestVersion = useRef(0);
  useEffect(() => { requestVersion.current++; setPreview(null); setStart(null); setEnd(null); setRouteError(""); setRouting(false); }, [data]);
  useEffect(() => { setSelection(null); setConfigure(false); }, [project, building, physicalHall]);
  function clearRoute() { requestVersion.current++; setPreview(null); setStart(null); setEnd(null); setRouteError(""); setRouting(false); }
  async function findRoute(destination: string) {
    if (!start || !data) return;
    const version = ++requestVersion.current;
    setEnd(destination); setRouting(true); setRouteError(""); setPreview(null);
    try {
      const result = await routingApi.preview(data.layout.uid, start, destination);
      if (version !== requestVersion.current) return;
      setPreview(result);
      setTiers(current => new Set([...current, ...result.nodes.map(n => n.tier)]));
    } catch (reason) { if (version === requestVersion.current) setRouteError((reason as Error).message); }
    finally { if (version === requestVersion.current) setRouting(false); }
  }
  function chooseNode(node: GraphNode) {
    setSelection({ kind: "node", uid: node.id });
    if (!routeMode || routing) return;
    if (!start || preview) { clearRoute(); setStart(node.id); }
    else void findRoute(node.id);
  }
  const hiddenRouteTiers = preview && preview.nodes.some(n => !tiers.has(n.tier));
  return <section className="routing-page">
    <div className="routing-heading"><div><span className="eyebrow">Technician routing schematic</span><h2>{project} · {physicalHall}</h2><p>Cold-aisle routes, passage tiers, section gaps and physical openings.</p></div>
      <div className="routing-actions"><button onClick={() => void reload()} disabled={loading || busy}>Refresh</button>{canManage && data && <button className={configure ? "is-active" : ""} onClick={() => { setConfigure(!configure); setSelection(null); }}>Configure routing</button>}</div>
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading && !data ? <div className="routing-empty">Loading routing layout…</div> : !data ? <div className="routing-empty"><h3>{error ? "Routing layout unavailable" : "No routing layout configured"}</h3><p>Existing hall topology is available independently of routing configuration.</p>{canManage && project === "LBB01" && physicalHall === "DH1" && !error && <button disabled={busy} onClick={() => void initialize()}>Initialize LBB01 DH1 routing</button>}</div> : <>
      <div className="routing-toolbar">
        <TierVisibility tiers={tiers} onChange={setTiers} />
        <div className="routing-actions"><button className={routeMode ? "is-active" : ""} onClick={() => { setRouteMode(!routeMode); clearRoute(); }}>Route preview</button><button disabled={!start && !preview} onClick={clearRoute}>Clear route</button><span>{busy || loading ? "Updating…" : `${data.sections.length} sections · ${data.row_pairs.length} pairs · ${data.cabinet_rows.length} rows · ${data.geometry.gaps.length} section gaps`}</span></div>
      </div>
      {!graph.nodes.length && <p className="routing-notice">Pathway tiers are unconfigured. Select Configure routing to enable confirmed tiers and choose ladder rack or basket tray.</p>}
      <div className="routing-workspace">
        <div className="routing-main">
          <RoutingSchematic key={data.layout.uid} data={data} graph={graph} tiers={tiers} selection={selection} onSelect={setSelection} onNode={chooseNode} preview={preview} start={start} routeMode={routeMode} />
          {routeMode && <section className="routing-preview" aria-label="Route preview results">
            <h3>Route preview</h3><p>{routing ? "Finding a configured pathway…" : !start ? "Select a start graph node, then a destination." : !preview ? "Select a destination graph node." : "Highlighted route follows the instructions below."}</p>
            <div className="routing-endpoints">
              <label>Start node<select aria-label="Route start node" value={start ?? ""} onChange={e => { clearRoute(); setStart(e.target.value || null); }} disabled={routing}><option value="">Choose start</option>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.passage_code} · T{n.tier} · {formatInches(n.station_in)} · {n.label ?? (n.cross_route_uid ? "Cross route" : "Passage station")}</option>)}</select></label>
              <label>Destination<select aria-label="Route destination node" value={end ?? ""} onChange={e => { if (e.target.value) void findRoute(e.target.value); }} disabled={!start || routing}><option value="">Choose destination</option>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.passage_code} · T{n.tier} · {formatInches(n.station_in)} · {n.label ?? (n.cross_route_uid ? "Cross route" : "Passage station")}</option>)}</select></label>
            </div>
            {routeError && <p className="routing-error" role="alert">{routeError}</p>}
            {preview && <><div className="routing-result-metrics"><strong>Vertical transitions: {preview.vertical_transition_count}</strong><strong>Planar pathway length: {formatInches(preview.planar_length_in)}</strong></div><ol>{preview.steps.map((step, i) => <li key={i}>{step}</li>)}</ol><p>Vertical openings used: {preview.vertical_opening_labels.join(", ") || "None"}</p>{hiddenRouteTiers && <button onClick={() => setTiers(new Set([...tiers, ...preview.nodes.map(n => n.tier)]))}>Show all tiers used by this route</button>}</>}
          </section>}
          <details className="routing-assumptions"><summary>V1 schematic assumptions</summary><ul><li>NORTH / SOUTH currently use measured 34-in widths; nominal 36-in widths may be confirmed later.</li><li>Cold-route envelopes default to immediately adjacent to each cabinet's cold face. Placement is schematic and configurable.</li><li>Section-gap routes default to the midpoint of the extra 18-ft gap; DERIVED stations are schematic.</li><li>Tier elevations are unknown. Planar pathway length excludes vertical distance, drops and slack.</li></ul></details>
        </div>
        <aside className="routing-side" aria-label="Routing details and configuration">
          {selection ? <><button className="routing-back" onClick={() => setSelection(null)}>Close selection</button><RoutingDetails data={data} graph={graph} selection={selection} onSelect={setSelection} canManage={canManage} busy={busy} mutate={mutate} /></> : configure && canManage ? <RoutingConfiguration data={data} disabled={busy} mutate={mutate} onSelect={setSelection} /> : <RoutingDetails data={data} graph={graph} selection={null} onSelect={setSelection} canManage={canManage} busy={busy} mutate={mutate} />}
        </aside>
      </div>
    </>}
  </section>;
}

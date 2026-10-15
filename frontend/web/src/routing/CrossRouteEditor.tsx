import { useState } from "react";
import type { CrossRoute, Mutate } from "./types";
import { parseInches, formatInches } from "./dimensions";

export function CrossRouteEditor({ route, mutate, disabled }: { route: CrossRoute; mutate: Mutate; disabled: boolean }) {
  const [width, setWidth] = useState(formatInches(route.width_in));
  const [source, setSource] = useState(route.station_source);
  const [station, setStation] = useState(formatInches(route.manual_station_in ?? 0));
  const [label, setLabel] = useState(route.label ?? "");
  const [notes, setNotes] = useState(route.notes ?? "");
  const [enabled, setEnabled] = useState(route.enabled);
  const [error, setError] = useState("");
  return <form className="routing-form" onSubmit={event => {
    event.preventDefault();
    try { void mutate("cross-routes", { width_in: parseInches(width), station_source: source, manual_station_in: source === "DERIVED" ? null : parseInches(station), label: label || null, notes: notes || null, enabled }, route.uid); setError(""); }
    catch (reason) { setError((reason as Error).message); }
  }}>
    <h3>Cross-route placement</h3>
    <label>Route width<input required value={width} onChange={e => setWidth(e.target.value)} /></label>
    <label>Station source<select value={source} onChange={e => setSource(e.target.value as CrossRoute["station_source"])}><option>DERIVED</option><option>MANUAL</option><option>FIELD_MEASURED</option></select></label>
    {source !== "DERIVED" && <label>Station<input required value={station} onChange={e => setStation(e.target.value)} /></label>}
    <label>Label<input value={label} onChange={e => setLabel(e.target.value)} /></label>
    <label>Notes<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label>
    <label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Enabled</label>
    {error && <p role="alert" className="routing-error">{error}</p>}
    <button disabled={disabled}>Save cross route</button>
  </form>;
}

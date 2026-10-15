import { useState } from "react";
import type { Mutate, ResolvedLayout, VerticalTransition } from "./types";
import { formatInches, parseInches } from "./dimensions";

type Props = { data: ResolvedLayout; opening?: VerticalTransition; disabled: boolean; mutate: Mutate; onDone?: () => void };
export function OpeningEditor({ data, opening, disabled, mutate, onDone }: Props) {
  const passages = data.bands.filter(b => b.kind === "PASSAGE").sort((a, b) => a.ordinal - b.ordinal);
  const [passage, setPassage] = useState(opening?.passage_band_uid ?? passages[0].uid);
  const [station, setStation] = useState(formatInches(opening?.station_in ?? 0));
  const [lower, setLower] = useState(opening?.lower_tier ?? 1);
  const [label, setLabel] = useState(opening?.label ?? "");
  const [notes, setNotes] = useState(opening?.notes ?? "");
  const [enabled, setEnabled] = useState(opening?.enabled ?? true);
  const [error, setError] = useState("");
  const [proposed, setProposed] = useState(opening?.station_in ?? 0);
  return <form className="routing-form" onSubmit={async event => {
    event.preventDefault();
    try {
      const station_in = parseInches(station); setError("");
      if (await mutate("vertical-transitions", { passage_band_uid: passage, station_in, lower_tier: lower, upper_tier: lower + 1, label: label || null, notes: notes || null, enabled }, opening?.uid)) {
        if (!opening) { setLabel(""); setNotes(""); }
        onDone?.();
      }
    } catch (reason) { setError((reason as Error).message); }
  }}>
    <h3>{opening ? "Edit physical opening" : "Add physical opening"}</h3>
    <label>Passage<select value={passage} onChange={event => setPassage(event.target.value)}>{passages.map(b => <option key={b.uid} value={b.uid}>{b.code}</option>)}</select></label>
    <label>Station (feet/inches or inches)<input value={station} onChange={event => { setStation(event.target.value); try { setProposed(parseInches(event.target.value)); setError(""); } catch { setProposed(-1); } }} placeholder={'22\'-0"'} required /></label>
    {proposed >= 0 && <small>Proposed station: {formatInches(proposed)} ({proposed} in)</small>}
    <label>Tier pair<select value={lower} onChange={event => setLower(Number(event.target.value) as 1 | 2)}><option value={1}>T1 ↕ T2</option><option value={2}>T2 ↕ T3</option></select></label>
    <label>Opening label<input value={label} onChange={event => setLabel(event.target.value)} placeholder="VT-C-07" /></label>
    <label>Notes<textarea value={notes} onChange={event => setNotes(event.target.value)} /></label>
    <label><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Enabled</label>
    {error && <p role="alert" className="routing-error">{error}</p>}
    <div className="routing-actions"><button disabled={disabled || proposed < 0} type="submit">Save opening</button>{opening && <button disabled={disabled} type="button" onClick={async () => { if (await mutate("vertical-transitions", {}, opening.uid, true)) onDone?.(); }}>Delete opening</button>}</div>
  </form>;
}

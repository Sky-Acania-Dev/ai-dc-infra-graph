import { useState } from "react";
import type { Mutate, ResolvedLayout, Selection } from "./types";
import { LayoutSettings } from "./LayoutSettings";
import { PairEditor, RowEditor } from "./RowEditor";
import { OpeningEditor } from "./OpeningEditor";
import { TierEditor } from "./TierEditor";

export function RoutingConfiguration({ data, disabled, mutate, onSelect }: { data: ResolvedLayout; disabled: boolean; mutate: Mutate; onSelect: (s: Selection) => void }) {
  const [tab, setTab] = useState("pathways");
  const [pair, setPair] = useState("");
  const [row, setRow] = useState("");
  return <div className="routing-configuration">
    <nav className="routing-tabs" aria-label="Routing configuration">
      {[["pathways", "Pathways"], ["rows", "Rows / pairs"], ["openings", "Openings"], ["layout", "Layout"]].map(([key, label]) => <button key={key} className={tab === key ? "is-active" : ""} onClick={() => setTab(key)}>{label}</button>)}
    </nav>
    {tab === "layout" && <LayoutSettings data={data} mutate={mutate} disabled={disabled} />}
    {tab === "rows" && <>
      <label className="routing-select-label">Row pair<select value={pair} onChange={e => setPair(e.target.value)}><option value="">Add a new pair</option>{data.row_pairs.map(p => <option key={p.uid} value={p.uid}>{data.sections.find(s => s.uid === p.routing_section_uid)?.name} · {p.name ?? p.ordinal_in_section}</option>)}</select></label>
      <PairEditor key={pair || "new-pair"} data={data} pair={data.row_pairs.find(p => p.uid === pair)} mutate={mutate} disabled={disabled} />
      <label className="routing-select-label">Cabinet row<select value={row} onChange={e => setRow(e.target.value)}><option value="">Add a new row</option>{data.cabinet_rows.map(r => <option key={r.uid} value={r.uid}>{r.name} · {r.position_in_pair}</option>)}</select></label>
      <RowEditor key={row || "new-row"} data={data} row={data.cabinet_rows.find(r => r.uid === row)} mutate={mutate} disabled={disabled} />
    </>}
    {tab === "openings" && <><div className="routing-linked-list">{data.vertical_transitions.map(v => <button key={v.uid} onClick={() => onSelect({ kind: "transition", uid: v.uid })}>{v.label ?? "Opening"} · T{v.lower_tier} ↕ T{v.upper_tier}{!v.enabled ? " · Disabled" : ""}</button>)}</div><OpeningEditor data={data} disabled={disabled} mutate={mutate} /></>}
    {tab === "pathways" && <>
      <p>Choose a pathway type to configure a tier. Physical tier availability must be confirmed.</p>
      {data.bands.filter(b => b.kind === "PASSAGE").sort((a, b) => a.ordinal - b.ordinal).map(b => <details key={b.uid} open><summary>{b.code} passage</summary><TierEditor kind="passage" owner={b.uid} records={data.passage_tiers.filter(t => t.passage_band_uid === b.uid)} disabled={disabled} mutate={mutate} /></details>)}
      <h3>Cross routes</h3><div className="routing-linked-list">{[...data.cross_routes].sort((a, b) => (a.kind === "SECTION_GAP" ? 0 : 1) - (b.kind === "SECTION_GAP" ? 0 : 1) || (a.label ?? data.cabinet_rows.find(r => r.uid === a.cabinet_row_uid)?.name ?? "").localeCompare(b.label ?? data.cabinet_rows.find(r => r.uid === b.cabinet_row_uid)?.name ?? "", undefined, { numeric: true })).map(r => <button key={r.uid} onClick={() => onSelect({ kind: "cross", uid: r.uid })}>{r.label ?? data.cabinet_rows.find(row => row.uid === r.cabinet_row_uid)?.name} · {r.kind === "SECTION_GAP" ? "Section gap" : "Cold aisle"}</button>)}</div>
    </>}
  </div>;
}

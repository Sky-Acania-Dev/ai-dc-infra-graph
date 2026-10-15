import { useState } from "react";
import type { CabinetRow, Mutate, ResolvedLayout, RowPair } from "./types";
import { formatInches, parseInches } from "./dimensions";

export function PairEditor({ data, pair, disabled, mutate }: { data: ResolvedLayout; pair?: RowPair; disabled: boolean; mutate: Mutate }) {
  const [section, setSection] = useState(pair?.routing_section_uid ?? [...data.sections].sort((a, b) => a.ordinal - b.ordinal)[0].uid);
  const [field, setField] = useState(pair?.row_field_band_uid ?? data.bands.find(b => b.code === "NORTH_FIELD")!.uid);
  const [ordinal, setOrdinal] = useState(pair?.ordinal_in_section ?? 9);
  const [name, setName] = useState(pair?.name ?? "");
  return <form className="routing-form" onSubmit={event => { event.preventDefault(); void mutate("row-pairs", { routing_section_uid: section, row_field_band_uid: field, ordinal_in_section: ordinal, name: name || null }, pair?.uid); }}>
    <h3>{pair ? "Edit row pair" : "Add row pair"}</h3>
    <label>Section<select value={section} onChange={e => setSection(e.target.value)}>{[...data.sections].sort((a, b) => a.ordinal - b.ordinal).map(s => <option key={s.uid} value={s.uid}>{s.name}</option>)}</select></label>
    <label>Row field<select value={field} onChange={e => setField(e.target.value)}>{data.bands.filter(b => b.kind === "ROW_FIELD").map(b => <option key={b.uid} value={b.uid}>{b.code}</option>)}</select></label>
    <label>Ordinal in section<input type="number" min={1} step={1} required value={ordinal} onChange={e => setOrdinal(Number(e.target.value))} /></label>
    <label>Pair name<input value={name} onChange={e => setName(e.target.value)} /></label>
    <div className="routing-actions"><button disabled={disabled}>Save pair</button>{pair && <button type="button" disabled={disabled} onClick={() => void mutate("row-pairs", {}, pair.uid, true)}>Delete pair and its rows</button>}</div>
  </form>;
}

export function RowEditor({ data, row, disabled, mutate }: { data: ResolvedLayout; row?: CabinetRow; disabled: boolean; mutate: Mutate }) {
  const [pair, setPair] = useState(row?.row_pair_uid ?? data.row_pairs[0]?.uid ?? "");
  const [position, setPosition] = useState(row?.position_in_pair ?? "A");
  const [name, setName] = useState(row?.name ?? "");
  const [reference, setReference] = useState(row?.existing_row_reference ?? "");
  const [first, setFirst] = useState(row?.cabinet_number_start?.toString() ?? "");
  const [offset, setOffset] = useState(formatInches(row?.cold_route_face_offset_in ?? 0));
  const [enabled, setEnabled] = useState(row?.enabled ?? true);
  const [error, setError] = useState("");
  return <form className="routing-form" onSubmit={event => {
    event.preventDefault();
    try {
      const cabinet_number_start = first ? Number(first) : null;
      void mutate("cabinet-rows", { row_pair_uid: pair, position_in_pair: position, name, existing_row_reference: reference || null,
        cabinet_number_start, cabinet_number_end: cabinet_number_start === null ? null : cabinet_number_start + data.layout.cabinets_per_row - 1,
        cold_route_face_offset_in: parseInches(offset), enabled }, row?.uid); setError("");
    } catch (reason) { setError((reason as Error).message); }
  }}>
    <h3>{row ? "Edit cabinet row" : "Add cabinet row"}</h3>
    <label>Pair<select value={pair} onChange={e => setPair(e.target.value)}>{data.row_pairs.map(p => <option key={p.uid} value={p.uid}>{data.sections.find(s => s.uid === p.routing_section_uid)?.name} · {p.name ?? p.ordinal_in_section} · {data.bands.find(b => b.uid === p.row_field_band_uid)?.code}</option>)}</select></label>
    <label>Position<select value={position} onChange={e => setPosition(e.target.value as "A" | "B")}><option>A</option><option>B</option></select></label>
    <label>Row name<input required value={name} onChange={e => setName(e.target.value)} /></label>
    <label>Existing row reference<input value={reference} onChange={e => setReference(e.target.value)} /></label>
    <label>First cabinet number (optional)<input type="number" min={1} max={1600} step={1} value={first} onChange={e => setFirst(e.target.value)} /></label>
    <small>{data.layout.cabinets_per_row} cabinets per row · range is linked to existing inventory</small>
    <label>Cold-route face offset<input value={offset} onChange={e => setOffset(e.target.value)} /></label>
    <label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Enabled</label>
    {error && <p className="routing-error" role="alert">{error}</p>}
    <div className="routing-actions"><button disabled={disabled || !pair}>Save row</button>{row && <button type="button" disabled={disabled} onClick={() => void mutate("cabinet-rows", {}, row.uid, true)}>Delete row and cold route</button>}</div>
  </form>;
}

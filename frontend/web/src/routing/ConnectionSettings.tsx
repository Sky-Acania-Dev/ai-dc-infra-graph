import { useState } from "react";
import { DimensionInput } from "./SectionSettings";
import { formatInches, parseInches } from "./dimensions";
import { occupationLabel } from "./occupation";
import type { BundleConnection, CabinetAttachment, Mutate, ResolvedLayout } from "./types";

export function ConnectionSettings({data, mutate, disabled}: {data: ResolvedLayout; mutate: Mutate; disabled: boolean}) {
  const [connectionUid, setConnectionUid] = useState(""), [attachmentUid, setAttachmentUid] = useState("");
  return <>
    <h3>Bundle connections at junctions</h3>
    <p>Connect the ends of two placements for the same group or bundle. START follows increasing passage station or NORTH → SOUTH across a row route.</p>
    <select aria-label="Bundle connection" value={connectionUid} onChange={e => setConnectionUid(e.target.value)}><option value="">Add a connection</option>{data.bundle_connections.map(c => <option key={c.uid} value={c.uid}>{data.bundle_placements.find(p => p.uid === c.from_placement_uid)?.resolved_label} · {c.from_end} → {c.to_end}{!c.enabled ? " · disabled" : ""}</option>)}</select>
    <BundleConnectionForm key={connectionUid || "new"} data={data} record={data.bundle_connections.find(c => c.uid === connectionUid)} mutate={mutate} disabled={disabled} />
    <h3>Cabinet attachments</h3><p>A takeoff along a pathway span. It does not split the graph or add a node.</p>
    <select aria-label="Cabinet attachment" value={attachmentUid} onChange={e => setAttachmentUid(e.target.value)}><option value="">Add an attachment</option>{data.cabinet_attachments.map(a => <option key={a.uid} value={a.uid}>{a.label ?? a.cabinet_uid} · {formatInches(a.offset_in)}{!a.enabled ? " · disabled" : ""}</option>)}</select>
    <CabinetAttachmentForm key={attachmentUid || "new"} data={data} record={data.cabinet_attachments.find(a => a.uid === attachmentUid)} mutate={mutate} disabled={disabled} />
  </>;
}

function BundleConnectionForm({data, record, mutate, disabled}: {data: ResolvedLayout; record?: BundleConnection; mutate: Mutate; disabled: boolean}) {
  const [from, setFrom] = useState(record?.from_placement_uid ?? ""), [to, setTo] = useState(record?.to_placement_uid ?? "");
  const [fromEnd, setFromEnd] = useState(record?.from_end ?? "END"), [toEnd, setToEnd] = useState(record?.to_end ?? "START");
  const [opening, setOpening] = useState(record?.vertical_transition_uid ?? ""), [enabled, setEnabled] = useState(record?.enabled ?? true), [notes, setNotes] = useState(record?.notes ?? "");
  return <form className="routing-form" onSubmit={async e => { e.preventDefault(); await mutate("bundle-connections", {from_placement_uid: from, from_end: fromEnd, to_placement_uid: to, to_end: toEnd, vertical_transition_uid: opening || null, enabled, notes: notes || null}, record?.uid); }}>
    {[["From placement", from, setFrom], ["To placement", to, setTo]].map(([name, value, setter]) => <label key={String(name)}>{String(name)}<select required value={String(value)} onChange={e => (setter as (v: string) => void)(e.target.value)}><option value="">Select a saved placement</option>{data.bundle_placements.map(p => <option key={p.uid} value={p.uid}>{p.resolved_label} · T{p.tier} · {occupationLabel(p)}</option>)}</select></label>)}
    <label>From endpoint<select value={fromEnd} onChange={e => setFromEnd(e.target.value as "START" | "END")}><option>START</option><option>END</option></select></label>
    <label>To endpoint<select value={toEnd} onChange={e => setToEnd(e.target.value as "START" | "END")}><option>START</option><option>END</option></select></label>
    <label>Physical opening (tier change only)<select value={opening} onChange={e => setOpening(e.target.value)}><option value="">Same tier</option>{data.vertical_transitions.map(v => <option key={v.uid} value={v.uid}>{v.label ?? v.uid} · T{v.lower_tier} ↕ T{v.upper_tier}</option>)}</select></label>
    <label>Notes<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label><label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Enabled</label>
    <button disabled={disabled || !from || !to}>{record ? "Save connection" : "Add connection"}</button>{record && <button type="button" disabled={disabled} onClick={() => void mutate("bundle-connections", {}, record.uid, true)}>Delete connection</button>}
  </form>;
}

function CabinetAttachmentForm({data, record, mutate, disabled}: {data: ResolvedLayout; record?: CabinetAttachment; mutate: Mutate; disabled: boolean}) {
  const [span, setSpan] = useState(record?.segment_annotation_uid ?? ""), [cabinet, setCabinet] = useState(record?.cabinet_uid ?? "");
  const [offset, setOffset] = useState(record ? formatInches(record.offset_in) : ""), [tier, setTier] = useState(record?.tier?.toString() ?? "");
  const [label, setLabel] = useState(record?.label ?? ""), [enabled, setEnabled] = useState(record?.enabled ?? true), [error, setError] = useState("");
  return <form className="routing-form" onSubmit={async e => { e.preventDefault(); setError(""); try { await mutate("cabinet-attachments", {segment_annotation_uid: span, cabinet_uid: cabinet, offset_in: parseInches(offset), tier: tier ? Number(tier) : null, label: label || null, enabled}, record?.uid); } catch (reason) { setError(String(reason)); } }}>
    <label>Pathway span<select required value={span} onChange={e => setSpan(e.target.value)}><option value="">Select a saved span</option>{data.segment_annotations.map(a => <option key={a.uid} value={a.uid}>{a.passage_band_uid ? `${data.bands.find(b => b.uid === a.passage_band_uid)?.code} ${formatInches(a.start_station_in!)}–${formatInches(a.end_station_in!)}` : data.geometry.cross_routes.find(r => r.uid === a.cross_route_uid)?.display_label} · {a.tier ? `T${a.tier}` : "all tiers"}</option>)}</select></label>
    <label>Cabinet<select required value={cabinet} onChange={e => setCabinet(e.target.value)}><option value="">Select a cabinet</option>{record && !record.cabinet_available && <option value={record.cabinet_uid}>{record.cabinet_uid} · unavailable</option>}{data.cabinets.map(c => <option key={c.cabinet_uid} value={c.cabinet_uid}>{c.cabinet_id} · {c.data_hall_id}</option>)}</select></label>
    <DimensionInput label="Offset from span START" value={offset} onChange={setOffset} />
    <label>Tier<select value={tier} onChange={e => setTier(e.target.value)}><option value="">Unknown</option>{[1,2,3].map(t => <option key={t} value={t}>T{t}</option>)}</select></label>
    <label>Label<input value={label} onChange={e => setLabel(e.target.value)} /></label><label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Enabled</label>
    <button disabled={disabled || !span || !cabinet}>{record ? "Save attachment" : "Add attachment"}</button>{record && <button type="button" disabled={disabled} onClick={() => void mutate("cabinet-attachments", {}, record.uid, true)}>Delete attachment</button>}{error && <p role="alert">{error}</p>}
  </form>;
}

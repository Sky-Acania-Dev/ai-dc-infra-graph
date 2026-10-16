import { useState } from "react";
import { formatInches, formatMillimeters, parseInches } from "./dimensions";
import type { CardinalDirection, SegmentAnnotation } from "./types";

export function DimensionInput({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  let conversion = "";
  try { if (value.trim()) { const inches = parseInches(value); conversion = `${inches} in · ${formatMillimeters(inches)}`; } } catch { /* Show validation on submission. */ }
  return <label>{label}<input value={value} onChange={e => onChange(e.target.value)} placeholder={`e.g. 6 or 1'-0"`} /><small>{conversion || "Feet/inches or integer inches"}</small></label>;
}

export function SectionSettings({parent, disabled, onSave, passage = true, central = false}: {parent?: SegmentAnnotation; disabled: boolean; onSave: (values: object) => Promise<boolean>; passage?: boolean; central?: boolean}) {
  const [columns, setColumns] = useState(parent?.grid_columns ?? 12), [rows, setRows] = useState(parent?.grid_rows ?? 8);
  const [height, setHeight] = useState(parent?.section_height_in == null ? "" : formatInches(parent.section_height_in));
  const [reference, setReference] = useState(parent?.section_reference ?? ""), [error, setError] = useState("");
  const [inner, setInner] = useState<CardinalDirection | "">(parent?.section_inner_direction ?? "");
  return <form className="routing-form" onSubmit={async e => { e.preventDefault(); setError(""); try { await onSave({grid_columns: columns, grid_rows: rows, section_height_in: height.trim() ? parseInches(height) : null, section_reference: reference.trim() || null, section_inner_direction: central ? null : inner || null}); } catch (reason) { setError(String(reason)); } }}>
    <label>Section viewing reference<input value={reference} onChange={e => setReference(e.target.value)} placeholder={central ? "North/South section viewing notes" : "Inner faces cabinets / hot aisle"} /></label>
    {central ? <small>CENTRAL uses North/South section sides; it has no inner side.</small> : <label>Inner side toward cabinets / hot aisle<select value={inner} onChange={e => setInner(e.target.value as CardinalDirection | "")}><option value="">Use pathway geometry</option>{(passage ? ["NORTH", "SOUTH"] : ["EAST", "WEST"]).map(d => <option key={d} value={d}>{d}</option>)}</select></label>}
    <div className="section-slot-inputs"><label>Grid width (columns)<input type="number" min={1} max={64} value={columns} onChange={e => setColumns(Number(e.target.value))} /></label><label>Grid height (layers)<input type="number" min={1} max={64} value={rows} onChange={e => setRows(Number(e.target.value))} /></label></div>
    <DimensionInput label="Section height above tray bed (optional)" value={height} onChange={setHeight} />
    <button disabled={disabled}>{parent ? "Save section definition" : "Create section definition"}</button>
    {error && <p role="alert">{error}</p>}
  </form>;
}

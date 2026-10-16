import { useState } from "react";
import { formatInches, formatMillimeters, parseInches } from "./dimensions";
import type { SegmentAnnotation } from "./types";

export function DimensionInput({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  let conversion = "";
  try { if (value.trim()) { const inches = parseInches(value); conversion = `${inches} in · ${formatMillimeters(inches)}`; } } catch { /* Show validation on submission. */ }
  return <label>{label}<input value={value} onChange={e => onChange(e.target.value)} placeholder={`e.g. 6 or 1'-0"`} /><small>{conversion || "Feet/inches or integer inches"}</small></label>;
}

export function SectionSettings({parent, disabled, onSave}: {parent?: SegmentAnnotation; disabled: boolean; onSave: (values: object) => Promise<boolean>}) {
  const [columns, setColumns] = useState(parent?.grid_columns ?? 12), [rows, setRows] = useState(parent?.grid_rows ?? 8);
  const [height, setHeight] = useState(parent?.section_height_in == null ? "" : formatInches(parent.section_height_in));
  const [reference, setReference] = useState(parent?.section_reference ?? ""), [error, setError] = useState("");
  return <form className="routing-form" onSubmit={async e => { e.preventDefault(); setError(""); try { await onSave({grid_columns: columns, grid_rows: rows, section_height_in: height.trim() ? parseInches(height) : null, section_reference: reference.trim() || null}); } catch (reason) { setError(String(reason)); } }}>
    <label>Section viewing / inner-side reference<input value={reference} onChange={e => setReference(e.target.value)} placeholder="Define which side is inner and viewing direction" /></label>
    <div className="section-slot-inputs"><label>Grid width (columns)<input type="number" min={1} max={64} value={columns} onChange={e => setColumns(Number(e.target.value))} /></label><label>Grid height (layers)<input type="number" min={1} max={64} value={rows} onChange={e => setRows(Number(e.target.value))} /></label></div>
    <DimensionInput label="Section height above tray bed (optional)" value={height} onChange={setHeight} />
    <button disabled={disabled}>{parent ? "Save section definition" : "Create section definition"}</button>
    {error && <p role="alert">{error}</p>}
  </form>;
}

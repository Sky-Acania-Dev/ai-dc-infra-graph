import { useEffect, useState } from "react";
import { routingApi } from "./api";
import { annotationFor, type ConceptualSegment } from "./conceptualSegments";
import { CABLE_STYLES } from "./RouteStroke";
import { formatInches, parseInches } from "./dimensions";
import { DimensionInput, SectionSettings } from "./SectionSettings";
import type { BundlePlacement, CableClass, Mutate, PlacementSource, ResolvedLayout, Tier } from "./types";

export function BundleSectionEditor({ data, segment, mutate, busy, placement }: { data: ResolvedLayout; segment: ConceptualSegment; mutate: Mutate; busy: boolean; placement?: BundlePlacement }) {
  const tiers = segment.passage_band_uid ? data.passage_tiers.filter(t => t.passage_band_uid === segment.passage_band_uid && t.enabled) : data.cross_route_tiers.filter(t => t.cross_route_uid === segment.cross_route_uid && t.enabled);
  const [tier, setTier] = useState<Tier>(placement?.tier ?? tiers[0]?.tier ?? 1);
  const parent = annotationFor(data, segment, tier) ?? annotationFor(data, segment, null);
  const central = data.bands?.find(b => b.uid === segment.passage_band_uid)?.code === "CENTRAL";
  const [label, setLabel] = useState(placement?.label ?? "");
  const [layer, setLayer] = useState(placement?.layer ?? 1), [position, setPosition] = useState(placement?.position ?? 1);
  const [slotWidth, setSlotWidth] = useState(placement?.slot_width ?? 1), [slotHeight, setSlotHeight] = useState(placement?.slot_height ?? 1);
  const [mode, setMode] = useState(placement?.offset_across_in != null ? placement.layer != null ? "BOTH" : "RECTANGLE" : "SLOTS");
  const [rectangle, setRectangle] = useState({ offset_across_in: placement?.offset_across_in == null ? "0" : formatInches(placement.offset_across_in), offset_up_in: placement?.offset_up_in == null ? "0" : formatInches(placement.offset_up_in), occupied_width_in: placement?.occupied_width_in == null ? "" : formatInches(placement.occupied_width_in), occupied_height_in: placement?.occupied_height_in == null ? "" : formatInches(placement.occupied_height_in) });
  const [source, setSource] = useState(placement?.source_uid ? `${placement.source_kind}:${placement.source_uid}` : "MANUAL");
  const [cableClass, setCableClass] = useState(placement?.cable_class ?? "");
  const [enabled, setEnabled] = useState(placement?.enabled ?? true);
  const [sources, setSources] = useState<PlacementSource[]>([]), [error, setError] = useState("");
  useEffect(() => { const controller = new AbortController(); void routingApi.placementSources(data.layout.uid, controller.signal).then(values => { setSources(values); setError(""); }).catch(e => { if (!controller.signal.aborted) setError(String(e)); }); return () => controller.abort(); }, [data.layout.uid]);
  const span = { passage_band_uid: segment.passage_band_uid, cross_route_uid: segment.cross_route_uid, start_station_in: segment.start_station_in,
    end_station_in: segment.end_station_in, from_passage_band_uid: segment.from_passage_band_uid, to_passage_band_uid: segment.to_passage_band_uid };
  return <div className="bundle-section-editor">
    <label>Tier<select value={tier} disabled={busy || Boolean(placement)} onChange={e => setTier(Number(e.target.value) as Tier)}>{tiers.map(t => <option key={t.uid} value={t.tier}>T{t.tier}</option>)}</select></label>
    {!tiers.length && <p className="routing-notice">Configure a confirmed pathway tier first.</p>}
    <SectionSettings key={`${parent?.uid}:${parent?.updated_at}`} parent={parent} passage={Boolean(segment.passage_band_uid)} central={central} disabled={busy || !tiers.length || Boolean(segment.passage_band_uid && segment.start_station_in === segment.end_station_in)} onSave={values => mutate("segment-annotations", { ...(parent ? {} : {...span, tier}), ...values }, parent?.uid)} />
    {parent && <>
      <form className="routing-form" onSubmit={async e => {
        e.preventDefault(); setError("");
        try {
        const entry = sources.find(s => `${s.kind}:${s.uid}` === source);
        if (source !== "MANUAL" && !entry && !placement) { setError("Select an available source."); return; }
        const box = Object.fromEntries(Object.entries(rectangle).map(([key, value]) => [key, mode === "SLOTS" ? null : parseInches(value)]));
        await mutate("bundle-placements", { segment_annotation_uid: parent.uid, tier, layer: mode === "RECTANGLE" ? null : layer, position: mode === "RECTANGLE" ? null : position, slot_width: mode === "RECTANGLE" ? null : slotWidth, slot_height: mode === "RECTANGLE" ? null : slotHeight, ...box,
          source_kind: source === "MANUAL" ? "MANUAL" : entry?.kind ?? placement?.source_kind,
          source_uid: source === "MANUAL" ? null : entry?.uid ?? placement?.source_uid, label: label.trim() || null, cable_class: cableClass || null, enabled }, placement?.uid);
        } catch (reason) { setError(String(reason)); }
      }}>
        <label>Group / bundle<select value={source} onChange={e => setSource(e.target.value)}><option value="MANUAL">Manual bundle label</option>{placement?.source_uid && !sources.some(s => s.kind === placement.source_kind && s.uid === placement.source_uid) && <option value={`${placement.source_kind}:${placement.source_uid}`}>{placement.source_uid} · source unavailable</option>}{sources.map(s => <option key={`${s.kind}:${s.uid}`} value={`${s.kind}:${s.uid}`}>{s.kind}: {s.name}</option>)}</select></label>
        <label>{source === "MANUAL" ? "Bundle label" : "Optional display label"}<input required={source === "MANUAL"} value={label} onChange={e => setLabel(e.target.value)} /></label>
        <label>Cable type<select value={cableClass} onChange={e => setCableClass(e.target.value as CableClass)}><option value="">Unspecified</option>{Object.entries(CABLE_STYLES).map(([key, style]) => <option key={key} value={key}>{style.label}</option>)}</select></label>
        <label>Occupation representation<select value={mode} onChange={e => setMode(e.target.value)}><option value="SLOTS">Grid slots</option><option value="RECTANGLE">Physical rectangle</option><option value="BOTH">Grid + rectangle</option></select></label>
        {mode !== "RECTANGLE" && <div className="section-slot-inputs"><label>Layer (bottom = 1)<input type="number" min={1} max={parent.grid_rows} value={layer} onChange={e => setLayer(Number(e.target.value))} /></label><label>{central ? "Position (North edge = 1)" : "Position (inner = 1)"}<input type="number" min={1} max={parent.grid_columns} value={position} onChange={e => setPosition(Number(e.target.value))} /></label><label>Width in cells<input type="number" min={1} max={parent.grid_columns} value={slotWidth} onChange={e => setSlotWidth(Number(e.target.value))} /></label><label>Height in cells<input type="number" min={1} max={parent.grid_rows} value={slotHeight} onChange={e => setSlotHeight(Number(e.target.value))} /></label></div>}
        {mode !== "SLOTS" && <fieldset><legend>Section rectangle · integer inches</legend>{Object.entries({offset_across_in: central ? "Across offset from North edge" : "Across offset from inner edge", offset_up_in: "Up offset above tray bed", occupied_width_in: "Occupied width", occupied_height_in: "Occupied height"}).map(([key, name]) => <DimensionInput key={key} label={name} value={rectangle[key as keyof typeof rectangle]} onChange={value => setRectangle(current => ({...current, [key]: value}))} />)}<small>Section offsets are separate from elevation above finished floor.</small></fieldset>}
        {mode === "BOTH" && <small>Grid cells are ordinal. Grid and physical rectangles are recorded independently; changing grid size does not rescale inches.</small>}
        <label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Enabled</label>
        <button disabled={busy || !tiers.length}>{placement ? "Save bundle placement" : "Add bundle placement"}</button>
        {placement && <button type="button" disabled={busy} onClick={() => void mutate("bundle-placements", {}, placement.uid, true)}>Delete placement</button>}
      </form>
    </>}
    {error && <p className="routing-error" role="alert">{error}</p>}
  </div>;
}

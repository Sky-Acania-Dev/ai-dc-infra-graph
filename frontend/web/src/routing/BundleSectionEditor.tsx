import { useEffect, useState } from "react";
import { routingApi } from "./api";
import { annotationFor, type ConceptualSegment } from "./conceptualSegments";
import { CABLE_STYLES } from "./RouteStroke";
import type { BundlePlacement, CableClass, Mutate, PlacementSource, ResolvedLayout, Tier } from "./types";

export function BundleSectionEditor({ data, segment, mutate, busy, placement }: { data: ResolvedLayout; segment: ConceptualSegment; mutate: Mutate; busy: boolean; placement?: BundlePlacement }) {
  const tiers = segment.passage_band_uid ? data.passage_tiers.filter(t => t.passage_band_uid === segment.passage_band_uid && t.enabled) : data.cross_route_tiers.filter(t => t.cross_route_uid === segment.cross_route_uid && t.enabled);
  const [tier, setTier] = useState<Tier>(placement?.tier ?? tiers[0]?.tier ?? 1);
  const parent = annotationFor(data, segment, tier) ?? annotationFor(data, segment, null);
  const [reference, setReference] = useState(parent?.section_reference ?? "");
  const [label, setLabel] = useState(placement?.label ?? "");
  const [layer, setLayer] = useState(placement?.layer ?? 1), [position, setPosition] = useState(placement?.position ?? 1);
  const [source, setSource] = useState(placement?.source_uid ? `${placement.source_kind}:${placement.source_uid}` : "MANUAL");
  const [cableClass, setCableClass] = useState(placement?.cable_class ?? "");
  const [enabled, setEnabled] = useState(placement?.enabled ?? true);
  const [sources, setSources] = useState<PlacementSource[]>([]), [error, setError] = useState("");
  useEffect(() => { const controller = new AbortController(); void routingApi.placementSources(data.layout.uid, controller.signal).then(values => { setSources(values); setError(""); }).catch(e => { if (!controller.signal.aborted) setError(String(e)); }); return () => controller.abort(); }, [data.layout.uid]);
  useEffect(() => setReference(parent?.section_reference ?? ""), [parent?.uid]);
  const span = { passage_band_uid: segment.passage_band_uid, cross_route_uid: segment.cross_route_uid, start_station_in: segment.start_station_in,
    end_station_in: segment.end_station_in, from_passage_band_uid: segment.from_passage_band_uid, to_passage_band_uid: segment.to_passage_band_uid };
  return <div className="bundle-section-editor">
    <label>Tier<select value={tier} disabled={busy || Boolean(placement)} onChange={e => setTier(Number(e.target.value) as Tier)}>{tiers.map(t => <option key={t.uid} value={t.tier}>T{t.tier}</option>)}</select></label>
    {!tiers.length && <p className="routing-notice">Configure a confirmed pathway tier first. Demo tiers are never saved automatically.</p>}
    <label>Section viewing / inner-side reference<input value={reference} onChange={e => setReference(e.target.value)} placeholder="e.g. inner toward CENTRAL; viewed in increasing row order" /></label>
    {!parent ? <button disabled={busy || !tiers.length || segment.start_station_in === segment.end_station_in && Boolean(segment.passage_band_uid)} onClick={() => void mutate("segment-annotations", { ...span, tier, section_reference: reference.trim() || null })}>Create section definition</button> : <>
      <button disabled={busy} onClick={() => void mutate("segment-annotations", { section_reference: reference.trim() || null }, parent.uid)}>Save viewing reference</button>
      <form className="routing-form" onSubmit={async e => {
        e.preventDefault(); setError("");
        const entry = sources.find(s => `${s.kind}:${s.uid}` === source);
        if (source !== "MANUAL" && !entry && !placement) { setError("Select an available source."); return; }
        await mutate("bundle-placements", { segment_annotation_uid: parent.uid, tier, layer, position,
          source_kind: source === "MANUAL" ? "MANUAL" : entry?.kind ?? placement?.source_kind,
          source_uid: source === "MANUAL" ? null : entry?.uid ?? placement?.source_uid, label: label.trim() || null, cable_class: cableClass || null, enabled }, placement?.uid);
      }}>
        <label>Group / bundle<select value={source} onChange={e => setSource(e.target.value)}><option value="MANUAL">Manual bundle label</option>{placement?.source_uid && !sources.some(s => s.kind === placement.source_kind && s.uid === placement.source_uid) && <option value={`${placement.source_kind}:${placement.source_uid}`}>{placement.source_uid} · source unavailable</option>}{sources.map(s => <option key={`${s.kind}:${s.uid}`} value={`${s.kind}:${s.uid}`}>{s.kind}: {s.name}</option>)}</select></label>
        <label>{source === "MANUAL" ? "Bundle label" : "Optional display label"}<input required={source === "MANUAL"} value={label} onChange={e => setLabel(e.target.value)} /></label>
        <label>Cable type<select value={cableClass} onChange={e => setCableClass(e.target.value as CableClass)}><option value="">Unspecified</option>{Object.entries(CABLE_STYLES).map(([key, style]) => <option key={key} value={key}>{style.label}</option>)}</select></label>
        <div className="section-slot-inputs"><label>Layer (bottom = 1)<input type="number" min={1} max={64} value={layer} onChange={e => setLayer(Number(e.target.value))} /></label><label>Position (inner = 1)<input type="number" min={1} max={64} value={position} onChange={e => setPosition(Number(e.target.value))} /></label></div>
        <label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Enabled</label>
        <button disabled={busy || !tiers.length}>{placement ? "Save bundle placement" : "Add bundle placement"}</button>
        {placement && <button type="button" disabled={busy} onClick={() => void mutate("bundle-placements", {}, placement.uid, true)}>Delete placement</button>}
      </form>
    </>}
    {error && <p className="routing-error" role="alert">{error}</p>}
  </div>;
}

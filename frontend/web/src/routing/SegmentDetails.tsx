import { useState } from "react";
import { annotationFor, type ConceptualSegment } from "./conceptualSegments";
import { formatInches } from "./dimensions";
import { CABLE_STYLES } from "./RouteStroke";
import type { CableClass, Mutate, ResolvedLayout, Tier } from "./types";

export function SegmentDetails({ data, segment, tier = null, canManage, busy, mutate }: {
  data: ResolvedLayout; segment: ConceptualSegment; tier?: Tier | null; canManage: boolean; busy: boolean; mutate: Mutate;
}) {
  const annotation = annotationFor(data, segment, tier) ?? (tier ? annotationFor(data, segment, null) : undefined);
  const scopeTier = annotation ? annotation.tier : tier;
  const [usable, setUsable] = useState(annotation?.usable ?? true);
  const [classes, setClasses] = useState<CableClass[]>(annotation?.cable_classes ?? []);
  const [notes, setNotes] = useState(annotation?.notes ?? "");
  const band = (uid: string | null) => data.bands.find(b => b.uid === uid)?.code;
  const crossRoute = data.geometry.cross_routes.find(r => r.uid === segment.cross_route_uid);
  return <div>
    <h3>{segment.label}</h3>
    <dl>
      <div><dt>Marking scope</dt><dd>{scopeTier ? `Tier ${scopeTier}` : "All configured tiers"}</dd></div>
      <div><dt>Span</dt><dd>{segment.passage_band_uid ? `${formatInches(segment.start_station_in!)} → ${formatInches(segment.end_station_in!)}` : `${band(segment.from_passage_band_uid)} → ${band(segment.to_passage_band_uid)}`}</dd></div>
      <div><dt>Planar pathway length</dt><dd>{formatInches(segment.planar_length_in)}</dd></div>
      <div><dt>Pathway width</dt><dd>{formatInches(segment.width_in)}</dd></div>
      {crossRoute && <><div><dt>Station</dt><dd>{formatInches(crossRoute.station_in)}</dd></div><div><dt>Station source</dt><dd>{crossRoute.station_source}</dd></div></>}
      <div><dt>Saved marking</dt><dd>{annotation ? "Manual" : "Empty / unassigned"}</dd></div>
      <div><dt>Usable</dt><dd>{annotation?.usable === false ? "No" : "Yes"}</dd></div>
      <div><dt>Designed cable types</dt><dd>{annotation?.cable_classes.length ? annotation.cable_classes.map(c => CABLE_STYLES[c].label).join(", ") : "Unassigned"}</dd></div>
      {annotation?.notes && <div><dt>Notes</dt><dd>{annotation.notes}</dd></div>}
    </dl>
    {canManage ? <details className="routing-marking-editor"><summary>Edit segment markings</summary><form className="routing-form" onSubmit={async event => {
      event.preventDefault();
      const span = annotation ?? segment;
      await mutate("segment-annotations", { passage_band_uid: span.passage_band_uid, cross_route_uid: span.cross_route_uid,
        start_station_in: span.start_station_in, end_station_in: span.end_station_in,
        from_passage_band_uid: span.from_passage_band_uid, to_passage_band_uid: span.to_passage_band_uid,
        tier: scopeTier, usable, cable_classes: classes, notes: notes || null }, annotation?.uid);
    }}>
      <label><input type="checkbox" checked={!usable} onChange={event => setUsable(!event.target.checked)} />Unusable segment</label>
      <fieldset disabled={busy}><legend>Designed cable types (manual)</legend>{Object.entries(CABLE_STYLES).map(([key, style]) => <label key={key}>
        <input type="checkbox" checked={classes.includes(key as CableClass)} onChange={event => setClasses(current => event.target.checked ? [...current, key as CableClass] : current.filter(c => c !== key))} />{style.label}
      </label>)}</fieldset>
      <label>Notes<textarea value={notes} onChange={event => setNotes(event.target.value)} /></label>
      <small>Markings describe design intent. They do not create tier pathways or assign inventory cables.</small>
      {annotation && (annotation.start_station_in !== segment.start_station_in || annotation.end_station_in !== segment.end_station_in) && <small>This marking covers a larger passage span; editing applies to that entire span.</small>}
      <button disabled={busy} type="submit">Save segment marking</button>
      {annotation && <button disabled={busy} type="button" onClick={() => void mutate("segment-annotations", {}, annotation.uid, true)}>Clear marking</button>}
    </form></details> : <p>Sign in as a manager to change segment markings.</p>}
  </div>;
}

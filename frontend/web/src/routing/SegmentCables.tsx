import type { FixtureCable } from "./cabinetFixtureRun";
import type { CableClass, InventoryCable } from "./types";
import { CABLE_STYLES } from "./RouteStroke";
import { filterCableMembers } from "./segmentCableMembers";

type Props = {
  cables: FixtureCable[]; inventoryCables?: InventoryCable[]; members?: Record<string, string[]>;
  selectedCableId: string | null; onSelect: (id: string | null) => void; routeLabel?: string;
  bundleFilter?: {uid: string; label: string; fixtureCableIds?: string[]} | null; onClearFilter?: () => void; loading?: boolean; error?: string;
};
export function SegmentCables({cables, inventoryCables = [], members = {}, selectedCableId, onSelect, routeLabel, bundleFilter, onClearFilter, loading, error}: Props) {
  const all = [
    ...inventoryCables.map(c => ({id: c.uid, type: c.cable_type, source: c.source_cabinet_id ?? "Unknown", destination: c.destination_cabinet_id ?? "Unknown", sourcePort: c.source_port_name, destinationPort: c.destination_port_name, sourceLabel: c.source_label, destinationLabel: c.destination_label, notes: c.notes, demo: false})),
    ...cables.map(c => ({id: c.id, type: c.cableClass, source: c.sourceCabinetId, destination: c.destinationCabinetId, sourcePort: null, destinationPort: null, sourceLabel: "", destinationLabel: "", notes: "", demo: true})),
  ];
  const visible = filterCableMembers(all, bundleFilter?.uid ?? null, members, bundleFilter?.fixtureCableIds);
  const summary = new Map<string, {type: string; source: string; destination: string; count: number}>();
  visible.forEach(c => {const key = JSON.stringify([c.type, c.source, c.destination]); const item = summary.get(key); if (item) item.count++; else summary.set(key, {...c, count: 1});});
  return <section className="segment-cables" aria-label="Cables on selected segment">
    <h3>{visible.length} {visible.length && visible.every(c => c.demo) ? "fixture " : ""}cable{visible.length === 1 ? "" : "s"}{bundleFilter ? " in group" : ""}</h3>
    {bundleFilter && <div className="segment-bundle-filter"><b>{bundleFilter.label}</b><button onClick={onClearFilter}>Show all segment cables</button></div>}
    {loading && <p role="status">Loading cable membership…</p>}
    {error && <p role="alert" className="routing-error">{error}</p>}
    {visible.some(c => c.demo) && <p className="conceptual-fixture-notice">Display-only review cables · 021 → 031. Device ports and actual routing tiers remain unassigned.</p>}
    {!!visible.length && <ul className="segment-cable-summary" aria-label="Cable type, count and rack-pair summary">{[...summary].map(([key, s]) => <li key={key}>{CABLE_STYLES[s.type as CableClass]?.label ?? s.type} × {s.count} · {s.source} → {s.destination}</li>)}</ul>}
    <div className="segment-cable-list">{visible.map(cable => {
      const style = CABLE_STYLES[cable.type as CableClass];
      return <button key={cable.id} className={`segment-cable-card ${selectedCableId === cable.id ? "is-selected" : ""}`} style={{borderLeftColor: style?.color ?? "#64748b"}}
        aria-label={`Inspect ${style?.label ?? cable.type} ${cable.demo ? "fixture " : ""}cable ${cable.source} to ${cable.destination}`} aria-pressed={selectedCableId === cable.id} onClick={() => onSelect(selectedCableId === cable.id ? null : cable.id)}>
        <strong>{style?.label ?? cable.type}</strong><span>{cable.source} → {cable.destination}</span>
        <small>{cable.id}</small><small>Source: Cabinet {cable.source} · {cable.sourcePort ?? "Port unassigned"}</small>
        <small>Destination: Cabinet {cable.destination} · {cable.destinationPort ?? "Port unassigned"}</small>
        {cable.sourceLabel && <small>A label: {cable.sourceLabel}</small>}{cable.destinationLabel && <small>Z label: {cable.destinationLabel}</small>}{cable.notes && <small>{cable.notes}</small>}
      </button>;
    })}</div>
    {!visible.length && !loading && <p className="routing-notice">{bundleFilter ? "No actual cable members linked to this group. Manual labels do not imply cable membership." : "No endpoint cable assignments on this segment. Style color samples are separate from inventory cables."}</p>}
    {visible.some(c => c.demo) && <><p className="routing-notice">Select a fixture cable to highlight its entire sample run. Fixtures never change inventory or saved routing data.</p><p className="routing-notice">Sample route: {routeLabel ?? "Row 3 → Central R3–4 → Row 4"}.</p></>}
  </section>;
}

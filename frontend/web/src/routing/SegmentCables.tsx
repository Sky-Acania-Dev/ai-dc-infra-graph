import type { FixtureCable } from "./cabinetFixtureRun";
import { CABLE_STYLES } from "./RouteStroke";

export function SegmentCables({ cables, selectedCableId, onSelect, routeLabel }: { cables: FixtureCable[]; selectedCableId: string | null; onSelect: (id: string | null) => void; routeLabel?: string }) {
  return <section className="segment-cables" aria-label="Cables on selected segment">
    <h3>{cables.length} fixture cables</h3>
    {cables.length ? <>
      <p className="conceptual-fixture-notice">Fake review cables · 021 → 031. Cabinet attachments are schematic. Tiers and device ports are unassigned.</p>
      <div className="segment-cable-list">{cables.map(cable => {
        const style = CABLE_STYLES[cable.cableClass];
        return <button key={cable.id} className={`segment-cable-card ${selectedCableId === cable.id ? "is-selected" : ""}`} style={{ borderLeftColor: style.color }}
          aria-label={`Inspect ${style.label} fixture cable 021 to 031`} aria-pressed={selectedCableId === cable.id} onClick={() => onSelect(selectedCableId === cable.id ? null : cable.id)}>
          <strong>{style.label}</strong><span>{cable.sourceCabinetId} → {cable.destinationCabinetId}</span>
          <small>{cable.id}</small><small>Source: Cabinet {cable.sourceCabinetId} · Port unassigned</small>
          <small>Destination: Cabinet {cable.destinationCabinetId} · Port unassigned</small>
        </button>;
      })}</div>
      <p className="routing-notice">Select a cable to highlight its entire sample run. These fixtures do not change inventory or saved routing data.</p>
      <p className="routing-notice">Sample route: {routeLabel ?? "Row 3 → Central R3–4 → Row 4"}.</p>
    </> : <p className="routing-notice">No endpoint cable assignments on this segment. Style color samples are separate from inventory cables.</p>}
  </section>;
}

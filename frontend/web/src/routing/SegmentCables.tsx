import { useState } from "react";
import { ConnectionCard } from "../components/ConnectionCard";
import type { FixtureCable } from "./cabinetFixtureRun";
import type { CableClass, InventoryCable } from "./types";
import { CABLE_STYLES } from "./RouteStroke";
import { filterCableMembers } from "./segmentCableMembers";

type Props = {
  cables: FixtureCable[]; inventoryCables?: InventoryCable[]; members?: Record<string, string[]>;
  selectedCableId: string | null; onSelect: (id: string | null) => void; routeLabel?: string;
  bundleFilter?: {uid: string; label: string; fixtureCableIds?: string[]} | null;
  onClearFilter?: () => void; loading?: boolean; error?: string; autoShowCables?: boolean;
};
type CableItem = {
  id: string; type: string; color: string; source: string; destination: string;
  sourcePort: string | null; destinationPort: string | null;
  sourceLabel: string; destinationLabel: string; notes: string; demo: boolean;
};
type Pair = {key: string; label: string; cables: CableItem[]};
const PAGE_SIZE = 60;
const compare = (a: string, b: string) => a.localeCompare(b, undefined, {numeric: true});

export function SegmentCables({cables, inventoryCables = [], members = {}, selectedCableId, onSelect, routeLabel, bundleFilter, onClearFilter, loading, error, autoShowCables}: Props) {
  const all: CableItem[] = [
    ...inventoryCables.map(c => ({id: c.uid, type: c.cable_type, color: CABLE_STYLES[c.cable_class as CableClass]?.color ?? "#64748b", source: c.source_cabinet_id ?? "Unknown", destination: c.destination_cabinet_id ?? "Unknown", sourcePort: c.source_port_name, destinationPort: c.destination_port_name, sourceLabel: c.source_label, destinationLabel: c.destination_label, notes: c.notes, demo: false})),
    ...cables.map(c => ({id: c.id, type: CABLE_STYLES[c.cableClass].label, color: CABLE_STYLES[c.cableClass].color, source: c.sourceCabinetId, destination: c.destinationCabinetId, sourcePort: null, destinationPort: null, sourceLabel: "", destinationLabel: "", notes: "", demo: true})),
  ];
  const visible = filterCableMembers(all, bundleFilter?.uid ?? null, members, bundleFilter?.fixtureCableIds)
    .sort((a, b) => compare(a.type, b.type) || compare(a.id, b.id));
  // Reset disclosure/page state when membership changes, not when a cable is selected.
  const scope = JSON.stringify([bundleFilter?.uid, Boolean(autoShowCables), visible.map(c => c.id)]);
  return <section className="segment-cables" aria-label="Cables on selected segment">
    {bundleFilter && <div className="segment-bundle-filter"><b>{bundleFilter.label}</b><button className="expand-button" onClick={onClearFilter}>Show all segment cables</button></div>}
    {loading && <p role="status">Loading cable membership…</p>}
    {error && <p role="alert" className="routing-error">{error}</p>}
    {visible.some(c => c.demo) && <p className="conceptual-fixture-notice">Display-only review cables · 021 → 031. Device ports and actual routing tiers remain unassigned.</p>}
    <SegmentCableContent key={scope} cables={visible} selectedCableId={selectedCableId} onSelect={onSelect}
      filtered={Boolean(bundleFilter)} autoShowCables={autoShowCables || Boolean(bundleFilter)} />
    {!visible.length && !loading && <p className="routing-notice">{bundleFilter ? "No actual cable members linked to this group. Manual labels do not imply cable membership." : "No endpoint cable assignments on this segment. Style color samples are separate from inventory cables."}</p>}
    {visible.some(c => c.demo) && <p className="routing-notice">Select a fixture cable to highlight its sample run. Sample route: {routeLabel ?? "Row 3 → Central R3–4 → Row 4"}. Fixtures never change inventory or saved routing data.</p>}
  </section>;
}

function typeCounts(cables: CableItem[]) {
  const counts: Record<string, number> = Object.create(null);
  for (const cable of cables) counts[cable.type] = (counts[cable.type] ?? 0) + 1;
  return counts;
}

function SegmentCableContent({cables, selectedCableId, onSelect, filtered, autoShowCables}: {
  cables: CableItem[]; selectedCableId: string | null; onSelect: Props["onSelect"]; filtered: boolean; autoShowCables?: boolean;
}) {
  const [openList, setOpenList] = useState<string | null>(autoShowCables ? "all" : null);
  const [showPairs, setShowPairs] = useState(false);
  const pairs = new Map<string, Pair>();
  for (const cable of cables) {
    // A/Z direction belongs to each cable; combine both directions in rack-pair summaries.
    const ends = [cable.source, cable.destination].sort(compare);
    const key = JSON.stringify(ends);
    if (!pairs.has(key)) pairs.set(key, {key, label: ends.join(" ↔ "), cables: []});
    pairs.get(key)!.cables.push(cable);
  }
  const orderedPairs = [...pairs.values()].sort((a, b) => compare(a.label, b.label));
  const metric = (items: CableItem[]) => <span>{items.length.toLocaleString()} {items.length && items.every(c => c.demo) ? "fixture " : ""}cable{items.length === 1 ? "" : "s"}{filtered ? " in group" : ""}</span>;
  const details = (items: CableItem[], key: string) => openList === key && <CableList key={key} cables={items} selectedCableId={selectedCableId} onSelect={onSelect} />;
  const action = (key: string, label: string) => <button className="detail-button" aria-label={`${openList === key ? "Hide" : "View"} cables · ${label}`} aria-expanded={openList === key} onClick={() => setOpenList(openList === key ? null : key)}>{openList === key ? "Hide cables" : "View cables"}</button>;
  if (orderedPairs.length === 1) {
    const pair = orderedPairs[0];
    return <div className="connection-list segment-connection-list"><ConnectionCard title={pair.label} metric={metric(cables)}
      subtitle="Rack-pair cables on this pathway" cableTypeCounts={typeCounts(cables)} actions={action("all", pair.label)}>
      {details(cables, "all")}
    </ConnectionCard></div>;
  }
  return <div className="connection-list segment-connection-list">
    <ConnectionCard title="On selected pathway" metric={metric(cables)} cableTypeCounts={typeCounts(cables)}
      subtitle={`${pairs.size.toLocaleString()} rack pairs`} actions={<>
        {!!cables.length && action("all", "selected pathway")}
        {!!pairs.size && <button className={`expand-button ${showPairs ? "is-expanded" : "is-collapsed"}`} aria-expanded={showPairs}
          onClick={() => setShowPairs(!showPairs)}>{showPairs ? "Hide rack pairs" : `Show rack pairs (${pairs.size.toLocaleString()})`}</button>}
      </>}>
      {details(cables, "all")}
    </ConnectionCard>
    {showPairs && orderedPairs.map(pair => <ConnectionCard key={pair.key} title={pair.label} metric={metric(pair.cables)}
      subtitle="Rack-pair cables on this pathway" cableTypeCounts={typeCounts(pair.cables)} actions={action(pair.key, pair.label)}>
      {details(pair.cables, pair.key)}
    </ConnectionCard>)}
  </div>;
}

function CableList({cables, selectedCableId, onSelect}: {cables: CableItem[]; selectedCableId: string | null; onSelect: Props["onSelect"]}) {
  const [limit, setLimit] = useState(PAGE_SIZE);
  const visibleLimit = Math.max(limit, cables.findIndex(c => c.id === selectedCableId) + 1);
  return <div className="connection-cable-details">
    <h4>Cable details <span>{Math.min(visibleLimit, cables.length).toLocaleString()} of {cables.length.toLocaleString()}</span></h4>
    <div className="connection-cable-list">{cables.slice(0, visibleLimit).map(cable => {
      const selected = selectedCableId === cable.id;
      return <button key={cable.id} className={`connection-cable-row ${selected ? "is-selected" : ""}`} style={{borderLeftColor: cable.color}}
        aria-label={`Inspect ${cable.type} ${cable.demo ? "fixture " : ""}cable ${cable.source} to ${cable.destination} · ${cable.id}`} aria-pressed={selected}
        onClick={() => onSelect(selected ? null : cable.id)}>
        <span className="connection-cable-heading"><strong>{cable.type}</strong><span>{cable.source} → {cable.destination}</span></span>
        <small>{cable.id}</small>
        <small>A: {cable.source} · {cable.sourcePort ?? "Port unassigned"}<br />Z: {cable.destination} · {cable.destinationPort ?? "Port unassigned"}</small>
        {selected && <span className="connection-cable-labels">{cable.sourceLabel && <small>A label: {cable.sourceLabel}</small>}{cable.destinationLabel && <small>Z label: {cable.destinationLabel}</small>}{cable.notes && <small>{cable.notes}</small>}{!cable.sourceLabel && !cable.destinationLabel && !cable.notes && <small>No additional labels or notes.</small>}</span>}
      </button>;
    })}</div>
    {cables.length > visibleLimit && <button className="expand-button is-collapsed" onClick={() => setLimit(visibleLimit + PAGE_SIZE)}>Show {Math.min(PAGE_SIZE, cables.length - visibleLimit)} more cables ({visibleLimit} of {cables.length})</button>}
  </div>;
}

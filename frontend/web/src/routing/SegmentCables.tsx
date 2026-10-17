import { useState } from "react";
import { ConnectionCard } from "../components/ConnectionCard";
import type { FixtureCable } from "./cabinetFixtureRun";
import type { InventoryCable } from "./types";
import type { RoutingCableTableRequest } from "./routingCableDetails";
import { CABLE_STYLES } from "./RouteStroke";
import { filterCableMembers } from "./segmentCableMembers";

type Props = {
  cables: FixtureCable[]; inventoryCables?: InventoryCable[]; members?: Record<string, string[]>;
  onViewCables: (request: RoutingCableTableRequest) => void; routeLabel?: string;
  bundleFilter?: {uid: string; label: string; fixtureCableIds?: string[]} | null;
  onClearFilter?: () => void; loading?: boolean; error?: string;
};
type CableItem = {id: string; type: string; source: string; destination: string; inventory?: InventoryCable; fixture?: FixtureCable};
type Pair = {key: string; ends: [string, string]; cables: CableItem[]};
const compare = (a: string, b: string) => a.localeCompare(b, undefined, {numeric: true});

export function SegmentCables({cables, inventoryCables = [], members = {}, onViewCables, routeLabel, bundleFilter, onClearFilter, loading, error}: Props) {
  const all: CableItem[] = [
    ...inventoryCables.map(c => ({id: c.uid, type: c.cable_type, source: c.source_cabinet_id ?? "Unknown", destination: c.destination_cabinet_id ?? "Unknown", inventory: c})),
    ...cables.map(c => ({id: c.id, type: CABLE_STYLES[c.cableClass].label, source: c.sourceCabinetId, destination: c.destinationCabinetId, fixture: c})),
  ];
  const visible = filterCableMembers(all, bundleFilter?.uid ?? null, members, bundleFilter?.fixtureCableIds)
    .sort((a, b) => compare(a.type, b.type) || compare(a.id, b.id));
  const scope = JSON.stringify([bundleFilter?.uid, visible.map(c => c.id)]);
  return <section className="segment-cables" aria-label="Cables on selected segment">
    {bundleFilter && <div className="segment-bundle-filter"><b>{bundleFilter.label}</b><button className="expand-button" onClick={onClearFilter}>Show all segment cables</button></div>}
    {loading && <p role="status">Loading cable membership…</p>}
    {error && <p role="alert" className="routing-error">{error}</p>}
    {visible.some(c => c.fixture) && <p className="conceptual-fixture-notice">Display-only review cables · 021 → 031. Device ports and actual routing tiers remain unassigned.</p>}
    <SegmentCableContent key={scope} cables={visible} onViewCables={onViewCables} filtered={Boolean(bundleFilter)} />
    {!visible.length && !loading && <p className="routing-notice">{bundleFilter ? "No actual cable members linked to this group. Manual labels do not imply cable membership." : "No endpoint cable assignments on this segment. Style color samples are separate from inventory cables."}</p>}
    {visible.some(c => c.fixture) && <p className="routing-notice">Select a cable in its detail table to highlight its sample run. Sample route: {routeLabel ?? "Row 3 → Central R3–4 → Row 4"}. Fixtures never change inventory or saved routing data.</p>}
  </section>;
}

function typeCounts(cables: CableItem[]) {
  const counts: Record<string, number> = Object.create(null);
  for (const cable of cables) counts[cable.type] = (counts[cable.type] ?? 0) + 1;
  return counts;
}

function SegmentCableContent({cables, onViewCables, filtered}: {cables: CableItem[]; onViewCables: Props["onViewCables"]; filtered: boolean}) {
  const [showPairs, setShowPairs] = useState(false);
  const pairs = new Map<string, Pair>();
  for (const cable of cables) {
    // A/Z direction belongs to each cable; combine both directions in rack-pair summaries.
    const ends = [cable.source, cable.destination].sort(compare) as [string, string];
    const key = JSON.stringify(ends);
    if (!pairs.has(key)) pairs.set(key, {key, ends, cables: []});
    pairs.get(key)!.cables.push(cable);
  }
  const orderedPairs = [...pairs.values()].sort((a, b) => compare(a.ends.join(), b.ends.join()));
  const metric = (items: CableItem[]) => <span>{items.length.toLocaleString()} {items.length && items.every(c => c.fixture) ? "fixture " : ""}cable{items.length === 1 ? "" : "s"}{filtered ? " in group" : ""}</span>;
  const pairCard = (pair: Pair) => <ConnectionCard key={pair.key} title={pair.ends.join(" ↔ ")} metric={metric(pair.cables)}
    subtitle="Rack-pair cables on this pathway" cableTypeCounts={typeCounts(pair.cables)} onViewCableType={type => {
      const selected = pair.cables.filter(c => c.type === type);
      onViewCables({source: pair.ends[0], target: pair.ends[1], cableType: type,
        inventoryCables: selected.flatMap(c => c.inventory ? [c.inventory] : []), fixtureCables: selected.flatMap(c => c.fixture ? [c.fixture] : [])});
    }} />;
  if (orderedPairs.length === 1) return <div className="connection-list segment-connection-list">{pairCard(orderedPairs[0])}</div>;
  return <div className="connection-list segment-connection-list">
    <ConnectionCard title="On selected pathway" metric={metric(cables)} cableTypeCounts={typeCounts(cables)}
      subtitle={`${pairs.size.toLocaleString()} rack pairs`} actions={!!pairs.size && <button className={`expand-button ${showPairs ? "is-expanded" : "is-collapsed"}`} aria-expanded={showPairs}
        onClick={() => setShowPairs(!showPairs)}>{showPairs ? "Hide rack pairs" : `Show rack pairs (${pairs.size.toLocaleString()})`}</button>} />
    {showPairs && orderedPairs.map(pairCard)}
  </div>;
}

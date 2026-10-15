import { useEffect, useState } from "react";
import type { SelectionGesture } from "../App";
import { RoutingSchematic } from "./RoutingSchematic";
import { RoutingDetails } from "./RoutingDetails";
import { TierVisibility } from "./TierVisibility";
import { useRoutingLayout, physicalHallCode } from "./useRoutingLayout";
import type { Selection, Tier } from "./types";
import "./routing.css";

type Props = {
  project: string; building: string; hall: string; selected: Set<string>; connected: Set<string>;
  onSelectCabinet: (uid: string, gesture: SelectionGesture) => void;
  onPrefetchCabinet: (uid: string) => void; onClearSelection: () => void; onOpenRouting: () => void;
};
export function CabinetRoutingMap({ project, building, hall, selected, connected, onSelectCabinet, onPrefetchCabinet, onClearSelection, onOpenRouting }: Props) {
  const physicalHall = physicalHallCode(project, hall);
  const { data, graph, loading, error, mutate } = useRoutingLayout(project, building, physicalHall);
  const [tiers, setTiers] = useState(new Set<Tier>([1, 2, 3]));
  const [selection, setSelection] = useState<Selection>(null);
  useEffect(() => setSelection(null), [project, building, hall]);
  const sectionUid = data?.geometry.sections.find(s => s.data_hall_id === hall)?.uid ?? "";
  return <div className="routing-page routing-integrated">
    <div className="routing-toolbar"><TierVisibility tiers={tiers} onChange={setTiers} /><button onClick={onOpenRouting}>Routing workspace</button></div>
    <p className="routing-notice">Select cabinets for devices and connections. Zoom for IDs; All sections returns to the global map.</p>
    {error && <p className="routing-error" role="alert">{error}</p>}
    {loading && !data ? <p>Loading pathways…</p> : !data ? <div className="routing-empty"><p>No routing layout is available for this hall. The standard cabinet map remains available.</p><button onClick={onOpenRouting}>Open routing configuration</button></div> : <>
      {!graph.nodes.length && <p className="routing-notice">Schematic route envelopes · Tiers and openings await configuration.</p>}
      <RoutingSchematic key={data.layout.uid} data={data} graph={graph} tiers={tiers} selection={selection} preview={null} start={null} routeMode={false}
        initialSectionUid={sectionUid} initialOrientation="cabinet-map"
        onSelect={next => { setSelection(next); if (!next) onClearSelection(); }} onNode={node => setSelection({ kind: "node", uid: node.id })}
        cabinetInteraction={{ selected, connected, onSelect: (cabinet, event) => { setSelection(null); onSelectCabinet(cabinet.cabinet_uid, event); }, onPrefetch: onPrefetchCabinet }} />
      {selection && <section className="routing-side routing-integrated-details" aria-label="Selected pathway details"><button onClick={() => setSelection(null)}>Close pathway details</button><RoutingDetails data={data} graph={graph} selection={selection} onSelect={setSelection} canManage={false} busy={false} mutate={mutate} /></section>}
    </>}
  </div>;
}

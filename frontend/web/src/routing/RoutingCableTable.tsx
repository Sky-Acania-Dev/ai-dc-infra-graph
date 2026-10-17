import { useEffect, useState } from "react";
import { fetchCabinetConnectionCables } from "../api";
import { CableDetailOverlay } from "../components/CableDetailOverlay";
import type { CableDetailResponse } from "../types";
import { loadRoutingCableTable, type RoutingCableTableRequest } from "./routingCableDetails";

export function RoutingCableTable({request, selectedCableId, onSelect, onClose}: {
  request: RoutingCableTableRequest; selectedCableId: string | null;
  onSelect: (uid: string | null) => void; onClose: () => void;
}) {
  const [detail, setDetail] = useState<CableDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedUids, setSelectedUids] = useState<string[]>([]);
  useEffect(() => {
    let active = true;
    setLoading(true); setDetail(null); setError(""); setSelectedUids([]); onSelect(null);
    void loadRoutingCableTable(request, fetchCabinetConnectionCables).then(data => {
      if (active) {setDetail(data); const uid = data.cables[0]?.uid ?? null; setSelectedUids(uid ? [uid] : []); onSelect(uid);}
    }).catch(reason => {
      if (active) {setError(`Unable to load cable details: ${String(reason)}`); setDetail({source_cabinet_uid: request.source, target_cabinet_uid: request.target, cables: []});}
    }).finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, [request, onSelect]);
  return <CableDetailOverlay cableDetail={detail} isLoading={loading}
    routeLabel={{source: request.source, target: `${request.target} · ${request.cableType}`}}
    selectedCableUid={selectedCableId} selectedCableUids={new Set(selectedUids)}
    selectionMode="single" canEdit={false} expectedVersion={null} topologyEnums={null}
    onClose={onClose} onSelectCable={cable => {const uid = cable.uid === selectedCableId ? null : cable.uid; setSelectedUids(uid ? [uid] : []); onSelect(uid);}}
    onSelectCableRange={(uids, uid) => {setSelectedUids(uids); onSelect(uid);}}
    onSetCableSelection={(uids, uid) => {setSelectedUids(uids); onSelect(uid);}} onCableUpdated={() => {}}
    selectorLabel={request.fixtureCables.length ? "Display-only fixture cables" : "Inventory cables on the selected pathway"}
    selectorMessage={error || null} />;
}

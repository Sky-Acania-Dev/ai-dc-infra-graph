import type { CabinetCableDetail, CableDetailResponse } from "../types";
import type { InventoryCable } from "./types";

export type RoutingCableTableRequest = {
  source: string; target: string; cableType: string;
  inventoryCables: InventoryCable[];
  wholePair?: [string, string]; groupUid?: string;
};

/** Use the existing inventory detail API, restricted to the selected segment's actual members. */
export async function loadRoutingCableTable(request: RoutingCableTableRequest,
  fetchPair: (source: string, target: string) => Promise<CableDetailResponse>): Promise<CableDetailResponse> {
  const pairs = new Map<string, [string, string]>();
  if (request.wholePair) pairs.set(JSON.stringify(request.wholePair), request.wholePair);
  for (const cable of request.inventoryCables) {
    if (!cable.source_cabinet_uid || !cable.destination_cabinet_uid) throw new Error("Cabinet references are missing for this cable group.");
    const ends = [cable.source_cabinet_uid, cable.destination_cabinet_uid].sort() as [string, string];
    pairs.set(JSON.stringify(ends), ends);
  }
  const allowed = new Set(request.inventoryCables.map(c => c.uid));
  const details = new Map<string, CabinetCableDetail>();
  for (const [source, target] of pairs.values()) {
    const response = await fetchPair(source, target);
    for (const cable of response.cables) {
      if ((request.wholePair || allowed.has(cable.uid)) && cable.cable_type === request.cableType) details.set(cable.uid, cable);
    }
  }
  return {source_cabinet_uid: request.source, target_cabinet_uid: request.target,
    cables: [...details.values()].sort((a, b) => a.uid.localeCompare(b.uid, undefined, {numeric: true}))};
}

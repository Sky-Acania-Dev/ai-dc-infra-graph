import { useEffect, useState } from "react";
import type { ConceptualSegment } from "./conceptualSegments";
import { routingApi } from "./api";
import { segmentTierModel } from "./segmentTierModel";
import { collectPlacementCables } from "./segmentCableMembers";
import type { ResolvedLayout } from "./types";

export function useSegmentCableMembers(data: ResolvedLayout | null, segment: ConceptualSegment | null | undefined) {
  const [state, setState] = useState({key: "", cables: [] as ReturnType<typeof collectPlacementCables>["cables"], members: {} as Record<string, string[]>, loading: false, error: ""});
  const ids = data && segment ? segmentTierModel(data, segment).blocks.filter(b => b.sourceAvailable).map(b => b.uid).sort() : [];
  const key = `${data?.layout.uid}:${segment?.id}:${ids.join("|")}`;
  useEffect(() => {
    const controller = new AbortController();
    setState({key, cables: [], members: {}, loading: ids.length > 0, error: ""});
    if (data && ids.length) void Promise.allSettled(ids.map(uid => routingApi.placementCables(data.layout.uid, uid, controller.signal))).then(results => {
      if (controller.signal.aborted) return;
      const fulfilled = results.flatMap(r => r.status === "fulfilled" ? [r.value] : []);
      const error = results.flatMap(r => r.status === "rejected" ? [String(r.reason)] : []).join(" ");
      setState({key, ...collectPlacementCables(fulfilled), loading: false, error});
    });
    return () => controller.abort();
  }, [data, key]);
  return state.key === key ? state : {cables: [], members: {}, loading: ids.length > 0, error: ""};
}

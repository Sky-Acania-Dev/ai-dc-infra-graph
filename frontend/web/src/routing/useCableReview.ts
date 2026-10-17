import { useEffect, useState } from "react";
import { routingApi } from "./api";
import type { CableReview, ResolvedLayout } from "./types";

export function useCableReview(data: ResolvedLayout | null, enabled: boolean) {
  const [state, setState] = useState<{layout: string; data: CableReview | null; loading: boolean; error: string}>({layout: "", data: null, loading: false, error: ""});
  useEffect(() => {
    const controller = new AbortController();
    if (!data || !enabled) {setState({layout: "", data: null, loading: false, error: ""}); return;}
    setState({layout: data.layout.uid, data: null, loading: true, error: ""});
    void routingApi.cableReview(data.layout.uid, controller.signal).then(result => { if (!controller.signal.aborted) setState({layout: data.layout.uid, data: result, loading: false, error: ""}); })
      .catch(e => {if (!controller.signal.aborted) setState({layout: data.layout.uid, data: null, loading: false, error: String(e)});});
    return () => controller.abort();
  }, [data, enabled]);
  return enabled && state.layout === data?.layout.uid ? state : {data: null, loading: enabled && Boolean(data), error: ""};
}

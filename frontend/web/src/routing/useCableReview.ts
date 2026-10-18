import { useCallback, useEffect, useState } from "react";
import { routingApi } from "./api";
import type { CableReview, ResolvedLayout, ReviewScope } from "./types";

export function useCableReview(data: ResolvedLayout | null, enabled: boolean, scope: ReviewScope = "pilot") {
  const [state, setState] = useState<{layout: string; data: CableReview | null; loading: boolean; error: string}>({layout: "", data: null, loading: false, error: ""});
  const [reloadCount, setReloadCount] = useState(0);
  const replace = useCallback((review: CableReview) => {if (data) setState({layout: data.layout.uid, data: review, loading: false, error: ""});}, [data]);
  useEffect(() => {
    const controller = new AbortController();
    if (!data || !enabled) {setState({layout: "", data: null, loading: false, error: ""}); return;}
    setState({layout: data.layout.uid, data: null, loading: true, error: ""});
    void routingApi.cableReview(data.layout.uid, controller.signal, scope).then(result => { if (!controller.signal.aborted) setState({layout: data.layout.uid, data: result, loading: false, error: ""}); })
      .catch(e => {if (!controller.signal.aborted) setState({layout: data.layout.uid, data: null, loading: false, error: String(e)});});
    return () => controller.abort();
  }, [data, enabled, reloadCount, scope]);
  return {...(enabled && state.layout === data?.layout.uid ? state : {data: null, loading: enabled && Boolean(data), error: ""}), replace, reload: () => setReloadCount(n => n + 1)};
}

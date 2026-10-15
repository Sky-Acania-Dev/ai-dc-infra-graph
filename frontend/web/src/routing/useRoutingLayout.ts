import { useCallback, useEffect, useRef, useState } from "react";
import { routingApi } from "./api";
import type { Mutate, ResolvedLayout, RoutingGraph } from "./types";

export const physicalHallCode = (project: string, hall: string) => project === "LBB01" && /^DH1(?:-[1-5])?$/.test(hall) ? "DH1" : hall;

export function useRoutingLayout(project: string, building: string, hall: string) {
  const [data, setData] = useState<ResolvedLayout | null>(null);
  const [graph, setGraph] = useState<RoutingGraph>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const scope = `${project}:${building}:${hall}`;
  const activeScope = useRef(scope);
  activeScope.current = scope;
  const load = useCallback(async (signal?: AbortSignal) => {
    if (activeScope.current !== scope) return;
    const current = ++generation.current;
    setLoading(true);
    try {
      const layouts = await routingApi.list(project, building, hall, signal);
      const [resolved, derived] = layouts.length ? await Promise.all([routingApi.resolved(layouts[0].uid, signal), routingApi.graph(layouts[0].uid, signal)]) : [null, { nodes: [], edges: [] }];
      if (current === generation.current) { setData(resolved); setGraph(derived); setError(""); }
    } catch (reason) {
      if (current === generation.current && !signal?.aborted) setError(String(reason instanceof Error ? reason.message : reason));
    } finally { if (current === generation.current) setLoading(false); }
  }, [project, building, hall, scope]);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setGraph({ nodes: [], edges: [] }); setError("");
    void load(controller.signal);
    return () => { controller.abort(); generation.current++; };
  }, [load]);
  const mutate: Mutate = async (resource, values, uid, remove = false) => {
    if (!data || busy) return false;
    setBusy(true); setError("");
    try { await routingApi.save(data.layout.uid, resource, values, uid, remove); await load(); return true; }
    catch (reason) { if (activeScope.current === scope) setError(reason instanceof Error ? reason.message : String(reason)); return false; }
    finally { setBusy(false); }
  };
  const initialize = async () => {
    setBusy(true); setError("");
    try { await routingApi.initialize(building); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  return { data, graph, loading, busy, error, mutate, initialize, reload: load };
}

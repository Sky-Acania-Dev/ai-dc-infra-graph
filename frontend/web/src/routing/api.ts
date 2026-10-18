import type { ResolvedLayout, Resource, RoutingGraph, RoutingLayout, RoutePreview, PlacementSource, PlacementCables, CableReview } from "./types";
import { decodeCableReview, type IndexedReview } from "./reviewEncoding";

const BASE = `${import.meta.env.VITE_API_BASE_URL ?? ""}/routing`;
async function request<T>(path: string, method = "GET", payload?: object, signal?: AbortSignal): Promise<T> {
  const response = await fetch(BASE + path, { method, signal, headers: { "Content-Type": "application/json" }, body: payload ? JSON.stringify(payload) : undefined });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: `Routing request failed (${response.status}).` }));
    const detail = Array.isArray(error.detail) ? error.detail.map((item: { msg: string }) => item.msg).join(" ") : error.detail;
    throw new Error(detail || `Routing request failed (${response.status}).`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
export const routingApi = {
  list: (project: string, building: string, hall: string, signal?: AbortSignal) => request<RoutingLayout[]>(`/layouts?${new URLSearchParams({ project_uid: project, building_id: building, hall_code: hall })}`, "GET", undefined, signal),
  resolved: (uid: string, signal?: AbortSignal) => request<ResolvedLayout>(`/layouts/${uid}`, "GET", undefined, signal),
  graph: (uid: string, signal?: AbortSignal) => request<RoutingGraph>(`/layouts/${uid}/graph`, "GET", undefined, signal),
  placementSources: (uid: string, signal?: AbortSignal) => request<PlacementSource[]>(`/layouts/${uid}/placement-sources`, "GET", undefined, signal),
  placementCables: (layout: string, uid: string, signal?: AbortSignal) => request<PlacementCables>(`/layouts/${layout}/bundle-placements/${uid}/cables`, "GET", undefined, signal),
  cableReview: async (layout: string, signal?: AbortSignal, scope = "pilot") => decodeCableReview(await request<CableReview | IndexedReview>(`/layouts/${layout}/cable-review?scope=${scope}`, "GET", undefined, signal)),
  manualBatch: async (layout: string, payload: {scope?: string; topology_revision: string; notes?: string; groups: Array<{group_uid: string; expected_version: string | null; segment_ids: string[]; start_tier: number; end_tier: number}>}, reset = false) => {
    const result = await request<{review: CableReview | IndexedReview; updated_group_uids: string[]}>(`/layouts/${layout}/manual-routes/${reset ? "reset" : "batch"}`, "POST", payload);
    return {...result, review: decodeCableReview(result.review)};
  },
  inventoryTestProfile: (layout: string) => request<{created_tier_count: number; created_opening_count: number; notes: string}>(`/layouts/${layout}/inventory-test-profile`, "POST"),
  testTiers: (layout: string) => request<{review: CableReview; created_tier_count: number}>(`/layouts/${layout}/manual-routes/test-tiers`, "POST"),
  initialize: (building: string) => request<ResolvedLayout>("/initialize-lbb01", "POST", { building_id: building }),
  save: (layout: string, resource: Resource | "layout", values: object, uid?: string, remove = false) =>
    request<unknown>(`/layouts/${layout}${resource === "layout" ? "" : `/${resource}${uid ? `/${uid}` : ""}`}`, remove ? "DELETE" : uid || resource === "layout" ? "PATCH" : "POST", remove ? undefined : values),
  preview: (uid: string, start: string, end: string) => request<RoutePreview>(`/layouts/${uid}/route-preview`, "POST", { start_node_id: start, end_node_id: end }),
};

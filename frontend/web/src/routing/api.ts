import type { ResolvedLayout, Resource, RoutingGraph, RoutingLayout, RoutePreview, PlacementSource } from "./types";

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
  initialize: (building: string) => request<ResolvedLayout>("/initialize-lbb01", "POST", { building_id: building }),
  save: (layout: string, resource: Resource | "layout", values: object, uid?: string, remove = false) =>
    request<unknown>(`/layouts/${layout}${resource === "layout" ? "" : `/${resource}${uid ? `/${uid}` : ""}`}`, remove ? "DELETE" : uid || resource === "layout" ? "PATCH" : "POST", remove ? undefined : values),
  preview: (uid: string, start: string, end: string) => request<RoutePreview>(`/layouts/${uid}/route-preview`, "POST", { start_node_id: start, end_node_id: end }),
};

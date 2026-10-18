import type { CableReview, ReviewGroup, ReviewLoad, ReviewPath, ReviewPoint } from "./types";

type IndexedPath = Omit<ReviewPath, "points" | "load_ids" | "segment_ids"> & {start: ReviewPoint; edge_indices: number[]};
export type IndexedReview = Omit<CableReview, "groups" | "loads"> & {encoding: "indexed-v1";
  groups: Array<Omit<ReviewGroup, "route"> & {route: IndexedPath | null}>;
  loads: Array<{edge_index: number; group_indices: number[]; cable_classes: ReviewLoad["cable_classes"]; cable_count: number}>};

/** Hydrate shared graph references; actual cable records remain in the detail API. */
export function decodeCableReview(value: CableReview | IndexedReview): CableReview {
  if (!("encoding" in value)) return value;
  const same = (a: ReviewPoint, b: ReviewPoint) => a.x_in === b.x_in && a.y_in === b.y_in && a.tier === b.tier;
  const groups: ReviewGroup[] = value.groups.map(group => {
    if (!group.route) return {...group, route: null};
    const {start, edge_indices, ...metrics} = group.route;
    const points = [start], edges = edge_indices.map(index => value.planning_segments[index]);
    for (const edge of edges) {
      const last = points.at(-1)!;
      if (!edge || !same(last, edge.source) && !same(last, edge.target)) throw new Error("The route response contains a disconnected chain. Reload the routing review.");
      points.push(same(last, edge.source) ? edge.target : edge.source);
    }
    return {...group, route: {...metrics, points, load_ids: edges.map(e => e.id), segment_ids: [...new Set(edges.map(e => e.segment_id))]}};
  });
  const loads = value.loads.map(load => ({...value.planning_segments[load.edge_index], cable_classes: load.cable_classes,
    cable_count: load.cable_count, group_uids: load.group_indices.map(i => groups[i].uid)}));
  return {...value, groups, loads};
}

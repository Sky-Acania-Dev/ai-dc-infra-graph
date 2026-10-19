import type { CableReview, ReviewGroup, ReviewLoad, ReviewPath, ReviewPoint } from "./types";

type IndexedPath = Omit<ReviewPath, "points" | "load_ids" | "segment_ids"> & {start: ReviewPoint; edge_indices: number[]};
export type IndexedReview = Omit<CableReview, "groups" | "loads"> & {encoding: "indexed-v1";
  groups: Array<Omit<ReviewGroup, "route"> & {route: IndexedPath | null}>;
  loads: Array<{edge_index: number; group_indices: number[]; cable_classes: ReviewLoad["cable_classes"]; cable_count: number}>};

/** A persistent overview contains group metadata and paths, never individual cable membership. */
export function encodeReviewSummary(review: CableReview): IndexedReview {
  const edgeIndex = new Map(review.planning_segments.map((e,i)=>[e.id,i]));
  const groupIndex = new Map(review.groups.map((g,i)=>[g.uid,i]));
  const edge = (id: string) => {const index=edgeIndex.get(id); if(index == null) throw new Error("Bundle summary references an unavailable pathway."); return index;};
  return {...review, encoding:"indexed-v1", scope:"hall", cables:[],
    groups:review.groups.map(group=>{
      const route=group.route;
      if(!route)return {...group,cable_uids:[],route:null};
      const {points,load_ids,segment_ids,...metrics}=route;
      return {...group,cable_uids:[],route:{...metrics,start:points[0],edge_indices:load_ids.map(edge)}};
    }),
    loads:review.loads.map(load=>({edge_index:edge(load.id),group_indices:load.group_uids.map(uid=>{
      const index=groupIndex.get(uid);if(index == null) throw new Error("Bundle summary references an unavailable group.");return index;
    }),cable_classes:load.cable_classes,cable_count:load.cable_count}))};
}

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

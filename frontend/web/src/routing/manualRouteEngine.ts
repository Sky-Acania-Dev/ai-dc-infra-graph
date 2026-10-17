import type { ManualChain, ManualDraft, ManualPreview, PlanningSegment, ReviewGroup, ReviewPath, ReviewPoint } from "./types";

type Cost = {vertical: number; length: number; ids: string[]};
const key = (p: ReviewPoint) => JSON.stringify([p.x_in, p.y_in, p.tier]);
const compareIds = (a: string[], b: string[]) => {
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  return a.length - b.length;
};
const compareCost = (a: Cost, b: Cost) => a.vertical - b.vertical || a.length - b.length || a.ids.length - b.ids.length || compareIds(a.ids, b.ids);

/** Uses only the server's enabled, tier-specific graph. No network requests during editing. */
export class ManualRouteEngine {
  readonly edges = new Map<string, PlanningSegment>();
  readonly nodes = new Map<string, ReviewPoint>();
  readonly adjacency = new Map<string, Array<{target: string; id: string}>>();
  constructor(segments: PlanningSegment[]) {
    for (const edge of segments) {
      const a = key(edge.source), b = key(edge.target);
      if (edge.planar_length_in < 0 || !Number.isInteger(edge.planar_length_in)) throw new Error("Invalid pathway length in routing graph.");
      if (edge.edge_type === "VERTICAL") {
        if (!edge.vertical_transition_uid || edge.source.x_in !== edge.target.x_in || edge.source.y_in !== edge.target.y_in || Math.abs(edge.source.tier - edge.target.tier) !== 1 || edge.planar_length_in !== 0) throw new Error("Invalid tier opening in routing graph.");
      } else {
        if (edge.source.tier !== edge.target.tier) throw new Error("A tier change requires a physical opening.");
        const dx = Math.abs(edge.source.x_in - edge.target.x_in), dy = Math.abs(edge.source.y_in - edge.target.y_in);
        if (dx && dy || edge.planar_length_in !== dx + dy) throw new Error("Invalid rectilinear pathway segment.");
      }
      this.edges.set(edge.id, edge);
      this.nodes.set(a, edge.source); this.nodes.set(b, edge.target);
      for (const [from, to] of [[a, b], [b, a]]) {
        if (!this.adjacency.has(from)) this.adjacency.set(from, []);
        this.adjacency.get(from)!.push({target: to, id: edge.id});
      }
    }
    for (const adjacent of this.adjacency.values()) adjacent.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  }
  endpoint(cabinet: string, tier: number) {
    return [...this.nodes].find(([, p]) => p.cabinet_uid === cabinet && p.tier === tier)?.[0];
  }
  path(start: string, ids: string[], method: ReviewPath["method"] = "MANUAL"): ReviewPath {
    const points = [this.nodes.get(start)!];
    for (const id of ids) {
      const edge = this.edges.get(id)!;
      points.push(key(edge.source) === key(points.at(-1)!) ? edge.target : edge.source);
    }
    return {method, points, load_ids: ids, segment_ids: [...new Set(ids.map(id => this.edges.get(id)!.segment_id))],
      planar_length_in: ids.reduce((sum, id) => sum + this.edges.get(id)!.planar_length_in, 0),
      vertical_transition_count: ids.filter(id => this.edges.get(id)!.edge_type === "VERTICAL").length, length_label: "Planar pathway length"};
  }
  shortest(start: string, end: string, forbidden: Set<string>): ReviewPath | null {
    const destination = this.nodes.get(end)!;
    const heuristic = (id: string) => {const p = this.nodes.get(id)!; return Math.abs(p.x_in - destination.x_in) + Math.abs(p.y_in - destination.y_in);};
    const initial: Cost = {vertical: 0, length: 0, ids: []};
    const best = new Map<string, Cost>([[start, initial]]);
    const queue = [{node: start, cost: initial}];
    while (queue.length) {
      queue.sort((a, b) => a.cost.vertical - b.cost.vertical || a.cost.length + heuristic(a.node) - b.cost.length - heuristic(b.node) || a.cost.ids.length - b.cost.ids.length || compareIds(a.cost.ids, b.cost.ids));
      const {node, cost} = queue.shift()!;
      if (best.get(node) !== cost) continue;
      if (node === end) return this.path(start, cost.ids, "ASTAR");
      for (const {target, id} of this.adjacency.get(node) ?? []) {
        if (forbidden.has(target)) continue;
        const edge = this.edges.get(id)!;
        const candidate = {vertical: cost.vertical + Number(edge.edge_type === "VERTICAL"), length: cost.length + edge.planar_length_in, ids: [...cost.ids, id]};
        if (!best.has(target) || compareCost(candidate, best.get(target)!) < 0) {best.set(target, candidate); queue.push({node: target, cost: candidate});}
      }
    }
    return null;
  }
  validate(group: ReviewGroup, draft: ManualDraft) {
    const start = this.endpoint(group.source_cabinet_uid, draft.startTier), end = this.endpoint(group.destination_cabinet_uid, draft.endTier);
    if (!start || !end) throw new Error("The endpoints need enabled pathways on the selected tiers.");
    let current = start;
    const visited = new Set([start]);
    for (const id of draft.ids) {
      if (current === end) throw new Error("The chain cannot continue beyond its destination.");
      const edge = this.edges.get(id);
      if (!edge) throw new Error("This segment is unavailable. Reload the routing graph.");
      const a = key(edge.source), b = key(edge.target);
      if (a !== current && b !== current) throw new Error("Choose a connected next segment.");
      current = a === current ? b : a;
      if (visited.has(current)) throw new Error("A route cannot loop or backtrack. Use Undo to change direction.");
      visited.add(current);
    }
    return {start, end, current, visited};
  }
  isComplete(group: ReviewGroup, draft: ManualDraft) {const result = this.validate(group, draft); return result.current === result.end;}
  preview(group: ReviewGroup, draft: ManualDraft): ManualPreview {
    const {start, end, current, visited} = this.validate(group, draft);
    const prefix = this.path(start, draft.ids), complete = current === end;
    const next_chains: ManualChain[] = [];
    if (!complete) for (const first of this.adjacency.get(current) ?? []) {
      if (visited.has(first.target)) continue;
      const ids = [first.id], walked = [current, first.target];
      let at = first.target;
      while (at !== end && this.adjacency.get(at)?.length === 2 && !this.adjacency.get(at)!.some(e => this.edges.get(e.id)!.edge_type === "VERTICAL")) {
        const next = this.adjacency.get(at)!.find(e => !visited.has(e.target) && !walked.includes(e.target));
        if (!next) break;
        ids.push(next.id); at = next.target; walked.push(at);
      }
      next_chains.push({...this.path(current, ids), id: ids.join("|"), label: this.edges.get(ids[0])!.label});
    }
    const forbidden = new Set(visited); forbidden.delete(current);
    return {prefix, complete, next_chains, suggestion: complete ? null : this.shortest(current, end, forbidden), destination: this.nodes.get(end)!};
  }
}

export function groupLabel(group: ReviewGroup) {return `${group.source_cabinet_id} ↔ ${group.destination_cabinet_id} · ${group.cable_type} × ${group.count}`;}
export function pointLabel(point: ReviewPoint) {return `${point.passage_code ?? (point.cabinet_uid ? "Cabinet takeoff" : "Station")} · Tier ${point.tier}`;}
export function sameRackPair(a: ReviewGroup, b: ReviewGroup) {return a.source_cabinet_uid === b.source_cabinet_uid && a.destination_cabinet_uid === b.destination_cabinet_uid;}
export function emptyDraft(group: ReviewGroup): ManualDraft {return {ids: [], checkpoints: [], startTier: group.start_tier ?? 1, endTier: group.end_tier ?? 1};}

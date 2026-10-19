import type { GraphNode, PlanningSegment, Tier } from "./types";

/** Display identity ignores logical tiers; domain graph identities remain untouched. */
export function physicalJunctions(nodes: GraphNode[], tiers: ReadonlySet<Tier>) {
  const groups = new Map<string, GraphNode[]>();
  for (const node of nodes) if (tiers.has(node.tier)) {
    const key = `${node.x_in}:${node.y_in}`;
    if (!groups.has(key)) groups.set(key,[]);
    groups.get(key)!.push(node);
  }
  return [...groups].map(([id,members])=>({id,members:members.sort((a,b)=>a.tier-b.tier || a.id.localeCompare(b.id))}));
}

export function physicalPlanningTargets(segments: PlanningSegment[], tiers?: ReadonlySet<Tier>) {
  const groups = new Map<string, PlanningSegment[]>();
  for (const segment of segments) {
    if (tiers && !tiers.has(segment.source.tier) && !tiers.has(segment.target.tier)) continue;
    const points = [segment.source,segment.target].map(p=>`${p.x_in}:${p.y_in}`).sort();
    // Two physical openings at the same station are still distinct records.
    const id = segment.edge_type === "VERTICAL" ? `opening:${segment.vertical_transition_uid}` : `${segment.segment_id ?? segment.label}:${points.join("/")}`;
    if (!groups.has(id)) groups.set(id,[]);
    groups.get(id)!.push(segment);
  }
  return [...groups].map(([id,members])=>({id,members:members.sort((a,b)=>a.source.tier-b.source.tier || a.id.localeCompare(b.id))}));
}

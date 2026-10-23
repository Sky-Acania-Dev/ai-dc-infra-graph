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

/** Disjoint screen-space targets preserve the clicked station in dense overviews. */
export function junctionHitTargets(junctions: ReturnType<typeof physicalJunctions>, project: (node: GraphNode)=>{x:number;y:number}, scale: number) {
  const targets=junctions.map(junction=>({...junction,point:project(junction.members[0]),hitRadius:8/scale}));
  const columns=new Map<number,typeof targets>();
  for(const target of targets){const x=target.point.x;if(!columns.has(x))columns.set(x,[]);columns.get(x)!.push(target);}
  const xs=[...columns.keys()].sort((a,b)=>a-b);
  xs.forEach((x,index)=>{
    const column=columns.get(x)!.sort((a,b)=>a.point.y-b.point.y);
    const across=Math.min(index?x-xs[index-1]:Infinity,index+1<xs.length?xs[index+1]-x:Infinity);
    column.forEach((target,i)=>{
      const along=Math.min(i?target.point.y-column[i-1].point.y:Infinity,i+1<column.length?column[i+1].point.y-target.point.y:Infinity);
      target.hitRadius=Math.min(target.hitRadius,.45*along,.45*across);
    });
  });
  return targets;
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

import {routeStrokeLines} from "./RouteStroke";
import type {CableClass,Tier} from "./types";

export type OverviewStroke={a:{x:number;y:number};b:{x:number;y:number};tier?:Tier;cableClasses:CableClass[];selected:boolean;muted:boolean};
/** Independent M/L subpaths preserve real gaps; grouping never joins unrelated pathways. */
export function overviewPaths(strokes:OverviewStroke[],scale:number) {
  const paths=new Map<string,ReturnType<typeof routeStrokeLines>[number]&{muted:boolean;parts:string[]}>();
  for(const stroke of strokes)for(const line of routeStrokeLines({...stroke,scale})){
    const key=JSON.stringify([line.color,line.width,line.dash,line.halo,stroke.muted]);
    if(!paths.has(key))paths.set(key,{...line,muted:stroke.muted,parts:[]});
    paths.get(key)!.parts.push(`M${line.a.x},${line.a.y}L${line.b.x},${line.b.y}`);
  }
  // Keep muted paths underneath the selected route and its colored lanes.
  return [...paths].sort(([,a],[,b])=>Number(b.muted)-Number(a.muted)||Number(b.halo)-Number(a.halo)).map(([id,p])=>({...p,id,d:p.parts.join(" ")}));
}
export function OverviewStrokes({strokes,scale}:{strokes:OverviewStroke[];scale:number}) {
  return <g className="bundle-overview-strokes" pointerEvents="none" data-overview-mode="summary">
    {overviewPaths(strokes,scale).map(path=><path key={path.id} d={path.d} fill="none" stroke={path.color} strokeWidth={path.width} strokeDasharray={path.dash}
      strokeLinecap={path.halo?undefined:"round"} vectorEffect="non-scaling-stroke" data-cable-class={path.cableClass??undefined}
      data-route-muted={path.muted||undefined} opacity={path.muted ? .35 : 1} />)}
  </g>;
}

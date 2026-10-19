import type { CableClass, Tier } from "./types";

export const CABLE_STYLES: Record<CableClass, { label: string; color: string }> = {
  LC: { label: "LC", color: "#246bfe" },
  CAT6: { label: "Cat6", color: "#ef3340" },
  MPO: { label: "MPO", color: "#25a653" },
  MPO_TRUNK_T2_T1_RO: { label: "MPO trunk T2-T1-RO", color: "#00d9f5" },
  CROSS_SECTION_CAT6: { label: "Cross-section Cat6", color: "#ff8c1a" },
  CROSS_SECTION_LC: { label: "Cross-section LC", color: "#f04ea8" },
};
export const EMPTY_ROUTE_COLOR = "#4b5057", UNUSABLE_ROUTE_COLOR = "#c5cbd1";
const DASH: Record<Tier, string | undefined> = { 1: undefined, 2: "9 5", 3: "9 4 2 4" };
// Screen-space styling only: reduce visual weight in overviews, preserving a readable minimum.
export const routeDetailScale = (scale: number) => Math.min(1, Math.max(0.3, Math.sqrt(Math.max(0, scale) / 0.65)));
// Ink gets thinner faster than interaction targets or opening markers at overview zoom.
export const routeInkScale = (scale: number) => Math.min(1, Math.max(0.12, scale / 0.65));
export const emptyRouteColor = (scale: number) => scale < 0.12 ? "#cbd2d9" : scale < 0.3 ? "#929ba5" : EMPTY_ROUTE_COLOR;
type Point = { x: number; y: number };
type StrokeProps = {
  a: Point; b: Point; scale: number; cableClasses?: CableClass[]; usable?: boolean; selected?: boolean; tier?: Tier;
};
export function routeStrokeLines({a,b,scale,cableClasses=[],usable=true,selected=false,tier}:StrokeProps) {
  const length = Math.hypot(b.x - a.x, b.y - a.y) || 1;
  const dx = -(b.y - a.y) / length, dy = (b.x - a.x) / length;
  const lanes = usable && cableClasses.length ? cableClasses : [null];
  const ink = routeInkScale(scale);
  const result:Array<{key:string;halo:boolean;cableClass:CableClass|null;a:Point;b:Point;color:string;width:number;dash?:string}>=[];
  if(selected)result.push({key:"halo",halo:true,cableClass:null,a,b,color:"#ffcc66",width:Math.max(2,Math.max(9,lanes.length*7+5)*ink)});
  lanes.forEach((kind,i)=>{
    const offset=(i-(lanes.length-1)/2)*7*ink/scale;
    result.push({key:kind??"empty",halo:false,cableClass:kind,a:{x:a.x+dx*offset,y:a.y+dy*offset},b:{x:b.x+dx*offset,y:b.y+dy*offset},
      color:!usable?UNUSABLE_ROUTE_COLOR:kind?CABLE_STYLES[kind].color:emptyRouteColor(scale),width:kind?Math.max(selected ? 0.9 : 0.6,5*ink):Math.max(0.5,3*ink),dash:tier?DASH[tier]:undefined});
  });
  return result;
}
export function RouteStroke(props:StrokeProps) {
  return <g pointerEvents="none" className="conceptual-route-strokes">
    {routeStrokeLines(props).map(line=><line key={line.key} className={line.halo?undefined:line.cableClass?"conceptual-cable-line":"conceptual-empty-line"} data-cable-class={line.cableClass??undefined}
      x1={line.a.x} y1={line.a.y} x2={line.b.x} y2={line.b.y} stroke={line.color} strokeWidth={line.width} strokeLinecap={line.halo?undefined:"round"} strokeDasharray={line.dash} vectorEffect="non-scaling-stroke" />)}
  </g>;
}

export function RouteLegend() {
  return <div className="conceptual-route-legend" aria-label="Route cable colors">
    <span><i style={{ borderColor: EMPTY_ROUTE_COLOR }} />Empty / unassigned</span>
    {Object.entries(CABLE_STYLES).map(([key, style]) => <span key={key}><i className="cable" style={{ borderColor: style.color }} />{style.label}</span>)}
    <span><i style={{ borderColor: UNUSABLE_ROUTE_COLOR }} />Unusable</span>
  </div>;
}

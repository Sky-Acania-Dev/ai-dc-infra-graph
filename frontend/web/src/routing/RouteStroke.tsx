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
type Point = { x: number; y: number };
export function RouteStroke({ a, b, scale, cableClasses = [], usable = true, selected = false, tier }: {
  a: Point; b: Point; scale: number; cableClasses?: CableClass[]; usable?: boolean; selected?: boolean; tier?: Tier;
}) {
  const length = Math.hypot(b.x - a.x, b.y - a.y) || 1;
  const dx = -(b.y - a.y) / length, dy = (b.x - a.x) / length;
  const lanes = usable && cableClasses.length ? cableClasses : [null];
  const detail = routeDetailScale(scale);
  return <g pointerEvents="none" className="conceptual-route-strokes">
    {selected && <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#ffcc66" strokeWidth={Math.max(4, Math.max(9, lanes.length * 7 + 5) * detail)} vectorEffect="non-scaling-stroke" />}
    {lanes.map((kind, i) => {
      const offset = (i - (lanes.length - 1) / 2) * 7 * detail / scale;
      return <line key={kind ?? "empty"} className={kind ? "conceptual-cable-line" : "conceptual-empty-line"} data-cable-class={kind ?? undefined}
        x1={a.x + dx * offset} y1={a.y + dy * offset} x2={b.x + dx * offset} y2={b.y + dy * offset}
        stroke={!usable ? UNUSABLE_ROUTE_COLOR : kind ? CABLE_STYLES[kind].color : EMPTY_ROUTE_COLOR}
        strokeWidth={(kind ? 5 : 3) * detail} strokeLinecap="round" strokeDasharray={tier ? DASH[tier] : undefined} vectorEffect="non-scaling-stroke" />;
    })}
  </g>;
}

export function RouteLegend() {
  return <div className="conceptual-route-legend" aria-label="Route cable colors">
    <span><i style={{ borderColor: EMPTY_ROUTE_COLOR }} />Empty / unassigned</span>
    {Object.entries(CABLE_STYLES).map(([key, style]) => <span key={key}><i className="cable" style={{ borderColor: style.color }} />{style.label}</span>)}
    <span><i style={{ borderColor: UNUSABLE_ROUTE_COLOR }} />Unusable</span>
  </div>;
}

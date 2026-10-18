import { projectReviewPoint } from "./cableReviewProjection";
import { pointLabel } from "./manualRouteEngine";
import { routeDetailScale } from "./RouteStroke";
import type { ConceptualLayout } from "./conceptualLayout";
import type { ManualPreview, PlanningSegment, ResolvedLayout, ReviewPath } from "./types";

export function ManualRouteLayer({data, view, segments, preview, scale, onAppend, disabled}: {
  data: ResolvedLayout; view: ConceptualLayout; segments: PlanningSegment[]; preview: ManualPreview | null;
  scale: number; onAppend: (ids: string[]) => void; disabled: boolean;
}) {
  const detail = routeDetailScale(scale);
  const line = (route: ReviewPath, color: string, width: number, dash?: string) => route.points.slice(1).map((point, i) => {
    const a = projectReviewPoint(data, view, route.points[i]), b = projectReviewPoint(data, view, point);
    if (!a || !b) return null;
    return point.tier !== route.points[i].tier ? <g key={i}><circle cx={a.x} cy={a.y} r={6 / scale} fill="#fff" stroke={color} vectorEffect="non-scaling-stroke" /><text x={a.x + 8 / scale} y={a.y - 6 / scale} fontSize={10 / scale}>T{route.points[i].tier} ↕ T{point.tier}</text></g>
      : <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color} strokeWidth={width * detail} strokeDasharray={dash ?? (point.tier === 2 ? "9 5" : point.tier === 3 ? "9 4 2 4" : undefined)} vectorEffect="non-scaling-stroke" strokeLinecap="round" />;
  });
  return <g className="manual-route-layer" aria-label="Manual route building paths">
    <g opacity={.45} pointerEvents="none">{segments.map(segment => <g key={segment.id}>{line({points: [segment.source, segment.target]} as ReviewPath, "#94a3b8", 1.5)}</g>)}</g>
    {preview && <>
      <g pointerEvents="none">{preview.suggestion && line(preview.suggestion, "#06a9cc", 5, "7 6")}{line(preview.prefix, "#ed8817", 5)}</g>
      {preview.next_chains.map(chain => <g key={chain.id} role="button" tabIndex={disabled ? -1 : 0} data-selectable="true" aria-label={`Append ${chain.label} to ${pointLabel(chain.points.at(-1)!)}`} aria-disabled={disabled}
        onClick={event => {event.stopPropagation(); if (!disabled) onAppend(chain.load_ids);}} onKeyDown={event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault(); event.stopPropagation(); if (!disabled) onAppend(chain.load_ids);}}}>
        {line(chain, "#087e80", 4)}
        {chain.points.slice(1).map((p, i) => {const a = projectReviewPoint(data, view, chain.points[i]), b = projectReviewPoint(data, view, p); return a && b ? <rect key={i} x={Math.min(a.x,b.x) - 9/scale} y={Math.min(a.y,b.y) - 9/scale} width={Math.abs(a.x-b.x) + 18/scale} height={Math.abs(a.y-b.y) + 18/scale} fill="transparent" /> : null;})}
        <title>Append this connected chain; no request is sent</title>
      </g>)}
      <g pointerEvents="none">{[preview.prefix.points[0], preview.prefix.points.at(-1)!, preview.destination].map((p, i) => {const projected = projectReviewPoint(data, view, p); return projected ? <g key={i}><circle cx={projected.x} cy={projected.y} r={(i === 1 ? 6 : 4)/scale} fill={i === 2 ? "#fff" : i === 1 ? "#ed8817" : "#087e80"} stroke="#334155" vectorEffect="non-scaling-stroke" /><text x={projected.x + 9/scale} y={projected.y - 9/scale} fontSize={10/scale} fontWeight="700">{i === 0 ? "Start" : i === 1 ? "Current" : "End"} T{p.tier}</text></g> : null;})}</g>
    </>}
  </g>;
}

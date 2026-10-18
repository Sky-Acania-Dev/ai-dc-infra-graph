import { offsetPolyline, type CabinetFixtureRun, type FixtureRunPart, type projectFixtureRun } from "./cabinetFixtureRun";
import { CABLE_STYLES, routeDetailScale } from "./RouteStroke";

export function CabinetFixtureLayer({ run, geometry, scale, selectedPartId, selectedCableId, onSelect }: {
  run: CabinetFixtureRun; geometry: NonNullable<ReturnType<typeof projectFixtureRun>>; scale: number;
  selectedPartId: string | null; selectedCableId: string | null; onSelect: (part: FixtureRunPart) => void;
}) {
  const detail = routeDetailScale(scale);
  const path = (offset: number) => offsetPolyline(geometry.points, offset).map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" ");
  return <g className="cabinet-fixture-run" data-fixture-run={run.id} aria-label="Display-only fixture cables from 021 to 031">
    {geometry.parts.filter(p => p.id === selectedPartId).map(p => <line key={p.id} x1={p.a.x} y1={p.a.y} x2={p.b.x} y2={p.b.y}
      stroke="#ffcc66" strokeWidth={Math.max(4, 27 * detail)} strokeLinecap="round" vectorEffect="non-scaling-stroke" pointerEvents="none" />)}
    {run.cables.map((cable, i) => <path key={cable.id} d={path((i - 1) * 7 * detail / scale)} data-fixture-cable={cable.id}
      stroke={CABLE_STYLES[cable.cableClass].color} strokeWidth={(selectedCableId === cable.id ? 6.5 : 5) * detail}
      opacity={selectedCableId && selectedCableId !== cable.id ? 0.2 : 1} fill="none" strokeLinejoin="round" strokeLinecap="butt" vectorEffect="non-scaling-stroke" pointerEvents="none" />)}
    {geometry.parts.map(part => <g key={`${part.kind}:${part.id}`} data-selectable="true" role="button" tabIndex={0}
      aria-label={`Inspect ${part.label}`} onClick={event => { event.stopPropagation(); onSelect(part); }}
      onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.stopPropagation(); onSelect(part); } }}>
      <line x1={part.a.x} y1={part.a.y} x2={part.b.x} y2={part.b.y} stroke="transparent" strokeWidth={part.kind === "attachment" ? 9 : 25} vectorEffect="non-scaling-stroke" />
      <title>021 → 031 · LC, MPO, Cat6 · Fake review cables only</title>
    </g>)}
    {[geometry.sourceFace, geometry.destinationFace].map((point, i) => <circle key={i} className="fixture-attachment-anchor" cx={point.x} cy={point.y} r={2 / scale}
      fill="#fff" stroke="#475569" strokeWidth={1} vectorEffect="non-scaling-stroke" pointerEvents="none" />)}
  </g>;
}

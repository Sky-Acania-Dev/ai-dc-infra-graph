import { CABLE_STYLES } from "./RouteStroke";
import { formatInches } from "./dimensions";
import { occupationLabel } from "./occupation";
import { occupationGrid } from "./sectionGrid";
import type { segmentTierModel } from "./segmentTierModel";
import type { Tier } from "./types";

type Props = {tier: Tier; model: ReturnType<typeof segmentTierModel>; onSelectPlacement: (uid: string) => void};
export function SectionOccupationDiagram({tier, model, onSelectPlacement}: Props) {
  const blocks = model.blocks.filter(b => b.tier === tier);
  const parent = model.parents.find(p => p.tier === tier) ?? model.parents.find(p => p.tier == null);
  const columns = model.demoMode ? 12 : parent?.grid_columns ?? 12, rows = model.demoMode ? 8 : parent?.grid_rows ?? 8;
  const saved = model.occupations.find(o => o.segment_annotation_uid === parent?.uid && o.tier === tier);
  const grid = model.demoMode ? occupationGrid(columns, rows, blocks) : {cells: saved?.cells ?? Array.from({length: rows}, () => Array<number>(columns).fill(0)), occupants: (saved?.occupants ?? []).map(o => ({...blocks.find(b => b.uid === o.placement_uid)!, value: o.value}))};
  const cellW = 220 / columns, cellH = 88 / rows;
  const reference = parent?.section_reference ?? model.reference;
  const rectangles = blocks.filter(b => b.offset_across_in != null);
  const height = model.demoMode ? null : parent?.section_height_in;
  const drawingHeight = height ?? Math.max(1, ...rectangles.map(b => b.offset_up_in! + b.occupied_height_in!));
  const scale = Math.min(220 / model.width_in, 88 / drawingHeight);
  return <div className="tier-section-card">
    <div><b>T{tier} section</b><span>{model.demoMode ? "DEMO · " : ""}{columns}W × {rows}H grid</span></div>
    <svg viewBox="0 0 290 136" role="img" aria-label={`Tier ${tier} ${columns} by ${rows} occupation grid, bottom layer 1, inner position 1`}>
      <text x={45} y={13} fontSize={9}>Inner (1)</text><text x={265} y={13} fontSize={9} textAnchor="end">Outer →</text>
      {grid.cells.flatMap((line, y) => line.map((value, x) => {
        const cableClass = grid.occupants[value - 1]?.cable_class;
        return <rect key={`${x}:${y}`} x={45 + x * cellW} y={20 + (rows - y - 1) * cellH} width={cellW} height={cellH} fill={value ? `${cableClass ? CABLE_STYLES[cableClass].color : "#64748b"}25` : "#fafcfe"} stroke="#cbd5e1" strokeWidth={.5} />;
      }))}
      <text x={7} y={29} fontSize={8}>L{rows}</text><text x={7} y={106} fontSize={8}>L1 ↓</text>
      {blocks.filter(b => b.layer != null).map(block => <g key={block.uid} role="button" tabIndex={0} aria-label={`Inspect ${block.label}, ${occupationLabel(block)}`} onClick={() => onSelectPlacement(block.uid)} onKeyDown={e => { if (e.key === "Enter") onSelectPlacement(block.uid); }}>
        <rect x={45 + (block.position! - 1) * cellW + 1} y={20 + (rows - block.layer! - block.slot_height! + 1) * cellH + 1} width={block.slot_width! * cellW - 2} height={block.slot_height! * cellH - 2} fill="transparent" stroke={block.cable_class ? CABLE_STYLES[block.cable_class].color : "#64748b"} strokeDasharray={block.demo ? "3 2" : undefined} strokeWidth={1.5} />
        <text x={45 + (block.position! - 1 + block.slot_width! / 2) * cellW} y={20 + (rows - block.layer! + 1 - block.slot_height! / 2) * cellH + 3} textAnchor="middle" fontSize={Math.min(9, cellH)}>{block.cable_class ?? "Bundle"}</text><title>{`${block.label} · ${occupationLabel(block)}`}</title>
      </g>)}
      <text x={45} y={126} fontSize={8}>{reference ? reference.slice(0, 51) : "Inner-side viewing reference not configured"}</text>
    </svg>
    {!!rectangles.length && <>
      <div><b>Physical rectangles</b><span>{model.demoMode ? "DEMO dimensions" : height == null ? "Section height unknown · auto-fit" : `${formatInches(model.width_in)} × ${formatInches(height)}`}</span></div>
      <svg viewBox="0 0 290 136" role="img" aria-label={`Tier ${tier} physical sectional rectangles, offsets from inner edge and tray bed`}>
        <text x={45} y={13} fontSize={9}>Inner → outer</text><path d={`M45 ${108 - drawingHeight * scale}V108H${45 + model.width_in * scale}V${108 - drawingHeight * scale}`} fill="#f8fafc" stroke="#64748b" strokeWidth={1} />
        {rectangles.map(b => <g key={b.uid} role="button" tabIndex={0} aria-label={`Inspect rectangle ${b.label}`} onClick={() => onSelectPlacement(b.uid)} onKeyDown={e => { if (e.key === "Enter") onSelectPlacement(b.uid); }}>
          <rect x={45 + b.offset_across_in! * scale} y={108 - (b.offset_up_in! + b.occupied_height_in!) * scale} width={b.occupied_width_in! * scale} height={b.occupied_height_in! * scale} fill={`${b.cable_class ? CABLE_STYLES[b.cable_class].color : "#64748b"}25`} stroke={b.cable_class ? CABLE_STYLES[b.cable_class].color : "#64748b"} strokeDasharray={b.demo ? "3 2" : undefined} />
          <text x={45 + (b.offset_across_in! + b.occupied_width_in! / 2) * scale} y={111 - (b.offset_up_in! + b.occupied_height_in! / 2) * scale} textAnchor="middle" fontSize={9}>{b.cable_class ?? "Bundle"}</text><title>{`${b.label} · ${occupationLabel(b)}`}</title>
        </g>)}<text x={45} y={126} fontSize={8}>Tray bed · width {formatInches(model.width_in)} · up offsets from bed</text>
      </svg>
    </>}
    {!blocks.length && <small>No bundle occupation configured.</small>}
    {blocks.map(b => <button className="section-bundle-label" key={b.uid} title={occupationLabel(b)} onClick={() => onSelectPlacement(b.uid)}>{b.label} · {occupationLabel(b)}{!b.sourceAvailable ? " · unresolved" : ""}</button>)}
  </div>;
}

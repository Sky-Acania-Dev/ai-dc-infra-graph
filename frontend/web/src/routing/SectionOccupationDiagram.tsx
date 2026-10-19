import { CABLE_STYLES } from "./RouteStroke";
import { formatInches } from "./dimensions";
import { occupationLabel } from "./occupation";
import { sectionView } from "./sectionDirections";
import type { segmentTierModel } from "./segmentTierModel";
import type { Tier } from "./types";

export type SectionDisplayMode = "GRID" | "PHYSICAL";
type Props = {tier: Tier | null; model: ReturnType<typeof segmentTierModel>; mode: SectionDisplayMode; reversed: boolean; selectedPlacementUid?: string | null; onSelectPlacement: (uid: string) => void};
export function SectionOccupationDiagram({tier, model, mode, reversed, selectedPlacementUid, onSelectPlacement}: Props) {
  const blocks = model.blocks.filter(b => b.tier === tier);
  const parent = model.parents.find(p => p.tier === tier) ?? model.parents.find(p => p.tier == null);
  const columns = parent?.grid_columns ?? 12, rows = parent?.grid_rows ?? 8;
  const saved = model.occupations.find(o => o.segment_annotation_uid === parent?.uid && o.tier === tier);
  const grid = {cells: saved?.cells ?? Array.from({length: rows}, () => Array<number>(columns).fill(0)), occupants: (saved?.occupants ?? []).map(o => ({...blocks.find(b => b.uid === o.placement_uid)!, value: o.value}))};
  const cellW = 220 / columns, cellH = 88 / rows;
  const reference = parent?.section_reference ?? model.reference;
  const rectangles = blocks.filter(b => b.offset_across_in != null);
  const height = parent?.section_height_in;
  const drawingHeight = height ?? Math.max(8, ...rectangles.map(b => b.offset_up_in! + b.occupied_height_in!));
  const scale = Math.min(220 / model.width_in, 88 / drawingHeight), frameWidth = model.width_in * scale;
  const view = sectionView(model.directions, parent?.section_inner_direction, reversed);
  const xAt = (offset: number, width: number, total: number) => 45 + (reversed ? total - offset - width : offset);
  const tierLabel = tier == null ? "Unassigned tier" : `T${tier}`;
  const visibleBlocks = mode === "GRID" ? blocks.filter(b => b.layer != null) : rectangles;
  return <div className="tier-section-card">
    <div><b>{tierLabel} section</b><span>{mode === "GRID" ? `${columns}W × ${rows}H grid` : "Physical rectangles"}</span></div>
    {mode === "GRID" ? <svg viewBox="0 0 290 136" role="img" aria-label={`${tierLabel} ${columns} by ${rows} occupation grid; ${view.left} to ${view.right}`}>
      <text x={45} y={13} fontSize={9}>{view.left}</text><text x={265} y={13} fontSize={9} textAnchor="end">{view.right}</text>
      {grid.cells.flatMap((line, y) => line.map((value, x) => {
        const cableClass = grid.occupants[value - 1]?.cable_class;
        return <rect key={`${x}:${y}`} x={xAt(x * cellW, cellW, 220)} y={20 + (rows - y - 1) * cellH} width={cellW} height={cellH} fill={value ? `${cableClass ? CABLE_STYLES[cableClass].color : "#64748b"}25` : "#fafcfe"} stroke="#cbd5e1" strokeWidth={.5} />;
      }))}
      <text x={7} y={29} fontSize={8}>L{rows}</text><text x={7} y={106} fontSize={8}>L1 ↓</text>
      {visibleBlocks.map(block => {
        const x = xAt((block.position! - 1) * cellW, block.slot_width! * cellW, 220), y = 20 + (rows - block.layer! - block.slot_height! + 1) * cellH;
        return <g key={block.uid} role="button" tabIndex={0} aria-label={`Inspect ${block.label}, ${occupationLabel(block)}`} aria-pressed={selectedPlacementUid === block.uid} className={selectedPlacementUid === block.uid ? "selected-section-block" : ""} onClick={() => onSelectPlacement(block.uid)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectPlacement(block.uid); } }}>
          <rect x={x + 1} y={y + 1} width={block.slot_width! * cellW - 2} height={block.slot_height! * cellH - 2} fill="transparent" stroke={block.cable_class ? CABLE_STYLES[block.cable_class].color : "#64748b"} strokeWidth={1.5} />
          <text x={x + block.slot_width! * cellW / 2} y={y + block.slot_height! * cellH / 2 + 3} textAnchor="middle" fontSize={Math.min(9, cellH)}>{block.cable_class ?? "Bundle"}</text><title>{`${block.label} · ${occupationLabel(block)}`}</title>
        </g>;
      })}
      <text x={45} y={126} fontSize={8}>Column 1 at {sectionView(model.directions, parent?.section_inner_direction, false).left} · bottom layer 1</text>
    </svg> : <>
      <svg viewBox="0 0 290 136" role="img" aria-label={`${tierLabel} physical sectional rectangles; ${view.left} to ${view.right}`}>
        <text x={45} y={13} fontSize={9}>{view.left}</text><text x={45 + frameWidth} y={13} fontSize={9} textAnchor="end">{view.right}</text>
        <path d={`M45 ${108 - drawingHeight * scale}V108H${45 + frameWidth}V${108 - drawingHeight * scale}`} fill="#f8fafc" stroke="#64748b" strokeWidth={1} />
        {rectangles.map(b => {
          const x = xAt(b.offset_across_in! * scale, b.occupied_width_in! * scale, frameWidth), y = 108 - (b.offset_up_in! + b.occupied_height_in!) * scale;
          return <g key={b.uid} role="button" tabIndex={0} aria-label={`Inspect rectangle ${b.label}`} aria-pressed={selectedPlacementUid === b.uid} className={selectedPlacementUid === b.uid ? "selected-section-block" : ""} onClick={() => onSelectPlacement(b.uid)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectPlacement(b.uid); } }}>
            <rect x={x} y={y} width={b.occupied_width_in! * scale} height={b.occupied_height_in! * scale} fill={`${b.cable_class ? CABLE_STYLES[b.cable_class].color : "#64748b"}25`} stroke={b.cable_class ? CABLE_STYLES[b.cable_class].color : "#64748b"} />
            <text x={x + b.occupied_width_in! * scale / 2} y={y + b.occupied_height_in! * scale / 2 + 3} textAnchor="middle" fontSize={9}>{b.cable_class ?? "Bundle"}</text><title>{`${b.label} · ${occupationLabel(b)}`}</title>
          </g>;
        })}<text x={45} y={126} fontSize={8}>Tray bed · width {formatInches(model.width_in)}</text>
      </svg>
      <small>{height == null ? "Section height unknown · schematic auto-fit" : `Section height ${formatInches(height)}`}</small>
    </>}
    {reference && <small>{reference}</small>}
    {!blocks.length ? <small>Empty section · no bundle occupation configured.</small> : visibleBlocks.length < blocks.length && <small>{blocks.length - visibleBlocks.length} bundle(s) have no {mode === "GRID" ? "grid footprint" : "physical rectangle"} recorded. Select a label to inspect.</small>}
    {model.directions.hasInner && !view.inner && <small>Inner side not assigned for this section.</small>}
    {blocks.map(b => <button className="section-bundle-label" key={b.uid} aria-pressed={selectedPlacementUid === b.uid} title={occupationLabel(b)} onClick={() => onSelectPlacement(b.uid)}>{b.label} · {occupationLabel(b)}{!b.sourceAvailable ? " · unresolved" : ""}</button>)}
  </div>;
}

import { useEffect, useRef } from "react";
import type { SectionBlock } from "./segmentTierModel";
import type { SectionDisplayMode } from "./SectionOccupationDiagram";
import { CABLE_STYLES } from "./RouteStroke";
import { formatInches } from "./dimensions";
import { occupationLabel } from "./occupation";

export function SectionBundleDetail({block, mode, onClose}: {block: SectionBlock; mode: SectionDisplayMode; onClose: () => void}) {
  const detail = useRef<HTMLElement>(null);
  useEffect(() => { detail.current?.scrollIntoView({block: "nearest", behavior: "smooth"}); }, [block.uid]);
  const width = mode === "GRID" ? block.slot_width : block.occupied_width_in;
  const height = mode === "GRID" ? block.slot_height : block.occupied_height_in;
  const scale = width && height ? Math.min(220 / width, 110 / height) : 1;
  const color = block.cable_class ? CABLE_STYLES[block.cable_class].color : "#64748b";
  return <section ref={detail} className="section-bundle-detail" aria-label="Enlarged bundle section">
    <div><h4>Bundle detail</h4><button onClick={onClose} aria-label="Close bundle detail">×</button></div>
    <b>{block.label}</b><small>T{block.tier} · {occupationLabel(block)}</small>
    {width && height ? <svg viewBox="0 0 270 160" role="img" aria-label={`Enlarged ${block.label} footprint`}>
      <rect x={(270 - width * scale) / 2} y={22} width={width * scale} height={height * scale} fill={`${color}20`} stroke={color} strokeWidth={2} />
      <text x={135} y={22 + height * scale / 2 + 4} fontSize={12} textAnchor="middle">{block.cable_class ?? "Bundle"}</text>
      <text x={135} y={150} fontSize={10} textAnchor="middle">{mode === "GRID" ? `${width} × ${height} cells` : `${formatInches(width)} × ${formatInches(height)}`}</text>
    </svg> : <p>No {mode === "GRID" ? "grid footprint" : "physical rectangle"} recorded for this bundle.</p>}
    <p>Cable list filtered to this group on the right. Individual cable positions inside the bundle are not yet recorded.</p>
  </section>;
}

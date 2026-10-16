import { CABLE_STYLES } from "./RouteStroke";
import { formatInches } from "./dimensions";
import type { segmentTierModel } from "./segmentTierModel";
import type { ResolvedLayout, Tier } from "./types";

type Model = ReturnType<typeof segmentTierModel>;
export function TierSectionDiagrams({ data, model, onSelectPlacement }: { data: ResolvedLayout; model: Model; onSelectPlacement: (uid: string) => void }) {
  return <section className="tier-sections" aria-label="Tier and bundle section diagrams">
    {model.demoMode && <p className="tier-demo-banner">DEMO placements · Display only. Unset heights remain unknown; openings come from saved records.</p>}
    <h4>Tier diagram</h4>
    {!model.tiers.length ? <p className="routing-notice">No tiers configured for this pathway. Add confirmed tiers below to populate the diagrams.</p> : <svg viewBox="0 0 290 145" role="img" aria-label="Tier diagram, logical layers with explicit physical openings only" className="tier-stack-svg">
      {[...model.tiers].sort((a, b) => b - a).map((tier, index) => {
        const record = model.records.find(r => r.tier === tier), y = 16 + index * 43;
        const blocks = model.blocks.filter(b => b.tier === tier);
        const types = [...new Set([...blocks.map(b => b.cable_class ?? b.label), ...(model.markedClasses[tier] ?? [])])];
        return <g key={tier} opacity={record && !record.enabled ? 0.4 : 1}>
          <text x={5} y={y + 8} fontSize={12} fontWeight={700}>T{tier}</text><line x1={36} x2={281} y1={y + 16} y2={y + 16} stroke="#64748b" strokeWidth={2} />
          <text x={39} y={y + 7} fontSize={9}>{record?.elevation_in == null ? "Height unknown" : `${formatInches(record.elevation_in)} AFF`}{!record ? " · unconfigured" : !record.enabled ? " · disabled" : ""}</text>
          <text x={39} y={y + 32} fontSize={9}>{types.length ? `${types.join(" · ")}${!blocks.length ? " · positions unset" : ""}` : "No bundles assigned"}</text>
        </g>;
      })}
      {model.openings.filter(o => o.enabled && model.tiers.includes(o.lower_tier as Tier) && model.tiers.includes(o.upper_tier as Tier)).map((opening, i) => {
        const order = [...model.tiers].sort((a, b) => b - a), a = 32 + order.indexOf(opening.lower_tier as Tier) * 43, b = 32 + order.indexOf(opening.upper_tier as Tier) * 43;
        return <g key={opening.uid}><line x1={270 - i * 9} x2={270 - i * 9} y1={a} y2={b} stroke="#7c3aed" strokeWidth={3} strokeDasharray="3 2" /><title>{opening.label ?? "Opening"}: T{opening.lower_tier} ↕ T{opening.upper_tier}</title></g>;
      })}
    </svg>}
    <div className="segment-opening-list" aria-label="Openings in selected segment">
      {model.openings.length ? model.openings.map(o => <div key={o.uid} className={o.enabled ? "" : "disabled"}><b>{o.label ?? "Physical opening"}</b> · {data.bands.find(b => b.uid === o.passage_band_uid)?.code} · T{o.lower_tier} ↕ T{o.upper_tier} · {formatInches(o.station_in)}{!o.enabled ? " · disabled" : ""}</div>) : <span>No configured opening in this span.</span>}
    </div>
    <h4>Sections by tier</h4>
    {model.tiers.map(tier => <TierSection key={tier} tier={tier} model={model} onSelectPlacement={onSelectPlacement} />)}
  </section>;
}

function TierSection({ tier, model, onSelectPlacement }: { tier: Tier; model: Model; onSelectPlacement: (uid: string) => void }) {
  const blocks = model.blocks.filter(b => b.tier === tier);
  const rows = Math.max(2, ...blocks.map(b => b.layer)), cols = Math.max(2, ...blocks.map(b => b.position));
  const cellW = 212 / cols, cellH = 56 / rows;
  const reference = model.parents.find(p => p.tier === tier && p.section_reference)?.section_reference ?? model.reference;
  return <div className="tier-section-card">
    <div><b>T{tier} section</b><span>{model.demoMode ? "Demo · ordinal view" : "Ordinal view · not to scale"}</span></div>
    <svg viewBox="0 0 290 104" role="img" aria-label={`Tier ${tier} sectional placement, layer 1 bottom and position 1 innermost`}>
      <text x={52} y={13} fontSize={9}>Inner (1)</text><text x={263} y={13} fontSize={9} textAnchor="end">Outer →</text>
      <path d="M44 21V81H270V21" fill="#f8fafc" stroke="#64748b" strokeWidth={2} />
      <text x={7} y={32} fontSize={8}>Top ↑</text><text x={3} y={79} fontSize={8}>L1 ↓</text>
      {blocks.map(block => {
        const x = 49 + (block.position - 1) * cellW, y = 79 - block.layer * cellH;
        const style = block.cable_class ? CABLE_STYLES[block.cable_class] : { color: "#64748b", label: "Bundle" };
        return <g key={block.uid} role="button" tabIndex={0} aria-label={`Inspect ${block.label}, Tier ${tier}, layer ${block.layer}, position ${block.position}`} onClick={() => onSelectPlacement(block.uid)} onKeyDown={e => { if (e.key === "Enter") onSelectPlacement(block.uid); }}>
          <rect x={x + 2} y={y + 2} width={cellW - 5} height={Math.max(3, cellH - 4)} rx={3} fill={`${style.color}20`} stroke={style.color} strokeWidth={1.5} strokeDasharray={block.demo ? "3 2" : undefined} />
          <text x={x + cellW / 2} y={y + cellH / 2 + 3} textAnchor="middle" fontSize={Math.min(10, cellH * 0.45)} fill="#1e293b">{block.cable_class ?? "Bundle"}</text>
          <title>{block.label} · layer {block.layer} (bottom=1) · position {block.position} (inner=1){block.demo ? " · DEMO ONLY" : !block.sourceAvailable ? " · reference unavailable" : ""}</title>
        </g>;
      })}
      {!blocks.length && <text x={155} y={52} textAnchor="middle" fontSize={10} fill="#64748b">{model.markedClasses[tier]?.length ? "Bundle positions not assigned" : "No bundles assigned"}</text>}
      <text x={49} y={98} fontSize={8}>{reference ? reference.slice(0, 51) : "Inner-side viewing reference not configured"}</text>
    </svg>
    {blocks.map(b => <button className="section-bundle-label" key={b.uid} onClick={() => onSelectPlacement(b.uid)}>{b.label} · L{b.layer} / P{b.position}{!b.sourceAvailable ? " · unresolved" : ""}</button>)}
  </div>;
}

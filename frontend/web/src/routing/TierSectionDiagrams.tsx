import { formatInches } from "./dimensions";
import type { segmentTierModel } from "./segmentTierModel";
import type { ResolvedLayout, Tier } from "./types";
import { SectionOccupationDiagram } from "./SectionOccupationDiagram";

type Model = ReturnType<typeof segmentTierModel>;
export function TierSectionDiagrams({ data, model, onSelectPlacement }: { data: ResolvedLayout; model: Model; onSelectPlacement: (uid: string) => void }) {
  return <section className="tier-sections" aria-label="Tier and bundle section diagrams">
    {model.demoMode && <p className="tier-demo-banner">DEMO placements · Display only. Unset heights remain unknown; openings come from saved records.</p>}
    <h4>Tier diagram</h4>
    {model.measuredBottom != null && <p className="routing-notice">Measured basket bottom: {formatInches(model.measuredBottom)} AFF.{model.measuredTop != null && <> NORTH/SOUTH top: {formatInches(model.measuredTop)} AFF; designate its confirmed T2 or T3 in configuration.</>}</p>}
    {!model.tiers.length ? <p className="routing-notice">No tiers configured for this pathway. Add confirmed tiers below to populate the diagrams.</p> : <svg viewBox="0 0 290 145" role="img" aria-label="Tier diagram, logical layers with explicit physical openings only" className="tier-stack-svg">
      {[...model.tiers].sort((a, b) => b - a).map((tier, index) => {
        const record = model.records.find(r => r.tier === tier), y = 16 + index * 43;
        const elevation = record?.effective_elevation_in ?? record?.elevation_in;
        const blocks = model.blocks.filter(b => b.tier === tier);
        const types = [...new Set([...blocks.map(b => b.cable_class ?? b.label), ...(model.markedClasses[tier] ?? [])])];
        return <g key={tier} opacity={record && !record.enabled ? 0.4 : 1}>
          <text x={5} y={y + 8} fontSize={12} fontWeight={700}>T{tier}</text><line x1={36} x2={281} y1={y + 16} y2={y + 16} stroke="#64748b" strokeWidth={2} />
          <text x={39} y={y + 7} fontSize={9}>{elevation == null ? "Height unknown" : `${formatInches(elevation)} AFF`}{!record ? " · unconfigured" : !record.enabled ? " · disabled" : ""}</text>
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
    {model.tiers.map(tier => <SectionOccupationDiagram key={tier} tier={tier} model={model} onSelectPlacement={onSelectPlacement} />)}
  </section>;
}

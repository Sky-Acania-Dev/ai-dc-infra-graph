import { formatInches } from "./dimensions";
import type { segmentTierModel } from "./segmentTierModel";
import type { ResolvedLayout, Tier } from "./types";
import { SectionOccupationDiagram, type SectionDisplayMode } from "./SectionOccupationDiagram";
import { SectionBundleDetail } from "./SectionBundleDetail";
import { directionName, sectionView } from "./sectionDirections";

type Model = ReturnType<typeof segmentTierModel>;
export function TierSectionDiagrams({ data, model, onSelectPlacement, selectedPlacementUid, mode, onModeChange, reversed, onReverse }: { data: ResolvedLayout; model: Model; onSelectPlacement: (uid: string | null) => void; selectedPlacementUid: string | null; mode: SectionDisplayMode; onModeChange: (mode: SectionDisplayMode) => void; reversed: boolean; onReverse: () => void }) {
  const selected = model.blocks.find(b => b.uid === selectedPlacementUid);
  const parent = model.parents.find(p => p.tier === selected?.tier) ?? model.parents.find(p => p.tier == null);
  const view = sectionView(model.directions, parent?.section_inner_direction, reversed);
  return <section className="tier-sections" aria-label="Tier and bundle section diagrams">
    <h4>Tier diagram</h4>
    {model.measuredBottom != null && <p className="routing-notice">Measured basket bottom: {formatInches(model.measuredBottom)} AFF.{model.measuredTop != null && <> NORTH/SOUTH top: {formatInches(model.measuredTop)} AFF; designate its confirmed T2 or T3 in configuration.</>}</p>}
    {!model.tiers.length ? <p className="routing-notice">No tiers configured for this pathway. Empty section shown without a tier assignment.</p> : <svg viewBox="0 0 290 145" role="img" aria-label="Tier diagram, logical layers with explicit physical openings only" className="tier-stack-svg">
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
    <div className="section-view-controls">
      <div role="group" aria-label="Section display mode"><button aria-pressed={mode === "GRID"} onClick={() => onModeChange("GRID")}>Grid</button><button aria-pressed={mode === "PHYSICAL"} onClick={() => onModeChange("PHYSICAL")}>Physical</button></div>
      <button aria-label="Reverse section viewing direction" aria-pressed={reversed} onClick={onReverse}>⇄ Reverse view</button>
    </div>
    <small className="section-view-caption">{view.from && view.to ? `View ${directionName(view.from)} → ${directionName(view.to)}` : "View direction unset"} · bottom stays down</small>
    {selected && <SectionBundleDetail block={selected} mode={mode} onClose={() => onSelectPlacement(null)} />}
    {(model.tiers.length ? model.tiers : [null]).map(tier => <SectionOccupationDiagram key={tier ?? "unassigned"} tier={tier} model={model} mode={mode} reversed={reversed} selectedPlacementUid={selectedPlacementUid} onSelectPlacement={onSelectPlacement} />)}
  </section>;
}

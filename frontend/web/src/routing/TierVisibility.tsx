import type { Tier } from "./types";

export function TierVisibility({ tiers, onChange }: { tiers: Set<Tier>; onChange: (tiers: Set<Tier>) => void }) {
  return <div className="routing-actions" aria-label="Tier visibility">{([1, 2, 3] as Tier[]).map(tier => <label className={`routing-tier-toggle routing-tier-${tier}`} key={tier}>
    <input type="checkbox" checked={tiers.has(tier)} onChange={event => { const next = new Set(tiers); if (event.target.checked) next.add(tier); else next.delete(tier); onChange(next); }} />
    <span className={`routing-tier-sample tier-${tier}`} />T{tier}
  </label>)}</div>;
}

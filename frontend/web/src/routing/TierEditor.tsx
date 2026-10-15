import type { CrossRouteTier, Mutate, PassageTier, Tier, PathwayType } from "./types";

type Props = { kind: "passage" | "cross"; owner: string; records: Array<PassageTier | CrossRouteTier>; mutate: Mutate; disabled: boolean };
export function TierEditor({ kind, owner, records, mutate, disabled }: Props) {
  const resource = kind === "passage" ? "passage-tiers" : "cross-route-tiers";
  const field = kind === "passage" ? "passage_band_uid" : "cross_route_uid";
  return <div className="routing-tier-editor">
    {([1, 2, 3] as Tier[]).map(tier => {
      const record = records.find(r => r.tier === tier);
      return <div key={tier} className={`routing-tier-${tier}`}>
        <label><input type="checkbox" checked={record?.enabled ?? false} disabled={disabled || !record} onChange={event => {
          if (record) void mutate(resource, { enabled: event.target.checked }, record.uid);
          // New tiers require an explicit pathway type selection below.
        }} />Tier {tier}</label>
        <select aria-label={`Tier ${tier} pathway type`} disabled={disabled} value={record?.pathway_type ?? ""} onChange={event => {
          const pathway_type = event.target.value as PathwayType;
          if (pathway_type) void mutate(resource, record ? { pathway_type } : { [field]: owner, tier, pathway_type, enabled: true }, record?.uid);
        }}>
          <option value="" disabled>Configure type…</option><option value="LADDER_RACK">Ladder rack</option><option value="BASKET_TRAY">Basket tray</option>
        </select>
        {!record && <small>Choose a type to add this tier</small>}
      </div>;
    })}
  </div>;
}

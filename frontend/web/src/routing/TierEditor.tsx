import type { CrossRouteTier, Mutate, PassageTier, Tier, PathwayType } from "./types";
import { useState } from "react";
import { formatInches, parseInches } from "./dimensions";

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
        {record && <TierElevation key={`${record.uid}:${record.elevation_in}`} record={record} resource={resource} mutate={mutate} disabled={disabled} />}
      </div>;
    })}
  </div>;
}

function TierElevation({ record, resource, mutate, disabled }: { record: CrossRouteTier | PassageTier; resource: "passage-tiers" | "cross-route-tiers"; mutate: Mutate; disabled: boolean }) {
  const [value, setValue] = useState(record.elevation_in == null ? "" : formatInches(record.elevation_in));
  const [error, setError] = useState("");
  return <form className="tier-elevation-form" onSubmit={async event => {
    event.preventDefault(); setError("");
    try { await mutate(resource, { elevation_in: value.trim() ? parseInches(value) : null }, record.uid); }
    catch (reason) { setError(String(reason)); }
  }}><label>T{record.tier} elevation above finished floor<input aria-label={`Tier ${record.tier} elevation AFF`} value={value} placeholder="Unknown · ft/in or inches" disabled={disabled} onChange={e => setValue(e.target.value)} /></label>
    <button disabled={disabled}>Save height</button>{error && <small role="alert">{error}</small>}
  </form>;
}

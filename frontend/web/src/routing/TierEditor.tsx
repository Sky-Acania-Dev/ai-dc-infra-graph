import type { CrossRouteTier, Mutate, PassageTier, Tier, PathwayType, RoutingLayout } from "./types";
import { useState } from "react";
import { formatInches, parseInches } from "./dimensions";

type Props = { kind: "passage" | "cross"; owner: string; records: Array<PassageTier | CrossRouteTier>; mutate: Mutate; disabled: boolean; layout?: RoutingLayout; passageCode?: string };
export function TierEditor({ kind, owner, records, mutate, disabled, layout, passageCode }: Props) {
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
          if (pathway_type) void mutate(resource, record ? { pathway_type, ...(record.elevation_reference === "BOTTOM_BASKET" && pathway_type !== "BASKET_TRAY" ? {elevation_reference: null} : {}) } : { [field]: owner, tier, pathway_type, enabled: true }, record?.uid);
        }}>
          <option value="" disabled>Configure type…</option><option value="LADDER_RACK">Ladder rack</option><option value="BASKET_TRAY">Basket tray</option>
        </select>
        {!record && <small>Choose a type to add this tier</small>}
        {record && <TierElevation key={`${record.uid}:${record.elevation_in}:${record.elevation_reference}`} record={record} resource={resource} mutate={mutate} disabled={disabled} layout={layout} allowTop={kind === "passage" && ["NORTH", "SOUTH"].includes(passageCode ?? "") && record.tier > 1} />}
      </div>;
    })}
  </div>;
}

function TierElevation({ record, resource, mutate, disabled, layout, allowTop }: { record: CrossRouteTier | PassageTier; resource: "passage-tiers" | "cross-route-tiers"; mutate: Mutate; disabled: boolean; layout?: RoutingLayout; allowTop: boolean }) {
  const [value, setValue] = useState(record.elevation_in == null ? "" : formatInches(record.elevation_in));
  const [error, setError] = useState("");
  const [reference, setReference] = useState(record.elevation_reference ?? "");
  const referencedHeight = reference === "BOTTOM_BASKET" ? layout?.bottom_basket_elevation_in : layout?.north_south_top_elevation_in;
  return <form className="tier-elevation-form" onSubmit={async event => {
    event.preventDefault(); setError("");
    try { await mutate(resource, { elevation_in: reference ? null : value.trim() ? parseInches(value) : null, elevation_reference: reference || null }, record.uid); }
    catch (reason) { setError(String(reason)); }
  }}><div><label>T{record.tier} elevation source<select aria-label={`Tier ${record.tier} elevation source`} value={reference} disabled={disabled} onChange={e => setReference(e.target.value)}><option value="">Manual / unknown</option>{record.tier === 1 && record.pathway_type === "BASKET_TRAY" && (layout?.bottom_basket_elevation_in != null || reference === "BOTTOM_BASKET") && <option value="BOTTOM_BASKET">Measured bottom basket · {layout?.bottom_basket_elevation_in == null ? "height unset" : `${formatInches(layout.bottom_basket_elevation_in)} AFF`}</option>}{allowTop && (layout?.north_south_top_elevation_in != null || reference === "NORTH_SOUTH_TOP") && <option value="NORTH_SOUTH_TOP">Measured NORTH/SOUTH top · {layout?.north_south_top_elevation_in == null ? "height unset" : `${formatInches(layout.north_south_top_elevation_in)} AFF`}</option>}</select></label><label>T{record.tier} elevation above finished floor<input aria-label={`Tier ${record.tier} elevation AFF`} value={reference ? referencedHeight == null ? "" : formatInches(referencedHeight) : value} placeholder="Unknown · ft/in or inches" disabled={disabled || Boolean(reference)} onChange={e => setValue(e.target.value)} /></label></div>
    <button disabled={disabled}>Save height</button>{error && <small role="alert">{error}</small>}
  </form>;
}

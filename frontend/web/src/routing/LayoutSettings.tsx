import { useState } from "react";
import type { Mutate, ResolvedLayout } from "./types";
import { parseInches, formatInches } from "./dimensions";
import { DimensionInput } from "./SectionSettings";

const DIMENSIONS = [
  ["cabinet_row_depth_in", "Cabinet row depth"], ["hot_aisle_clear_in", "Hot aisle clear"], ["cold_aisle_clear_in", "Cold aisle clear"],
  ["section_extra_gap_in", "Extra section gap"], ["default_cross_route_width_in", "Default cross-route width"],
] as const;
export function LayoutSettings({ data, disabled, mutate }: { data: ResolvedLayout; disabled: boolean; mutate: Mutate }) {
  const [name, setName] = useState(data.layout.name);
  const [count, setCount] = useState(data.layout.cabinets_per_row);
  const [longitudinal, setLongitudinal] = useState(data.layout.longitudinal_direction ?? "");
  const [dimensions, setDimensions] = useState(Object.fromEntries(DIMENSIONS.map(([key]) => [key, formatInches(data.layout[key])])));
  const [error, setError] = useState("");
  const [bottom, setBottom] = useState(data.layout.bottom_basket_elevation_in == null ? "" : formatInches(data.layout.bottom_basket_elevation_in));
  const [top, setTop] = useState(data.layout.north_south_top_elevation_in == null ? "" : formatInches(data.layout.north_south_top_elevation_in));
  return <div>
    <form className="routing-form" onSubmit={event => {
      event.preventDefault();
      try { void mutate("layout", { name, cabinets_per_row: count, longitudinal_direction: longitudinal || null, bottom_basket_elevation_in: bottom.trim() ? parseInches(bottom) : null, north_south_top_elevation_in: top.trim() ? parseInches(top) : null, ...Object.fromEntries(Object.entries(dimensions).map(([key, value]) => [key, parseInches(value)])) }); setError(""); }
      catch (reason) { setError((reason as Error).message); }
    }}>
      <h3>Layout dimensions</h3>
      <label>Name<input value={name} onChange={e => setName(e.target.value)} required /></label>
      <label>Section 1 → 5 direction<select value={longitudinal} onChange={e => setLongitudinal(e.target.value as "EAST" | "WEST" | "")}><option value="">Unconfirmed</option><option value="EAST">East · cabinet-map top is West</option><option value="WEST">West · cabinet-map top is East</option></select></label>
      <label>Cabinets per row<input type="number" min={1} step={1} value={count} onChange={e => setCount(Number(e.target.value))} required /></label>
      {DIMENSIONS.map(([key, label]) => <label key={key}>{label}<input value={dimensions[key]} onChange={e => setDimensions({ ...dimensions, [key]: e.target.value })} required /></label>)}
      <h4>Measured elevations above finished floor</h4><DimensionInput label="Bottom basket tier · all routes" value={bottom} onChange={setBottom} /><DimensionInput label="Top tier · NORTH / SOUTH passages only" value={top} onChange={setTop} />
      <small>Top is a physical role. Designate the confirmed T2 or T3 using its elevation source; no tiers are created by these measurements.</small>
      <small>Row-pair module: {formatInches(data.layout.row_pair_module_in)}. The backend derives the module when row or aisle dimensions change. Row counts come from configured pairs.</small>
      <small>Existing cabinet ranges must match cabinets per row. Changing defaults preserves configured route widths and manual stations.</small>
      {error && <p role="alert" className="routing-error">{error}</p>}
      <button disabled={disabled}>Save dimensions</button>
    </form>
    <h3>Transverse bands</h3>
    {[...data.bands].sort((a, b) => a.ordinal - b.ordinal).map(band => <form className="routing-inline-form" key={`${band.uid}:${band.width_in}`} onSubmit={event => {
      event.preventDefault();
      try { const input = new FormData(event.currentTarget); void mutate("bands", { width_in: parseInches(String(input.get("width"))) }, band.uid); setError(""); }
      catch (reason) { setError((reason as Error).message); }
    }}><label>{band.code}<input name="width" defaultValue={formatInches(band.width_in)} required aria-label={`${band.code} width`} /></label><button disabled={disabled}>Save</button></form>)}
    <h3>Section definitions</h3>
    {[...data.sections].sort((a, b) => a.ordinal - b.ordinal).map(section => <form className="routing-inline-form" key={`${section.uid}:${section.name}`} onSubmit={event => {
      event.preventDefault(); const input = new FormData(event.currentTarget); void mutate("sections", { name: input.get("name") }, section.uid);
    }}><label>Section {section.ordinal}<input name="name" defaultValue={section.name} required /><small>{section.room_uid ?? "No existing room linked"}</small></label><button disabled={disabled}>Save</button></form>)}
  </div>;
}

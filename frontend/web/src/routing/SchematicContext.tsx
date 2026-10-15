import type { ResolvedLayout, Selection } from "./types";
import { formatInches } from "./dimensions";

type Props = { data: ResolvedLayout; scale: number; selection: Selection; onSelect: (selection: Selection) => void };
export function SchematicContext({ data, scale, selection, onSelect }: Props) {
  const g = data.geometry;
  const fields = g.bands.filter(b => b.kind === "ROW_FIELD");
  const font = 11 / scale;
  return <g className="routing-context">
    {g.sections.map(section => <g key={section.uid}>
      <rect x={section.start_in} y={0} width={section.end_in - section.start_in} height={g.total_width_in} fill={section.ordinal % 2 ? "var(--routing-section-a)" : "var(--routing-section-b)"} />
      <text x={(section.start_in + section.end_in) / 2} y={-35 / scale} textAnchor="middle" fontSize={font} fontWeight="700">{section.name}</text>
    </g>)}
    {g.gaps.map((gap, index) => <g key={gap.after_section_uid}>
      <rect x={gap.start_in} y={0} width={gap.end_in - gap.start_in} height={g.total_width_in} fill="url(#routing-gap-hatch)" />
      <text x={gap.center_in} y={-15 / scale} textAnchor="middle" fontSize={10 / scale}>{formatInches(gap.end_in - gap.start_in)}</text>
      <title>{`Section ${index + 1}-${index + 2}: extra ${formatInches(gap.end_in - gap.start_in)}; passages continue through gap`}</title>
    </g>)}
    {g.cold_aisles.map((aisle, index) => {
      const field = fields.find(f => f.uid === aisle.row_field_band_uid)!;
      return <g key={index}>
        <rect x={aisle.start_in} y={field.start_in} width={aisle.end_in - aisle.start_in} height={field.width_in} fill="var(--routing-cold)" />
        {scale > 0.3 && <text transform={`translate(${(aisle.start_in + aisle.end_in) / 2} ${field.center_in}) rotate(-90)`} textAnchor="middle" fontSize={11 / scale}>COLD AISLE {formatInches(aisle.end_in - aisle.start_in)}</text>}
      </g>;
    })}
    {g.row_pairs.map(pair => {
      const field = fields.find(f => f.uid === pair.row_field_band_uid)!;
      return <g key={pair.uid}>
        <rect x={pair.hot_aisle_start_in} y={field.start_in} width={pair.hot_aisle_end_in - pair.hot_aisle_start_in} height={field.width_in} fill="url(#routing-hot-hatch)" />
        {scale > 0.3 && <text transform={`translate(${(pair.hot_aisle_start_in + pair.hot_aisle_end_in) / 2} ${field.center_in}) rotate(-90)`} textAnchor="middle" fontSize={10 / scale}>HOT AISLE {formatInches(data.layout.hot_aisle_clear_in)} · NON-ROUTING</text>}
      </g>;
    })}
    {g.cabinet_rows.map(row => {
      const field = fields.find(f => f.uid === row.row_field_band_uid)!;
      return <g key={row.uid} data-selectable="true" tabIndex={0} role="button" aria-label={`Select ${row.name}`} onClick={event => { event.stopPropagation(); onSelect({ kind: "row", uid: row.uid }); }} onKeyDown={event => { if (event.key === "Enter") onSelect({ kind: "row", uid: row.uid }); }}>
        <rect x={row.start_in} y={field.start_in} width={row.end_in - row.start_in} height={field.width_in} className={`routing-cabinet ${selection?.kind === "row" && selection.uid === row.uid ? "selected" : ""}`} opacity={row.enabled ? 1 : 0.35} vectorEffect="non-scaling-stroke" />
        {scale > 0.4 && <text className="routing-row-label" transform={`translate(${row.center_in} ${field.center_in}) rotate(-90)`} textAnchor="middle" fontSize={9 / scale}>{row.name} · {row.position_in_pair}</text>}
        <title>{`${row.name} · ${row.position_in_pair} · ${field.code} · ${row.enabled ? "Enabled" : "Disabled"}`}</title>
      </g>;
    })}
  </g>;
}

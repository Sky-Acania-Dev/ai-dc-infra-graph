import type { KeyboardEvent, MouseEvent } from "react";
import { categoryColor } from "../colors";
import type { CabinetTile } from "./cabinetPlacement";
import type { RoutingCabinet } from "./types";

export type CabinetInteraction = {
  selected: Set<string>; connected?: Set<string>;
  onSelect: (cabinet: RoutingCabinet, event: MouseEvent<SVGGElement> | KeyboardEvent<SVGGElement>) => void;
  onPrefetch?: (uid: string) => void;
};
export function CabinetLayer({ tiles, scale, interaction, horizontal = false }: { tiles: CabinetTile[]; scale: number; interaction: CabinetInteraction; horizontal?: boolean }) {
  return <g className="routing-inventory" aria-label="Existing cabinet inventory">
    {tiles.map(tile => {
      const { cabinet, x, y, width, height } = tile;
      const selected = interaction.selected.has(cabinet.cabinet_uid), connected = interaction.connected?.has(cabinet.cabinet_uid);
      const labelSize = horizontal ? Math.min(11 / scale, height * 0.7, width / (cabinet.cabinet_id.length * 0.65 + 0.5))
        : Math.min(11 / scale, width * 0.55, height / Math.max(2.5, cabinet.cabinet_id.length * 0.65));
      return <g key={cabinet.cabinet_uid} data-selectable="true" role="button" tabIndex={0} aria-label={`Select cabinet ${cabinet.cabinet_id} in ${cabinet.data_hall_id}`}
        className={`routing-inventory-cabinet ${selected ? "selected" : ""} ${connected ? "connected" : ""}`} opacity={tile.enabled ? 1 : 0.35}
        onClick={event => { event.stopPropagation(); interaction.onSelect(cabinet, event); }}
        onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.stopPropagation(); interaction.onSelect(cabinet, event); } }}
        onFocus={() => interaction.onPrefetch?.(cabinet.cabinet_uid)}>
        <rect className="routing-inventory-tile" x={x + 1} y={y + 1} width={width - 2} height={height - 2} rx={1} vectorEffect="non-scaling-stroke" />
        <rect x={horizontal ? x + 1 : x + width - 4} y={horizontal ? y + height - 4 : y + 1} width={horizontal ? width - 2 : 3} height={horizontal ? 3 : height - 2} fill={categoryColor(cabinet.category)} pointerEvents="none" />
        {labelSize * scale >= 5.5 && <text transform={`translate(${x + width / 2} ${y + height / 2})${horizontal ? "" : " rotate(-90)"}`} textAnchor="middle" dominantBaseline="central" fontSize={labelSize}>{cabinet.cabinet_id}</text>}
        <title>{`${cabinet.cabinet_id} · ${cabinet.category} · ${cabinet.cabinet_group}\n${cabinet.cabinet_uid}`}</title>
      </g>;
    })}
  </g>;
}

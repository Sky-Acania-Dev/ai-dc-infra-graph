import { categoryColor, labelColors } from "../colors";
import type { CabinetLayoutItem } from "../types";

type PositionedCabinet = CabinetLayoutItem & {
  block: number;
  row: number;
  col: number;
};

type CabinetMapProps = {
  cabinets: CabinetLayoutItem[];
  selectedCabinetUid: string | null;
  connectedCabinetUids: Set<string>;
  onSelectCabinet: (cabinetUid: string) => void;
};

const CELL_WIDTH = 34;
const CELL_HEIGHT = 22;
const BLOCK_GAP = 52;
const HOT_AISLE_GAP = 8;
const COLD_AISLE_GAP = 26;
const PADDING = 24;

export function CabinetMap({ cabinets, selectedCabinetUid, connectedCabinetUids, onSelectCabinet }: CabinetMapProps) {
  const positioned = normalizeCabinets(cabinets);
  const maxBlock = Math.max(...positioned.map((cabinet) => cabinet.block), 0);
  const maxRow = Math.max(...positioned.map((cabinet) => cabinet.row), 0);
  const width = PADDING * 2 + (maxBlock + 1) * 10 * CELL_WIDTH + maxBlock * BLOCK_GAP;
  const height = PADDING * 2 + rowY(maxRow) + CELL_HEIGHT;
  const hasSelection = Boolean(selectedCabinetUid);

  return (
    <section className="map-pane">
      <div className="pane-header">
        <div>
          <span className="eyebrow">Cabinet Map</span>
          <h2>{cabinets[0]?.data_hall_id ?? "Data Hall"}</h2>
        </div>
      </div>
      <div className="map-scroll">
        <svg className="cabinet-map" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img">
          {positioned.map((cabinet) => {
            const fill = categoryColor(cabinet.category);
            const label = labelColors(fill);
            const x = PADDING + cabinet.block * (10 * CELL_WIDTH + BLOCK_GAP) + cabinet.col * CELL_WIDTH;
            const y = PADDING + rowY(cabinet.row);
            const isSelected = cabinet.cabinet_uid === selectedCabinetUid;
            const isConnected = connectedCabinetUids.has(cabinet.cabinet_uid);
            const isDimmed = hasSelection && !isSelected && !isConnected;

            return (
              <g
                key={cabinet.cabinet_uid}
                className={`map-cabinet ${isSelected ? "is-selected" : ""} ${isConnected ? "is-connected" : ""} ${isDimmed ? "is-dimmed" : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => onSelectCabinet(cabinet.cabinet_uid)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onSelectCabinet(cabinet.cabinet_uid);
                }}
              >
                <rect x={x} y={y} width={CELL_WIDTH - 2} height={CELL_HEIGHT - 2} fill={fill}>
                  <title>{`${cabinet.cabinet_uid}\n${cabinet.category}\n${cabinet.cabinet_group}`}</title>
                </rect>
                <text className="cabinet-id" x={x + 16} y={y + 8} fill={label.fill} stroke={label.stroke}>
                  {cabinet.cabinet_id}
                </text>
                <text className="cabinet-type" x={x + 16} y={y + 17} fill={label.fill} stroke={label.stroke}>
                  {cabinet.category}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}

function normalizeCabinets(cabinets: CabinetLayoutItem[]): PositionedCabinet[] {
  const rows = [...new Set(cabinets.map((cabinet) => cabinet.source_row ?? 0))].sort((a, b) => a - b);
  return rows.flatMap((sourceRow, rowIndex) => {
    const rowCabinets = cabinets
      .filter((cabinet) => (cabinet.source_row ?? 0) === sourceRow)
      .sort((a, b) => (a.source_col ?? 0) - (b.source_col ?? 0));

    return rowCabinets.map((cabinet, index) => ({
      ...cabinet,
      block: Math.floor(index / 10),
      row: rowIndex,
      col: index % 10,
    }));
  });
}

function rowY(rowIndex: number): number {
  let y = 0;
  for (let row = 0; row < rowIndex; row += 1) {
    y += CELL_HEIGHT;
    y += row % 2 === 0 ? HOT_AISLE_GAP : COLD_AISLE_GAP;
  }
  return y;
}

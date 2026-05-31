import { categoryColor, labelColors } from "../colors";
import { useI18n } from "../i18n";
import type { CabinetLayoutItem } from "../types";

type PositionedCabinet = CabinetLayoutItem & {
  block: number;
  row: number;
  col: number;
};

type CabinetMapProps = {
  cabinets: CabinetLayoutItem[];
  selectedCabinetUid: string | null;
  selectedDeviceCabinetUid: string | null;
  connectedCabinetUids: Set<string>;
  isDeviceMode: boolean;
  mapSize: MapSize;
  onSelectCabinet: (cabinetUid: string) => void;
  onClearSelection: () => void;
  onMapSizeChange: (mapSize: MapSize) => void;
};

export type MapSize = "compact" | "normal" | "large";

const MAP_SIZE_SETTINGS: Record<
  MapSize,
  {
    label: string;
    cellWidth: number;
    cellHeight: number;
    blockGap: number;
    hotAisleGap: number;
    coldAisleGap: number;
    cabinetIdFontSize: number;
    cabinetTypeFontSize: number;
  }
> = {
  compact: {
    label: "S",
    cellWidth: 28,
    cellHeight: 18,
    blockGap: 42,
    hotAisleGap: 6,
    coldAisleGap: 20,
    cabinetIdFontSize: 6,
    cabinetTypeFontSize: 3.4,
  },
  normal: {
    label: "M",
    cellWidth: 34,
    cellHeight: 22,
    blockGap: 52,
    hotAisleGap: 8,
    coldAisleGap: 26,
    cabinetIdFontSize: 7,
    cabinetTypeFontSize: 4,
  },
  large: {
    label: "L",
    cellWidth: 44,
    cellHeight: 28,
    blockGap: 66,
    hotAisleGap: 10,
    coldAisleGap: 34,
    cabinetIdFontSize: 8.5,
    cabinetTypeFontSize: 5.2,
  },
};
const PADDING = 24;

export function CabinetMap({
  cabinets,
  selectedCabinetUid,
  selectedDeviceCabinetUid,
  connectedCabinetUids,
  isDeviceMode,
  mapSize,
  onSelectCabinet,
  onClearSelection,
  onMapSizeChange,
}: CabinetMapProps) {
  const { t } = useI18n();
  const settings = MAP_SIZE_SETTINGS[mapSize];
  const positioned = normalizeCabinets(cabinets);
  const maxBlock = Math.max(...positioned.map((cabinet) => cabinet.block), 0);
  const maxRow = Math.max(...positioned.map((cabinet) => cabinet.row), 0);
  const width = PADDING * 2 + (maxBlock + 1) * 10 * settings.cellWidth + maxBlock * settings.blockGap;
  const height = PADDING * 2 + rowY(maxRow, settings) + settings.cellHeight;
  const hasSelection = Boolean(selectedCabinetUid);

  return (
    <section className="map-pane">
      <div className="pane-header">
        <div>
          <span className="eyebrow">{t("map.cabinetMap")}</span>
          <h2>{cabinets[0]?.data_hall_id ?? t("dataHall.fallback")}</h2>
        </div>
        <div className="map-size-control" aria-label={t("map.size")}>
          {(Object.keys(MAP_SIZE_SETTINGS) as MapSize[]).map((size) => (
            <button className={size === mapSize ? "is-active" : ""} key={size} onClick={() => onMapSizeChange(size)}>
              {MAP_SIZE_SETTINGS[size].label}
            </button>
          ))}
        </div>
      </div>
      <div className="map-scroll">
        <svg
          className="cabinet-map"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          onClick={onClearSelection}
        >
          {positioned.map((cabinet) => {
            const fill = categoryColor(cabinet.category);
            const label = labelColors(fill);
            const x =
              PADDING +
              cabinet.block * (10 * settings.cellWidth + settings.blockGap) +
              cabinet.col * settings.cellWidth;
            const y = PADDING + rowY(cabinet.row, settings);
            const isSelected = cabinet.cabinet_uid === selectedCabinetUid;
            const isDeviceSource = isDeviceMode && cabinet.cabinet_uid === selectedDeviceCabinetUid;
            const isConnected = connectedCabinetUids.has(cabinet.cabinet_uid);
            const isDimmed = hasSelection && !isSelected && !isConnected;

            return (
              <g
                key={cabinet.cabinet_uid}
                className={`map-cabinet ${isSelected ? "is-selected" : ""} ${isDeviceSource ? "is-device-source" : ""} ${isConnected ? "is-connected" : ""} ${isDimmed ? "is-dimmed" : ""}`}
                role="button"
                tabIndex={0}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectCabinet(cabinet.cabinet_uid);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onSelectCabinet(cabinet.cabinet_uid);
                }}
              >
                <rect x={x} y={y} width={settings.cellWidth - 2} height={settings.cellHeight - 2} fill={fill}>
                  <title>{`${cabinet.cabinet_uid}\n${cabinet.category}\n${cabinet.cabinet_group}`}</title>
                </rect>
                <text
                  className="cabinet-id"
                  x={x + (settings.cellWidth - 2) / 2}
                  y={y + settings.cellHeight * 0.38}
                  fill={label.fill}
                  stroke={label.stroke}
                  style={{ fontSize: settings.cabinetIdFontSize }}
                >
                  {cabinet.cabinet_id}
                </text>
                <text
                  className="cabinet-type"
                  x={x + (settings.cellWidth - 2) / 2}
                  y={y + settings.cellHeight * 0.78}
                  fill={label.fill}
                  stroke={label.stroke}
                  style={{ fontSize: settings.cabinetTypeFontSize }}
                >
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

function rowY(rowIndex: number, settings: (typeof MAP_SIZE_SETTINGS)[MapSize]): number {
  let y = 0;
  for (let row = 0; row < rowIndex; row += 1) {
    y += settings.cellHeight;
    y += row % 2 === 0 ? settings.hotAisleGap : settings.coldAisleGap;
  }
  return y;
}

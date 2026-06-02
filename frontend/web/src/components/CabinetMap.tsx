import { categoryColor, labelColors } from "../colors";
import { useDragPan } from "../hooks/useDragPan";
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
  progressDisplay: MapProgressDisplay;
  onSelectCabinet: (cabinetUid: string) => void;
  onClearSelection: () => void;
  onMapSizeChange: (mapSize: MapSize) => void;
  onProgressDisplayChange: (progressDisplay: MapProgressDisplay) => void;
};

export type MapSize = "compact" | "normal" | "large";
export type MapProgressDisplay = "text" | "termination" | "dress";

const MAP_SIZE_SETTINGS: Record<
  MapSize,
  {
    labelKey: string;
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
    labelKey: "map.size.compact",
    cellWidth: 34,
    cellHeight: 22,
    blockGap: 48,
    hotAisleGap: 8,
    coldAisleGap: 24,
    cabinetIdFontSize: 9,
    cabinetTypeFontSize: 6.2,
  },
  normal: {
    labelKey: "map.size.normal",
    cellWidth: 46,
    cellHeight: 30,
    blockGap: 62,
    hotAisleGap: 10,
    coldAisleGap: 32,
    cabinetIdFontSize: 12,
    cabinetTypeFontSize: 8,
  },
  large: {
    labelKey: "map.size.large",
    cellWidth: 58,
    cellHeight: 38,
    blockGap: 78,
    hotAisleGap: 12,
    coldAisleGap: 40,
    cabinetIdFontSize: 15,
    cabinetTypeFontSize: 10,
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
  progressDisplay,
  onSelectCabinet,
  onClearSelection,
  onMapSizeChange,
  onProgressDisplayChange,
}: CabinetMapProps) {
  const { t } = useI18n();
  const settings = MAP_SIZE_SETTINGS[mapSize];
  const positioned = normalizeCabinets(cabinets);
  const maxBlock = Math.max(...positioned.map((cabinet) => cabinet.block), 0);
  const maxRow = Math.max(...positioned.map((cabinet) => cabinet.row), 0);
  const width = PADDING * 2 + (maxBlock + 1) * 10 * settings.cellWidth + maxBlock * settings.blockGap;
  const height = PADDING * 2 + rowY(maxRow, settings) + settings.cellHeight;
  const hasSelection = Boolean(selectedCabinetUid);
  const mapPan = useDragPan<HTMLDivElement>();

  return (
    <section className="map-pane">
      <div className="pane-header">
        <div>
          <span className="eyebrow">{t("map.cabinetMap")}</span>
          <h2>{cabinets[0]?.data_hall_id ?? t("dataHall.fallback")}</h2>
        </div>
        <div className="map-controls">
          <div className="map-size-control" aria-label={t("map.display")}>
            {(["text", "termination", "dress"] as MapProgressDisplay[]).map((display) => (
              <button
                className={display === progressDisplay ? "is-active" : ""}
                key={display}
                onClick={() => onProgressDisplayChange(display)}
              >
                {display === "text" ? t("map.displayType") : display === "termination" ? t("map.displayTermination") : t("map.displayDress")}
              </button>
            ))}
          </div>
          <div className="map-size-control" aria-label={t("map.size")}>
            {(Object.keys(MAP_SIZE_SETTINGS) as MapSize[]).map((size) => (
              <button className={size === mapSize ? "is-active" : ""} key={size} onClick={() => onMapSizeChange(size)}>
                {t(MAP_SIZE_SETTINGS[size].labelKey)}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="map-scroll drag-pan-surface" {...mapPan}>
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
                <rect className="cabinet-rect" x={x} y={y} width={settings.cellWidth - 2} height={settings.cellHeight - 2} fill={fill}>
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
                  {progressDisplay === "text" ? cabinet.category : ""}
                </text>
                {progressDisplay !== "text" ? (
                  <ProgressBar
                    x={x + 2}
                    y={y + settings.cellHeight * 0.58}
                    width={settings.cellWidth - 5}
                    height={Math.max(4, settings.cellHeight * 0.22)}
                    percent={
                      progressDisplay === "termination"
                        ? cabinet.cable_termination_percent
                        : cabinet.cable_dress_percent
                    }
                    fontSize={settings.cabinetTypeFontSize}
                  />
                ) : null}
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

function ProgressBar({
  x,
  y,
  width,
  height,
  percent,
  fontSize,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
  percent: number;
  fontSize: number;
}) {
  const clamped = Math.min(100, Math.max(0, percent));
  const label = `${Math.round(clamped)}%`;
  const labelWidth = Math.max(7, fontSize * 3.3);
  const gap = 1;
  const barX = x + labelWidth + gap;
  const barWidth = Math.max(2, width - labelWidth - gap);
  return (
    <g className="map-progress-bar">
      <text x={x} y={y + height - 0.5} style={{ fontSize }}>
        {label}
      </text>
      <rect className="map-progress-bg" x={barX} y={y} width={barWidth} height={height} />
      <rect
        className="map-progress-fill"
        x={barX}
        y={y}
        width={(barWidth * clamped) / 100}
        height={height}
        fill={progressColor(clamped)}
      />
    </g>
  );
}

function progressColor(percent: number): string {
  if (percent < 25) return "#ef4444";
  if (percent < 50) return "#f97316";
  if (percent < 75) return "#eab308";
  return "#22c55e";
}

import { categoryColor, labelColors } from "../colors";
import { useDragPan } from "../hooks/useDragPan";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { useI18n } from "../i18n";
import type { CabinetLayoutItem } from "../types";
import type { SelectionGesture } from "../App";
import { ViewerScaleSlider } from "./ViewerScaleSlider";

type PositionedCabinet = CabinetLayoutItem & {
  block: number;
  row: number;
  col: number;
};

type CabinetMapProps = {
  cabinets: CabinetLayoutItem[];
  connectedDataHalls: Set<string>;
  dataHall: string;
  dataHalls: string[];
  selectedCabinetUid: string | null;
  selectedCabinetUids: Set<string>;
  selectedDeviceCabinetUid: string | null;
  connectedCabinetUids: Set<string>;
  connectedCabinetCounts: Map<string, number>;
  isDeviceMode: boolean;
  mapSize: MapSize;
  progressDisplay: MapProgressDisplay;
  onSelectCabinet: (cabinetUid: string, gesture: SelectionGesture) => void;
  onClearSelection: () => void;
  onDataHallChange: (dataHall: string) => void;
  onMapSizeChange: (mapSize: MapSize) => void;
  onProgressDisplayChange: (progressDisplay: MapProgressDisplay) => void;
};

export type MapSize = "xsmall" | "small" | "medium" | "large" | "xlarge";
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
  xsmall: {
    labelKey: "map.size.xsmall",
    cellWidth: 34,
    cellHeight: 22,
    blockGap: 48,
    hotAisleGap: 8,
    coldAisleGap: 24,
    cabinetIdFontSize: 9,
    cabinetTypeFontSize: 6.2,
  },
  small: {
    labelKey: "map.size.small",
    cellWidth: 40,
    cellHeight: 26,
    blockGap: 54,
    hotAisleGap: 9,
    coldAisleGap: 28,
    cabinetIdFontSize: 10.5,
    cabinetTypeFontSize: 7.2,
  },
  medium: {
    labelKey: "map.size.medium",
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
  xlarge: {
    labelKey: "map.size.xlarge",
    cellWidth: 70,
    cellHeight: 46,
    blockGap: 94,
    hotAisleGap: 14,
    coldAisleGap: 48,
    cabinetIdFontSize: 18,
    cabinetTypeFontSize: 12,
  },
};
const LANDSCAPE_MAP_SIZE_SETTINGS: Record<MapSize, (typeof MAP_SIZE_SETTINGS)[MapSize]> = {
  xsmall: {
    labelKey: "map.size.xsmall",
    cellWidth: 18,
    cellHeight: 12,
    blockGap: 24,
    hotAisleGap: 4,
    coldAisleGap: 12,
    cabinetIdFontSize: 5.8,
    cabinetTypeFontSize: 3.8,
  },
  small: {
    labelKey: "map.size.small",
    cellWidth: 23,
    cellHeight: 15,
    blockGap: 31,
    hotAisleGap: 5,
    coldAisleGap: 15,
    cabinetIdFontSize: 6.6,
    cabinetTypeFontSize: 4.4,
  },
  medium: {
    labelKey: "map.size.medium",
    cellWidth: 28,
    cellHeight: 18,
    blockGap: 38,
    hotAisleGap: 6,
    coldAisleGap: 18,
    cabinetIdFontSize: 7.4,
    cabinetTypeFontSize: 5,
  },
  large: {
    labelKey: "map.size.large",
    cellWidth: 36,
    cellHeight: 24,
    blockGap: 48,
    hotAisleGap: 8,
    coldAisleGap: 24,
    cabinetIdFontSize: 9.4,
    cabinetTypeFontSize: 6.4,
  },
  xlarge: {
    labelKey: "map.size.xlarge",
    cellWidth: 44,
    cellHeight: 30,
    blockGap: 58,
    hotAisleGap: 10,
    coldAisleGap: 30,
    cabinetIdFontSize: 11.2,
    cabinetTypeFontSize: 7.4,
  },
};
const PADDING = 24;
const MAP_SIZE_STEPS: Array<{ value: MapSize; labelKey: string }> = [
  { value: "xsmall", labelKey: "map.size.xsmall" },
  { value: "small", labelKey: "map.size.small" },
  { value: "medium", labelKey: "map.size.medium" },
  { value: "large", labelKey: "map.size.large" },
  { value: "xlarge", labelKey: "map.size.xlarge" },
];

export function CabinetMap({
  cabinets,
  connectedDataHalls,
  dataHall,
  dataHalls,
  selectedCabinetUid,
  selectedCabinetUids,
  selectedDeviceCabinetUid,
  connectedCabinetUids,
  connectedCabinetCounts,
  isDeviceMode,
  mapSize,
  progressDisplay,
  onSelectCabinet,
  onClearSelection,
  onDataHallChange,
  onMapSizeChange,
  onProgressDisplayChange,
}: CabinetMapProps) {
  const { t } = useI18n();
  const isPhoneLandscape = useMediaQuery("(max-width: 1100px) and (min-width: 760px) and (orientation: landscape)");
  const settings = isPhoneLandscape ? LANDSCAPE_MAP_SIZE_SETTINGS[mapSize] : MAP_SIZE_SETTINGS[mapSize];
  const positioned = normalizeCabinets(cabinets);
  const maxBlock = Math.max(...positioned.map((cabinet) => cabinet.block), 0);
  const maxRow = Math.max(...positioned.map((cabinet) => cabinet.row), 0);
  const width = PADDING * 2 + (maxBlock + 1) * 10 * settings.cellWidth + maxBlock * settings.blockGap;
  const height = PADDING * 2 + rowY(maxRow, settings) + settings.cellHeight;
  const hasSelection = selectedCabinetUids.size > 0;
  const mapPan = useDragPan<HTMLDivElement>();

  return (
    <section className="map-pane">
      <div className="pane-header">
        <div>
          <span className="eyebrow">{t("map.cabinetMap")}</span>
          <h2>{cabinets[0]?.data_hall_id ?? t("dataHall.fallback")}</h2>
        </div>
        <div className="map-controls">
          <div className="map-size-control" role="tablist" aria-label={t("dataHall.selector")}>
            {dataHalls.map((hall) => (
              <button
                className={`${hall === dataHall ? "is-active" : ""} ${connectedDataHalls.has(hall) && hall !== dataHall ? "has-graph-neighbor" : ""}`}
                key={hall}
                onClick={() => onDataHallChange(hall)}
              >
                {hall}
              </button>
            ))}
          </div>
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
          <ViewerScaleSlider
            label={t("viewer.scale")}
            onChange={onMapSizeChange}
            steps={MAP_SIZE_STEPS.map((step) => ({ value: step.value, label: t(step.labelKey) }))}
            value={mapSize}
          />
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
            const isSelected = selectedCabinetUids.has(cabinet.cabinet_uid);
            const isPrimarySelected = cabinet.cabinet_uid === selectedCabinetUid;
            const isDeviceSource = isDeviceMode && cabinet.cabinet_uid === selectedDeviceCabinetUid;
            const isConnected = connectedCabinetUids.has(cabinet.cabinet_uid);
            const connectedSourceCount = connectedCabinetCounts.get(cabinet.cabinet_uid) ?? 0;
            const showConnectionCount = connectedSourceCount > 1;
            const isDimmed = hasSelection && !isSelected && !isConnected;
            const cabinetTypeLabel = progressDisplay === "text" ? cabinet.category : "";
            const cabinetTypeFit = fitSvgText(
              cabinetTypeLabel,
              settings.cabinetTypeFontSize,
              settings.cellWidth - 6,
            );

            return (
              <g
                key={cabinet.cabinet_uid}
                className={`map-cabinet ${isSelected ? "is-selected" : ""} ${isPrimarySelected ? "is-primary-selected" : ""} ${isDeviceSource ? "is-device-source" : ""} ${isConnected ? "is-connected" : ""} ${isDimmed ? "is-dimmed" : ""}`}
                role="button"
                tabIndex={0}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectCabinet(cabinet.cabinet_uid, event);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onSelectCabinet(cabinet.cabinet_uid, event);
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
                  textLength={cabinetTypeFit.textLength}
                  lengthAdjust="spacingAndGlyphs"
                  style={{ fontSize: cabinetTypeFit.fontSize }}
                >
                  {cabinetTypeLabel}
                </text>
                {progressDisplay !== "text" ? (
                  <ProgressBar
                    x={x + 2}
                    y={y + settings.cellHeight * 0.53}
                    width={settings.cellWidth - 4}
                    height={Math.max(6, settings.cellHeight * 0.32)}
                    percent={
                      progressDisplay === "termination"
                        ? cabinet.cable_termination_percent
                        : cabinet.cable_dress_percent
                    }
                    fontSize={settings.cabinetTypeFontSize}
                  />
                ) : null}
                {showConnectionCount ? (
                  <ConnectionCountBadge
                    count={connectedSourceCount}
                    x={x + settings.cellWidth - 2}
                    y={y}
                    cellHeight={settings.cellHeight}
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

function fitSvgText(text: string, fontSize: number, maxWidth: number): { fontSize: number; textLength?: number } {
  if (!text) return { fontSize };

  const estimatedWidth = estimateSvgTextWidth(text, fontSize);
  if (estimatedWidth <= maxWidth) return { fontSize };

  const compressedWidth = estimatedWidth * 0.8;
  if (compressedWidth <= maxWidth) {
    return { fontSize, textLength: Math.max(1, compressedWidth) };
  }

  const fittedFontSize = Math.max(4.5, fontSize * (maxWidth / compressedWidth));
  return { fontSize: fittedFontSize, textLength: Math.max(1, maxWidth) };
}

function estimateSvgTextWidth(text: string, fontSize: number): number {
  const narrowChars = text.match(/[I1il|.,:;\-]/g)?.length ?? 0;
  const wideChars = text.match(/[MW@#%&]/g)?.length ?? 0;
  const normalChars = Math.max(0, text.length - narrowChars - wideChars);
  return fontSize * (normalChars * 0.58 + narrowChars * 0.32 + wideChars * 0.78);
}

function ConnectionCountBadge({
  count,
  x,
  y,
  cellHeight,
  fontSize,
}: {
  count: number;
  x: number;
  y: number;
  cellHeight: number;
  fontSize: number;
}) {
  const label = String(count);
  const radius = Math.max(5, Math.min(9, cellHeight * 0.28));
  const badgeFontSize = Math.max(6, Math.min(fontSize + 1, radius * 1.18));
  return (
    <g className="cabinet-connection-count" aria-label={`${label} selected cabinets connected`}>
      <circle cx={x - radius * 0.35} cy={y + radius * 0.35} r={radius} />
      <text
        dominantBaseline="central"
        textAnchor="middle"
        x={x - radius * 0.35}
        y={y + radius * 0.35}
        style={{ fontSize: badgeFontSize }}
      >
        {label}
      </text>
    </g>
  );
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
  const labelFontSize = Math.min(fontSize, Math.max(5, height * 0.58));
  return (
    <g className="map-progress-bar">
      <rect className="map-progress-bg" x={x} y={y} width={width} height={height} rx={1.5} />
      <rect
        className="map-progress-fill"
        x={x}
        y={y}
        width={(width * clamped) / 100}
        height={height}
        rx={1.5}
        fill={progressColor(clamped)}
      />
      <text
        dominantBaseline="central"
        textAnchor="middle"
        x={x + width / 2}
        y={y + height / 2}
        style={{ fontSize: labelFontSize }}
      >
        {label}
      </text>
    </g>
  );
}

function progressColor(percent: number): string {
  if (percent < 25) return "#ef4444";
  if (percent < 50) return "#f97316";
  if (percent < 75) return "#eab308";
  return "#22c55e";
}

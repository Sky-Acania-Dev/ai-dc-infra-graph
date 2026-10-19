import { lazy, Suspense, useState } from "react";
import { useDragPan } from "../hooks/useDragPan";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { useI18n } from "../i18n";
import type { CabinetLayoutItem, ChangeOrderCabinetStats } from "../types";
import type { SelectionGesture } from "../App";
import { CabinetGraphics } from "./CabinetGraphics";
import { ViewerScaleSlider } from "./ViewerScaleSlider";
const CabinetRoutingMap = lazy(() => import("../routing/CabinetRoutingMap").then(module => ({default: module.CabinetRoutingMap})));

type PositionedCabinet = CabinetLayoutItem & {
  block: number;
  row: number;
  col: number;
};

type NormalizedCabinetLayout = {
  cabinets: PositionedCabinet[];
};

export type DataHallBadgeCounts = {
  count: number;
  added: number;
  removed: number;
};

export type CabinetMapProps = {
  canManage: boolean;
  routingInspectorHost: HTMLDivElement | null;
  pathwayInspectorHost: HTMLDivElement | null;
  onRoutingInspectorActiveChange: (active: boolean) => void;
  onPathwayInspectorActiveChange: (active: boolean) => void;
  project: string;
  building: string;
  onOpenRouting: () => void;
  showRoutes: boolean;
  onShowRoutesChange: (show: boolean) => void;
  cabinets: CabinetLayoutItem[];
  connectedDataHallCounts: Map<string, number>;
  dataHallBadges?: Map<string, DataHallBadgeCounts>;
  dataHall: string;
  dataHalls: string[];
  selectedCabinetUid: string | null;
  selectedCabinetUids: Set<string>;
  selectedDeviceCabinetUid: string | null;
  connectedCabinetUids: Set<string>;
  connectedCabinetCounts: Map<string, number>;
  addedCabinetUids: Set<string>;
  removedCabinetUids: Set<string>;
  addedConnectedCabinetCounts: Map<string, number>;
  reducedConnectedCabinetCounts: Map<string, number>;
  lostConnectedCabinetUids: Set<string>;
  isDeviceMode: boolean;
  isDataLoading: boolean;
  mapSize: MapSize;
  progressDisplay: MapProgressDisplay;
  changeOrderStats: Map<string, ChangeOrderCabinetStats>;
  changeOrderOptions: Array<{ key: string; number: number; label: string }>;
  selectedChangeOrderNumbers: Set<number>;
  modeHint?: string | null;
  onChangeOrderSelectionChange: (changeOrderNumbers: number[]) => void;
  onSelectCabinet: (cabinetUid: string, gesture: SelectionGesture) => void;
  onPrefetchCabinet: (cabinetUid: string) => void;
  onClearSelection: () => void;
  onDataHallChange: (dataHall: string) => void;
  onMapSizeChange: (mapSize: MapSize) => void;
  onProgressDisplayChange: (progressDisplay: MapProgressDisplay) => void;
};

export type MapSize = "xsmall" | "small" | "medium" | "large" | "xlarge";
export type MapProgressDisplay = "text" | "termination" | "dress" | "change_orders";

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
    cellWidth: 10,
    cellHeight: 7,
    blockGap: 14,
    hotAisleGap: 3,
    coldAisleGap: 8,
    cabinetIdFontSize: 3.8,
    cabinetTypeFontSize: 2.6,
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

export function CabinetMap(props: CabinetMapProps) {
  const {
    project, building, onOpenRouting, showRoutes, onShowRoutesChange, cabinets,
    connectedDataHallCounts, dataHallBadges, dataHall, dataHalls,
    selectedCabinetUids, connectedCabinetUids, isDataLoading, mapSize,
    progressDisplay, changeOrderOptions, selectedChangeOrderNumbers, modeHint,
    onChangeOrderSelectionChange, onSelectCabinet, onPrefetchCabinet,
    onClearSelection, onDataHallChange, onMapSizeChange, onProgressDisplayChange,
  } = props;
  const { t } = useI18n();
  const [tierHost, setTierHost] = useState<HTMLDivElement | null>(null);
  const isPhoneLandscape = useMediaQuery("(max-width: 1100px) and (orientation: landscape)");
  const settings = isPhoneLandscape ? LANDSCAPE_MAP_SIZE_SETTINGS[mapSize] : MAP_SIZE_SETTINGS[mapSize];
  const normalizedLayout = normalizeCabinets(cabinets);
  const positioned = normalizedLayout.cabinets;
  const maxBlock = Math.max(...positioned.map((cabinet) => cabinet.block), 0);
  const maxRow = Math.max(...positioned.map((cabinet) => cabinet.row), 0);
  const width = PADDING * 2 + (maxBlock + 1) * 10 * settings.cellWidth + maxBlock * settings.blockGap;
  const height = PADDING * 2 + rowY(maxRow, settings) + settings.cellHeight;
  const mapPan = useDragPan<HTMLDivElement>();
  const positions = positioned.map(cabinet => ({ cabinet,
    x: PADDING + cabinet.block * (10 * settings.cellWidth + settings.blockGap) + cabinet.col * settings.cellWidth,
    y: PADDING + rowY(cabinet.row, settings),
  }));

  return (
    <section className="map-pane">
      <div className="pane-header cabinet-map-header">
        <div className="map-title-line">
          <h2>{cabinets[0]?.data_hall_id ?? t("dataHall.fallback")}</h2>
          {showRoutes && <div className="map-tier-host" ref={setTierHost} />}
          <span>{modeHint ?? t("map.cabinetMap")}</span>
        </div>
        <div className="map-controls" role="group" aria-label="Cabinet map controls" tabIndex={0}>
          <div className="map-size-control" role="group" aria-label="Cabinet map layers">
            <label className="map-route-toggle"><input type="checkbox" aria-label="Show conceptual routes" checked={showRoutes} onChange={event => onShowRoutesChange(event.target.checked)} />Conceptual routes</label>
          </div>
          <div className="map-size-control" role="tablist" aria-label={t("dataHall.selector")}>
            {dataHalls.map((hall) => {
              const graphNeighborCount = hall === dataHall ? 0 : connectedDataHallCounts.get(hall) ?? 0;
              const badgeCounts = dataHallBadges?.get(hall);
              const badgeLabel = dataHallBadgeLabel(badgeCounts) ?? (graphNeighborCount > 0 ? String(graphNeighborCount) : null);
              const hasBadge = Boolean(badgeLabel);
              const hasPositiveDelta = (badgeCounts?.added ?? 0) > 0;
              const hasNegativeDelta = (badgeCounts?.removed ?? 0) > 0;
              return (
                <button
                  className={`${hall === dataHall ? "is-active" : ""} ${hasBadge ? "has-graph-neighbor" : ""} ${hasPositiveDelta ? "has-positive-delta" : ""} ${hasNegativeDelta ? "has-negative-delta" : ""}`}
                  key={hall}
                  onClick={() => onDataHallChange(hall)}
                >
                  <span>{hall}</span>
                  {badgeLabel ? <b className="data-hall-graph-count">{badgeLabel}</b> : null}
                </button>
              );
            })}
          </div>
          <div className="map-size-control" aria-label={t("map.display")}>
            {(["text", "termination", "dress", "change_orders"] as MapProgressDisplay[]).map((display) => (
              <button
                className={display === progressDisplay ? "is-active" : ""}
                key={display}
                onClick={() => onProgressDisplayChange(display)}
              >
                {display === "text" ? t("map.displayType") : display === "termination" ? t("map.displayTermination") : display === "dress" ? t("map.displayDress") : "CO"}
              </button>
            ))}
          </div>
          {progressDisplay === "change_orders" ? (
            <ChangeOrderFilter
              onChange={onChangeOrderSelectionChange}
              options={changeOrderOptions}
              selectedNumbers={selectedChangeOrderNumbers}
            />
          ) : null}
          <ViewerScaleSlider
            label={t("viewer.scale")}
            onChange={onMapSizeChange}
            steps={MAP_SIZE_STEPS.map((step) => ({ value: step.value, label: t(step.labelKey) }))}
            value={mapSize}
          />
        </div>
      </div>
      {isDataLoading ? (
        <div className="map-loading-overlay" aria-live="polite" aria-atomic="true">
          <span className="map-loading-spinner" aria-hidden="true" />
          <span>{t("map.loadingData")}</span>
        </div>
      ) : null}
      {showRoutes ? <Suspense fallback={<p className="empty-state">Loading routing map…</p>}><CabinetRoutingMap project={project} building={building} hall={dataHall} selected={selectedCabinetUids} connected={connectedCabinetUids}
        inspectorHost={props.routingInspectorHost} onInspectorActiveChange={props.onRoutingInspectorActiveChange}
        onPathwayInspectorActiveChange={props.onPathwayInspectorActiveChange}
        pathwayInspectorHost={props.pathwayInspectorHost}
        tierHost={tierHost}
        canManage={props.canManage} cabinets={cabinets} settings={settings}
        renderCabinets={(positions, clearPath) => <CabinetGraphics {...props} positions={positions} settings={settings}
          onSelectCabinet={(uid, gesture) => { clearPath(); onSelectCabinet(uid, gesture); }} />}
        onSelectCabinet={onSelectCabinet} onPrefetchCabinet={onPrefetchCabinet} onClearSelection={onClearSelection} onOpenRouting={onOpenRouting} /></Suspense> : <div className="map-scroll drag-pan-surface" {...mapPan}>
        <svg
          className="cabinet-map"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          onClick={onClearSelection}
        >
          <CabinetGraphics {...props} positions={positions} settings={settings} />
        </svg>
      </div>}
    </section>
  );
}

function dataHallBadgeLabel(counts: DataHallBadgeCounts | undefined): string | null {
  if (!counts) return null;
  const parts: string[] = [];
  if (counts.count > 0) parts.push(String(counts.count));
  if (counts.added > 0) parts.push(`+${counts.added}`);
  if (counts.removed > 0) parts.push(`-${counts.removed}`);
  return parts.length ? parts.join("") : null;
}

function normalizeCabinets(cabinets: CabinetLayoutItem[]): NormalizedCabinetLayout {
  const columnBlocks = sourceColumnBlocks(cabinets);
  const rowGroups = sourceRowGroups(cabinets, columnBlocks);
  const positioned = rowGroups.flatMap((sourceRows, rowIndex) => {
    const rowCabinets = cabinets
      .filter((cabinet) => sourceRows.includes(cabinet.source_row ?? 0))
      .sort((a, b) => (a.source_col ?? 0) - (b.source_col ?? 0));

    return rowCabinets.map((cabinet, index) => {
      const sourceCol = cabinet.source_col ?? 0;
      const block = columnBlocks.findIndex(({ start, end }) => sourceCol >= start && sourceCol <= end);
      const normalizedBlock = block >= 0 ? block : Math.floor(index / 10);
      const normalizedCol = block >= 0 ? sourceCol - columnBlocks[block].start : index % 10;
      return {
        ...cabinet,
        block: normalizedBlock,
        row: rowIndex,
        col: normalizedCol,
      };
    });
  });
  return { cabinets: positioned };
}

function sourceColumnBlocks(cabinets: CabinetLayoutItem[]): Array<{ start: number; end: number }> {
  const columns = [...new Set(cabinets.map((cabinet) => cabinet.source_col).filter((column): column is number => column !== null && column !== undefined && column > 0))].sort(
    (a, b) => a - b,
  );
  const blocks: Array<{ start: number; end: number }> = [];
  for (const column of columns) {
    const current = blocks.at(-1);
    if (!current || column > current.end) {
      blocks.push({ start: column, end: column + 9 });
    }
  }
  return blocks;
}

function sourceRowGroups(
  cabinets: CabinetLayoutItem[],
  columnBlocks: Array<{ start: number; end: number }>,
): number[][] {
  const blocksByRow = new Map<number, Set<number>>();
  for (const cabinet of cabinets) {
    const sourceRow = cabinet.source_row ?? 0;
    const sourceCol = cabinet.source_col ?? 0;
    const block = columnBlocks.findIndex(({ start, end }) => sourceCol >= start && sourceCol <= end);
    const rowBlocks = blocksByRow.get(sourceRow) ?? new Set<number>();
    if (block >= 0) rowBlocks.add(block);
    blocksByRow.set(sourceRow, rowBlocks);
  }

  const rowGroups: number[][] = [];
  for (const sourceRow of [...blocksByRow.keys()].sort((a, b) => a - b)) {
    const previousGroup = rowGroups.at(-1);
    const previousRow = previousGroup?.at(-1);
    const previousBlocks = previousRow === undefined ? undefined : blocksByRow.get(previousRow);
    const currentBlocks = blocksByRow.get(sourceRow);
    const previousIsLeftOnly = previousBlocks?.size === 1 && previousBlocks.has(0);
    const previousIsRightOnly = previousBlocks !== undefined && previousBlocks.size > 0 && [...previousBlocks].every((block) => block > 0);
    const currentIsLeftOnly = currentBlocks?.size === 1 && currentBlocks.has(0);
    const currentIsRightOnly = currentBlocks !== undefined && currentBlocks.size > 0 && [...currentBlocks].every((block) => block > 0);
    const isAdjacentComplement =
      previousRow !== undefined &&
      sourceRow === previousRow + 1 &&
      ((previousIsLeftOnly && currentIsRightOnly) || (previousIsRightOnly && currentIsLeftOnly));

    if (isAdjacentComplement && previousGroup) {
      previousGroup.push(sourceRow);
    } else {
      rowGroups.push([sourceRow]);
    }
  }
  return rowGroups;
}

function rowY(rowIndex: number, settings: (typeof MAP_SIZE_SETTINGS)[MapSize]): number {
  let y = 0;
  for (let row = 0; row < rowIndex; row += 1) {
    y += settings.cellHeight;
    y += row % 2 === 0 ? settings.hotAisleGap : settings.coldAisleGap;
  }
  return y;
}

function ChangeOrderFilter({
  options,
  selectedNumbers,
  onChange,
}: {
  options: Array<{ key: string; number: number; label: string }>;
  selectedNumbers: Set<number>;
  onChange: (changeOrderNumbers: number[]) => void;
}) {
  const selectedLabel = selectedNumbers.size === 0 ? "All COs" : [...selectedNumbers].sort((a, b) => a - b).map((number) => `#${number}`).join(", ");
  const selectionCount = selectedNumbers.size === 0 ? options.length : selectedNumbers.size;

  function toggle(number: number, checked: boolean) {
    const next = new Set(selectedNumbers);
    if (checked) next.add(number);
    else next.delete(number);
    onChange([...next].sort((a, b) => a - b));
  }

  return (
    <details className="map-change-order-filter" onClick={(event) => event.stopPropagation()}>
      <summary>
        <span className="map-change-order-filter-title">Change Orders</span>
        <span className="map-change-order-filter-value">{selectedLabel}</span>
        <span className="map-change-order-filter-count">{selectionCount}</span>
      </summary>
      <div className="map-change-order-menu">
        <label>
          <input checked={selectedNumbers.size === 0} onChange={() => onChange([])} type="checkbox" />
          <span>All change orders</span>
        </label>
        {options.map((option) => (
          <label key={option.key}>
            <input
              checked={selectedNumbers.has(option.number)}
              onChange={(event) => toggle(option.number, event.target.checked)}
              type="checkbox"
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </details>
  );
}


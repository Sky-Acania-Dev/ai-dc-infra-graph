import { useEffect, useRef } from "react";
import { categoryColor, labelColors } from "../colors";
import type { CabinetLayoutItem, ChangeOrderCabinetStats } from "../types";
import type { CabinetMapProps } from "./CabinetMap";

export type CabinetGraphicPosition = { cabinet: CabinetLayoutItem; x: number; y: number };
export type CabinetGraphicSettings = { cellWidth: number; cellHeight: number; cabinetIdFontSize: number; cabinetTypeFontSize: number };
type Props = Pick<CabinetMapProps, "selectedCabinetUid" | "selectedCabinetUids" | "selectedDeviceCabinetUid" | "connectedCabinetUids" | "connectedCabinetCounts" | "addedCabinetUids" | "removedCabinetUids" | "addedConnectedCabinetCounts" | "reducedConnectedCabinetCounts" | "lostConnectedCabinetUids" | "isDeviceMode" | "progressDisplay" | "changeOrderStats" | "onSelectCabinet" | "onPrefetchCabinet"> & { positions: CabinetGraphicPosition[]; settings: CabinetGraphicSettings };

// Shared by the standard cabinet map and its conceptual routing view.
export function CabinetGraphics({ positions, settings, selectedCabinetUid, selectedCabinetUids, selectedDeviceCabinetUid,
  connectedCabinetUids, connectedCabinetCounts, addedCabinetUids, removedCabinetUids,
  addedConnectedCabinetCounts, reducedConnectedCabinetCounts, lostConnectedCabinetUids,
  isDeviceMode, progressDisplay, changeOrderStats, onSelectCabinet, onPrefetchCabinet }: Props) {
  const hasSelection = selectedCabinetUids.size > 0;
  const primaryFrame = positions.find(p => p.cabinet.cabinet_uid === selectedCabinetUid);
  const prefetchTimeoutRef = useRef<number | null>(null);
  useEffect(() => () => {
    if (prefetchTimeoutRef.current !== null) window.clearTimeout(prefetchTimeoutRef.current);
  }, []);
  function clearCabinetPrefetch() {
    if (prefetchTimeoutRef.current !== null) window.clearTimeout(prefetchTimeoutRef.current);
    prefetchTimeoutRef.current = null;
  }
  function scheduleCabinetPrefetch(uid: string) {
    clearCabinetPrefetch();
    prefetchTimeoutRef.current = window.setTimeout(() => { prefetchTimeoutRef.current = null; onPrefetchCabinet(uid); }, 250);
  }
  return <g className="cabinet-graphics">
          {positions.map(({ cabinet, x, y }) => {
            const fill = categoryColor(cabinet.category);
            const label = labelColors(fill);
            const isSelected = selectedCabinetUids.has(cabinet.cabinet_uid);
            const isDeviceSource = isDeviceMode && cabinet.cabinet_uid === selectedDeviceCabinetUid;
            const isAdded = addedCabinetUids.has(cabinet.cabinet_uid);
            const isRemoved = removedCabinetUids.has(cabinet.cabinet_uid);
            const isLostConnection = lostConnectedCabinetUids.has(cabinet.cabinet_uid);
            const reducedConnectionCount = reducedConnectedCabinetCounts.get(cabinet.cabinet_uid) ?? 0;
            const isReducedConnection = reducedConnectionCount > 0;
            const connectedSourceCount = connectedCabinetCounts.get(cabinet.cabinet_uid) ?? 0;
            const addedConnectionCount = addedConnectedCabinetCounts.get(cabinet.cabinet_uid) ?? 0;
            const isConnected = connectedCabinetUids.has(cabinet.cabinet_uid);
            const showConnectionCount = connectedSourceCount > 0 || addedConnectionCount > 0 || reducedConnectionCount > 0;
            const isAddedOnlyNeighbor = addedConnectionCount > 0 && connectedSourceCount === 0 && !isSelected && !isAdded && !isRemoved;
            const isDimmed = (hasSelection && !isSelected && !isConnected) || isAdded || isAddedOnlyNeighbor || (isLostConnection && !isSelected);
            const cabinetChangeStats = changeOrderStats.get(cabinet.cabinet_uid) ?? emptyChangeOrderStats();
            const cabinetTypeLabel = progressDisplay === "text" ? cabinet.category : "";
            const cabinetTypeFit = fitSvgText(
              cabinetTypeLabel,
              settings.cabinetTypeFontSize,
              settings.cellWidth - 6,
            );

            return (
              <g
                key={cabinet.cabinet_uid}
                className={`map-cabinet ${isSelected ? "is-selected" : ""} ${isAdded ? "is-added-selection" : ""} ${isRemoved ? "is-removed-selection" : ""} ${isConnected ? "is-connected" : ""} ${addedConnectionCount > 0 ? "is-added-connected" : ""} ${isLostConnection ? "is-lost-connection" : ""} ${isReducedConnection ? "is-reduced-connection" : ""} ${isDeviceSource ? "is-device-source" : ""} ${isDimmed ? "is-dimmed" : ""}`}
                data-selectable="true"
                aria-label={`Select cabinet ${cabinet.cabinet_id} in ${cabinet.data_hall_id}`}
                role="button"
                tabIndex={0}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectCabinet(cabinet.cabinet_uid, event);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onSelectCabinet(cabinet.cabinet_uid, event);
                }}
                onFocus={() => onPrefetchCabinet(cabinet.cabinet_uid)}
                onPointerEnter={() => scheduleCabinetPrefetch(cabinet.cabinet_uid)}
                onPointerLeave={clearCabinetPrefetch}
              >
                <rect className="cabinet-rect" x={x} y={y} width={settings.cellWidth - 2} height={settings.cellHeight - 2} fill={fill}>
                  <title>{`${cabinet.cabinet_uid}\n${cabinet.category}\n${cabinet.cabinet_group}`}</title>
                </rect>
                <rect
                  className="cabinet-state-frame"
                  x={x - 1}
                  y={y - 1}
                  width={settings.cellWidth}
                  height={settings.cellHeight}
                  rx={Math.max(3, settings.cellHeight * 0.14)}
                />
                <rect
                  className="cabinet-neighbor-frame"
                  x={x}
                  y={y}
                  width={settings.cellWidth - 2}
                  height={settings.cellHeight - 2}
                />
                <text
                  className="cabinet-id"
                  x={x + (settings.cellWidth - 2) / 2}
                  y={y + settings.cellHeight * 0.38}
                  fill={label.fill}
                  stroke={label.stroke}
                  style={{ fontSize: settings.cabinetIdFontSize, fill: label.fill }}
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
                  style={{ fontSize: cabinetTypeFit.fontSize, fill: label.fill }}
                >
                  {cabinetTypeLabel}
                </text>
                {progressDisplay !== "text" && (progressDisplay !== "change_orders" || cabinetChangeStats.total > 0) ? (
                  <ProgressBar
                    x={x + 2}
                    y={y + settings.cellHeight * 0.53}
                    width={settings.cellWidth - 4}
                    height={Math.max(6, settings.cellHeight * 0.32)}
                    percent={
                      progressDisplay === "termination"
                        ? cabinet.cable_termination_percent
                        : progressDisplay === "dress"
                          ? cabinet.cable_dress_percent
                          : changeOrderPercent(cabinetChangeStats)
                    }
                    fontSize={settings.cabinetTypeFontSize}
                    label={progressDisplay === "change_orders" ? `${cabinetChangeStats.completed}/${cabinetChangeStats.total}` : undefined}
                  />
                ) : null}

              </g>
            );
          })}
          {primaryFrame ? (
            <rect
              className="cabinet-primary-frame"
              x={primaryFrame.x - 1.6}
              y={primaryFrame.y - 1.6}
              width={settings.cellWidth + 1.2}
              height={settings.cellHeight + 1.2}
              rx={Math.max(3.5, settings.cellHeight * 0.16)}
            />
          ) : null}
          {positions.map(({ cabinet, x, y }) => {
            const reducedConnectionCount = reducedConnectedCabinetCounts.get(cabinet.cabinet_uid) ?? 0;
            const isReducedConnection = reducedConnectionCount > 0;
            const connectedSourceCount = connectedCabinetCounts.get(cabinet.cabinet_uid) ?? 0;
            const addedConnectionCount = addedConnectedCabinetCounts.get(cabinet.cabinet_uid) ?? 0;
            const showConnectionCount = connectedSourceCount > 0 || addedConnectionCount > 0 || reducedConnectionCount > 0;
            return showConnectionCount ? (
              <ConnectionCountBadge
                addedCount={addedConnectionCount}
                count={isReducedConnection ? reducedConnectionCount : connectedSourceCount}
                isReduced={isReducedConnection}
                isAddedOnly={connectedSourceCount === 0 && !isReducedConnection && addedConnectionCount > 0}
                key={`badge:${cabinet.cabinet_uid}`}
                x={x + settings.cellWidth - 2}
                y={y}
                cellHeight={settings.cellHeight}
                fontSize={settings.cabinetTypeFontSize}
              />
            ) : null;
          })}
  </g>;
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
  addedCount = 0,
  count,
  isAddedOnly,
  isReduced,
  x,
  y,
  cellHeight,
  fontSize,
}: {
  addedCount?: number;
  count: number;
  isAddedOnly: boolean;
  isReduced: boolean;
  x: number;
  y: number;
  cellHeight: number;
  fontSize: number;
}) {
  const label = addedCount > 0 && count > 0 ? `${count}+${addedCount}` : String(count || addedCount);
  const radius = Math.max(5, Math.min(10, cellHeight * 0.3, 5 + label.length * 2.1));
  const badgeFontSize = Math.max(6, Math.min(fontSize + 1, radius * 0.95));
  return (
    <g className={`cabinet-connection-count ${isAddedOnly ? "is-added-only" : ""} ${isReduced ? "is-reduced" : ""}`.trim()} aria-label={`${label} connected cabinets`}>
      <circle cx={x - radius * 0.35} cy={y + radius * 0.35} r={radius} />
      <text
        dominantBaseline="central"
        textAnchor="middle"
        x={x - radius * 0.35}
        y={y + radius * 0.35}
        style={{ fontSize: badgeFontSize }}
      >
        {count > 0 ? <tspan className="active-count">{count}</tspan> : null}
        {addedCount > 0 ? <tspan className="added-count">{count > 0 ? `+${addedCount}` : addedCount}</tspan> : null}
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
  label,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
  percent: number;
  fontSize: number;
  label?: string;
}) {
  const clamped = Math.min(100, Math.max(0, percent));
  const displayLabel = label ?? `${Math.round(clamped)}%`;
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
        {displayLabel}
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
function emptyChangeOrderStats(): ChangeOrderCabinetStats {
  return { completed: 0, total: 0, added: 0, changed: 0, removed: 0, replaced: 0 };
}

function changeOrderPercent(stats: ChangeOrderCabinetStats): number {
  return stats.total > 0 ? (stats.completed / stats.total) * 100 : 0;
}

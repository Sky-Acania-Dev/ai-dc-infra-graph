import { useEffect } from "react";
import { useDragPan } from "../hooks/useDragPan";
import type { Device } from "../types";
import { useI18n } from "../i18n";
import type { SelectionGesture } from "../App";

type CabinetDeviceLayoutProps = {
  devices: Device[];
  maxRackUnit: number;
  selectedDeviceUid: string | null;
  selectedDeviceUids: string[];
  scrollRequest: number;
  connectedDeviceUids: Set<string>;
  onSelectDevice: (device: Device, gesture: SelectionGesture) => void;
  onViewPortLayout: (device: Device) => void;
  activePortLayoutDeviceUid: string | null;
  onShowCabinetMap: () => void;
  canEdit: boolean;
  lifecycleStatuses: string[];
  onDeviceStatusChange: (device: Device, lifecycleStatus: string) => void;
};

export function CabinetDeviceLayout({
  devices,
  maxRackUnit,
  selectedDeviceUid,
  selectedDeviceUids,
  scrollRequest,
  connectedDeviceUids,
  onSelectDevice,
  onViewPortLayout,
  activePortLayoutDeviceUid,
  onShowCabinetMap,
  canEdit,
  lifecycleStatuses,
  onDeviceStatusChange,
}: CabinetDeviceLayoutProps) {
  const { formatConstructionPhase, formatLifecycleStatus, formatNumber, t } = useI18n();
  const rackGridPan = useDragPan<HTMLDivElement>();
  const selectedDeviceUidSet = new Set(selectedDeviceUids);
  const devicesByRu = new Map<number, Device[]>();
  for (const device of devices) {
    devicesByRu.set(device.rack_unit, [...(devicesByRu.get(device.rack_unit) ?? []), device]);
  }
  const rackUnits = Array.from({ length: maxRackUnit }, (_, index) => maxRackUnit - index);
  const baseRowMinHeights = new Map<number, number>();
  for (const [rackUnit, unitDevices] of devicesByRu.entries()) {
    baseRowMinHeights.set(rackUnit, baseRackRowMinHeight(unitDevices, canEdit));
  }
  const rackGridTemplateRows = rackUnits.map((rackUnit) => `${baseRowMinHeights.get(rackUnit) ?? 24}px`).join(" ");

  useEffect(() => {
    if (!scrollRequest || !selectedDeviceUid || !rackGridPan.ref.current) return;
    const rackGrid = rackGridPan.ref.current;
    const selectedElement = rackGrid.querySelector<HTMLElement>(
      `[data-device-uid="${cssEscape(selectedDeviceUid)}"]`,
    );
    if (!selectedElement) return;

    const targetElement = selectedElement.closest<HTMLElement>(".rack-device-span") ?? selectedElement;
    const containerRect = rackGrid.getBoundingClientRect();
    const targetRect = targetElement.getBoundingClientRect();
    const targetTop =
      rackGrid.scrollTop + targetRect.top - containerRect.top - (rackGrid.clientHeight - targetRect.height) / 2;
    rackGrid.scrollTo({ behavior: "smooth", top: Math.max(0, targetTop) });
  }, [devices, rackGridPan.ref, scrollRequest, selectedDeviceUid]);

  return (
    <section className="device-layout">
      <div className="section-title">{t("rack.units")}</div>
      <div
        className="rack-grid drag-pan-surface"
        style={{ gridTemplateRows: rackGridTemplateRows }}
        {...rackGridPan}
      >
        {rackUnits.map((rackUnit) => (
          <span
            className="rack-unit"
            key={`unit-${rackUnit}`}
            style={{
              gridColumn: 1,
              gridRow: rackRow(maxRackUnit, rackUnit),
              minHeight: `${baseRowMinHeights.get(rackUnit) ?? 24}px`,
            }}
          >
            {t("rack.unitLabel", { unit: rackUnit })}
          </span>
        ))}
        {rackUnits.map((rackUnit) => (
          <div
            className="rack-slot"
            key={`slot-${rackUnit}`}
            style={{
              gridColumn: 2,
              gridRow: rackRow(maxRackUnit, rackUnit),
              minHeight: `${baseRowMinHeights.get(rackUnit) ?? 24}px`,
            }}
          />
        ))}
        {Array.from(devicesByRu.entries()).map(([rackUnit, unitDevices]) => {
          const span = Math.max(...unitDevices.map((device) => deviceRackUnits(device)), 1);
          const topRackUnit = Math.min(maxRackUnit, rackUnit + span - 1);
          const rowStart = rackRow(maxRackUnit, topRackUnit);
          return (
            <div
              className="rack-device-span"
              key={rackUnit}
              style={{ gridColumn: 2, gridRow: `${rowStart} / span ${topRackUnit - rackUnit + 1}` }}
            >
              {unitDevices.map((device, index) => renderDeviceChip({
                canEdit,
                connectedDeviceUids,
                device,
                formatConstructionPhase,
                formatLifecycleStatus,
                formatNumber,
                index,
                lifecycleStatuses,
                onDeviceStatusChange,
                onSelectDevice,
                onViewPortLayout,
                activePortLayoutDeviceUid,
                onShowCabinetMap,
                selectedDeviceUid,
                selectedDeviceUidSet,
                t,
              }))}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function portCount(device: Device): number {
  return Object.values(device.ports_by_type).reduce((total, ports) => total + (ports?.length ?? 0), 0);
}

function deviceRackUnits(device: Device): number {
  return Math.max(1, Number(device.rack_units ?? 1));
}

function baseRackRowMinHeight(devices: Device[], canEdit: boolean): number {
  const rowGap = Math.max(0, devices.length - 1) * 2;
  const contentHeight = devices.reduce(
    (total, device) => total + baseRowDeviceHeight(device, canEdit),
    rowGap + 4,
  );
  return Math.max(24, contentHeight);
}

function baseRowDeviceHeight(device: Device, canEdit: boolean): number {
  const occupiedUpperRowHeight = Math.max(0, deviceRackUnits(device) - 1) * 24;
  return Math.max(24, estimatedDeviceChipHeight(device, canEdit) - occupiedUpperRowHeight);
}

function estimatedDeviceChipHeight(device: Device, canEdit: boolean): number {
  let height = 42;
  if (deviceRackUnits(device) > 1) height += 14;
  if (device.aliases.length || device.model_aliases.length) height += 14;
  height += canEdit ? 32 : 14;
  return height;
}

function formatRackUnitSpan(device: Device): string {
  const rackUnits = deviceRackUnits(device);
  const topRackUnit = device.rack_unit + rackUnits - 1;
  return `${rackUnits}U, U${topRackUnit}-U${device.rack_unit}`;
}

function deviceKey(device: Device): string {
  return `${device.cabinet_id}:${device.rack_unit}`;
}

function rackRow(maxRackUnit: number, rackUnit: number): number {
  return maxRackUnit - rackUnit + 1;
}

type DeviceChipRenderArgs = {
  canEdit: boolean;
  connectedDeviceUids: Set<string>;
  device: Device;
  formatConstructionPhase: (value: string) => string;
  formatLifecycleStatus: (value: string) => string;
  formatNumber: (value: number) => string;
  index: number;
  lifecycleStatuses: string[];
  onDeviceStatusChange: (device: Device, lifecycleStatus: string) => void;
  onSelectDevice: (device: Device, gesture: SelectionGesture) => void;
  onViewPortLayout: (device: Device) => void;
  activePortLayoutDeviceUid: string | null;
  onShowCabinetMap: () => void;
  selectedDeviceUid: string | null;
  selectedDeviceUidSet: Set<string>;
  t: (key: string, values?: Record<string, string | number>) => string;
};

function renderDeviceChip({
  canEdit,
  connectedDeviceUids,
  device,
  formatConstructionPhase,
  formatLifecycleStatus,
  formatNumber,
  index,
  lifecycleStatuses,
  onDeviceStatusChange,
  onSelectDevice,
  onViewPortLayout,
  activePortLayoutDeviceUid,
  onShowCabinetMap,
  selectedDeviceUid,
  selectedDeviceUidSet,
  t,
}: DeviceChipRenderArgs) {
  const deviceUid = deviceKey(device);
  const isPortLayoutActive = activePortLayoutDeviceUid === deviceUid;
  const isSelected = selectedDeviceUidSet.has(deviceUid);
  const isPrimarySelected = selectedDeviceUid === deviceUid;
  return (
    <div
      className={`device-chip ${isSelected ? "is-selected" : ""} ${isPrimarySelected ? "is-primary-selected" : ""} ${connectedDeviceUids.has(deviceUid) ? "is-connected" : ""}`}
      data-device-uid={deviceUid}
      key={`${device.rack_unit}-${device.device_model}-${index}`}
      onClick={(event) => {
        event.stopPropagation();
        onSelectDevice(device, event);
      }}
      role="button"
      tabIndex={0}
      title={`${formatConstructionPhase(device.construction_phase)}\n${formatLifecycleStatus(device.lifecycle_status)}${device.note ? `\n${device.note}` : ""}`}
    >
      <span>{device.device_model}</span>
      {deviceRackUnits(device) > 1 ? <small className="device-ru-span">{formatRackUnitSpan(device)}</small> : null}
      <small className="device-phase">{formatConstructionPhase(device.construction_phase)}</small>
      {device.aliases.length || device.model_aliases.length ? (
        <em>{[...device.aliases, ...device.model_aliases].join(", ")}</em>
      ) : null}
      {canEdit ? (
        <select
          className="inline-select device-status-select"
          value={device.lifecycle_status}
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => onDeviceStatusChange(device, event.target.value)}
        >
          {lifecycleStatuses.map((status) => (
            <option key={status} value={status}>
              {formatLifecycleStatus(status)}
            </option>
          ))}
        </select>
      ) : (
        <small>
          {t("device.statusAndPorts", {
            count: formatNumber(portCount(device)),
            status: formatLifecycleStatus(device.lifecycle_status),
          })}
        </small>
      )}
      <button
        aria-label={t("device.viewPortLayout")}
        className={`device-layout-button ${isPortLayoutActive ? "is-active" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (isPortLayoutActive) {
            onShowCabinetMap();
            return;
          }
          onViewPortLayout(device);
        }}
        title={t("device.viewPortLayout")}
        type="button"
      >
        {isPortLayoutActive ? (
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        ) : (
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
            <circle cx="12" cy="12" r="2.5" />
          </svg>
        )}
      </button>
    </div>
  );
}

function cssEscape(value: string) {
  if (typeof CSS !== "undefined" && CSS.escape) return CSS.escape(value);
  return value.replace(/["\\]/g, "\\$&");
}

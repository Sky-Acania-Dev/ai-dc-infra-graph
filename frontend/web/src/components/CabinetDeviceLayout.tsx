import { useEffect } from "react";
import { useDragPan } from "../hooks/useDragPan";
import type { Device } from "../types";
import { useI18n } from "../i18n";

type CabinetDeviceLayoutProps = {
  devices: Device[];
  maxRackUnit: number;
  selectedDeviceUid: string | null;
  connectedDeviceUids: Set<string>;
  onSelectDevice: (device: Device) => void;
  canEdit: boolean;
  lifecycleStatuses: string[];
  onDeviceStatusChange: (device: Device, lifecycleStatus: string) => void;
};

export function CabinetDeviceLayout({
  devices,
  maxRackUnit,
  selectedDeviceUid,
  connectedDeviceUids,
  onSelectDevice,
  canEdit,
  lifecycleStatuses,
  onDeviceStatusChange,
}: CabinetDeviceLayoutProps) {
  const { formatLifecycleStatus, formatNumber, t } = useI18n();
  const rackGridPan = useDragPan<HTMLDivElement>();
  const devicesByRu = new Map<number, Device[]>();
  for (const device of devices) {
    devicesByRu.set(device.rack_unit, [...(devicesByRu.get(device.rack_unit) ?? []), device]);
  }

  useEffect(() => {
    if (!selectedDeviceUid || !rackGridPan.ref.current) return;
    const selectedElement = rackGridPan.ref.current.querySelector<HTMLElement>(
      `[data-device-uid="${cssEscape(selectedDeviceUid)}"]`,
    );
    selectedElement?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [devices, rackGridPan.ref, selectedDeviceUid]);

  return (
    <section className="device-layout">
      <div className="section-title">{t("rack.units")}</div>
      <div className="rack-grid drag-pan-surface" {...rackGridPan}>
        {Array.from({ length: maxRackUnit }, (_, index) => maxRackUnit - index).map((rackUnit) => {
          const unitDevices = devicesByRu.get(rackUnit) ?? [];
          return (
            <div className={`rack-row ${unitDevices.length ? "has-device" : ""}`} key={rackUnit}>
              <span className="rack-unit">{t("rack.unitLabel", { unit: rackUnit })}</span>
              <div className="rack-device">
                {unitDevices.map((device, index) => {
                  const deviceUid = deviceKey(device);
                  return (
                    <div
                      className={`device-chip ${selectedDeviceUid === deviceUid ? "is-selected" : ""} ${connectedDeviceUids.has(deviceUid) ? "is-connected" : ""}`}
                      data-device-uid={deviceUid}
                      key={`${device.rack_unit}-${device.device_model}-${index}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelectDevice(device);
                      }}
                      role="button"
                      tabIndex={0}
                      title={`${formatLifecycleStatus(device.lifecycle_status)}${device.note ? `\n${device.note}` : ""}`}
                    >
                      <span>{device.device_model}</span>
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
                    </div>
                );
                })}
              </div>
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

function deviceKey(device: Device): string {
  return `${device.cabinet_id}:${device.rack_unit}`;
}

function cssEscape(value: string) {
  if (typeof CSS !== "undefined" && CSS.escape) return CSS.escape(value);
  return value.replace(/["\\]/g, "\\$&");
}

import { useMemo, useState } from "react";
import type { ConnectorType, Device, PortConnector } from "../types";
import { useI18n } from "../i18n";

type DevicePortLayoutProps = {
  device: Device | null;
  onShowCabinetMap: () => void;
};

type PortMarker = {
  port: PortConnector;
  connectorType: ConnectorType;
  x: number;
  y: number;
};

const PANEL_WIDTH = 940;
const PANEL_HEIGHT = 250;

export function DevicePortLayout({ device, onShowCabinetMap }: DevicePortLayoutProps) {
  const { formatConstructionPhase, formatLifecycleStatus, formatNumber, t } = useI18n();
  const [selectedPortUid, setSelectedPortUid] = useState<string | null>(null);
  const frontPorts = useMemo(() => generatedPortMarkers(device), [device]);
  const selectedPort = frontPorts.find((marker) => marker.port.uid === selectedPortUid) ?? null;

  return (
    <section className="map-pane port-layout-pane">
      <div className="pane-header">
        <div>
          <span className="eyebrow">{t("portLayout.eyebrow")}</span>
          <h2>{device ? `${device.cabinet_id}:${device.rack_unit} ${device.device_model}` : t("portLayout.noDevice")}</h2>
        </div>
        <div className="map-controls">
          <div className="map-size-control" aria-label={t("portLayout.mode")}>
            <button onClick={onShowCabinetMap}>{t("map.cabinetMap")}</button>
            <button className="is-active">{t("portLayout.title")}</button>
          </div>
        </div>
      </div>
      {device ? (
        <>
          <div className="port-layout-meta">
            <span>{formatConstructionPhase(device.construction_phase)}</span>
            <span>{formatLifecycleStatus(device.lifecycle_status)}</span>
            <span>{t("device.portsCount", { count: formatNumber(frontPorts.length) })}</span>
          </div>
          <div className="port-layout-panels">
            <DeviceFace
              markers={frontPorts}
              onSelectPort={setSelectedPortUid}
              selectedPortUid={selectedPortUid}
              title={t("portLayout.front")}
            />
            <DeviceFace
              emptyText={t("portLayout.noBackPorts")}
              markers={[]}
              onSelectPort={setSelectedPortUid}
              selectedPortUid={selectedPortUid}
              title={t("portLayout.back")}
            />
          </div>
          {selectedPort ? (
            <div className="port-selection">
              <b>{selectedPort.port.uid}</b>
              <span>{selectedPort.connectorType}</span>
              {selectedPort.port.note ? <span>{selectedPort.port.note}</span> : null}
            </div>
          ) : null}
        </>
      ) : (
        <div className="port-layout-empty">{t("portLayout.selectDevice")}</div>
      )}
    </section>
  );
}

function DeviceFace({
  emptyText,
  markers,
  onSelectPort,
  selectedPortUid,
  title,
}: {
  emptyText?: string;
  markers: PortMarker[];
  onSelectPort: (portUid: string) => void;
  selectedPortUid: string | null;
  title: string;
}) {
  return (
    <div className="device-face">
      <div className="device-face-title">{title}</div>
      <svg className="device-face-svg" viewBox={`0 0 ${PANEL_WIDTH} ${PANEL_HEIGHT}`} role="img">
        <rect className="device-face-bg" x={10} y={20} width={PANEL_WIDTH - 20} height={PANEL_HEIGHT - 34} rx={4} />
        {markers.length ? (
          markers.map((marker) => (
            <g
              className={`port-marker ${selectedPortUid === marker.port.uid ? "is-selected" : ""}`}
              key={marker.port.uid}
              onClick={() => onSelectPort(marker.port.uid)}
              role="button"
              tabIndex={0}
            >
              <rect
                fill={portColor(marker.connectorType)}
                height={13}
                rx={2}
                width={28}
                x={marker.x - 14}
                y={marker.y - 6.5}
              >
                <title>{`${marker.port.uid}\n${marker.connectorType}`}</title>
              </rect>
              <text x={marker.x} y={marker.y + 20}>
                {portShortName(marker.port.uid)}
              </text>
            </g>
          ))
        ) : (
          <text className="device-face-empty-text" x={PANEL_WIDTH / 2} y={PANEL_HEIGHT / 2}>
            {emptyText}
          </text>
        )}
      </svg>
    </div>
  );
}

function generatedPortMarkers(device: Device | null): PortMarker[] {
  if (!device) return [];
  const ports = Object.entries(device.ports_by_type).flatMap(([connectorType, portsByType]) =>
    (portsByType ?? []).map((port) => ({ connectorType: connectorType as ConnectorType, port })),
  );
  const columns = Math.min(24, Math.max(1, Math.ceil(Math.sqrt(ports.length * 2))));
  const xGap = (PANEL_WIDTH - 80) / Math.max(1, columns - 1);
  const rowGap = 36;
  return ports.map((entry, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    return {
      ...entry,
      x: 40 + col * xGap,
      y: 58 + row * rowGap,
    };
  });
}

function portColor(connectorType: ConnectorType): string {
  if (connectorType === "CAT6") return "#06B6D4";
  if (connectorType === "LC") return "#22C55E";
  if (connectorType === "MPO") return "#F97316";
  if (connectorType === "SC") return "#A855F7";
  if (connectorType === "power") return "#EF4444";
  return "#64748B";
}

function portShortName(portUid: string): string {
  const parts = portUid.split(":");
  return parts[parts.length - 1] ?? portUid;
}

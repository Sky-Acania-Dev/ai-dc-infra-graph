import { useEffect, useMemo, useState } from "react";
import type { CabinetCableDetail, CableDetailResponse, ConnectorType, Device, DevicePortLayoutEntry, PortConnector } from "../types";
import { useI18n } from "../i18n";

type DevicePortLayoutProps = {
  device: Device | null;
  cableDetail: CableDetailResponse | null;
  selectedCable: CabinetCableDetail | null;
};

type PortMarker = {
  uid: string;
  label: string;
  connectorType: ConnectorType;
  x: number;
  y: number;
  width: number;
  height: number;
  note: string;
  source: "model" | "override" | "preset" | "discovered";
};

type PanelSide = "front" | "back";
type LayoutSource = "model" | "override" | "preset";
type LayoutWithSource = DevicePortLayoutEntry & { source: LayoutSource };

const PANEL_WIDTH = 940;
const PANEL_HEIGHT = 250;
const PANEL_INSET_X = 24;

export function DevicePortLayout({ cableDetail, device, selectedCable }: DevicePortLayoutProps) {
  const { formatConstructionPhase, formatLifecycleStatus, formatNumber, t } = useI18n();
  const [selectedPortUid, setSelectedPortUid] = useState<string | null>(null);
  const deviceUid = device ? `${device.cabinet_id}:${device.rack_unit}`.toUpperCase() : "";
  const endpointPortUids = useMemo(() => portUidsForDevice(cableDetail?.cables ?? [], deviceUid), [cableDetail, deviceUid]);
  const selectedEndpointPortUids = useMemo(
    () => portUidsForDevice(selectedCable ? [selectedCable] : [], deviceUid),
    [deviceUid, selectedCable],
  );
  const { backPorts, frontPorts, totalPorts } = useMemo(() => buildPortMarkers(device), [device]);
  const allMarkers = useMemo(() => [...frontPorts, ...backPorts], [backPorts, frontPorts]);
  const selectedPort = allMarkers.find((marker) => marker.uid === selectedPortUid) ?? null;

  useEffect(() => {
    setSelectedPortUid(null);
  }, [deviceUid]);

  useEffect(() => {
    if (!selectedEndpointPortUids.size) return;
    const firstEndpoint = allMarkers.find((marker) => selectedEndpointPortUids.has(marker.uid));
    if (firstEndpoint) setSelectedPortUid(firstEndpoint.uid);
  }, [allMarkers, selectedEndpointPortUids]);

  return (
    <section className="map-pane port-layout-pane">
      <div className="pane-header">
        <div>
          <span className="eyebrow">{t("portLayout.eyebrow")}</span>
          <h2>{device ? `${device.cabinet_id}:${device.rack_unit} ${device.device_model}` : t("portLayout.noDevice")}</h2>
        </div>
      </div>
      {device ? (
        <>
          <div className="port-layout-meta">
            <span>{formatConstructionPhase(device.construction_phase)}</span>
            <span>{formatLifecycleStatus(device.lifecycle_status)}</span>
            <span>{t("device.portsCount", { count: formatNumber(totalPorts) })}</span>
            {selectedCable ? <span>{selectedCable.uid}</span> : null}
          </div>
          <div className="port-layout-panels">
            <DeviceFace
              activePortUids={endpointPortUids}
              markers={frontPorts}
              onSelectPort={setSelectedPortUid}
              panelSvg={device.front_panel_svg || modelPanelSvg(device, "front")}
              selectedEndpointPortUids={selectedEndpointPortUids}
              selectedPortUid={selectedPortUid}
              side="front"
              title={t("portLayout.front")}
            />
            <DeviceFace
              activePortUids={endpointPortUids}
              emptyText={t("portLayout.noBackPorts")}
              markers={backPorts}
              onSelectPort={setSelectedPortUid}
              panelSvg={device.back_panel_svg || modelPanelSvg(device, "back")}
              selectedEndpointPortUids={selectedEndpointPortUids}
              selectedPortUid={selectedPortUid}
              side="back"
              title={t("portLayout.back")}
            />
          </div>
          {selectedPort ? (
            <div className="port-selection">
              <b>{selectedPort.uid}</b>
              <span>{selectedPort.connectorType}</span>
              <span>{selectedPort.source}</span>
              {selectedEndpointPortUids.has(selectedPort.uid) ? <span>{selectedCable?.uid}</span> : null}
              {selectedPort.note ? <span>{selectedPort.note}</span> : null}
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
  activePortUids,
  emptyText,
  markers,
  onSelectPort,
  panelSvg,
  selectedEndpointPortUids,
  selectedPortUid,
  side,
  title,
}: {
  activePortUids: Set<string>;
  emptyText?: string;
  markers: PortMarker[];
  onSelectPort: (portUid: string) => void;
  panelSvg: string;
  selectedEndpointPortUids: Set<string>;
  selectedPortUid: string | null;
  side: PanelSide;
  title: string;
}) {
  const panelSvgHref = svgHref(panelSvg);
  return (
    <div className="device-face">
      <div className="device-face-title">
        <span>{title}</span>
        <span>{markers.length}</span>
      </div>
      <svg className="device-face-svg" viewBox={`0 0 ${PANEL_WIDTH} ${PANEL_HEIGHT}`} role="img">
        <defs>
          <filter id={`port-glow-${side}`} x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <rect className="device-face-shadow" x={12} y={22} width={PANEL_WIDTH - 24} height={PANEL_HEIGHT - 38} rx={8} />
        <rect className="device-face-bg" x={18} y={16} width={PANEL_WIDTH - 36} height={PANEL_HEIGHT - 36} rx={7} />
        <rect className="device-face-rail" x={32} y={34} width={PANEL_WIDTH - 64} height={8} rx={2} />
        <rect className="device-face-rail" x={32} y={PANEL_HEIGHT - 56} width={PANEL_WIDTH - 64} height={8} rx={2} />
        {panelSvgHref ? (
          <image
            className="device-face-background-image"
            height={PANEL_HEIGHT - 44}
            href={panelSvgHref}
            preserveAspectRatio="xMidYMid meet"
            width={PANEL_WIDTH - 56}
            x={28}
            y={22}
          />
        ) : (
          <FallbackPanelDetail />
        )}
        {markers.length ? (
          markers.map((marker) => (
            <PortShape
              active={activePortUids.has(marker.uid)}
              key={marker.uid}
              marker={marker}
              onSelectPort={onSelectPort}
              selected={selectedPortUid === marker.uid}
              selectedEndpoint={selectedEndpointPortUids.has(marker.uid)}
            />
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

function FallbackPanelDetail() {
  return (
    <g className="device-face-fallback">
      <rect x={54} y={64} width={198} height={96} rx={2} />
      <line x1={70} x2={236} y1={84} y2={84} />
      <line x1={70} x2={236} y1={108} y2={108} />
      <line x1={70} x2={236} y1={132} y2={132} />
      <rect x={292} y={70} width={118} height={72} rx={2} />
      <line x1={314} x2={388} y1={94} y2={94} />
      <line x1={314} x2={388} y1={118} y2={118} />
      <rect x={448} y={64} width={310} height={96} rx={2} />
      <line x1={468} x2={738} y1={88} y2={88} />
      <line x1={468} x2={738} y1={116} y2={116} />
      <line x1={468} x2={738} y1={140} y2={140} />
      <circle cx={812} cy={92} r={10} />
      <circle cx={850} cy={92} r={10} />
      <rect x={798} y={124} width={72} height={28} rx={2} />
    </g>
  );
}

function PortShape({
  active,
  marker,
  onSelectPort,
  selected,
  selectedEndpoint,
}: {
  active: boolean;
  marker: PortMarker;
  onSelectPort: (portUid: string) => void;
  selected: boolean;
  selectedEndpoint: boolean;
}) {
  const width = Math.max(marker.width, 16);
  const height = Math.max(marker.height, 10);
  const x = marker.x - width / 2;
  const y = marker.y - height / 2;
  const className = [
    "port-marker",
    `connector-${connectorClass(marker.connectorType)}`,
    active ? "is-active-endpoint" : "",
    selected ? "is-selected" : "",
    selectedEndpoint ? "is-selected-endpoint" : "",
  ]
    .filter(Boolean)
    .join(" ");

  function select() {
    onSelectPort(marker.uid);
  }

  return (
    <g
      aria-label={`${marker.label} ${marker.connectorType}`}
      className={className}
      onClick={select}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select();
        }
      }}
      role="button"
      tabIndex={0}
    >
      <rect className="port-marker-hitbox" x={x - 5} y={y - 7} width={width + 10} height={height + 24} rx={6} />
      <rect className="port-marker-shell" x={x - 2} y={y - 2} width={width + 4} height={height + 4} rx={3} />
      <rect className="port-marker-core" height={height} rx={2} width={width} x={x} y={y}>
        <title>{`${marker.uid}\n${marker.connectorType}`}</title>
      </rect>
      {isHighDensityConnector(marker.connectorType) ? (
        <>
          <line className="port-marker-lane" x1={x + width * 0.33} x2={x + width * 0.33} y1={y + 2} y2={y + height - 2} />
          <line className="port-marker-lane" x1={x + width * 0.66} x2={x + width * 0.66} y1={y + 2} y2={y + height - 2} />
        </>
      ) : null}
      <text x={marker.x} y={y + height + 11}>
        {marker.label}
      </text>
    </g>
  );
}

function buildPortMarkers(device: Device | null): { frontPorts: PortMarker[]; backPorts: PortMarker[]; totalPorts: number } {
  if (!device) return { frontPorts: [], backPorts: [], totalPorts: 0 };
  const discoveredPorts = Object.entries(device.ports_by_type).flatMap(([connectorType, portsByType]) =>
    (portsByType ?? []).map((port) => ({ connectorType: connectorType as ConnectorType, port })),
  );
  const portsByKey = new Map<string, { connectorType: ConnectorType; port: PortConnector }>();
  for (const entry of discoveredPorts) {
    portsByKey.set(normalizePortKey(entry.port.uid), entry);
    portsByKey.set(normalizePortKey(portShortName(entry.port.uid)), entry);
  }

  const layoutsByKey = new Map<string, LayoutWithSource>();
  for (const layout of device.port_layout ?? []) {
    layoutsByKey.set(normalizePortKey(layout.port_name), { ...layout, source: "model" });
  }
  for (const layout of device.port_layout_overrides ?? []) {
    layoutsByKey.set(normalizePortKey(layout.port_name), { ...layout, source: "override" });
  }
  if (!layoutsByKey.size) {
    for (const layout of modelPortLayout(device)) {
      layoutsByKey.set(normalizePortKey(layout.port_name), { ...layout, source: "preset" });
    }
  }

  if (!layoutsByKey.size) {
    const fallbackMarkers = generatedPortMarkers(discoveredPorts);
    return {
      frontPorts: fallbackMarkers,
      backPorts: [],
      totalPorts: fallbackMarkers.length,
    };
  }

  const usedPortUids = new Set<string>();
  const markers: PortMarker[] = [];
  for (const layout of layoutsByKey.values()) {
    const discovered = portsByKey.get(normalizePortKey(layout.port_name));
    const uid = discovered?.port.uid ?? layout.port_name;
    usedPortUids.add(uid);
    markers.push(markerFromLayout(layout, discovered));
  }

  const fallbackDiscovered = discoveredPorts.filter((entry) => !usedPortUids.has(entry.port.uid));
  markers.push(...generatedPortMarkers(fallbackDiscovered));

  return {
    frontPorts: markers.filter((marker) => markerSide(marker.uid, device, layoutsByKey) === "front"),
    backPorts: markers.filter((marker) => markerSide(marker.uid, device, layoutsByKey) === "back"),
    totalPorts: markers.length,
  };
}

function markerFromLayout(
  layout: LayoutWithSource,
  discovered: { connectorType: ConnectorType; port: PortConnector } | undefined,
): PortMarker {
  const width = normalizeSize(layout.width, 28, PANEL_WIDTH);
  const height = normalizeSize(layout.height, 14, PANEL_HEIGHT);
  return {
    uid: discovered?.port.uid ?? layout.port_name,
    label: displayPortLabel(discovered?.port.uid ?? layout.port_name),
    connectorType: layout.connector_type || discovered?.connectorType || "other",
    x: normalizeCoordinate(layout.x, PANEL_WIDTH),
    y: normalizeCoordinate(layout.y, PANEL_HEIGHT),
    width,
    height,
    note: layout.note || discovered?.port.note || "",
    source: layout.source,
  };
}

function markerSide(uid: string, device: Device, layoutsByKey: Map<string, LayoutWithSource>): PanelSide {
  const layout = layoutsByKey.get(normalizePortKey(uid)) ?? layoutsByKey.get(normalizePortKey(portShortName(uid)));
  return layout?.side === "back" ? "back" : "front";
}

function generatedPortMarkers(ports: Array<{ connectorType: ConnectorType; port: PortConnector }>): PortMarker[] {
  const columns = Math.min(28, Math.max(1, Math.ceil(Math.sqrt(ports.length * 2.4))));
  const xGap = (PANEL_WIDTH - PANEL_INSET_X * 2) / Math.max(1, columns - 1);
  const rowGap = 31;
  return ports.map((entry, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    return {
      connectorType: entry.connectorType,
      height: isHighDensityConnector(entry.connectorType) ? 15 : 17,
      label: displayPortLabel(entry.port.uid),
      note: entry.port.note,
      source: "discovered",
      uid: entry.port.uid,
      width: connectorWidth(entry.connectorType),
      x: PANEL_INSET_X + col * xGap,
      y: 64 + row * rowGap,
    };
  });
}

function portUidsForDevice(cables: CabinetCableDetail[], deviceUid: string): Set<string> {
  const ports = new Set<string>();
  if (!deviceUid) return ports;
  const prefix = `${deviceUid}:`;
  for (const cable of cables) {
    if (cable.a_port_uid.toUpperCase().startsWith(prefix)) ports.add(cable.a_port_uid);
    if (cable.z_port_uid.toUpperCase().startsWith(prefix)) ports.add(cable.z_port_uid);
  }
  return ports;
}

function svgHref(value: string | undefined): string {
  const trimmed = (value ?? "").trim();
  if (!trimmed) return "";
  if (/^(data:image\/svg\+xml|https?:|\/)/i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("<svg")) return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(trimmed)}`;
  return "";
}

function modelPanelSvg(device: Device, side: PanelSide): string {
  if (normalizedModelName(device).includes("SN2201")) return side === "front" ? sn2201FrontSvg() : sn2201RearSvg();
  return "";
}

function modelPortLayout(device: Device): DevicePortLayoutEntry[] {
  if (normalizedModelName(device).includes("SN2201")) return sn2201PortLayout();
  return [];
}

function sn2201PortLayout(): DevicePortLayoutEntry[] {
  const entries: DevicePortLayoutEntry[] = [];
  const bankStarts = [91, 357, 623];
  for (let port = 1; port <= 48; port += 1) {
    const bank = Math.floor((port - 1) / 16);
    const indexInBank = (port - 1) % 16;
    const col = Math.floor(indexInBank / 2);
    const row = indexInBank % 2;
    entries.push({
      connector_type: "CAT6",
      height: 20,
      note: "SN2201 front RJ45 switch port",
      port_name: `swp${port}`,
      side: "front",
      width: 24,
      x: bankStarts[bank] + col * 28,
      y: row === 0 ? 92 : 124,
    });
  }
  for (let index = 0; index < 4; index += 1) {
    entries.push({
      connector_type: "LC",
      height: 22,
      note: "SN2201 front SFP uplink",
      port_name: `swp${49 + index}`,
      side: "front",
      width: 31,
      x: 796 + Math.floor(index / 2) * 38,
      y: index % 2 === 0 ? 91 : 124,
    });
  }
  entries.push(
    {
      connector_type: "CAT6",
      height: 22,
      note: "SN2201 management Ethernet",
      port_name: "mgmt",
      side: "front",
      width: 24,
      x: 900,
      y: 91,
    },
    {
      connector_type: "CAT6",
      height: 22,
      note: "SN2201 console port",
      port_name: "console",
      side: "front",
      width: 24,
      x: 900,
      y: 124,
    },
  );
  return entries;
}

function sn2201FrontSvg(): string {
  const bankFrames = [
    portBankFrameSvg(58, 66, "1-16"),
    portBankFrameSvg(324, 66, "17-32"),
    portBankFrameSvg(590, 66, "33-48"),
  ].join("");
  const uplinks = `${technicalRect(776, 66, 78, 76)}${technicalLabel(785, 157, "49-52")}`;
  const management = `${technicalRect(878, 66, 44, 76)}${technicalLabel(884, 157, "MGMT")}`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${PANEL_WIDTH} ${PANEL_HEIGHT}"><rect x="28" y="42" width="902" height="126" rx="3" fill="#fff" stroke="#111" stroke-width="2"/><line x1="42" x2="916" y1="58" y2="58" stroke="#111" stroke-width="1"/><line x1="42" x2="916" y1="154" y2="154" stroke="#111" stroke-width="1"/><text x="42" y="195" font-family="monospace" font-size="16" font-weight="700" fill="#111">NVIDIA SN2201 FRONT</text>${bankFrames}${uplinks}${management}</svg>`;
}

function sn2201RearSvg(): string {
  const modules = [
    technicalRect(64, 72, 92, 64),
    technicalRect(184, 72, 92, 64),
    technicalRect(304, 72, 92, 64),
    technicalRect(424, 72, 92, 64),
    technicalRect(550, 72, 112, 64),
    technicalRect(692, 64, 92, 82),
    technicalRect(812, 64, 92, 82),
  ].join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${PANEL_WIDTH} ${PANEL_HEIGHT}"><rect x="28" y="48" width="902" height="118" rx="3" fill="#fff" stroke="#111" stroke-width="2"/><text x="42" y="196" font-family="monospace" font-size="16" font-weight="700" fill="#111">NVIDIA SN2201 REAR</text>${modules}${technicalLabel(92, 154, "FAN")}${technicalLabel(710, 164, "PSU")}</svg>`;
}

function portBankFrameSvg(x: number, y: number, label: string): string {
  return `${technicalRect(x, y, 250, 76)}<line x1="${x + 10}" x2="${x + 240}" y1="${y + 38}" y2="${y + 38}" stroke="#111" stroke-width="1"/>${technicalLabel(x + 95, y + 101, label)}`;
}

function technicalRect(x: number, y: number, width: number, height: number): string {
  return `<rect x="${x}" y="${y}" width="${width}" height="${height}" fill="#fff" stroke="#111" stroke-width="1.4"/>`;
}

function technicalLabel(x: number, y: number, label: string): string {
  return `<text x="${x}" y="${y}" font-family="monospace" font-size="11" fill="#111">${label}</text>`;
}

function normalizedModelName(device: Device): string {
  return `${device.device_model} ${device.device_model_uid}`.toUpperCase();
}

function normalizeCoordinate(value: number, size: number): number {
  if (value > 0 && value <= 1) return value * size;
  return value;
}

function normalizeSize(value: number, fallback: number, size: number): number {
  if (value > 0 && value <= 1) return value * size;
  return value > 0 ? value : fallback;
}

function connectorWidth(connectorType: ConnectorType): number {
  if (connectorType === "power") return 34;
  if (connectorType === "CAT6") return 26;
  if (connectorType === "MPO") return 34;
  return 28;
}

function isHighDensityConnector(connectorType: ConnectorType): boolean {
  return connectorType === "LC" || connectorType === "MPO";
}

function connectorClass(connectorType: ConnectorType): string {
  return connectorType.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function normalizePortKey(value: string): string {
  return value.trim().toUpperCase();
}

function portShortName(portUid: string): string {
  const parts = portUid.split(":");
  return parts[parts.length - 1] ?? portUid;
}

function displayPortLabel(portUid: string): string {
  const shortName = portShortName(portUid);
  const switchPort = /^swp(\d+)$/i.exec(shortName);
  if (switchPort) return switchPort[1];
  if (shortName.toLowerCase() === "console") return "cons";
  return shortName;
}

import { useEffect, useMemo, useState } from "react";
import {
  fetchCabinetConnectionCables,
  fetchCabinetDetail,
  fetchCabinetLayout,
  fetchDeviceConnectionCables,
  fetchDeviceConnections,
} from "./api";
import { CableDetailOverlay } from "./components/CableDetailOverlay";
import { CabinetConnectionsPanel } from "./components/CabinetConnectionsPanel";
import { CabinetDetailsPanel } from "./components/CabinetDetailsPanel";
import { CabinetMap } from "./components/CabinetMap";
import { ValidationView } from "./components/ValidationView";
import type { MapSize } from "./components/CabinetMap";
import type {
  CableDetailResponse,
  CabinetDetailResponse,
  CabinetLayoutItem,
  Device,
  DeviceConnectionResponse,
} from "./types";
import { useI18n, type Locale } from "./i18n";

const DATA_HALLS = ["DH1", "DH2"];
type AppMode = "topology" | "validation";

export function App() {
  const { locale, setLocale, t } = useI18n();
  const [mode, setMode] = useState<AppMode>("topology");
  const [dataHall, setDataHall] = useState("DH1");
  const [cabinets, setCabinets] = useState<CabinetLayoutItem[]>([]);
  const [selectedCabinetUid, setSelectedCabinetUid] = useState<string | null>(null);
  const [detail, setDetail] = useState<CabinetDetailResponse | null>(null);
  const [cableDetail, setCableDetail] = useState<CableDetailResponse | null>(null);
  const [selectedDeviceUid, setSelectedDeviceUid] = useState<string | null>(null);
  const [deviceDetail, setDeviceDetail] = useState<DeviceConnectionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mapSize, setMapSize] = useState<MapSize>("normal");

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchCabinetLayout(dataHall)
      .then(setCabinets)
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setIsLoading(false));
  }, [dataHall]);

  useEffect(() => {
    if (!selectedCabinetUid) return;
    setError(null);
    fetchCabinetDetail(selectedCabinetUid)
      .then(setDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }, [selectedCabinetUid]);

  const connectedCabinetUids = useMemo(() => {
    if (deviceDetail) return new Set(deviceDetail.connected_cabinet_uids);
    return new Set(detail?.connections.map((connection) => connection.target_cabinet_uid) ?? []);
  }, [detail, deviceDetail]);
  const connectedDataHalls = useMemo(
    () => new Set([...connectedCabinetUids].map((cabinetUid) => cabinetUid.split(":")[0])),
    [connectedCabinetUids],
  );
  const connectedDeviceUids = useMemo(
    () => new Set(deviceDetail?.connected_devices.map((connection) => connection.target_device_uid) ?? []),
    [deviceDetail],
  );

  function clearSelection() {
    setSelectedCabinetUid(null);
    setDetail(null);
    setCableDetail(null);
    clearDeviceSelection();
  }

  function clearDeviceSelection() {
    setSelectedDeviceUid(null);
    setDeviceDetail(null);
  }

  function viewConnectionCables(targetCabinetUid: string) {
    if (!selectedCabinetUid) return;
    setError(null);
    fetchCabinetConnectionCables(selectedCabinetUid, targetCabinetUid)
      .then(setCableDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }

  function viewDeviceConnectionCables(targetDeviceUid: string) {
    if (!selectedDeviceUid) return;
    setError(null);
    fetchDeviceConnectionCables(selectedDeviceUid, targetDeviceUid)
      .then(setCableDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }

  function selectDevice(device: Device) {
    const deviceUid = `${device.cabinet_id}:${device.rack_unit}`;
    setSelectedDeviceUid(deviceUid);
    setCableDetail(null);
    setError(null);
    fetchDeviceConnections(device.cabinet_id, device.rack_unit)
      .then(setDeviceDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }

  function jumpToDevice(deviceUid: string) {
    const parsed = parseDeviceUid(deviceUid);
    if (!parsed) return;
    setMode("topology");
    setDataHall(parsed.dataHall);
    setSelectedCabinetUid(parsed.cabinetUid);
    setSelectedDeviceUid(parsed.deviceUid);
    setCableDetail(null);
    setError(null);
    fetchDeviceConnections(parsed.cabinetUid, parsed.rackUnit)
      .then(setDeviceDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }

  function jumpToPort(portUid: string) {
    const parsed = parseDeviceUid(portUid);
    if (!parsed) return;
    jumpToDevice(parsed.deviceUid);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">{t("app.name")}</span>
          <h1>{mode === "topology" ? t("app.topologyTitle") : t("app.validationTitle")}</h1>
        </div>
        <div className="topbar-controls">
          <div className="segmented-control" role="tablist" aria-label={t("settings.label")}>
            <button className={mode === "topology" ? "is-active" : ""} onClick={() => setMode("topology")}>
              {t("view.topology")}
            </button>
            <button className={mode === "validation" ? "is-active" : ""} onClick={() => setMode("validation")}>
              {t("view.validation")}
            </button>
          </div>
          <label className="settings-control">
            <span>{t("settings.language")}</span>
            <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
              <option value="en">{t("settings.english")}</option>
              <option value="zh-CN">{t("settings.chineseSimplified")}</option>
            </select>
          </label>
          {mode === "topology" ? (
            <div className="segmented-control" role="tablist" aria-label={t("dataHall.selector")}>
              {DATA_HALLS.map((hall) => (
                <button
                  className={`${hall === dataHall ? "is-active" : ""} ${connectedDataHalls.has(hall) && hall !== dataHall ? "has-graph-neighbor" : ""}`}
                  key={hall}
                  onClick={() => setDataHall(hall)}
                >
                  {hall}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {mode === "validation" ? (
        <ValidationView onJumpToDevice={jumpToDevice} onJumpToPort={jumpToPort} />
      ) : (
        <div className="workspace">
          <CabinetDetailsPanel
            detail={detail}
            dataHall={dataHall}
            cabinets={cabinets}
            selectedDeviceUid={selectedDeviceUid}
            connectedDeviceUids={connectedDeviceUids}
            onSelectDevice={selectDevice}
            onClearDeviceSelection={clearDeviceSelection}
          />
          {isLoading ? (
            <section className="map-pane loading-pane">{t("common.loading", { target: dataHall })}</section>
          ) : (
            <div className="map-stack">
              <CabinetMap
                cabinets={cabinets}
                selectedCabinetUid={selectedCabinetUid}
                selectedDeviceCabinetUid={deviceDetail?.source_cabinet_uid ?? null}
                connectedCabinetUids={connectedCabinetUids}
                isDeviceMode={Boolean(selectedDeviceUid)}
                mapSize={mapSize}
                onSelectCabinet={(cabinetUid) => {
                  setSelectedCabinetUid(cabinetUid);
                  setCableDetail(null);
                  clearDeviceSelection();
                }}
                onClearSelection={clearSelection}
                onMapSizeChange={setMapSize}
              />
              <CableDetailOverlay cableDetail={cableDetail} onClose={() => setCableDetail(null)} />
            </div>
          )}
          <CabinetConnectionsPanel
            detail={detail}
            deviceDetail={deviceDetail}
            onViewCables={viewConnectionCables}
            onViewDeviceCables={viewDeviceConnectionCables}
          />
        </div>
      )}
    </main>
  );
}

function parseDeviceUid(value: string) {
  const parts = value.toUpperCase().split(":");
  if (parts.length < 3) return null;
  const rackUnit = Number.parseInt(parts[2], 10);
  if (Number.isNaN(rackUnit)) return null;
  const cabinetUid = `${parts[0]}:${parts[1]}`;
  return {
    cabinetUid,
    dataHall: parts[0],
    deviceUid: `${cabinetUid}:${rackUnit}`,
    rackUnit,
  };
}

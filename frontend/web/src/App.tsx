import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchCabinetConnectionCables,
  fetchCabinetDetail,
  fetchCabinetLayout,
  fetchCurrentUser,
  fetchDataHallCableSummary,
  fetchDataHallCables,
  fetchDeviceConnectionCables,
  fetchDeviceConnections,
  fetchTopologyEnums,
} from "./api";
import { CableDetailOverlay } from "./components/CableDetailOverlay";
import { CabinetConnectionsPanel } from "./components/CabinetConnectionsPanel";
import { CabinetDetailsPanel } from "./components/CabinetDetailsPanel";
import { CabinetMap } from "./components/CabinetMap";
import { ValidationView } from "./components/ValidationView";
import type { MapProgressDisplay, MapSize } from "./components/CabinetMap";
import type {
  CableDetailResponse,
  CabinetDetailResponse,
  CabinetLayoutItem,
  AuthUser,
  DataHallCableBucket,
  DataHallCableSummaryResponse,
  Device,
  DeviceConnectionResponse,
  TopologyEnums,
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
  const [mapProgressDisplay, setMapProgressDisplay] = useState<MapProgressDisplay>("text");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [topologyEnums, setTopologyEnums] = useState<TopologyEnums | null>(null);
  const [dataHallCableSummary, setDataHallCableSummary] = useState<DataHallCableSummaryResponse | null>(null);
  const cabinetLayoutCacheRef = useRef<Record<string, CabinetLayoutItem[]>>({});
  const dataHallCableSummaryCacheRef = useRef<Record<string, DataHallCableSummaryResponse>>({});
  const canEdit = currentUser?.role === "manager" || currentUser?.role === "editor";

  useEffect(() => {
    fetchCurrentUser()
      .then(setCurrentUser)
      .catch((requestError: Error) => setError(requestError.message));
    fetchTopologyEnums()
      .then(setTopologyEnums)
      .catch((requestError: Error) => setError(requestError.message));
  }, []);

  useEffect(() => {
    const cachedLayout = cabinetLayoutCacheRef.current[dataHall];
    if (cachedLayout) {
      setCabinets(cachedLayout);
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetchCabinetLayout(dataHall)
      .then((layout) => {
        if (cancelled) return;
        cabinetLayoutCacheRef.current[dataHall] = layout;
        setCabinets(layout);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dataHall]);

  useEffect(() => {
    const cachedSummary = dataHallCableSummaryCacheRef.current[dataHall];
    if (cachedSummary) {
      setDataHallCableSummary(cachedSummary);
      return;
    }

    let cancelled = false;
    fetchDataHallCableSummary(dataHall)
      .then((summary) => {
        if (cancelled) return;
        dataHallCableSummaryCacheRef.current[dataHall] = summary;
        setDataHallCableSummary(summary);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
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

  function viewDataHallCables(bucket: DataHallCableBucket, cableType: string) {
    setError(null);
    fetchDataHallCables(dataHall, bucket.scope, cableType, bucket.target_data_hall)
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

  function refreshTopologyContext() {
    cabinetLayoutCacheRef.current = {};
    dataHallCableSummaryCacheRef.current = {};
    if (selectedCabinetUid) {
      fetchCabinetDetail(selectedCabinetUid)
        .then(setDetail)
        .catch((requestError: Error) => setError(requestError.message));
    }
    fetchCabinetLayout(dataHall)
      .then((layout) => {
        cabinetLayoutCacheRef.current[dataHall] = layout;
        setCabinets(layout);
      })
      .catch((requestError: Error) => setError(requestError.message));
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
          <div className="role-pill">{currentUser ? t(`auth.role.${currentUser.role}`) : t("auth.loading")}</div>
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
            canEdit={canEdit}
            lifecycleStatuses={topologyEnums?.lifecycle_statuses ?? []}
            onStatusChanged={() => {
              dataHallCableSummaryCacheRef.current = {};
              if (selectedCabinetUid) {
                fetchCabinetDetail(selectedCabinetUid)
                  .then(setDetail)
                  .catch((requestError: Error) => setError(requestError.message));
              }
              fetchCabinetLayout(dataHall)
                .then((layout) => {
                  cabinetLayoutCacheRef.current[dataHall] = layout;
                  setCabinets(layout);
                })
                .catch((requestError: Error) => setError(requestError.message));
            }}
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
                progressDisplay={mapProgressDisplay}
                onSelectCabinet={(cabinetUid) => {
                  setSelectedCabinetUid(cabinetUid);
                  setCableDetail(null);
                  clearDeviceSelection();
                }}
                onClearSelection={clearSelection}
                onMapSizeChange={setMapSize}
                onProgressDisplayChange={setMapProgressDisplay}
              />
              <CableDetailOverlay
                cableDetail={cableDetail}
                canEdit={canEdit}
                topologyEnums={topologyEnums}
                onClose={() => setCableDetail(null)}
                onCableUpdated={(updatedCable) => {
                  setCableDetail((current) => {
                    if (!current) return current;
                    return {
                      ...current,
                      cables: current.cables.map((cable) => (cable.uid === updatedCable.uid ? updatedCable : cable)),
                    };
                  });
                  refreshTopologyContext();
                }}
              />
            </div>
          )}
          <CabinetConnectionsPanel
            detail={detail}
            deviceDetail={deviceDetail}
            dataHallCableSummary={dataHallCableSummary}
            onViewCables={viewConnectionCables}
            onViewDeviceCables={viewDeviceConnectionCables}
            onViewDataHallCables={viewDataHallCables}
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

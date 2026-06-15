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
  fetchOperations,
  fetchTopologyEnums,
  updateCabinetStatus,
  updateCable,
  updateDeviceStatus,
  type UpdateCablePayload,
} from "./api";
import { CableDetailOverlay } from "./components/CableDetailOverlay";
import { CabinetConnectionsPanel, type CabinetCableRoute, type DeviceCableRoute } from "./components/CabinetConnectionsPanel";
import { CabinetDetailsPanel } from "./components/CabinetDetailsPanel";
import { CabinetMap } from "./components/CabinetMap";
import { DevicePortLayout } from "./components/DevicePortLayout";
import { ValidationView } from "./components/ValidationView";
import type { MapProgressDisplay, MapSize } from "./components/CabinetMap";
import type {
  CableDetailResponse,
  CabinetDetailResponse,
  CabinetCableDetail,
  CabinetCableDetailResponse,
  CabinetLayoutItem,
  AuthUser,
  DataHallCableBucket,
  DataHallCableSummaryResponse,
  Device,
  DeviceConnectionResponse,
  Operation,
  BulkOperationResponse,
  OperationListResponse,
  OperationResponse,
  TopologyEnums,
} from "./types";
import { useI18n, type Locale } from "./i18n";

const DATA_HALLS = ["DH1", "DH2"];
const OPERATION_POLL_INTERVAL_MS = 5000;
type AppMode = "topology" | "validation" | "operations";
type CenterViewMode = "cabinet_map" | "port_layout";
type CableDetailPageLoader = (offset: number, limit: number) => Promise<CableDetailResponse>;
export type SelectionMode = "single" | "multi" | "remove";
export type SelectionGesture = {
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
};

export function App() {
  const { locale, setLocale, t } = useI18n();
  const [mode, setMode] = useState<AppMode>("topology");
  const [dataHall, setDataHall] = useState("DH1");
  const [cabinets, setCabinets] = useState<CabinetLayoutItem[]>([]);
  const [selectedCabinetUid, setSelectedCabinetUid] = useState<string | null>(null);
  const [selectedCabinetUids, setSelectedCabinetUids] = useState<string[]>([]);
  const [detail, setDetail] = useState<CabinetDetailResponse | null>(null);
  const [selectedCabinetDetails, setSelectedCabinetDetails] = useState<CabinetDetailResponse[]>([]);
  const [cableDetail, setCableDetail] = useState<CableDetailResponse | null>(null);
  const [selectedCableUid, setSelectedCableUid] = useState<string | null>(null);
  const [selectedCableUids, setSelectedCableUids] = useState<string[]>([]);
  const [isCableDetailLoading, setIsCableDetailLoading] = useState(false);
  const [cableDetailRoute, setCableDetailRoute] = useState<{ source: string; target: string } | null>(null);
  const [cableDetailPageLoader, setCableDetailPageLoader] = useState<CableDetailPageLoader | null>(null);
  const [selectedDeviceUid, setSelectedDeviceUid] = useState<string | null>(null);
  const [selectedDeviceUids, setSelectedDeviceUids] = useState<string[]>([]);
  const [deviceScrollRequest, setDeviceScrollRequest] = useState(0);
  const [deviceDetail, setDeviceDetail] = useState<DeviceConnectionResponse | null>(null);
  const [selectedDeviceDetails, setSelectedDeviceDetails] = useState<DeviceConnectionResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mapSize, setMapSize] = useState<MapSize>("medium");
  const [mapProgressDisplay, setMapProgressDisplay] = useState<MapProgressDisplay>("text");
  const [centerViewMode, setCenterViewMode] = useState<CenterViewMode>("cabinet_map");
  const [selectionMode, setSelectionMode] = useState<SelectionMode>("single");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [topologyEnums, setTopologyEnums] = useState<TopologyEnums | null>(null);
  const [dataHallCableSummary, setDataHallCableSummary] = useState<DataHallCableSummaryResponse | null>(null);
  const [operationList, setOperationList] = useState<OperationListResponse | null>(null);
  const [pendingSaveCount, setPendingSaveCount] = useState(0);
  const [lastSavedVersion, setLastSavedVersion] = useState<number | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [operationCursorVersion, setOperationCursorVersion] = useState<number | null>(null);
  const [undoStack, setUndoStack] = useState<Operation[]>([]);
  const [redoStack, setRedoStack] = useState<Operation[]>([]);
  const cabinetLayoutCacheRef = useRef<Record<string, CabinetLayoutItem[]>>({});
  const cabinetDetailCacheRef = useRef<Record<string, CabinetDetailResponse>>({});
  const dataHallCableSummaryCacheRef = useRef<Record<string, DataHallCableSummaryResponse>>({});
  const deviceDetailCacheRef = useRef<Record<string, DeviceConnectionResponse>>({});
  const cableDetailRequestRef = useRef(0);
  const lastSeenOperationIdRef = useRef<number | null>(null);
  const isPollingOperationsRef = useRef(false);
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
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isEditable =
        target?.tagName === "INPUT" || target?.tagName === "SELECT" || target?.tagName === "TEXTAREA";
      if (isEditable || !(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() === "z" && !event.shiftKey) {
        event.preventDefault();
        runClientUndo();
      }
      if (event.key.toLowerCase() === "y" || (event.key.toLowerCase() === "z" && event.shiftKey)) {
        event.preventDefault();
        runClientRedo();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

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
    loadCabinetDetail(selectedCabinetUid)
      .then(setDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }, [selectedCabinetUid]);

  useEffect(() => {
    let cancelled = false;
    if (selectedCabinetUids.length <= 1) {
      setSelectedCabinetDetails([]);
      return;
    }

    setSelectedCabinetDetails((current) =>
      current.filter((selectedDetail) => selectedCabinetUids.includes(selectedDetail.cabinet.cabinet_uid)),
    );
    setError(null);
    Promise.all(selectedCabinetUids.map(loadCabinetDetail))
      .then((details) => {
        if (!cancelled) setSelectedCabinetDetails(details);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCabinetUids]);

  useEffect(() => {
    let cancelled = false;
    if (selectedDeviceUids.length <= 1) {
      setSelectedDeviceDetails([]);
      return;
    }

    setError(null);
    Promise.all(selectedDeviceUids.map(loadDeviceConnections))
      .then((details) => {
        if (!cancelled) setSelectedDeviceDetails(details);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDeviceUids]);

  useEffect(() => {
    if (mode !== "operations") return;
    refreshOperations();
  }, [mode]);

  useEffect(() => {
    let cancelled = false;
    let intervalId: number | null = null;

    fetchOperations(1)
      .then((operations) => {
        if (cancelled) return;
        updateOperationCursor(operations.version);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      });

    intervalId = window.setInterval(() => {
      pollOperations();
    }, OPERATION_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalId != null) window.clearInterval(intervalId);
    };
  }, []);

  const cabinetConnectionCounts = useMemo(() => {
    if (selectedCabinetUids.length <= 1) return new Map<string, number>();
    const selectedCabinetUidSet = new Set(selectedCabinetUids);
    const counts = new Map<string, number>();
    for (const selectedDetail of selectedCabinetDetails) {
      if (!selectedCabinetUidSet.has(selectedDetail.cabinet.cabinet_uid)) continue;
      for (const connection of selectedDetail.connections) {
        counts.set(connection.target_cabinet_uid, (counts.get(connection.target_cabinet_uid) ?? 0) + 1);
      }
    }
    return counts;
  }, [selectedCabinetDetails, selectedCabinetUids]);
  const connectedCabinetUids = useMemo(() => {
    if (deviceDetail) return new Set(deviceDetail.connected_cabinet_uids);
    if (selectedCabinetUids.length > 1) return new Set(cabinetConnectionCounts.keys());
    return new Set(detail?.connections.map((connection) => connection.target_cabinet_uid) ?? []);
  }, [cabinetConnectionCounts, detail, deviceDetail, selectedCabinetUids.length]);
  const connectedDataHalls = useMemo(
    () => new Set([...connectedCabinetUids].map((cabinetUid) => cabinetUid.split(":")[0])),
    [connectedCabinetUids],
  );
  const connectedDeviceUids = useMemo(
    () => new Set(deviceDetail?.connected_devices.map((connection) => connection.target_device_uid) ?? []),
    [deviceDetail],
  );
  const selectedCabinetUidSet = useMemo(() => new Set(selectedCabinetUids), [selectedCabinetUids]);
  const selectedDeviceUidSet = useMemo(() => new Set(selectedDeviceUids), [selectedDeviceUids]);
  const selectedCableUidSet = useMemo(() => new Set(selectedCableUids), [selectedCableUids]);
  const selectedDevice = useMemo(() => {
    if (!selectedDeviceUid) return null;
    return detail?.devices.find((device) => `${device.cabinet_id}:${device.rack_unit}` === selectedDeviceUid) ?? null;
  }, [detail, selectedDeviceUid]);
  const selectedCable = useMemo(
    () => cableDetail?.cables.find((cable) => cable.uid === selectedCableUid) ?? null,
    [cableDetail, selectedCableUid],
  );

  function clearSelection() {
    setSelectedCabinetUid(null);
    setSelectedCabinetUids([]);
    setDetail(null);
    setSelectedCabinetDetails([]);
    closeCableDetail();
    setCenterViewMode("cabinet_map");
    clearDeviceSelection();
  }

  function loadCabinetDetail(cabinetUid: string): Promise<CabinetDetailResponse> {
    const cachedDetail = cabinetDetailCacheRef.current[cabinetUid];
    if (cachedDetail) return Promise.resolve(cachedDetail);
    return fetchCabinetDetail(cabinetUid).then((nextDetail) => {
      cabinetDetailCacheRef.current[cabinetUid] = nextDetail;
      return nextDetail;
    });
  }

  function loadDeviceConnections(deviceUid: string): Promise<DeviceConnectionResponse> {
    const cachedDetail = deviceDetailCacheRef.current[deviceUid];
    if (cachedDetail) return Promise.resolve(cachedDetail);
    const parsed = parseDeviceUid(deviceUid);
    if (!parsed) return Promise.reject(new Error(`Invalid device uid: ${deviceUid}`));
    return fetchDeviceConnections(parsed.cabinetUid, parsed.rackUnit).then((nextDetail) => {
      deviceDetailCacheRef.current[deviceUid] = nextDetail;
      return nextDetail;
    });
  }

  function clearDeviceSelection() {
    setSelectedDeviceUid(null);
    setSelectedDeviceUids([]);
    setDeviceDetail(null);
    setSelectedDeviceDetails([]);
    setCenterViewMode("cabinet_map");
  }

  function viewConnectionCables(routes: CabinetCableRoute[]) {
    if (!routes.length) return;
    const sourceLabel = routes.length === 1 ? routes[0].sourceCabinetUid : `${routes.length} cabinet routes`;
    const targetUids = [...new Set(routes.map((route) => route.targetCabinetUid))];
    const targetLabel = targetUids.length === 1 ? targetUids[0] : `${targetUids.length} peer cabinets`;
    openCableDetail(
      { source: sourceLabel, target: targetLabel },
      () =>
        Promise.all(
          routes.map((route) => fetchCabinetConnectionCables(route.sourceCabinetUid, route.targetCabinetUid)),
        ).then((responses) => mergeCabinetCableDetails(sourceLabel, targetLabel, responses)),
    );
  }

  function viewDeviceConnectionCables(routes: DeviceCableRoute[]) {
    if (!routes.length) return;
    const sourceLabel = routes.length === 1 ? routes[0].sourceDeviceUid : `${routes.length} device routes`;
    const targetUids = [...new Set(routes.map((route) => route.targetDeviceUid))];
    const targetLabel = targetUids.length === 1 ? targetUids[0] : `${targetUids.length} peer devices`;
    openCableDetail(
      { source: sourceLabel, target: targetLabel },
      () =>
        Promise.all(routes.map((route) => fetchDeviceConnectionCables(route.sourceDeviceUid, route.targetDeviceUid))).then(
          (responses) => mergeDeviceCableDetails(sourceLabel, targetLabel, responses),
        ),
    );
  }

  function viewDataHallCables(bucket: DataHallCableBucket, cableType: string) {
    const target = bucket.scope === "internal" ? `${dataHall} ${cableType}` : `${bucket.target_data_hall ?? "External"} ${cableType}`;
    const loadPage: CableDetailPageLoader = (offset, limit) =>
      fetchDataHallCables(dataHall, bucket.scope, cableType, bucket.target_data_hall, limit, offset);
    openCableDetail(
      { source: dataHall, target },
      () => loadPage(0, 500),
      loadPage,
    );
  }

  function openCableDetail(
    route: { source: string; target: string },
    load: () => Promise<CableDetailResponse>,
    pageLoad: CableDetailPageLoader | null = null,
  ) {
    const requestId = cableDetailRequestRef.current + 1;
    cableDetailRequestRef.current = requestId;
    setCableDetail(null);
    setSelectedCableUid(null);
    setSelectedCableUids([]);
    setCableDetailRoute(route);
    setCableDetailPageLoader(() => pageLoad);
    setIsCableDetailLoading(true);
    setError(null);
    load()
      .then((nextCableDetail) => {
        if (cableDetailRequestRef.current !== requestId) return;
        setCableDetail(nextCableDetail);
        const firstCableUid = nextCableDetail.cables[0]?.uid ?? null;
        setSelectedCableUid(firstCableUid);
        setSelectedCableUids(firstCableUid ? [firstCableUid] : []);
      })
      .catch((requestError: Error) => {
        if (cableDetailRequestRef.current !== requestId) return;
        setError(requestError.message);
        setCableDetailRoute(null);
      })
      .finally(() => {
        if (cableDetailRequestRef.current === requestId) setIsCableDetailLoading(false);
      });
  }

  function closeCableDetail() {
    cableDetailRequestRef.current += 1;
    setCableDetail(null);
    setSelectedCableUid(null);
    setSelectedCableUids([]);
    setCableDetailRoute(null);
    setCableDetailPageLoader(null);
    setIsCableDetailLoading(false);
  }

  function requestCableDetailPage(offset: number, limit: number) {
    if (!cableDetailPageLoader) return;
    const requestId = cableDetailRequestRef.current + 1;
    cableDetailRequestRef.current = requestId;
    setIsCableDetailLoading(true);
    setError(null);
    cableDetailPageLoader(offset, limit)
      .then((nextCableDetail) => {
        if (cableDetailRequestRef.current !== requestId) return;
        setCableDetail(nextCableDetail);
        const firstCableUid = nextCableDetail.cables[0]?.uid ?? null;
        setSelectedCableUid(firstCableUid);
        setSelectedCableUids(firstCableUid ? [firstCableUid] : []);
      })
      .catch((requestError: Error) => {
        if (cableDetailRequestRef.current !== requestId) return;
        setError(requestError.message);
      })
      .finally(() => {
        if (cableDetailRequestRef.current === requestId) setIsCableDetailLoading(false);
      });
  }

  function selectDevice(device: Device) {
    const deviceUid = `${device.cabinet_id}:${device.rack_unit}`;
    setSelectedDeviceUid(deviceUid);
    setSelectedDeviceUids([deviceUid]);
    closeCableDetail();
    setError(null);
    loadDeviceConnections(deviceUid)
      .then(setDeviceDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }

  function viewPortLayout(device: Device) {
    selectDevice(device);
    setCenterViewMode("port_layout");
  }

  function jumpToDevice(deviceUid: string) {
    const parsed = parseDeviceUid(deviceUid);
    if (!parsed) return;
    setMode("topology");
    setDataHall(parsed.dataHall);
    setSelectedCabinetUid(parsed.cabinetUid);
    setSelectedCabinetUids([parsed.cabinetUid]);
    setSelectedDeviceUid(parsed.deviceUid);
    setSelectedDeviceUids([parsed.deviceUid]);
    setDeviceScrollRequest((current) => current + 1);
    closeCableDetail();
    setError(null);
    loadDeviceConnections(parsed.deviceUid)
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
    cabinetDetailCacheRef.current = {};
    dataHallCableSummaryCacheRef.current = {};
    deviceDetailCacheRef.current = {};
    if (selectedCabinetUid) {
      loadCabinetDetail(selectedCabinetUid)
        .then(setDetail)
        .catch((requestError: Error) => setError(requestError.message));
    }
    if (selectedCabinetUids.length > 1) {
      Promise.all(selectedCabinetUids.map(loadCabinetDetail))
        .then(setSelectedCabinetDetails)
        .catch((requestError: Error) => setError(requestError.message));
    }
    if (selectedDeviceUids.length > 1) {
      Promise.all(selectedDeviceUids.map(loadDeviceConnections))
        .then(setSelectedDeviceDetails)
        .catch((requestError: Error) => setError(requestError.message));
    }
    fetchCabinetLayout(dataHall)
      .then((layout) => {
        cabinetLayoutCacheRef.current[dataHall] = layout;
        setCabinets(layout);
      })
      .catch((requestError: Error) => setError(requestError.message));
  }

  function selectCabinet(cabinetUid: string, gesture: SelectionGesture) {
    if (isRemoveGesture(gesture, selectionMode)) {
      const nextSelection = selectedCabinetUids.filter((uid) => uid !== cabinetUid);
      setSelectedCabinetUids(nextSelection);
      if (selectedCabinetUid === cabinetUid) {
        setSelectedCabinetUid(nextSelection.at(-1) ?? null);
        if (!nextSelection.length) setDetail(null);
      }
      return;
    }

    if (isMultiGesture(gesture, selectionMode)) {
      setSelectedCabinetUids((current) => (current.includes(cabinetUid) ? current : [...current, cabinetUid]));
    } else {
      setSelectedCabinetUids([cabinetUid]);
    }
    setSelectedCabinetUid(cabinetUid);
    closeCableDetail();
    clearDeviceSelection();
  }

  function selectDeviceWithGesture(device: Device, gesture: SelectionGesture) {
    const deviceUid = `${device.cabinet_id}:${device.rack_unit}`;
    if (isRemoveGesture(gesture, selectionMode)) {
      const nextSelection = selectedDeviceUids.filter((uid) => uid !== deviceUid);
      setSelectedDeviceUids(nextSelection);
      if (selectedDeviceUid === deviceUid) {
        setSelectedDeviceUid(nextSelection.at(-1) ?? null);
        setDeviceDetail(null);
        setCenterViewMode("cabinet_map");
      }
      return;
    }

    if (isMultiGesture(gesture, selectionMode)) {
      setSelectedDeviceUids((current) => (current.includes(deviceUid) ? current : [...current, deviceUid]));
    } else {
      setSelectedDeviceUids([deviceUid]);
    }
    setSelectedDeviceUid(deviceUid);
    closeCableDetail();
    setError(null);
    loadDeviceConnections(deviceUid)
      .then(setDeviceDetail)
      .catch((requestError: Error) => setError(requestError.message));
  }

  function selectCable(cableUid: string, gesture: SelectionGesture) {
    if (isRemoveGesture(gesture, selectionMode)) {
      const nextSelection = selectedCableUids.filter((uid) => uid !== cableUid);
      setSelectedCableUids(nextSelection);
      if (selectedCableUid === cableUid) setSelectedCableUid(nextSelection.at(-1) ?? null);
      return;
    }

    if (isMultiGesture(gesture, selectionMode)) {
      setSelectedCableUids((current) => (current.includes(cableUid) ? current : [...current, cableUid]));
    } else {
      setSelectedCableUids([cableUid]);
    }
    setSelectedCableUid(cableUid);
  }

  function handleOperationResponse(response: OperationResponse, options: { recordUndo?: boolean } = {}) {
    const shouldRecordUndo = options.recordUndo ?? true;
    applyOperation(response.operation);
    updateOperationCursor(response.version);
    setLastSavedVersion(response.version);
    setLastSavedAt(new Date().toLocaleTimeString());
    if (shouldRecordUndo) {
      setUndoStack((current) => [...current, response.operation]);
      setRedoStack([]);
    }
    setOperationList((current) =>
      current
        ? {
            operations: [...current.operations.filter((operation) => operation.opId !== response.operation.opId), response.operation],
            version: response.version,
          }
        : current,
    );
  }

  function submitOperation(
    operation: Promise<OperationResponse>,
    options: {
      onError?: () => void;
      onSuccess?: (response: OperationResponse) => void;
      recordUndo?: boolean;
    } = {},
  ) {
    setPendingSaveCount((current) => current + 1);
    setError(null);
    operation
      .then((response) => {
        handleOperationResponse(response, { recordUndo: options.recordUndo });
        options.onSuccess?.(response);
      })
      .catch((requestError: Error) => {
        setError(requestError.message);
        options.onError?.();
      })
      .finally(() => setPendingSaveCount((current) => Math.max(0, current - 1)));
  }

  function submitBulkOperation(
    operation: Promise<BulkOperationResponse>,
    options: {
      onError?: () => void;
      onSuccess?: (response: BulkOperationResponse) => void;
      recordUndo?: boolean;
    } = {},
  ) {
    const shouldRecordUndo = options.recordUndo ?? true;
    setPendingSaveCount((current) => current + 1);
    setError(null);
    operation
      .then((response) => {
        for (const nextOperation of response.operations) {
          applyOperation(nextOperation);
        }
        updateOperationCursor(response.version);
        setLastSavedVersion(response.version);
        setLastSavedAt(new Date().toLocaleTimeString());
        if (shouldRecordUndo && response.operations.length) {
          setUndoStack((current) => [...current, ...response.operations]);
          setRedoStack([]);
        }
        setOperationList((current) =>
          current
            ? {
                operations: [
                  ...current.operations.filter(
                    (operation) => !response.operations.some((nextOperation) => nextOperation.opId === operation.opId),
                  ),
                  ...response.operations,
                ],
                version: response.version,
              }
            : current,
        );
        options.onSuccess?.(response);
      })
      .catch((requestError: Error) => {
        setError(requestError.message);
        options.onError?.();
      })
      .finally(() => setPendingSaveCount((current) => Math.max(0, current - 1)));
  }

  function runClientUndo() {
    const operation = undoStack.at(-1);
    if (!operation || pendingSaveCount > 0) return;
    const undoRequest = operationRequestForValues(operation, operation.before);
    if (!undoRequest) return;
    setUndoStack((current) => current.slice(0, -1));
    submitOperation(undoRequest, {
      recordUndo: false,
      onError: () => setUndoStack((current) => [...current, operation]),
      onSuccess: () => setRedoStack((current) => [...current, operation]),
    });
  }

  function runClientRedo() {
    const operation = redoStack.at(-1);
    if (!operation || pendingSaveCount > 0) return;
    const redoRequest = operationRequestForValues(operation, operation.after);
    if (!redoRequest) return;
    setRedoStack((current) => current.slice(0, -1));
    submitOperation(redoRequest, {
      recordUndo: false,
      onError: () => setRedoStack((current) => [...current, operation]),
      onSuccess: () => setUndoStack((current) => [...current, operation]),
    });
  }

  function refreshOperations() {
    setError(null);
    fetchOperations()
      .then((operations) => {
        setOperationList(operations);
        updateOperationCursor(operations.version);
      })
      .catch((requestError: Error) => setError(requestError.message));
  }

  function pollOperations() {
    const after = lastSeenOperationIdRef.current;
    if (after == null || isPollingOperationsRef.current) return;
    isPollingOperationsRef.current = true;
    fetchOperations(100, after)
      .then((nextOperations) => {
        if (!nextOperations.operations.length) {
          updateOperationCursor(nextOperations.version);
          return;
        }
        for (const operation of nextOperations.operations) {
          applyOperation(operation);
        }
        const latestVersion = nextOperations.version;
        updateOperationCursor(latestVersion);
        setLastSavedVersion(latestVersion);
        setLastSavedAt(new Date().toLocaleTimeString());
        setOperationList((current) =>
          current
            ? {
                operations: [
                  ...current.operations.filter(
                    (operation) => !nextOperations.operations.some((nextOperation) => nextOperation.opId === operation.opId),
                  ),
                  ...nextOperations.operations,
                ],
                version: latestVersion,
              }
            : nextOperations,
        );
        refreshTopologyContext();
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => {
        isPollingOperationsRef.current = false;
      });
  }

  function updateOperationCursor(version: number) {
    const nextVersion = Math.max(lastSeenOperationIdRef.current ?? 0, version);
    lastSeenOperationIdRef.current = nextVersion;
    setOperationCursorVersion(nextVersion);
  }

  function applyOperation(operation: Operation) {
    const values = operation.after;
    if (operation.entityType === "cabinet") {
      const lifecycleStatus = asString(values.lifecycle_status);
      if (!lifecycleStatus) return;
      setCabinets((current) =>
        current.map((cabinet) =>
          cabinet.cabinet_uid === operation.entityId ? { ...cabinet, lifecycle_status: lifecycleStatus } : cabinet,
        ),
      );
      cabinetLayoutCacheRef.current = Object.fromEntries(
        Object.entries(cabinetLayoutCacheRef.current).map(([hall, layout]) => [
          hall,
          layout.map((cabinet) =>
            cabinet.cabinet_uid === operation.entityId ? { ...cabinet, lifecycle_status: lifecycleStatus } : cabinet,
          ),
        ]),
      );
      setDetail((current) =>
        current && current.cabinet.cabinet_uid === operation.entityId
          ? { ...current, cabinet: { ...current.cabinet, lifecycle_status: lifecycleStatus } }
          : current,
      );
      setSelectedCabinetDetails((current) =>
        current.map((selectedDetail) =>
          selectedDetail.cabinet.cabinet_uid === operation.entityId
            ? { ...selectedDetail, cabinet: { ...selectedDetail.cabinet, lifecycle_status: lifecycleStatus } }
            : selectedDetail,
        ),
      );
      cabinetDetailCacheRef.current = Object.fromEntries(
        Object.entries(cabinetDetailCacheRef.current).map(([cabinetUid, cachedDetail]) => [
          cabinetUid,
          cachedDetail.cabinet.cabinet_uid === operation.entityId
            ? { ...cachedDetail, cabinet: { ...cachedDetail.cabinet, lifecycle_status: lifecycleStatus } }
            : cachedDetail,
        ]),
      );
      return;
    }

    if (operation.entityType === "device") {
      const lifecycleStatus = asString(values.lifecycle_status);
      if (!lifecycleStatus) return;
      const updateDevices = (devices: Device[]) =>
        devices.map((device) =>
          `${device.cabinet_id}:${device.rack_unit}`.toUpperCase() === operation.entityId.toUpperCase()
            ? { ...device, lifecycle_status: lifecycleStatus }
            : device,
        );
      setDetail((current) => {
        if (!current) return current;
        return {
          ...current,
          devices: updateDevices(current.devices),
        };
      });
      setSelectedCabinetDetails((current) =>
        current.map((selectedDetail) => ({ ...selectedDetail, devices: updateDevices(selectedDetail.devices) })),
      );
      cabinetDetailCacheRef.current = Object.fromEntries(
        Object.entries(cabinetDetailCacheRef.current).map(([cabinetUid, cachedDetail]) => [
          cabinetUid,
          { ...cachedDetail, devices: updateDevices(cachedDetail.devices) },
        ]),
      );
      return;
    }

    if (operation.entityType === "cable") {
      setCableDetail((current) => {
        if (!current) return current;
        return {
          ...current,
          cables: current.cables.map((cable) =>
            cable.uid === operation.entityId
              ? {
                  ...cable,
                  status: asString(values.status) ?? cable.status,
                  length_used_meters:
                    typeof values.length_used_meters === "number" ? values.length_used_meters : cable.length_used_meters,
                  length_meters:
                    typeof values.length_used_meters === "number" ? values.length_used_meters : cable.length_meters,
                  note: asString(values.note) ?? cable.note,
                  current_phase: "current_phase" in values ? (values.current_phase as typeof cable.current_phase) : cable.current_phase,
                  progress: "progress" in values ? (values.progress as typeof cable.progress) : cable.progress,
                }
              : cable,
          ),
        };
      });
    }
  }

  return (
    <main className={`app-shell selection-mode-${selectionMode}`}>
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
            <button className={mode === "operations" ? "is-active" : ""} onClick={() => setMode("operations")}>
              Operations
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
          <div className="segmented-control selection-mode-control" role="group" aria-label="Selection mode">
            <button className={selectionMode === "single" ? "is-active" : ""} onClick={() => setSelectionMode("single")}>
              Pointer
            </button>
            <button className={selectionMode === "multi" ? "is-active" : ""} onClick={() => setSelectionMode("multi")}>
              Multi
            </button>
            <button className={selectionMode === "remove" ? "is-active" : ""} onClick={() => setSelectionMode("remove")}>
              Remove
            </button>
          </div>
          <div className="segmented-control" role="group" aria-label="Operations">
            <button disabled={!canEdit || pendingSaveCount > 0 || undoStack.length === 0} onClick={runClientUndo}>
              Undo
            </button>
            <button disabled={!canEdit || pendingSaveCount > 0 || redoStack.length === 0} onClick={runClientRedo}>
              Redo
            </button>
          </div>
          <div className="role-pill" title={lastSavedAt ? `Last saved at ${lastSavedAt}` : undefined}>
            {pendingSaveCount > 0 ? "Saving" : "Saved"}
          </div>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {mode === "validation" ? (
        <ValidationView onJumpToDevice={jumpToDevice} onJumpToPort={jumpToPort} />
      ) : mode === "operations" ? (
        <OperationDebugView operationList={operationList} onRefresh={refreshOperations} />
      ) : (
        <div className="workspace">
          <CabinetDetailsPanel
            detail={detail}
            dataHall={dataHall}
            cabinets={cabinets}
            selectedCabinetUids={selectedCabinetUids}
            selectedDeviceUid={selectedDeviceUid}
            selectedDeviceUids={selectedDeviceUids}
            deviceScrollRequest={deviceScrollRequest}
            connectedDeviceUids={connectedDeviceUids}
            onSelectDevice={selectDeviceWithGesture}
            onViewPortLayout={viewPortLayout}
            activePortLayoutDeviceUid={centerViewMode === "port_layout" ? selectedDeviceUid : null}
            onShowCabinetMap={() => setCenterViewMode("cabinet_map")}
            onClearDeviceSelection={clearDeviceSelection}
            canEdit={canEdit}
            expectedVersion={operationCursorVersion}
            lifecycleStatuses={topologyEnums?.lifecycle_statuses ?? []}
            onStatusChanged={submitOperation}
            onBulkStatusChanged={submitBulkOperation}
          />
          {isLoading ? (
            <section className="map-pane loading-pane">{t("common.loading", { target: dataHall })}</section>
          ) : (
            <div className={`map-stack ${selectedDevice ? "has-center-toggle" : ""}`}>
              {selectedDevice ? (
                <div className="center-view-toggle map-size-control" aria-label={t("portLayout.mode")}>
                  <button
                    className={centerViewMode === "cabinet_map" ? "is-active" : ""}
                    onClick={() => setCenterViewMode("cabinet_map")}
                    type="button"
                  >
                    {t("map.cabinetMap")}
                  </button>
                  <button
                    className={centerViewMode === "port_layout" ? "is-active" : ""}
                    onClick={() => setCenterViewMode("port_layout")}
                    type="button"
                  >
                    {t("portLayout.title")}
                  </button>
                </div>
              ) : null}
              {centerViewMode === "port_layout" ? (
                <DevicePortLayout
                  cableDetail={cableDetail}
                  device={selectedDevice}
                  selectedCable={selectedCable}
                />
              ) : (
                <CabinetMap
                  cabinets={cabinets}
                  connectedDataHalls={connectedDataHalls}
                  dataHall={dataHall}
                  dataHalls={DATA_HALLS}
                  selectedCabinetUid={selectedCabinetUid}
                  selectedCabinetUids={selectedCabinetUidSet}
                  selectedDeviceCabinetUid={deviceDetail?.source_cabinet_uid ?? null}
                  connectedCabinetUids={connectedCabinetUids}
                  connectedCabinetCounts={cabinetConnectionCounts}
                  isDeviceMode={Boolean(selectedDeviceUid)}
                  mapSize={mapSize}
                  progressDisplay={mapProgressDisplay}
                  onSelectCabinet={selectCabinet}
                  onClearSelection={clearSelection}
                  onDataHallChange={setDataHall}
                  onMapSizeChange={setMapSize}
                  onProgressDisplayChange={setMapProgressDisplay}
                />
              )}
              <CableDetailOverlay
                cableDetail={cableDetail}
                isLoading={isCableDetailLoading}
                routeLabel={cableDetailRoute}
                selectedCableUid={selectedCableUid}
                selectedCableUids={selectedCableUidSet}
                selectionMode={selectionMode}
                canEdit={canEdit}
                expectedVersion={operationCursorVersion}
                topologyEnums={topologyEnums}
                onClose={closeCableDetail}
                onPageRequest={cableDetailPageLoader ? requestCableDetailPage : undefined}
                onSelectCable={(cable, gesture) => selectCable(cable.uid, gesture)}
                onCableUpdated={handleOperationResponse}
              />
            </div>
          )}
          <CabinetConnectionsPanel
            detail={detail}
            selectedCabinetDetails={selectedCabinetDetails}
            deviceDetail={deviceDetail}
            selectedDeviceDetails={selectedDeviceDetails}
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

function mergeCabinetCableDetails(
  sourceCabinetUid: string,
  targetCabinetUid: string,
  responses: CableDetailResponse[],
): CabinetCableDetailResponse {
  const cables = uniqueCables(responses.flatMap((response) => response.cables));
  const totalCables = responses.reduce((total, response) => total + (cableDetailTotal(response) ?? response.cables.length), 0);
  return {
    source_cabinet_uid: sourceCabinetUid,
    target_cabinet_uid: targetCabinetUid,
    cables,
    total_cables: totalCables,
    offset: 0,
    limit: cables.length,
    has_more: responses.some(hasMoreCables),
  };
}

function cableDetailTotal(response: CableDetailResponse): number | null {
  return "total_cables" in response && typeof response.total_cables === "number" ? response.total_cables : null;
}

function hasMoreCables(response: CableDetailResponse): boolean {
  return "has_more" in response && Boolean(response.has_more);
}

function mergeDeviceCableDetails(
  sourceDeviceUid: string,
  targetDeviceUid: string,
  responses: CableDetailResponse[],
): CableDetailResponse {
  return {
    source_device_uid: sourceDeviceUid,
    target_device_uid: targetDeviceUid,
    cables: uniqueCables(responses.flatMap((response) => response.cables)),
  };
}

function uniqueCables(cables: CabinetCableDetail[]): CabinetCableDetail[] {
  const byUid = new Map<string, CabinetCableDetail>();
  for (const cable of cables) {
    byUid.set(cable.uid, cable);
  }
  return [...byUid.values()];
}

function OperationDebugView({
  operationList,
  onRefresh,
}: {
  operationList: OperationListResponse | null;
  onRefresh: () => void;
}) {
  const operations = [...(operationList?.operations ?? [])].reverse();
  return (
    <section className="operations-pane">
      <div className="pane-header">
        <div>
          <span className="eyebrow">Debug</span>
          <h2>Operation Log</h2>
        </div>
        <div className="table-pagination-controls">
          <span>{operationList ? `Version ${operationList.version}` : "Loading"}</span>
          <button type="button" onClick={onRefresh}>
            Refresh
          </button>
        </div>
      </div>
      <div className="validation-table-scroll operations-table-scroll">
        <table className="validation-table operations-table">
          <thead>
            <tr>
              <th>opId</th>
              <th>Type</th>
              <th>Entity</th>
              <th>Timestamp</th>
              <th>User</th>
              <th>Before</th>
              <th>After</th>
            </tr>
          </thead>
          <tbody>
            {operations.map((operation) => (
              <tr key={operation.opId}>
                <td>{operation.opId}</td>
                <td>{operation.type}</td>
                <td>{`${operation.entityType}:${operation.entityId}`}</td>
                <td>{operation.timestamp}</td>
                <td>{operation.userUid ? `${operation.userUid}${operation.userRole ? ` (${operation.userRole})` : ""}` : ""}</td>
                <td>
                  <code>{JSON.stringify(operation.before)}</code>
                </td>
                <td>
                  <code>{JSON.stringify(operation.after)}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!operations.length ? <div className="empty-table-space">No logged operations.</div> : null}
      </div>
    </section>
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

function operationRequestForValues(operation: Operation, values: Record<string, unknown>): Promise<OperationResponse> | null {
  if (operation.entityType === "cabinet") {
    const lifecycleStatus = asString(values.lifecycle_status);
    return lifecycleStatus ? updateCabinetStatus(operation.entityId, lifecycleStatus) : null;
  }

  if (operation.entityType === "device") {
    const lifecycleStatus = asString(values.lifecycle_status);
    return lifecycleStatus ? updateDeviceStatus(operation.entityId, lifecycleStatus) : null;
  }

  if (operation.entityType === "cable") {
    const payload: UpdateCablePayload = {};
    if ("status" in values && (typeof values.status === "string" || values.status === null)) {
      payload.status = values.status ?? undefined;
    }
    if ("progress" in values && isRecord(values.progress)) {
      payload.progress = Object.fromEntries(
        Object.entries(values.progress).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
      );
    }
    if ("current_phase" in values && isRecord(values.current_phase) && typeof values.current_phase.name === "string") {
      payload.current_phase = values.current_phase as UpdateCablePayload["current_phase"];
    }
    if ("length_used_meters" in values && (typeof values.length_used_meters === "number" || values.length_used_meters === null)) {
      payload.length_used_meters = values.length_used_meters;
    }
    if ("length_meters" in values && (typeof values.length_meters === "number" || values.length_meters === null)) {
      payload.length_meters = values.length_meters;
    }
    if ("note" in values && (typeof values.note === "string" || values.note === null)) {
      payload.note = values.note;
    }
    return Object.keys(payload).length ? updateCable(operation.entityId, payload) : null;
  }

  return null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isMultiGesture(gesture: SelectionGesture, selectionMode: SelectionMode): boolean {
  return selectionMode === "multi" || gesture.shiftKey;
}

function isRemoveGesture(gesture: SelectionGesture, selectionMode: SelectionMode): boolean {
  return selectionMode === "remove" || gesture.ctrlKey || gesture.metaKey;
}

import { useEffect, useMemo, useState } from "react";
import { fetchCabinetDetail, fetchCabinetLayout } from "./api";
import { CabinetConnectionsPanel } from "./components/CabinetConnectionsPanel";
import { CabinetDetailsPanel } from "./components/CabinetDetailsPanel";
import { CabinetMap } from "./components/CabinetMap";
import type { CabinetDetailResponse, CabinetLayoutItem } from "./types";

const DATA_HALLS = ["DH1", "DH2"];

export function App() {
  const [dataHall, setDataHall] = useState("DH1");
  const [cabinets, setCabinets] = useState<CabinetLayoutItem[]>([]);
  const [selectedCabinetUid, setSelectedCabinetUid] = useState<string | null>(null);
  const [detail, setDetail] = useState<CabinetDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    setDetail(null);
    setSelectedCabinetUid(null);
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

  const connectedCabinetUids = useMemo(
    () => new Set(detail?.connections.map((connection) => connection.target_cabinet_uid) ?? []),
    [detail],
  );

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">AI DC Infra Graph</span>
          <h1>Infrastructure Topology</h1>
        </div>
        <div className="segmented-control" role="tablist" aria-label="Data hall">
          {DATA_HALLS.map((hall) => (
            <button className={hall === dataHall ? "is-active" : ""} key={hall} onClick={() => setDataHall(hall)}>
              {hall}
            </button>
          ))}
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="workspace">
        <CabinetDetailsPanel detail={detail} />
        {isLoading ? (
          <section className="map-pane loading-pane">Loading {dataHall}</section>
        ) : (
          <CabinetMap
            cabinets={cabinets}
            selectedCabinetUid={selectedCabinetUid}
            connectedCabinetUids={connectedCabinetUids}
            onSelectCabinet={setSelectedCabinetUid}
          />
        )}
        <CabinetConnectionsPanel detail={detail} />
      </div>
    </main>
  );
}

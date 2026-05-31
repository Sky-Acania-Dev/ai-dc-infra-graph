import { useEffect, useRef, useState } from "react";
import type { CabinetDetailResponse, CabinetLayoutItem, Device } from "../types";
import { CabinetDeviceLayout } from "./CabinetDeviceLayout";
import { useI18n } from "../i18n";

type CabinetDetailsPanelProps = {
  detail: CabinetDetailResponse | null;
  dataHall: string;
  cabinets: CabinetLayoutItem[];
  selectedDeviceUid: string | null;
  connectedDeviceUids: Set<string>;
  onSelectDevice: (device: Device) => void;
  onClearDeviceSelection: () => void;
};

export function CabinetDetailsPanel({
  detail,
  dataHall,
  cabinets,
  selectedDeviceUid,
  connectedDeviceUids,
  onSelectDevice,
  onClearDeviceSelection,
}: CabinetDetailsPanelProps) {
  const { formatLifecycleStatus, formatNumber, t } = useI18n();
  const categorySummaryRef = useRef<HTMLElement | null>(null);
  const [categorySummaryHasScrollbar, setCategorySummaryHasScrollbar] = useState(false);

  useEffect(() => {
    if (detail) return;

    function updateScrollbarState() {
      const element = categorySummaryRef.current;
      setCategorySummaryHasScrollbar(Boolean(element && element.scrollHeight > element.clientHeight));
    }

    updateScrollbarState();
    window.addEventListener("resize", updateScrollbarState);
    return () => window.removeEventListener("resize", updateScrollbarState);
  }, [cabinets, detail]);

  if (!detail) {
    const categories = categoryCounts(cabinets);
    return (
      <aside className="side-pane">
        <span className="eyebrow">{t("dataHall.summary")}</span>
        <h1>{dataHall}</h1>
        <dl className="facts">
          <div>
            <dt>{t("cabinet.cabinets")}</dt>
            <dd>{formatNumber(cabinets.length)}</dd>
          </div>
          <div>
            <dt>{t("cabinet.categories")}</dt>
            <dd>{formatNumber(categories.length)}</dd>
          </div>
        </dl>
        <section
          className={`category-summary ${categorySummaryHasScrollbar ? "has-scrollbar" : ""}`}
          ref={categorySummaryRef}
        >
          <div className="section-title">{t("cabinet.types")}</div>
          {categories.map(([category, count]) => (
            <div className="category-row" key={category}>
              <span>{category}</span>
              <b>{formatNumber(count)}</b>
            </div>
          ))}
        </section>
      </aside>
    );
  }

  return (
    <aside className="side-pane" onClick={onClearDeviceSelection}>
      <span className="eyebrow">{t("cabinet.details")}</span>
      <h1>{detail.cabinet.cabinet_uid}</h1>
      <dl className="facts">
        <div>
          <dt>{t("cabinet.category")}</dt>
          <dd>{detail.cabinet.category}</dd>
        </div>
        <div>
          <dt>{t("cabinet.group")}</dt>
          <dd>{detail.cabinet.cabinet_group || t("cabinet.unassigned")}</dd>
        </div>
        <div>
          <dt>{t("cabinet.status")}</dt>
          <dd>{formatLifecycleStatus(detail.cabinet.lifecycle_status)}</dd>
        </div>
        <div>
          <dt>{t("cabinet.rackUnits")}</dt>
          <dd>{formatNumber(detail.cabinet.max_rack_unit)}U</dd>
        </div>
        <div>
          <dt>{t("cabinet.devices")}</dt>
          <dd>{formatNumber(detail.stats.devices)}</dd>
        </div>
        <div>
          <dt>{t("cabinet.ports")}</dt>
          <dd>{formatNumber(detail.stats.ports)}</dd>
        </div>
        <div>
          <dt>{t("cabinet.cables")}</dt>
          <dd>{formatNumber(detail.stats.cables)}</dd>
        </div>
      </dl>
      <CabinetDeviceLayout
        devices={detail.devices}
        maxRackUnit={detail.cabinet.max_rack_unit}
        selectedDeviceUid={selectedDeviceUid}
        connectedDeviceUids={connectedDeviceUids}
        onSelectDevice={onSelectDevice}
      />
    </aside>
  );
}

function categoryCounts(cabinets: CabinetLayoutItem[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const cabinet of cabinets) {
    counts.set(cabinet.category, (counts.get(cabinet.category) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

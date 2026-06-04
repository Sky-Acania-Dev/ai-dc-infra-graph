import { useEffect, useState } from "react";
import type { CabinetDetailResponse, CabinetLayoutItem, Device, OperationResponse } from "../types";
import { CabinetDeviceLayout } from "./CabinetDeviceLayout";
import { ProgressCircle } from "./ProgressCircle";
import { useI18n } from "../i18n";
import { updateCabinetStatus, updateDeviceStatus } from "../api";
import { categoryColor } from "../colors";
import { useDragPan } from "../hooks/useDragPan";

type CabinetDetailsPanelProps = {
  detail: CabinetDetailResponse | null;
  dataHall: string;
  cabinets: CabinetLayoutItem[];
  selectedDeviceUid: string | null;
  deviceScrollRequest: number;
  connectedDeviceUids: Set<string>;
  onSelectDevice: (device: Device) => void;
  onViewPortLayout: (device: Device) => void;
  onClearDeviceSelection: () => void;
  canEdit: boolean;
  lifecycleStatuses: string[];
  onStatusChanged: (operation: Promise<OperationResponse>) => void;
};

export function CabinetDetailsPanel({
  detail,
  dataHall,
  cabinets,
  selectedDeviceUid,
  deviceScrollRequest,
  connectedDeviceUids,
  onSelectDevice,
  onViewPortLayout,
  onClearDeviceSelection,
  canEdit,
  lifecycleStatuses,
  onStatusChanged,
}: CabinetDetailsPanelProps) {
  const { formatConstructionPhase, formatLifecycleStatus, formatNumber, t } = useI18n();
  const categorySummaryPan = useDragPan<HTMLElement>();
  const [categorySummaryHasScrollbar, setCategorySummaryHasScrollbar] = useState(false);

  useEffect(() => {
    if (detail) return;

    function updateScrollbarState() {
      const element = categorySummaryPan.ref.current;
      setCategorySummaryHasScrollbar(Boolean(element && element.scrollHeight > element.clientHeight));
    }

    updateScrollbarState();
    window.addEventListener("resize", updateScrollbarState);
    return () => window.removeEventListener("resize", updateScrollbarState);
  }, [cabinets, categorySummaryPan.ref, detail]);

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
          className={`category-summary drag-pan-surface ${categorySummaryHasScrollbar ? "has-scrollbar" : ""}`}
          {...categorySummaryPan}
        >
          <div className="section-title">{t("cabinet.types")}</div>
          {categories.map(([category, count]) => (
            <div className="category-row" key={category}>
              <span style={{ color: categoryColor(category) }}>{category}</span>
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
          <dd>
            {canEdit ? (
              <select
                className="inline-select"
                value={detail.cabinet.lifecycle_status}
                onClick={(event) => event.stopPropagation()}
                onChange={(event) => {
                  onStatusChanged(updateCabinetStatus(detail.cabinet.cabinet_uid, event.target.value));
                }}
              >
                {lifecycleStatuses.map((status) => (
                  <option key={status} value={status}>
                    {formatLifecycleStatus(status)}
                  </option>
                ))}
              </select>
            ) : (
              formatLifecycleStatus(detail.cabinet.lifecycle_status)
            )}
          </dd>
        </div>
        <div>
          <dt>{t("cabinet.constructionPhase")}</dt>
          <dd>{formatConstructionPhase(detail.cabinet.construction_phase)}</dd>
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
        <div>
          <dt>{t("cabinet.termination")}</dt>
          <dd className="progress-fact">
            <ProgressCircle percent={detail.stats.cable_termination_percent} />
            {formatNumber(detail.stats.cable_termination_percent)}%
          </dd>
        </div>
        <div>
          <dt>{t("cabinet.dress")}</dt>
          <dd className="progress-fact">
            <ProgressCircle percent={detail.stats.cable_dress_percent} />
            {formatNumber(detail.stats.cable_dress_percent)}%
          </dd>
        </div>
      </dl>
      <CabinetDeviceLayout
        devices={detail.devices}
        maxRackUnit={detail.cabinet.max_rack_unit}
        selectedDeviceUid={selectedDeviceUid}
        scrollRequest={deviceScrollRequest}
        connectedDeviceUids={connectedDeviceUids}
        onSelectDevice={onSelectDevice}
        onViewPortLayout={onViewPortLayout}
        canEdit={canEdit}
        lifecycleStatuses={lifecycleStatuses}
        onDeviceStatusChange={(device, lifecycleStatus) => {
          onStatusChanged(updateDeviceStatus(`${device.cabinet_id}:${device.rack_unit}`, lifecycleStatus));
        }}
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

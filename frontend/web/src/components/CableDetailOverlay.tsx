import { useMemo, useState } from "react";
import type { CabinetCableDetail, CableDetailResponse } from "../types";
import { useI18n } from "../i18n";

type CableDetailOverlayProps = {
  cableDetail: CableDetailResponse | null;
  onClose: () => void;
};

type SortDirection = "asc" | "desc";
type CableColumnKey =
  | "cable_type"
  | "status"
  | "group"
  | "a_port_uid"
  | "z_port_uid"
  | "a_optic"
  | "z_optic";
type CableColumn = {
  key: CableColumnKey;
  label: string;
};

const COLUMNS: Array<CableColumn & { labelKey: string }> = [
  { key: "cable_type", label: "Type", labelKey: "cable.column.type" },
  { key: "status", label: "Status", labelKey: "cable.column.status" },
  { key: "group", label: "Group", labelKey: "cable.column.group" },
  { key: "a_port_uid", label: "A Port", labelKey: "cable.column.aPort" },
  { key: "z_port_uid", label: "Z Port", labelKey: "cable.column.zPort" },
  { key: "a_optic", label: "A Optic", labelKey: "cable.column.aOptic" },
  { key: "z_optic", label: "Z Optic", labelKey: "cable.column.zOptic" },
];

export function CableDetailOverlay({ cableDetail, onClose }: CableDetailOverlayProps) {
  const { formatCableStatus, formatNumber, t } = useI18n();
  const [sortKey, setSortKey] = useState<CableColumnKey>("cable_type");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [filters, setFilters] = useState<Partial<Record<CableColumnKey, string>>>({});
  const visibleCables = useMemo(() => {
    if (!cableDetail) return [];
    return cableDetail.cables
      .filter((cable) =>
        COLUMNS.every((column) => {
          const filter = (filters[column.key] ?? "").trim().toLowerCase();
          return !filter || String(cable[column.key] ?? "").toLowerCase().includes(filter);
        }),
      )
      .slice()
      .sort((left, right) => {
        const leftValue = String(left[sortKey] ?? "");
        const rightValue = String(right[sortKey] ?? "");
        const result = leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: "base" });
        return sortDirection === "asc" ? result : -result;
      });
  }, [cableDetail, filters, sortDirection, sortKey]);

  if (!cableDetail) return null;
  const sourceLabel = "source_device_uid" in cableDetail ? cableDetail.source_device_uid : cableDetail.source_cabinet_uid;
  const targetLabel = "target_device_uid" in cableDetail ? cableDetail.target_device_uid : cableDetail.target_cabinet_uid;

  function toggleSort(columnKey: CableColumnKey) {
    if (sortKey === columnKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(columnKey);
    setSortDirection("asc");
  }

  return (
    <div className="cable-overlay">
      <div className="overlay-header">
        <div>
          <span className="eyebrow">{t("cable.details")}</span>
          <h2>
            {t("cable.routeTitle", { source: sourceLabel, target: targetLabel })}
          </h2>
          <div className="overlay-count">
            {t("cable.countVisible", {
              visible: formatNumber(visibleCables.length),
              total: formatNumber(cableDetail.cables.length),
            })}
          </div>
        </div>
        <button className="icon-button" onClick={onClose} aria-label={t("cable.closeDetails")}>
          X
        </button>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {COLUMNS.map((column) => (
                <th key={column.key}>
                  <button className="sort-button" onClick={() => toggleSort(column.key)}>
                    <span>{t(column.labelKey)}</span>
                    <span className="sort-indicator">
                      {sortKey === column.key ? (sortDirection === "asc" ? "▲" : "▼") : "↕"}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
            <tr className="filter-row">
              {COLUMNS.map((column) => (
                <th key={column.key}>
                  <input
                    aria-label={`${t("common.filter")} ${t(column.labelKey)}`}
                    value={filters[column.key] ?? ""}
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        [column.key]: event.target.value,
                      }))
                    }
                    placeholder={t("common.filter")}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleCables.map((cable, index) => (
              <tr key={`${cable.a_port_uid}-${cable.z_port_uid}-${index}`}>
                {COLUMNS.map((column) => (
                  <td key={column.key}>{column.key === "status" ? formatCableStatus(cable.status) : cable[column.key]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

import { useMemo, useState } from "react";
import type { CabinetCableDetail, CabinetCableDetailResponse } from "../types";

type CableDetailOverlayProps = {
  cableDetail: CabinetCableDetailResponse | null;
  onClose: () => void;
};

type SortDirection = "asc" | "desc";
type CableColumn = {
  key: keyof CabinetCableDetail;
  label: string;
};

const COLUMNS: CableColumn[] = [
  { key: "cable_type", label: "Type" },
  { key: "status", label: "Status" },
  { key: "group", label: "Group" },
  { key: "a_port_uid", label: "A Port" },
  { key: "z_port_uid", label: "Z Port" },
  { key: "a_optic", label: "A Optic" },
  { key: "z_optic", label: "Z Optic" },
];

export function CableDetailOverlay({ cableDetail, onClose }: CableDetailOverlayProps) {
  const [sortKey, setSortKey] = useState<keyof CabinetCableDetail>("cable_type");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [filters, setFilters] = useState<Partial<Record<keyof CabinetCableDetail, string>>>({});
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

  function toggleSort(columnKey: keyof CabinetCableDetail) {
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
          <span className="eyebrow">Cable Details</span>
          <h2>
            {cableDetail.source_cabinet_uid} to {cableDetail.target_cabinet_uid}
          </h2>
          <div className="overlay-count">
            {visibleCables.length.toLocaleString()} of {cableDetail.cables.length.toLocaleString()} cables
          </div>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close cable details">
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
                    <span>{column.label}</span>
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
                    aria-label={`Filter ${column.label}`}
                    value={filters[column.key] ?? ""}
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        [column.key]: event.target.value,
                      }))
                    }
                    placeholder="Filter"
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleCables.map((cable, index) => (
              <tr key={`${cable.a_port_uid}-${cable.z_port_uid}-${index}`}>
                {COLUMNS.map((column) => (
                  <td key={column.key}>{cable[column.key]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

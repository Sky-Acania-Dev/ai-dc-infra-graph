import { useEffect, useMemo, useRef, useState } from "react";
import { updateCable } from "../api";
import type { CabinetCableDetail, CableDetailResponse, CableProgressPhase, CableProgressPhaseDefinition, TopologyEnums } from "../types";
import { useI18n } from "../i18n";

type CableDetailOverlayProps = {
  cableDetail: CableDetailResponse | null;
  canEdit: boolean;
  topologyEnums: TopologyEnums | null;
  onClose: () => void;
  onCableUpdated: (cable: CabinetCableDetail) => void;
};

type SortDirection = "asc" | "desc";
type CableColumnKey =
  | "uid"
  | "cable_type"
  | "status"
  | "progress"
  | "length_meters"
  | "group"
  | "a_port_uid"
  | "z_port_uid"
  | "a_optic"
  | "z_optic"
  | "note";
type CableColumn = {
  key: CableColumnKey;
  label: string;
};
type NumericRange = { min: number; max: number };
type RangeFilter = NumericRange;

const COLUMNS: Array<CableColumn & { labelKey: string }> = [
  { key: "uid", label: "Cable ID", labelKey: "cable.column.uid" },
  { key: "cable_type", label: "Type", labelKey: "cable.column.type" },
  { key: "status", label: "Status", labelKey: "cable.column.status" },
  { key: "progress", label: "Progress", labelKey: "cable.column.progress" },
  { key: "length_meters", label: "Length (m)", labelKey: "cable.column.lengthMeters" },
  { key: "group", label: "Group", labelKey: "cable.column.group" },
  { key: "a_port_uid", label: "A Port", labelKey: "cable.column.aPort" },
  { key: "z_port_uid", label: "Z Port", labelKey: "cable.column.zPort" },
  { key: "a_optic", label: "A Optic", labelKey: "cable.column.aOptic" },
  { key: "z_optic", label: "Z Optic", labelKey: "cable.column.zOptic" },
  { key: "note", label: "Note", labelKey: "cable.column.note" },
];

export function CableDetailOverlay({
  cableDetail,
  canEdit,
  topologyEnums,
  onClose,
  onCableUpdated,
}: CableDetailOverlayProps) {
  const {
    formatCableProgressPhaseName,
    formatCableProgressStep,
    formatCableStatus,
    formatNumber,
    t,
  } = useI18n();
  const [sortKey, setSortKey] = useState<CableColumnKey>("cable_type");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [filters, setFilters] = useState<Partial<Record<CableColumnKey, string[]>>>({});
  const [rangeFilters, setRangeFilters] = useState<Partial<Record<CableColumnKey, RangeFilter>>>({});
  const [filterText, setFilterText] = useState<Partial<Record<CableColumnKey, string>>>({});
  const [openFilterColumn, setOpenFilterColumn] = useState<CableColumnKey | null>(null);
  const debouncedFilterText = useDebouncedValue(filterText, 500);
  const uniqueValues = useMemo(() => {
    const values: Partial<Record<CableColumnKey, string[]>> = {};
    if (!cableDetail) return values;
    for (const column of COLUMNS) {
      values[column.key] = [
        ...new Set(cableDetail.cables.map((cable) => columnValue(cable, column.key)).map((value) => value || "(blank)")),
      ].sort((left, right) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));
    }
    return values;
  }, [cableDetail]);
  const filteredUniqueValues = useMemo(() => {
    const values: Partial<Record<CableColumnKey, string[]>> = {};
    for (const column of COLUMNS) {
      const text = (debouncedFilterText[column.key] ?? "").trim().toLowerCase();
      values[column.key] = (uniqueValues[column.key] ?? []).filter((value) =>
        displayValue(value, column.key, formatCableStatus).toLowerCase().includes(text),
      );
    }
    return values;
  }, [debouncedFilterText, formatCableStatus, uniqueValues]);
  const numericRanges = useMemo(() => {
    const ranges: Partial<Record<CableColumnKey, NumericRange>> = {};
    if (!cableDetail) return ranges;
    for (const column of COLUMNS) {
      if (!isNumericColumn(column.key)) continue;
      const values = cableDetail.cables
        .map((cable) => numericColumnValue(cable, column.key))
        .filter((value): value is number => value !== null && value > 0);
      if (!values.length) continue;
      ranges[column.key] = { min: Math.min(...values), max: Math.max(...values) };
    }
    return ranges;
  }, [cableDetail]);
  const visibleCables = useMemo(() => {
    if (!cableDetail) return [];
    return cableDetail.cables
      .filter((cable) =>
        COLUMNS.every((column) => {
          const selectedValues = filters[column.key];
          if (!selectedValues) return true;
          if (selectedValues.length === 0) return false;
          return selectedValues.includes(columnValue(cable, column.key) || "(blank)");
        }) &&
        COLUMNS.every((column) => {
          if (!isNumericColumn(column.key)) return true;
          const filter = rangeFilters[column.key];
          if (!filter) return true;
          const value = numericColumnValue(cable, column.key);
          if (value === null) return false;
          return value >= filter.min && value <= filter.max;
        }),
      )
      .slice()
      .sort((left, right) => {
        const leftValue = String(left[sortKey] ?? "");
        const rightValue = String(right[sortKey] ?? "");
        const result = leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: "base" });
        return sortDirection === "asc" ? result : -result;
      });
  }, [cableDetail, filters, rangeFilters, sortDirection, sortKey]);

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

  function setColumnFilter(columnKey: CableColumnKey, value: string, checked: boolean) {
    const allValues = uniqueValues[columnKey] ?? [];
    setFilters((current) => {
      const existing = current[columnKey] ?? allValues;
      const nextValues = checked ? [...new Set([...existing, value])] : existing.filter((item) => item !== value);
      return {
        ...current,
        [columnKey]: nextValues.length === allValues.length ? undefined : nextValues,
      };
    });
  }

  function setVisibleColumnFilter(columnKey: CableColumnKey, shouldIncludeVisible: boolean) {
    const allValues = uniqueValues[columnKey] ?? [];
    const visibleValues = filteredUniqueValues[columnKey] ?? [];
    setFilters((current) => {
      const currentSelected = current[columnKey] ?? allValues;
      const visibleSet = new Set(visibleValues);
      const selectedSet = new Set(currentSelected);
      if (shouldIncludeVisible) {
        for (const value of visibleValues) selectedSet.add(value);
      } else {
        for (const value of visibleValues) selectedSet.delete(value);
      }
      const nextValues = allValues.filter((value) => selectedSet.has(value));
      return {
        ...current,
        [columnKey]: nextValues.length === allValues.length ? undefined : nextValues,
      };
    });
  }

  return (
    <div className="cable-overlay" onClick={() => setOpenFilterColumn(null)}>
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
      <div className="table-scroll" onClick={() => setOpenFilterColumn(null)}>
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
                  <details
                    className="value-filter"
                    onClick={(event) => event.stopPropagation()}
                    onToggle={(event) => {
                      if (event.currentTarget.open) setOpenFilterColumn(column.key);
                      else if (openFilterColumn === column.key) setOpenFilterColumn(null);
                    }}
                    open={openFilterColumn === column.key}
                  >
                    <summary className={isFilterActive(column.key, filters, rangeFilters, numericRanges) ? "is-filtered" : ""}>
                      {t("common.filter")}
                    </summary>
                    <div className="value-filter-menu">
                      {isNumericColumn(column.key) ? (
                        <RangeFilterMenu
                          columnKey={column.key}
                          onChange={(range) => setRangeFilters((current) => ({ ...current, [column.key]: range }))}
                          onReset={() => setRangeFilters((current) => ({ ...current, [column.key]: undefined }))}
                          range={rangeFilters[column.key] ?? numericRanges[column.key]}
                          sourceRange={numericRanges[column.key]}
                        />
                      ) : (
                        <>
                          <div className="value-filter-actions">
                            <TriStateToggle
                              checked={visibleSelectionState(column.key, uniqueValues, filteredUniqueValues, filters) === "all"}
                              indeterminate={visibleSelectionState(column.key, uniqueValues, filteredUniqueValues, filters) === "partial"}
                              label={t("cable.filterAll")}
                              onChange={() => setVisibleColumnFilter(column.key, true)}
                            />
                            <button type="button" onClick={() => setVisibleColumnFilter(column.key, false)}>
                              {t("cable.filterNone")}
                            </button>
                          </div>
                          <input
                            aria-label={`${t("common.filter")} ${t(column.labelKey)}`}
                            className="value-filter-search"
                            onChange={(event) => setFilterText((current) => ({ ...current, [column.key]: event.target.value }))}
                            placeholder={t("common.filter")}
                            type="search"
                            value={filterText[column.key] ?? ""}
                          />
                          <FilterHiddenSummary
                            allValues={uniqueValues[column.key] ?? []}
                            filteredValues={filteredUniqueValues[column.key] ?? []}
                            selectedValues={filters[column.key]}
                          />
                          {(filteredUniqueValues[column.key] ?? []).map((value) => {
                            const selectedValues = filters[column.key] ?? uniqueValues[column.key] ?? [];
                            const isChecked = selectedValues.includes(value);
                            return (
                              <label key={value}>
                                <input
                                  checked={isChecked}
                                  onChange={(event) => setColumnFilter(column.key, value, event.target.checked)}
                                  type="checkbox"
                                />
                                <span>{displayValue(value, column.key, formatCableStatus)}</span>
                              </label>
                            );
                          })}
                        </>
                      )}
                    </div>
                  </details>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleCables.map((cable, index) => (
              <tr key={`${cable.a_port_uid}-${cable.z_port_uid}-${index}`}>
                {COLUMNS.map((column) => (
                  <td key={column.key}>
                    {renderCableCell({
                      cable,
                      canEdit,
                      columnKey: column.key,
                      formatCableProgressPhaseName,
                      formatCableProgressStep,
                      formatCableStatus,
                      onCableUpdated,
                      topologyEnums,
                    })}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {!visibleCables.length ? <div className="empty-table-space" /> : null}
      </div>
    </div>
  );
}

function columnValue(cable: CabinetCableDetail, columnKey: CableColumnKey): string {
  if (columnKey === "progress") return phaseSummary(cable.current_phase) || progressSummary(cable.progress);
  if (columnKey === "length_meters") return cable.length_used_meters > 0 ? String(cable.length_used_meters) : "";
  return String(cable[columnKey] ?? "");
}

function numericColumnValue(cable: CabinetCableDetail, columnKey: CableColumnKey): number | null {
  if (columnKey === "length_meters") return cable.length_used_meters > 0 ? cable.length_used_meters : null;
  return null;
}

function isNumericColumn(columnKey: CableColumnKey): boolean {
  return columnKey === "length_meters";
}

function isFilterActive(
  columnKey: CableColumnKey,
  filters: Partial<Record<CableColumnKey, string[]>>,
  rangeFilters: Partial<Record<CableColumnKey, RangeFilter>>,
  numericRanges: Partial<Record<CableColumnKey, NumericRange>>,
): boolean {
  const valueFilter = filters[columnKey];
  if (valueFilter !== undefined) return true;
  const rangeFilter = rangeFilters[columnKey];
  const sourceRange = numericRanges[columnKey];
  if (!rangeFilter || !sourceRange) return false;
  return rangeFilter.min !== sourceRange.min || rangeFilter.max !== sourceRange.max;
}

function displayValue(value: string, columnKey: CableColumnKey, formatCableStatus: (status: string) => string) {
  if (value === "(blank)") return value;
  if (columnKey === "status") return formatCableStatus(value);
  return value;
}

function progressSummary(progress: Record<string, string>): string {
  const entries = Object.entries(progress);
  if (!entries.length) return "";
  return entries.map(([step, state]) => `${step}:${state}`).join(", ");
}

function phaseSummary(phase: CableProgressPhase | null): string {
  if (!phase) return "";
  if (Object.keys(phase.task_values ?? {}).length) {
    return `${phase.name}: ${Object.entries(phase.task_values)
      .map(([task, detail]) => `${task} ${detail.value ?? ""}${detail.task_type === "percent" ? "%" : ""}`)
      .join(", ")}`;
  }
  if (phase.phase_type === "parallel_percent") {
    return `${phase.name}: ${Object.entries(phase.tasks)
      .map(([task, value]) => `${task} ${value}%`)
      .join(", ")}`;
  }
  if (phase.phase_type === "enum_state") {
    return `${phase.name}: ${phase.value ?? ""}`;
  }
  return `${phase.name}: ${typeof phase.value === "number" ? phase.value : 0}%`;
}

function renderCableCell({
  cable,
  canEdit,
  columnKey,
  formatCableProgressPhaseName,
  formatCableProgressStep,
  formatCableStatus,
  onCableUpdated,
  topologyEnums,
}: {
  cable: CabinetCableDetail;
  canEdit: boolean;
  columnKey: CableColumnKey;
  formatCableProgressPhaseName: (phase: string) => string;
  formatCableProgressStep: (step: string) => string;
  formatCableStatus: (status: string) => string;
  onCableUpdated: (cable: CabinetCableDetail) => void;
  topologyEnums: TopologyEnums | null;
}) {
  if (columnKey === "status") {
    if (!canEdit) return formatCableStatus(cable.status);
    return (
      <DeferredSelect
        className="inline-select"
        onCommit={(value) => updateCable(cable.uid, { status: value }).then(onCableUpdated)}
        options={(topologyEnums?.cable_import_statuses ?? [cable.status]).map((status) => ({
          label: formatCableStatus(status),
          value: status,
        }))}
        value={cable.status}
      />
    );
  }

  if (columnKey === "length_meters") {
    if (!canEdit) return cable.length_used_meters > 0 ? cable.length_used_meters : "";
    return (
      <DeferredNumberInput
        className="length-input"
        min={0.1}
        onCommit={(value) => updateCable(cable.uid, { length_used_meters: value }).then(onCableUpdated)}
        step={0.1}
        value={cable.length_used_meters > 0 ? cable.length_used_meters : ""}
      />
    );
  }

  if (columnKey === "progress") {
    if (!canEdit) return phaseSummary(cable.current_phase) || progressSummary(cable.progress);
    return renderPhaseEditor({
      cable,
      formatCableProgressPhaseName,
      formatCableProgressStep,
      onCableUpdated,
      topologyEnums,
    });
  }

  return columnValue(cable, columnKey);
}

function renderPhaseEditor({
  cable,
  formatCableProgressPhaseName,
  formatCableProgressStep,
  onCableUpdated,
  topologyEnums,
}: {
  cable: CabinetCableDetail;
  formatCableProgressPhaseName: (phase: string) => string;
  formatCableProgressStep: (step: string) => string;
  onCableUpdated: (cable: CabinetCableDetail) => void;
  topologyEnums: TopologyEnums | null;
}) {
  const phase = cable.current_phase ?? defaultPhase(topologyEnums);
  const phaseDefinitions = topologyEnums?.cable_progress_phases ?? [phaseDefinitionFromPhase(phase)];
  const phaseDefinition = phaseDefinitions.find((definition) => definition.name === phase.name) ?? phaseDefinitions[0];
  const normalizedPhase = normalizePhaseForDefinition(phase, phaseDefinition);
  const primaryTask = phaseDefinition.tasks.find((task) => task.task_type === "percent") ?? phaseDefinition.tasks[0];
  const secondaryTasks = phaseDefinition.tasks.filter((task) => task.name !== primaryTask?.name);

  function save(nextPhase: CableProgressPhase) {
    updateCable(cable.uid, { current_phase: nextPhase }).then(onCableUpdated);
  }

  return (
    <div className="progress-editor">
      <div className="progress-main-row">
        <DeferredSelect
          className="inline-select"
          onCommit={(value) => {
            const nextDefinition = phaseDefinitions.find((definition) => definition.name === value);
            if (nextDefinition) save(defaultPhaseForDefinition(nextDefinition));
          }}
          options={phaseDefinitions.map((definition) => ({
            label: formatPhaseName(definition.name, formatCableProgressPhaseName, formatCableProgressStep),
            value: definition.name,
          }))}
          value={normalizedPhase.name}
        />
        {primaryTask
          ? renderProgressTaskInput({ definition: primaryTask, formatCableProgressStep, normalizedPhase, save })
          : null}
      </div>
      {secondaryTasks.length ? (
        <div className="progress-task-row">
          {secondaryTasks.map((definition) =>
            renderProgressTaskInput({ definition, formatCableProgressStep, normalizedPhase, save }),
          )}
        </div>
      ) : null}
    </div>
  );
}

function defaultPhase(topologyEnums: TopologyEnums | null): CableProgressPhase {
  return defaultPhaseForDefinition(
    topologyEnums?.cable_progress_phases[0] ?? {
      name: "preparation",
      tasks: [
        {
          name: "preparation",
          task_type: "enum",
          enum_values: ["ordered", "received", "labeled", "bundled", "pulled"],
          default_value: "ordered",
        },
      ],
    },
  );
}

function renderProgressTaskInput({
  definition,
  formatCableProgressStep,
  normalizedPhase,
  save,
}: {
  definition: CableProgressPhaseDefinition["tasks"][number];
  formatCableProgressStep: (step: string) => string;
  normalizedPhase: CableProgressPhase;
  save: (nextPhase: CableProgressPhase) => void;
}) {
  const task = normalizedPhase.task_values[definition.name];
  if (definition.task_type === "enum") {
    return (
      <label className="progress-task" key={definition.name}>
        <span>{formatCableProgressStep(definition.name)}</span>
        <DeferredSelect
          className="inline-select"
          onCommit={(value) =>
            save({
              ...normalizedPhase,
              task_values: {
                ...normalizedPhase.task_values,
                [definition.name]: {
                  task_type: definition.task_type,
                  value,
                  enum_values: definition.enum_values,
                },
              },
            })
          }
          options={definition.enum_values.map((value) => ({
            label: formatCableProgressStep(value),
            value,
          }))}
          value={typeof task?.value === "string" ? task.value : String(definition.default_value ?? definition.enum_values[0] ?? "")}
        />
      </label>
    );
  }
  return (
    <label className="progress-task" key={definition.name}>
      <span>{formatCableProgressStep(definition.name)}</span>
      <DeferredNumberInput
        className="length-input"
        max={100}
        min={0}
        onCommit={(value) =>
          save({
            ...normalizedPhase,
            task_values: {
              ...normalizedPhase.task_values,
              [definition.name]: {
                task_type: definition.task_type,
                value: clampPercent(value),
                enum_values: [],
              },
            },
          })
        }
        step={1}
        value={typeof task?.value === "number" ? task.value : Number(definition.default_value ?? 0)}
      />
    </label>
  );
}

function defaultPhaseForDefinition(definition: CableProgressPhaseDefinition): CableProgressPhase {
  return {
    name: definition.name,
    phase_type: definition.tasks.length > 1 ? "parallel_percent" : definition.tasks[0]?.task_type === "enum" ? "enum_state" : "single_percent",
    value: null,
    tasks: {},
    enum_values: [],
    task_values: Object.fromEntries(
      definition.tasks.map((task) => [
        task.name,
        {
          task_type: task.task_type,
          value: task.default_value,
          enum_values: task.enum_values,
        },
      ]),
    ),
  };
}

function normalizePhaseForDefinition(phase: CableProgressPhase, definition: CableProgressPhaseDefinition): CableProgressPhase {
  const normalized = defaultPhaseForDefinition(definition);
  return {
    ...normalized,
    task_values: Object.fromEntries(
      definition.tasks.map((task) => {
        const existing = phase.task_values?.[task.name];
        if (task.task_type === "enum") {
          const value = typeof existing?.value === "string" && task.enum_values.includes(existing.value) ? existing.value : task.default_value;
          return [task.name, { task_type: task.task_type, value, enum_values: task.enum_values }];
        }
        const value = typeof existing?.value === "number" ? existing.value : Number(task.default_value ?? 0);
        return [task.name, { task_type: task.task_type, value: clampPercent(value), enum_values: [] }];
      }),
    ),
  };
}

function phaseDefinitionFromPhase(phase: CableProgressPhase): CableProgressPhaseDefinition {
  const taskEntries = Object.entries(phase.task_values ?? {});
  return {
    name: phase.name,
    tasks: taskEntries.length
      ? taskEntries.map(([name, task]) => ({
          name,
          task_type: task.task_type,
          enum_values: task.enum_values,
          default_value: task.value,
        }))
      : [
          {
            name: "preparation",
            task_type: "enum",
            enum_values: ["ordered", "received", "labeled", "bundled", "pulled"],
            default_value: "ordered",
          },
        ],
  };
}

function formatPhaseName(
  phaseName: string,
  formatCableProgressPhaseName: (phase: string) => string,
  formatCableProgressStep: (step: string) => string,
): string {
  const formattedPhase = formatCableProgressPhaseName(phaseName);
  if (formattedPhase !== `cable.phaseName.${phaseName}`) return formattedPhase;
  return formatCableProgressStep(phaseName);
}

function clampPercent(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function visibleSelectionState(
  columnKey: CableColumnKey,
  uniqueValues: Partial<Record<CableColumnKey, string[]>>,
  filteredUniqueValues: Partial<Record<CableColumnKey, string[]>>,
  filters: Partial<Record<CableColumnKey, string[]>>,
): "all" | "none" | "partial" {
  const allValues = uniqueValues[columnKey] ?? [];
  const visibleValues = filteredUniqueValues[columnKey] ?? [];
  const selectedValues = filters[columnKey] ?? allValues;
  const visibleSelected = visibleValues.filter((value) => selectedValues.includes(value)).length;
  if (visibleSelected === 0) return "none";
  if (visibleSelected === visibleValues.length) return "all";
  return "partial";
}

function TriStateToggle({
  checked,
  indeterminate,
  label,
  onChange,
}: {
  checked: boolean;
  indeterminate: boolean;
  label: string;
  onChange: () => void;
}) {
  const ref = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <label className="tri-state-toggle">
      <input checked={checked} onChange={onChange} ref={ref} type="checkbox" />
      <span>{label}</span>
    </label>
  );
}

function RangeFilterMenu({
  columnKey,
  onChange,
  onReset,
  range,
  sourceRange,
}: {
  columnKey: CableColumnKey;
  onChange: (range: RangeFilter) => void;
  onReset: () => void;
  range: RangeFilter | undefined;
  sourceRange: NumericRange | undefined;
}) {
  const { t } = useI18n();
  if (!sourceRange || !range) {
    return <div className="value-filter-hidden">{t("common.noExamples")}</div>;
  }
  const activeRange = range;
  const span = Math.max(sourceRange.max - sourceRange.min, 1);
  const leftPercent = ((activeRange.min - sourceRange.min) / span) * 100;
  const rightPercent = 100 - ((activeRange.max - sourceRange.min) / span) * 100;

  function updateMin(value: number) {
    onChange({ min: Math.min(value, activeRange.max), max: activeRange.max });
  }

  function updateMax(value: number) {
    onChange({ min: activeRange.min, max: Math.max(value, activeRange.min) });
  }

  return (
    <div className="range-filter">
      <div className="range-filter-labels">
        <span>{sourceRange.min}</span>
        <span>{sourceRange.max}</span>
      </div>
      <div className="range-slider">
        <div className="range-slider-rail">
          <div className="range-slider-track" />
          <div className="range-slider-active" style={{ left: `${leftPercent}%`, right: `${rightPercent}%` }} />
        </div>
        <input
          aria-label={`${columnKey} min`}
          max={sourceRange.max}
          min={sourceRange.min}
          onChange={(event) => updateMin(Number(event.target.value))}
          step={0.1}
          type="range"
          value={activeRange.min}
        />
        <input
          aria-label={`${columnKey} max`}
          max={sourceRange.max}
          min={sourceRange.min}
          onChange={(event) => updateMax(Number(event.target.value))}
          step={0.1}
          type="range"
          value={activeRange.max}
        />
      </div>
      <div className="range-inputs">
        <input
          max={sourceRange.max}
          min={sourceRange.min}
          onChange={(event) => updateMin(Number(event.target.value))}
          step={0.1}
          type="number"
          value={activeRange.min}
        />
        <input
          max={sourceRange.max}
          min={sourceRange.min}
          onChange={(event) => updateMax(Number(event.target.value))}
          step={0.1}
          type="number"
          value={activeRange.max}
        />
      </div>
      <button className="range-reset-button" onClick={onReset} type="button">
        {t("cable.filterAll")}
      </button>
    </div>
  );
}

function FilterHiddenSummary({
  allValues,
  filteredValues,
  selectedValues,
}: {
  allValues: string[];
  filteredValues: string[];
  selectedValues: string[] | undefined;
}) {
  const { formatNumber, t } = useI18n();
  const selected = selectedValues ?? allValues;
  const filtered = new Set(filteredValues);
  const hiddenValues = allValues.filter((value) => !filtered.has(value));
  const hiddenSelected = hiddenValues.filter((value) => selected.includes(value)).length;
  const hiddenExcluded = hiddenValues.length - hiddenSelected;
  if (!hiddenValues.length) return null;
  return (
    <div className="value-filter-hidden">
      <span>{t("cable.filterHiddenOn", { count: formatNumber(hiddenSelected) })}</span>
      <span>{t("cable.filterHiddenOff", { count: formatNumber(hiddenExcluded) })}</span>
    </div>
  );
}

function DeferredNumberInput({
  className,
  max,
  min,
  onCommit,
  step,
  value,
}: {
  className?: string;
  max?: number;
  min?: number;
  onCommit: (value: number) => void;
  step?: number;
  value: number | "";
}) {
  const [draft, setDraft] = useState(value === "" ? "" : String(value));
  const skipNextBlur = useRef(false);
  const original = value === "" ? "" : String(value);

  useEffect(() => {
    setDraft(original);
  }, [original]);

  function commit() {
    if (draft === original) return;
    const nextValue = Number(draft);
    if (!Number.isFinite(nextValue) || (min !== undefined && nextValue < min) || (max !== undefined && nextValue > max)) {
      setDraft(original);
      return;
    }
    onCommit(nextValue);
  }

  function revert() {
    setDraft(original);
  }

  return (
    <input
      className={className}
      data-cable-editable="true"
      max={max}
      min={min}
      onBlur={() => {
        if (skipNextBlur.current) {
          skipNextBlur.current = false;
          return;
        }
        commit();
      }}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          revert();
          skipNextBlur.current = true;
          event.currentTarget.blur();
          return;
        }
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
          skipNextBlur.current = true;
          event.currentTarget.blur();
          return;
        }
        if (event.key === "Tab") {
          event.preventDefault();
          commit();
          skipNextBlur.current = true;
          focusAdjacentEditable(event.currentTarget, event.shiftKey);
        }
      }}
      step={step}
      type="number"
      value={draft}
    />
  );
}

function DeferredSelect({
  className,
  onCommit,
  options,
  value,
}: {
  className?: string;
  onCommit: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  value: string;
}) {
  const [draft, setDraft] = useState(value);
  const skipNextBlur = useRef(false);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  function commit() {
    if (draft !== value) onCommit(draft);
  }

  function revert() {
    setDraft(value);
  }

  return (
    <select
      className={className}
      data-cable-editable="true"
      onBlur={() => {
        if (skipNextBlur.current) {
          skipNextBlur.current = false;
          return;
        }
        commit();
      }}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          revert();
          skipNextBlur.current = true;
          event.currentTarget.blur();
          return;
        }
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
          skipNextBlur.current = true;
          event.currentTarget.blur();
          return;
        }
        if (event.key === "Tab") {
          event.preventDefault();
          commit();
          skipNextBlur.current = true;
          focusAdjacentEditable(event.currentTarget, event.shiftKey);
        }
      }}
      value={draft}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

function focusAdjacentEditable(current: HTMLElement, reverse: boolean) {
  const controls = Array.from(document.querySelectorAll<HTMLElement>(".cable-overlay [data-cable-editable='true']"));
  const currentIndex = controls.indexOf(current);
  if (currentIndex < 0) return;
  const nextIndex = reverse ? currentIndex - 1 : currentIndex + 1;
  const next = controls[nextIndex];
  if (next) window.setTimeout(() => next.focus(), 0);
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedValue(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs, value]);
  return debouncedValue;
}

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import type { BulkOperationResponse, CabinetDetailResponse, CabinetLayoutItem, Device, Operation, OperationResponse } from "../types";
import { CabinetDeviceLayout } from "./CabinetDeviceLayout";
import { ProgressCircle } from "./ProgressCircle";
import { useI18n } from "../i18n";
import { bulkUpdateLifecycleStatus, updateCabinetStatus, updateDeviceStatus } from "../api";
import { categoryColor } from "../colors";
import { useDragPan } from "../hooks/useDragPan";
import type { SelectionGesture } from "../App";

type CabinetDetailsPanelProps = {
  detail: CabinetDetailResponse | null;
  dataHall: string;
  cabinets: CabinetLayoutItem[];
  selectedCabinetUids: string[];
  selectedDeviceUid: string | null;
  selectedDeviceUids: string[];
  deviceScrollRequest: number;
  connectedDeviceUids: Set<string>;
  onSelectDevice: (device: Device, gesture: SelectionGesture) => void;
  onViewPortLayout: (device: Device) => void;
  activePortLayoutDeviceUid: string | null;
  onShowCabinetMap: () => void;
  onClearDeviceSelection: () => void;
  canEdit: boolean;
  expectedVersion: number | null;
  lifecycleStatuses: string[];
  onStatusChanged: (
    operation: Promise<OperationResponse>,
    options?: {
      onError?: () => void;
      onSuccess?: (response: OperationResponse) => void;
      recordUndo?: boolean;
    },
  ) => void;
  onBulkStatusChanged: (
    operation: Promise<BulkOperationResponse>,
    options?: {
      onError?: () => void;
      onSuccess?: (response: BulkOperationResponse) => void;
      recordUndo?: boolean;
    },
  ) => void;
};

export function CabinetDetailsPanel({
  detail,
  dataHall,
  cabinets,
  selectedCabinetUids,
  selectedDeviceUid,
  selectedDeviceUids,
  deviceScrollRequest,
  connectedDeviceUids,
  onSelectDevice,
  onViewPortLayout,
  activePortLayoutDeviceUid,
  onShowCabinetMap,
  onClearDeviceSelection,
  canEdit,
  expectedVersion,
  lifecycleStatuses,
  onStatusChanged,
  onBulkStatusChanged,
}: CabinetDetailsPanelProps) {
  const { formatConstructionPhase, formatLifecycleStatus, formatNumber, t } = useI18n();
  const categorySummaryPan = useDragPan<HTMLElement>();
  const [categorySummaryHasScrollbar, setCategorySummaryHasScrollbar] = useState(false);
  const [writeFeedback, setWriteFeedback] = useState<Record<string, "success" | "error">>({});
  const [cabinetStatusDraft, setCabinetStatusDraft] = useState("");
  const [bulkStatusDraft, setBulkStatusDraft] = useState("");
  const [deviceStatusDrafts, setDeviceStatusDrafts] = useState<Record<string, string>>({});
  const selectedCabinets = selectedCabinetUids.length > 1
    ? cabinets.filter((cabinet) => selectedCabinetUids.includes(cabinet.cabinet_uid))
    : [];
  const selectedDevices = detail && selectedDeviceUids.length > 1
    ? detail.devices.filter((device) => selectedDeviceUids.includes(`${device.cabinet_id}:${device.rack_unit}`))
    : [];
  const selectedDevice = detail && selectedDeviceUid
    ? detail.devices.find((device) => `${device.cabinet_id}:${device.rack_unit}` === selectedDeviceUid) ?? null
    : null;

  useEffect(() => {
    setCabinetStatusDraft(detail?.cabinet.lifecycle_status ?? "");
    setBulkStatusDraft("");
    setDeviceStatusDrafts({});
  }, [detail?.cabinet.cabinet_uid, detail?.cabinet.lifecycle_status]);

  useEffect(() => {
    setBulkStatusDraft("");
  }, [selectedCabinetUids.join("|"), selectedDeviceUids.join("|")]);

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

  if (selectedCabinets.length > 1) {
    const categories = categoryCounts(selectedCabinets);
    const statuses = countBy(selectedCabinets, (cabinet) => cabinet.lifecycle_status);
    const avgTermination = average(selectedCabinets.map((cabinet) => cabinet.cable_termination_percent));
    const avgDress = average(selectedCabinets.map((cabinet) => cabinet.cable_dress_percent));
    return (
      <aside className="side-pane">
        <span className="eyebrow">Multi-selection</span>
        <h1>{formatNumber(selectedCabinets.length)} cabinets</h1>
        <dl className="facts">
          <div>
            <dt>{t("cabinet.categories")}</dt>
            <dd>{formatNumber(categories.length)}</dd>
          </div>
          <div>
            <dt>{t("cabinet.termination")}</dt>
            <dd className="progress-fact">
              <ProgressCircle percent={avgTermination} />
              {formatNumber(avgTermination)}%
            </dd>
          </div>
          <div>
            <dt>{t("cabinet.dress")}</dt>
            <dd className="progress-fact">
              <ProgressCircle percent={avgDress} />
              {formatNumber(avgDress)}%
            </dd>
          </div>
        </dl>
        <section className="category-summary">
          <div className="section-title">{t("cabinet.types")}</div>
          {categories.map(([category, count]) => (
            <div className="category-row" key={category}>
              <span style={{ color: categoryColor(category) }}>{category}</span>
              <b>{formatNumber(count)}</b>
            </div>
          ))}
        </section>
        <section className="category-summary aggregate-section bulk-status-summary">
          <div className="section-title">{t("cabinet.status")}</div>
          {statuses.map(([status, count]) => (
            <div className="category-row" key={status}>
              <span>{formatLifecycleStatus(status)}</span>
              <b>{formatNumber(count)}</b>
            </div>
          ))}
        </section>
        <BulkLifecycleStatusEditor
          canEdit={canEdit}
          entityType="cabinet"
          entityUids={selectedCabinets.map((cabinet) => cabinet.cabinet_uid)}
          expectedVersion={expectedVersion}
          feedback={writeFeedback.bulkStatus}
          lifecycleStatuses={lifecycleStatuses}
          statusDraft={bulkStatusDraft}
          onBulkStatusChanged={onBulkStatusChanged}
          onDraftChanged={setBulkStatusDraft}
          onWriteFeedback={(feedback) => flashWriteFeedback(setWriteFeedback, "bulkStatus", feedback)}
        />
      </aside>
    );
  }

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
      {selectedDevices.length > 1 ? (
        <DeviceSelectionSummary
          canEdit={canEdit}
          devices={selectedDevices}
          expectedVersion={expectedVersion}
          formatConstructionPhase={formatConstructionPhase}
          formatLifecycleStatus={formatLifecycleStatus}
          formatNumber={formatNumber}
          lifecycleStatuses={lifecycleStatuses}
          onBulkStatusChanged={onBulkStatusChanged}
          setBulkStatusDraft={setBulkStatusDraft}
          setWriteFeedback={setWriteFeedback}
          statusDraft={bulkStatusDraft}
          writeFeedback={writeFeedback}
        />
      ) : selectedDevice ? (
        <DeviceDetailSummary
          canEdit={canEdit}
          device={selectedDevice}
          deviceStatusDraft={deviceStatusDrafts[`${selectedDevice.cabinet_id}:${selectedDevice.rack_unit}`]}
          expectedVersion={expectedVersion}
          formatConstructionPhase={formatConstructionPhase}
          formatLifecycleStatus={formatLifecycleStatus}
          formatNumber={formatNumber}
          lifecycleStatuses={lifecycleStatuses}
          onStatusChanged={onStatusChanged}
          setDeviceStatusDrafts={setDeviceStatusDrafts}
          setWriteFeedback={setWriteFeedback}
          writeFeedback={writeFeedback}
        />
      ) : (
        <>
          <h1>{detail.cabinet.cabinet_uid}</h1>
          <ChangeOperationSummary operations={detail.change_operations ?? []} title="Cabinet changes" />
          <dl className="facts single-cabinet-facts">
            <div>
              <dt>{t("cabinet.category")}</dt>
              <dd>{detail.cabinet.category}</dd>
            </div>
            <div>
              <dt>{t("cabinet.status")}</dt>
              <dd>
                {canEdit ? (
                  <select
                    className={`inline-select ${feedbackClass(writeFeedback.cabinetStatus)}`}
                    value={cabinetStatusDraft || detail.cabinet.lifecycle_status}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => {
                      const nextStatus = event.target.value;
                      setCabinetStatusDraft(nextStatus);
                      onStatusChanged(updateCabinetStatus(detail.cabinet.cabinet_uid, nextStatus, expectedVersion), {
                        onError: () => {
                          setCabinetStatusDraft(detail.cabinet.lifecycle_status);
                          flashWriteFeedback(setWriteFeedback, "cabinetStatus", "error");
                        },
                        onSuccess: () => flashWriteFeedback(setWriteFeedback, "cabinetStatus", "success"),
                      });
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
              <dt>{t("cabinet.group")}</dt>
              <dd>{detail.cabinet.cabinet_group || t("cabinet.unassigned")}</dd>
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
        </>
      )}
      <CabinetDeviceLayout
        devices={detail.devices}
        maxRackUnit={detail.cabinet.max_rack_unit}
        selectedDeviceUid={selectedDeviceUid}
        selectedDeviceUids={selectedDeviceUids}
        scrollRequest={deviceScrollRequest}
        connectedDeviceUids={connectedDeviceUids}
        onSelectDevice={onSelectDevice}
        onViewPortLayout={onViewPortLayout}
        activePortLayoutDeviceUid={activePortLayoutDeviceUid}
        onShowCabinetMap={onShowCabinetMap}
        canEdit={canEdit}
        lifecycleStatuses={lifecycleStatuses}
        onDeviceStatusChange={(device, lifecycleStatus) => {
          const deviceUid = `${device.cabinet_id}:${device.rack_unit}`;
          setDeviceStatusDrafts((current) => ({ ...current, [deviceUid]: lifecycleStatus }));
          onStatusChanged(updateDeviceStatus(deviceUid, lifecycleStatus, expectedVersion), {
            onError: () => {
              setDeviceStatusDrafts((current) => ({ ...current, [deviceUid]: device.lifecycle_status }));
              flashWriteFeedback(setWriteFeedback, `device:${deviceUid}`, "error");
            },
            onSuccess: () => flashWriteFeedback(setWriteFeedback, `device:${deviceUid}`, "success"),
          });
        }}
        statusDrafts={deviceStatusDrafts}
        statusFeedback={writeFeedback}
      />
    </aside>
  );
}

function DeviceDetailSummary({
  canEdit,
  device,
  deviceStatusDraft,
  expectedVersion,
  formatConstructionPhase,
  formatLifecycleStatus,
  formatNumber,
  lifecycleStatuses,
  onStatusChanged,
  setDeviceStatusDrafts,
  setWriteFeedback,
  writeFeedback,
}: {
  canEdit: boolean;
  device: Device;
  deviceStatusDraft?: string;
  expectedVersion: number | null;
  formatConstructionPhase: (value: string) => string;
  formatLifecycleStatus: (value: string) => string;
  formatNumber: (value: number) => string;
  lifecycleStatuses: string[];
  onStatusChanged: CabinetDetailsPanelProps["onStatusChanged"];
  setDeviceStatusDrafts: Dispatch<SetStateAction<Record<string, string>>>;
  setWriteFeedback: Dispatch<SetStateAction<Record<string, "success" | "error">>>;
  writeFeedback: Record<string, "success" | "error">;
}) {
  const deviceUid = `${device.cabinet_id}:${device.rack_unit}`;
  const portCount = Object.values(device.ports_by_type).reduce((total, ports) => total + (ports?.length ?? 0), 0);
  const aliasCount = device.aliases.length + device.model_aliases.length;

  return (
    <>
      <h1>{deviceUid}</h1>
      <ChangeOperationSummary operations={device.change_operations ?? []} title="Device changes" />
      <dl className="facts">
        <div>
          <dt>Model</dt>
          <dd>{device.device_model}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>
            {canEdit ? (
              <select
                className={`inline-select ${feedbackClass(writeFeedback[`device:${deviceUid}`])}`}
                value={deviceStatusDraft ?? device.lifecycle_status}
                onClick={(event) => event.stopPropagation()}
                onChange={(event) => {
                  const nextStatus = event.target.value;
                  setDeviceStatusDrafts((current) => ({ ...current, [deviceUid]: nextStatus }));
                  onStatusChanged(updateDeviceStatus(deviceUid, nextStatus, expectedVersion), {
                    onError: () => {
                      setDeviceStatusDrafts((current) => ({ ...current, [deviceUid]: device.lifecycle_status }));
                      flashWriteFeedback(setWriteFeedback, `device:${deviceUid}`, "error");
                    },
                    onSuccess: () => flashWriteFeedback(setWriteFeedback, `device:${deviceUid}`, "success"),
                  });
                }}
              >
                {lifecycleStatuses.map((status) => (
                  <option key={status} value={status}>
                    {formatLifecycleStatus(status)}
                  </option>
                ))}
              </select>
            ) : (
              formatLifecycleStatus(device.lifecycle_status)
            )}
          </dd>
        </div>
        <div>
          <dt>Phase</dt>
          <dd>{formatConstructionPhase(device.construction_phase)}</dd>
        </div>
        <div>
          <dt>Rack Unit</dt>
          <dd>U{formatNumber(device.rack_unit)}</dd>
        </div>
        <div>
          <dt>Rack Units</dt>
          <dd>{formatNumber(device.rack_units)}U</dd>
        </div>
        <div>
          <dt>Ports</dt>
          <dd>{formatNumber(portCount)}</dd>
        </div>
        <div>
          <dt>Aliases</dt>
          <dd>{formatNumber(aliasCount)}</dd>
        </div>
      </dl>
    </>
  );
}

function ChangeOperationSummary({ operations, title }: { operations: Operation[]; title: string }) {
  if (!operations.length) return null;
  return (
    <section className="change-operation-summary" onClick={(event) => event.stopPropagation()}>
      <div className="section-title">{title}</div>
      {operations.slice(0, 5).map((operation) => (
        <div className="change-operation-row" key={operation.opId}>
          <span>{String(operation.after?.change_type ?? operation.type)}</span>
          <b>{operation.sourceOperator ?? operation.sourceType ?? "source"}</b>
        </div>
      ))}
    </section>
  );
}

function feedbackClass(feedback?: "success" | "error"): string {
  if (feedback === "success") return "is-write-success";
  if (feedback === "error") return "is-write-error";
  return "";
}

function flashWriteFeedback(
  setWriteFeedback: Dispatch<SetStateAction<Record<string, "success" | "error">>>,
  key: string,
  feedback: "success" | "error",
) {
  setWriteFeedback((current) => ({ ...current, [key]: feedback }));
  window.setTimeout(() => {
    setWriteFeedback((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, 900);
}

function categoryCounts(cabinets: CabinetLayoutItem[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const cabinet of cabinets) {
    counts.set(cabinet.category, (counts.get(cabinet.category) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function BulkLifecycleStatusEditor({
  canEdit,
  entityType,
  entityUids,
  expectedVersion,
  feedback,
  lifecycleStatuses,
  statusDraft,
  onBulkStatusChanged,
  onDraftChanged,
  onWriteFeedback,
}: {
  canEdit: boolean;
  entityType: "cabinet" | "device";
  entityUids: string[];
  expectedVersion: number | null;
  feedback?: "success" | "error";
  lifecycleStatuses: string[];
  statusDraft: string;
  onBulkStatusChanged: CabinetDetailsPanelProps["onBulkStatusChanged"];
  onDraftChanged: (status: string) => void;
  onWriteFeedback: (feedback: "success" | "error") => void;
}) {
  const { formatLifecycleStatus, t } = useI18n();
  if (!canEdit) return null;

  return (
    <section className="aggregate-section bulk-status-editor" onClick={(event) => event.stopPropagation()}>
      <div className="section-title">{t("bulkStatus.setStatus")}</div>
      <select
        className={`inline-select ${feedbackClass(feedback)}`}
        value={statusDraft}
        onChange={(event) => {
          const nextStatus = event.target.value;
          if (!nextStatus) return;
          onDraftChanged(nextStatus);
          onBulkStatusChanged(bulkUpdateLifecycleStatus(entityType, entityUids, nextStatus, expectedVersion), {
            onError: () => {
              onDraftChanged("");
              onWriteFeedback("error");
            },
            onSuccess: () => {
              onDraftChanged("");
              onWriteFeedback("success");
            },
          });
        }}
      >
        <option value="">{t("bulkStatus.chooseStatus", { count: entityUids.length })}</option>
        {lifecycleStatuses.map((status) => (
          <option key={status} value={status}>
            {formatLifecycleStatus(status)}
          </option>
        ))}
      </select>
    </section>
  );
}

function DeviceSelectionSummary({
  canEdit,
  devices,
  expectedVersion,
  formatConstructionPhase,
  formatLifecycleStatus,
  formatNumber,
  lifecycleStatuses,
  onBulkStatusChanged,
  setBulkStatusDraft,
  setWriteFeedback,
  statusDraft,
  writeFeedback,
}: {
  canEdit: boolean;
  devices: Device[];
  expectedVersion: number | null;
  formatConstructionPhase: (value: string) => string;
  formatLifecycleStatus: (value: string) => string;
  formatNumber: (value: number) => string;
  lifecycleStatuses: string[];
  onBulkStatusChanged: CabinetDetailsPanelProps["onBulkStatusChanged"];
  setBulkStatusDraft: Dispatch<SetStateAction<string>>;
  setWriteFeedback: Dispatch<SetStateAction<Record<string, "success" | "error">>>;
  statusDraft: string;
  writeFeedback: Record<string, "success" | "error">;
}) {
  const statusCounts = countBy(devices, (device) => device.lifecycle_status);
  const phaseCounts = countBy(devices, (device) => device.construction_phase);
  const modelCounts = countBy(devices, (device) => device.device_model);
  const portTotal = devices.reduce(
    (total, device) => total + Object.values(device.ports_by_type).reduce((portCount, ports) => portCount + (ports?.length ?? 0), 0),
    0,
  );

  return (
    <section className="aggregate-section bulk-status-summary">
      <div className="section-title">Selected devices</div>
      <dl className="facts compact-facts">
        <div>
          <dt>Devices</dt>
          <dd>{formatNumber(devices.length)}</dd>
        </div>
        <div>
          <dt>Ports</dt>
          <dd>{formatNumber(portTotal)}</dd>
        </div>
        <div>
          <dt>Models</dt>
          <dd>{formatNumber(modelCounts.length)}</dd>
        </div>
      </dl>
      <AggregateRows title="Status" rows={statusCounts} formatValue={formatLifecycleStatus} formatNumber={formatNumber} />
      <BulkLifecycleStatusEditor
        canEdit={canEdit}
        entityType="device"
        entityUids={devices.map((device) => `${device.cabinet_id}:${device.rack_unit}`)}
        expectedVersion={expectedVersion}
        feedback={writeFeedback.bulkStatus}
        lifecycleStatuses={lifecycleStatuses}
        statusDraft={statusDraft}
        onBulkStatusChanged={onBulkStatusChanged}
        onDraftChanged={setBulkStatusDraft}
        onWriteFeedback={(feedback) => flashWriteFeedback(setWriteFeedback, "bulkStatus", feedback)}
      />
      <AggregateRows title="Phase" rows={phaseCounts} formatValue={formatConstructionPhase} formatNumber={formatNumber} />
    </section>
  );
}

function AggregateRows({
  title,
  rows,
  formatValue,
  formatNumber,
}: {
  title: string;
  rows: [string, number][];
  formatValue: (value: string) => string;
  formatNumber: (value: number) => string;
}) {
  return (
    <div className="aggregate-rows">
      <div className="section-title">{title}</div>
      {rows.map(([value, count]) => (
        <div className="category-row" key={value}>
          <span>{formatValue(value)}</span>
          <b>{formatNumber(count)}</b>
        </div>
      ))}
    </div>
  );
}

function countBy<T>(items: T[], getKey: (item: T) => string): [string, number][] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const key = getKey(item) || "(blank)";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function average(values: number[]): number {
  if (!values.length) return 0;
  return Math.round(values.reduce((total, value) => total + value, 0) / values.length);
}

import { useState } from "react";
import type {
  CabinetDetailResponse,
  CabinetConnection,
  CableStatusSummary,
  DataHallCableBucket,
  DataHallCableSummaryResponse,
  DeviceConnection,
  DeviceConnectionResponse,
} from "../types";
import { useDragPan } from "../hooks/useDragPan";
import { useI18n } from "../i18n";

export type CabinetCableRoute = {
  sourceCabinetUid: string;
  targetCabinetUid: string;
};

export type DeviceCableRoute = {
  sourceDeviceUid: string;
  targetDeviceUid: string;
};

type CabinetConnectionsPanelProps = {
  detail: CabinetDetailResponse | null;
  selectedCabinetDetails: CabinetDetailResponse[];
  deviceDetail: DeviceConnectionResponse | null;
  selectedDeviceDetails: DeviceConnectionResponse[];
  dataHallCableSummary: DataHallCableSummaryResponse | null;
  onViewCables: (routes: CabinetCableRoute[]) => void;
  onViewDeviceCables: (routes: DeviceCableRoute[]) => void;
  onViewDataHallCables: (bucket: DataHallCableBucket, cableType: string) => void;
  guidance?: string | null;
  headingOverride?: string | null;
};

export function CabinetConnectionsPanel({
  detail,
  selectedCabinetDetails,
  deviceDetail,
  selectedDeviceDetails,
  dataHallCableSummary,
  onViewCables,
  onViewDeviceCables,
  onViewDataHallCables,
  guidance,
  headingOverride,
}: CabinetConnectionsPanelProps) {
  const { formatNumber, t } = useI18n();
  const connectionListPan = useDragPan<HTMLDivElement>();
  const [isDataHallExternalExpanded, setIsDataHallExternalExpanded] = useState(false);
  const [isCabinetExternalExpanded, setIsCabinetExternalExpanded] = useState(false);
  const [isDeviceExternalExpanded, setIsDeviceExternalExpanded] = useState(false);

  if (selectedDeviceDetails.length > 1) {
    const sourceDeviceUids = new Set(selectedDeviceDetails.map((selectedDetail) => selectedDetail.source_device_uid));
    const internalConnections = aggregateDeviceConnections(
      selectedDeviceDetails,
      (connection) => sourceDeviceUids.has(connection.target_device_uid),
    );
    const externalConnections = aggregateDeviceConnections(
      selectedDeviceDetails,
      (connection) => !sourceDeviceUids.has(connection.target_device_uid),
    );
    const allConnections = [...internalConnections, ...externalConnections];

    return (
      <aside className="side-pane connections-pane">
        <span className="eyebrow">{t("connections.connectedDevices")}</span>
        <h2>{t("connections.connectedDevicesCount", { count: formatNumber(allConnections.length) })}</h2>
        <PanelGuidance guidance={guidance} />
        <div className="connection-list drag-pan-surface" {...connectionListPan}>
          <ConnectionSummaryCard
            headingMetric={t("connections.deviceCount", { count: formatNumber(internalConnections.length) })}
            onViewCables={
              internalConnections.length > 0
                ? () =>
                    onViewDeviceCables(
                      internalConnections.flatMap((connection) =>
                        connection.source_device_uids.map((sourceDeviceUid) => ({
                          sourceDeviceUid,
                          targetDeviceUid: connection.target_device_uid,
                        })),
                      ),
                    )
                : undefined
            }
            summary={aggregateConnectionSummaries(internalConnections)}
            title={t("connections.selectedDevices", { count: formatNumber(selectedDeviceDetails.length) })}
            subtitle={t("connections.intraDeviceSelection")}
          />
          <ExternalDeviceConnections
            connections={externalConnections}
            isExpanded={isDeviceExternalExpanded}
            onToggleExpanded={() => setIsDeviceExternalExpanded((current) => !current)}
            onViewDeviceCables={(connection, targetDeviceUid) =>
              onViewDeviceCables(
                "source_device_uids" in connection
                  ? connection.source_device_uids.map((sourceDeviceUid) => ({ sourceDeviceUid, targetDeviceUid }))
                  : [{ sourceDeviceUid: connection.target_device_uid, targetDeviceUid }],
              )
            }
            subtitle={t("connections.totalExternalDeviceSelectionSubtitle")}
            title={t("connections.totalExternal")}
          />
        </div>
      </aside>
    );
  }

  if (deviceDetail) {
    const internalConnections = deviceDetail.connected_devices.filter(
      (connection) => connection.target_cabinet_uid === deviceDetail.source_cabinet_uid,
    );
    const externalConnections = deviceDetail.connected_devices.filter(
      (connection) => connection.target_cabinet_uid !== deviceDetail.source_cabinet_uid,
    );

    return (
      <aside className="side-pane connections-pane">
        <span className="eyebrow">{t("connections.connectedDevices")}</span>
        <h2>{t("connections.connectedDevicesCount", { count: formatNumber(deviceDetail.connected_devices.length) })}</h2>
        <PanelGuidance guidance={guidance} />
        <div className="connection-list drag-pan-surface" {...connectionListPan}>
          <ConnectionSummaryCard
            headingMetric={t("connections.deviceCount", { count: formatNumber(internalConnections.length) })}
            onViewCables={
              internalConnections.length > 0
                ? () =>
                    onViewDeviceCables(
                      internalConnections.map((connection) => ({
                        sourceDeviceUid: deviceDetail.source_device_uid,
                        targetDeviceUid: connection.target_device_uid,
                      })),
                    )
                : undefined
            }
            summary={aggregateConnectionSummaries(internalConnections)}
            title={t("connections.insideCabinet", { cabinetUid: deviceDetail.source_cabinet_uid })}
            subtitle={t("connections.intraDevice")}
          />
          <ExternalDeviceConnections
            connections={externalConnections}
            isExpanded={isDeviceExternalExpanded}
            onToggleExpanded={() => setIsDeviceExternalExpanded((current) => !current)}
            onViewDeviceCables={(_, targetDeviceUid) =>
              onViewDeviceCables([{ sourceDeviceUid: deviceDetail.source_device_uid, targetDeviceUid }])
            }
            subtitle={t("connections.totalExternalDeviceSubtitle")}
            title={t("connections.totalExternal")}
          />
        </div>
      </aside>
    );
  }

  if (!detail) {
    return (
      <aside className="side-pane connections-pane">
        <span className="eyebrow">{t("connections.dataHallCables")}</span>
        <h2>{dataHallCableSummary?.data_hall_id ?? t("dataHall.fallback")}</h2>
        <PanelGuidance guidance={guidance} />
        {dataHallCableSummary ? (
          <div className="connection-list drag-pan-surface" {...connectionListPan}>
            <DataHallCableBucketCard
              bucket={dataHallCableSummary.internal}
              title={t("connections.insideDataHall", { dataHall: dataHallCableSummary.data_hall_id })}
              subtitle={t("connections.intraDataHall")}
              onViewDataHallCables={onViewDataHallCables}
            />
            {dataHallCableSummary.external.length === 1 ? (
              <DataHallCableBucketCard
                bucket={dataHallCableSummary.external[0]}
                title={t("connections.toDataHall", {
                  dataHall: dataHallCableSummary.external[0].target_data_hall ?? t("dataHall.fallback"),
                })}
                subtitle={t("connections.crossDataHall")}
                onViewDataHallCables={onViewDataHallCables}
              />
            ) : (
              <>
                <DataHallCableBucketCard
                  bucket={aggregateExternalBuckets(dataHallCableSummary.external)}
                  isExpanded={isDataHallExternalExpanded}
                  onToggleExpanded={
                    dataHallCableSummary.external.length > 0
                      ? () => setIsDataHallExternalExpanded((current) => !current)
                      : undefined
                  }
                  peerCount={dataHallCableSummary.external.length}
                  title={t("connections.totalExternal")}
                  subtitle={t("connections.totalExternalSubtitle")}
                />
                {isDataHallExternalExpanded
                  ? dataHallCableSummary.external.map((bucket) => (
                      <DataHallCableBucketCard
                        bucket={bucket}
                        key={bucket.target_data_hall ?? "external"}
                        title={t("connections.toDataHall", { dataHall: bucket.target_data_hall ?? t("dataHall.fallback") })}
                        subtitle={t("connections.crossDataHall")}
                        onViewDataHallCables={onViewDataHallCables}
                      />
                    ))
                  : null}
              </>
            )}
          </div>
        ) : (
          <p className="empty-state">{t("common.loading", { target: t("connections.dataHallCables") })}</p>
        )}
      </aside>
    );
  }

  if (selectedCabinetDetails.length > 1) {
    const sourceCabinetUids = new Set(selectedCabinetDetails.map((selectedDetail) => selectedDetail.cabinet.cabinet_uid));
    const intraCabinetConnections = selectedCabinetDetails
      .map((selectedDetail) => selectedDetail.intra_cabinet_connection)
      .filter((connection): connection is CabinetConnection => Boolean(connection));
    const internalPeerConnections = aggregateCabinetConnections(selectedCabinetDetails, (connection) =>
      sourceCabinetUids.has(connection.target_cabinet_uid),
    );
    const externalConnections = aggregateCabinetConnections(selectedCabinetDetails, (connection) =>
      !sourceCabinetUids.has(connection.target_cabinet_uid),
    );

    return (
      <aside className="side-pane connections-pane">
        <span className="eyebrow">{t("connections.connectedCabinets")}</span>
        <h2>{headingOverride ?? t("connections.connectedCabinetsCount", { count: formatNumber(externalConnections.length) })}</h2>
        <PanelGuidance guidance={guidance} />
        <div className="connection-list drag-pan-surface" {...connectionListPan}>
          <ConnectionSummaryCard
            className="intra-connection"
            onViewCables={
              intraCabinetConnections.length > 0
                ? () =>
                    onViewCables(
                      selectedCabinetDetails.map((selectedDetail) => ({
                        sourceCabinetUid: selectedDetail.cabinet.cabinet_uid,
                        targetCabinetUid: selectedDetail.cabinet.cabinet_uid,
                      })),
                    )
                : undefined
            }
            summary={aggregateConnectionSummaries(intraCabinetConnections)}
            title={t("connections.selectedCabinets", { count: formatNumber(selectedCabinetDetails.length) })}
            subtitle={t("connections.intraCabinetSelection")}
          />
          {internalPeerConnections.length > 0 ? (
            <ConnectionSummaryCard
              summary={aggregateConnectionSummaries(internalPeerConnections)}
              title={t("connections.betweenSelectedCabinets")}
              subtitle={t("connections.selectedCabinetPeerSubtitle")}
            />
          ) : null}
          <ExternalCabinetConnections
            connections={externalConnections}
            isExpanded={isCabinetExternalExpanded}
            onToggleExpanded={() => setIsCabinetExternalExpanded((current) => !current)}
            onViewCables={(connection, targetCabinetUid) =>
              onViewCables(
                "source_cabinet_uids" in connection
                  ? connection.source_cabinet_uids.map((sourceCabinetUid) => ({ sourceCabinetUid, targetCabinetUid }))
                  : [{ sourceCabinetUid: connection.target_cabinet_uid, targetCabinetUid }],
              )
            }
            subtitle={t("connections.totalExternalCabinetSelectionSubtitle")}
            title={t("connections.totalExternal")}
          />
        </div>
      </aside>
    );
  }

  const intraCabinetSummary = detail.intra_cabinet_connection ?? emptyConnectionSummary();
  return (
    <aside className="side-pane connections-pane">
      <span className="eyebrow">{t("connections.connectedCabinets")}</span>
      <h2>{headingOverride ?? t("connections.connectedCabinetsCount", { count: formatNumber(detail.stats.connected_cabinets) })}</h2>
      <PanelGuidance guidance={guidance} />
      <div className="connection-list drag-pan-surface" {...connectionListPan}>
        <ConnectionSummaryCard
          className="intra-connection"
          onViewCables={
            detail.intra_cabinet_connection
              ? () =>
                  onViewCables([
                    { sourceCabinetUid: detail.cabinet.cabinet_uid, targetCabinetUid: detail.cabinet.cabinet_uid },
                  ])
              : undefined
          }
          summary={intraCabinetSummary}
          title={t("connections.insideCabinet", { cabinetUid: detail.cabinet.cabinet_uid })}
          subtitle={t("connections.intraCabinet")}
        />
        <ExternalCabinetConnections
          connections={detail.connections}
          isExpanded={isCabinetExternalExpanded}
          onToggleExpanded={() => setIsCabinetExternalExpanded((current) => !current)}
          onViewCables={(_, targetCabinetUid) =>
            onViewCables([{ sourceCabinetUid: detail.cabinet.cabinet_uid, targetCabinetUid }])
          }
          subtitle={t("connections.totalExternalCabinetSubtitle")}
          title={t("connections.totalExternal")}
        />
      </div>
    </aside>
  );
}

function PanelGuidance({ guidance }: { guidance?: string | null }) {
  return guidance ? <div className="panel-guidance">{guidance}</div> : null;
}
type ChangeOrderDiffStats = NonNullable<CabinetConnection["change_order_stats"]>;

type ConnectionSummary = {
  total_cables: number;
  cable_type_counts: Record<string, number>;
  status_summary: CableStatusSummary;
  change_order_stats?: ChangeOrderDiffStats | null;
};

type AggregatedCabinetConnection = CabinetConnection & {
  source_cabinet_uids: string[];
};

type AggregatedDeviceConnection = DeviceConnection & {
  source_device_uids: string[];
};

function ExternalCabinetConnections({
  connections,
  isExpanded,
  onToggleExpanded,
  onViewCables,
  subtitle,
  title,
}: {
  connections: AggregatedCabinetConnection[] | CabinetConnection[];
  isExpanded: boolean;
  onToggleExpanded: () => void;
  onViewCables: (connection: AggregatedCabinetConnection | CabinetConnection, targetCabinetUid: string) => void;
  subtitle: string;
  title: string;
}) {
  if (connections.length === 1) {
    const connection = connections[0];
    return (
      <CabinetConnectionCard
        connection={connection}
        onViewCables={(targetCabinetUid) => onViewCables(connection, targetCabinetUid)}
      />
    );
  }

  return (
    <>
      <ConnectionSummaryCard
        isExpanded={isExpanded}
        onToggleExpanded={connections.length > 0 ? onToggleExpanded : undefined}
        peerCount={connections.length}
        summary={aggregateConnectionSummaries(connections)}
        title={title}
        subtitle={subtitle}
      />
      {isExpanded
        ? connections.map((connection) => (
            <CabinetConnectionCard
              connection={connection}
              key={connection.target_cabinet_uid}
              onViewCables={(targetCabinetUid) => onViewCables(connection, targetCabinetUid)}
            />
          ))
        : null}
    </>
  );
}

function ExternalDeviceConnections({
  connections,
  isExpanded,
  onToggleExpanded,
  onViewDeviceCables,
  subtitle,
  title,
}: {
  connections: AggregatedDeviceConnection[] | DeviceConnection[];
  isExpanded: boolean;
  onToggleExpanded: () => void;
  onViewDeviceCables: (connection: AggregatedDeviceConnection | DeviceConnection, targetDeviceUid: string) => void;
  subtitle: string;
  title: string;
}) {
  const { formatNumber, t } = useI18n();
  if (connections.length === 1) {
    const connection = connections[0];
    return (
      <DeviceConnectionCard
        connection={connection}
        onViewDeviceCables={(targetDeviceUid) => onViewDeviceCables(connection, targetDeviceUid)}
      />
    );
  }

  return (
    <>
      <ConnectionSummaryCard
        isExpanded={isExpanded}
        onToggleExpanded={connections.length > 0 ? onToggleExpanded : undefined}
        headingMetric={t("connections.deviceCount", { count: formatNumber(connections.length) })}
        peerCount={connections.length}
        summary={aggregateConnectionSummaries(connections)}
        title={title}
        subtitle={subtitle}
      />
      {isExpanded
        ? connections.map((connection) => (
            <DeviceConnectionCard
              connection={connection}
              key={connection.target_device_uid}
              onViewDeviceCables={(targetDeviceUid) => onViewDeviceCables(connection, targetDeviceUid)}
            />
          ))
        : null}
    </>
  );
}

function emptyConnectionSummary(): ConnectionSummary {
  return {
    total_cables: 0,
    cable_type_counts: {},
    status_summary: {
      completed: 0,
      total: 0,
      status_counts: {},
    },
    change_order_stats: null,
  };
}

function aggregateConnectionSummaries(connections: Array<CabinetConnection | DeviceConnection>): ConnectionSummary {
  const cableTypeCounts: Record<string, number> = {};
  const statusCounts: Record<string, number> = {};
  let totalCables = 0;
  let completed = 0;
  let total = 0;
  let changeOrderStats: ChangeOrderDiffStats | null = null;

  for (const connection of connections) {
    totalCables += connection.total_cables;
    completed += connection.status_summary.completed;
    total += connection.status_summary.total;
    for (const [type, count] of Object.entries(connection.cable_type_counts)) {
      cableTypeCounts[type] = (cableTypeCounts[type] ?? 0) + count;
    }
    for (const [status, count] of Object.entries(connection.status_summary.status_counts)) {
      statusCounts[status] = (statusCounts[status] ?? 0) + count;
    }
    changeOrderStats = mergeChangeOrderDiffStats(changeOrderStats, changeOrderDiffStats(connection));
  }

  return {
    total_cables: totalCables,
    cable_type_counts: sortCounts(cableTypeCounts),
    status_summary: {
      completed,
      total,
      status_counts: sortCounts(statusCounts),
    },
    change_order_stats: changeOrderStats,
  };
}

function aggregateCabinetConnections(
  details: CabinetDetailResponse[],
  includeConnection: (connection: CabinetConnection) => boolean,
): AggregatedCabinetConnection[] {
  const byTarget = new Map<string, AggregatedCabinetConnection>();
  for (const detail of details) {
    for (const connection of detail.connections) {
      if (!includeConnection(connection)) continue;
      const existing = byTarget.get(connection.target_cabinet_uid);
      if (existing) {
        mergeConnectionSummary(existing, connection);
        existing.source_cabinet_uids.push(detail.cabinet.cabinet_uid);
      } else {
        byTarget.set(connection.target_cabinet_uid, {
          ...cloneCabinetConnection(connection),
          source_cabinet_uids: [detail.cabinet.cabinet_uid],
        });
      }
    }
  }
  return [...byTarget.values()].sort((left, right) => right.total_cables - left.total_cables || left.target_cabinet_uid.localeCompare(right.target_cabinet_uid));
}

function aggregateDeviceConnections(
  details: DeviceConnectionResponse[],
  includeConnection: (connection: DeviceConnection) => boolean,
): AggregatedDeviceConnection[] {
  const byTarget = new Map<string, AggregatedDeviceConnection>();
  for (const detail of details) {
    for (const connection of detail.connected_devices) {
      if (!includeConnection(connection)) continue;
      const existing = byTarget.get(connection.target_device_uid);
      if (existing) {
        mergeConnectionSummary(existing, connection);
        existing.source_device_uids.push(detail.source_device_uid);
      } else {
        byTarget.set(connection.target_device_uid, {
          ...cloneDeviceConnection(connection),
          source_device_uids: [detail.source_device_uid],
        });
      }
    }
  }
  return [...byTarget.values()].sort((left, right) => right.total_cables - left.total_cables || left.target_device_uid.localeCompare(right.target_device_uid));
}

function cloneCabinetConnection(connection: CabinetConnection): CabinetConnection {
  return {
    ...connection,
    cable_type_counts: { ...connection.cable_type_counts },
    status_summary: {
      ...connection.status_summary,
      status_counts: { ...connection.status_summary.status_counts },
    },
  };
}

function cloneDeviceConnection(connection: DeviceConnection): DeviceConnection {
  return {
    ...connection,
    cable_type_counts: { ...connection.cable_type_counts },
    status_summary: {
      ...connection.status_summary,
      status_counts: { ...connection.status_summary.status_counts },
    },
  };
}

function mergeConnectionSummary(target: CabinetConnection | DeviceConnection, source: CabinetConnection | DeviceConnection) {
  target.total_cables += source.total_cables;
  target.status_summary.completed += source.status_summary.completed;
  target.status_summary.total += source.status_summary.total;
  for (const [type, count] of Object.entries(source.cable_type_counts)) {
    target.cable_type_counts[type] = (target.cable_type_counts[type] ?? 0) + count;
  }
  for (const [status, count] of Object.entries(source.status_summary.status_counts)) {
    target.status_summary.status_counts[status] = (target.status_summary.status_counts[status] ?? 0) + count;
  }
  target.cable_type_counts = sortCounts(target.cable_type_counts);
  target.status_summary.status_counts = sortCounts(target.status_summary.status_counts);
  if ("change_order_stats" in target) {
    target.change_order_stats = mergeChangeOrderDiffStats(target.change_order_stats ?? null, changeOrderDiffStats(source));
  }
}

function ConnectionSummaryCard({
  className = "",
  headingMetric,
  isExpanded,
  onToggleExpanded,
  onViewCables,
  peerCount,
  summary,
  subtitle,
  title,
}: {
  className?: string;
  headingMetric?: string;
  isExpanded?: boolean;
  onToggleExpanded?: () => void;
  onViewCables?: () => void;
  peerCount?: number;
  summary: ConnectionSummary;
  subtitle: string;
  title: string;
}) {
  const { formatNumber, t } = useI18n();
  return (
    <article className={`connection-item ${className}`.trim()}>
      <div className="connection-heading">
        <strong>{title}</strong>
        {headingMetric ? <span>{headingMetric}</span> : <ConnectionCountMetric diffStats={summary.change_order_stats} totalCables={summary.total_cables} />}
      </div>
      <StatusCompletion summary={summary.status_summary} />
      <div className="connection-meta">{subtitle}</div>
      <ul className="cable-types">
        {Object.entries(summary.cable_type_counts).map(([type, count]) => (
          <li key={type}>
            <span>{type}</span>
            <b>{formatNumber(count)}</b>
          </li>
        ))}
      </ul>
      {onViewCables ? (
        <button className="detail-button" onClick={onViewCables}>
          {t("connections.viewCables")}
        </button>
      ) : null}
      {onToggleExpanded ? (
        <button className={`expand-button ${isExpanded ? "is-expanded" : "is-collapsed"}`} onClick={onToggleExpanded}>
          {isExpanded
            ? t("connections.collapsePeers")
            : t("connections.expandPeers", { count: formatNumber(peerCount ?? 0) })}
        </button>
      ) : null}
    </article>
  );
}

function CabinetConnectionCard({
  connection,
  onViewCables,
}: {
  connection: CabinetConnection;
  onViewCables: (targetCabinetUid: string) => void;
}) {
  const { formatNumber, t } = useI18n();
  return (
    <article className="connection-item">
      <div className="connection-heading">
        <strong>{connection.target_cabinet_uid}</strong>
        <ConnectionCountMetric diffStats={connection.change_order_stats} totalCables={connection.total_cables} />
      </div>
      <StatusCompletion summary={connection.status_summary} />
      <div className="connection-meta">
        {connection.target_category} {connection.target_cabinet_group ? `- ${connection.target_cabinet_group}` : ""}
      </div>
      <ul className="cable-types">
        {Object.entries(connection.cable_type_counts).map(([type, count]) => (
          <li key={type}>
            <span>{type}</span>
            <b>{formatNumber(count)}</b>
          </li>
        ))}
      </ul>
      <button className="detail-button" onClick={() => onViewCables(connection.target_cabinet_uid)}>
        {t("connections.viewCables")}
      </button>
    </article>
  );
}

function ConnectionCountMetric({ diffStats, totalCables }: { diffStats?: ChangeOrderDiffStats | null; totalCables: number }) {
  const { formatNumber, t } = useI18n();
  const removed = diffStats?.removed ?? 0;
  const changed = diffStats?.changed ?? 0;
  const added = diffStats?.added ?? 0;
  if (!removed && !changed && !added) {
    return <span>{t("connections.cableCount", { count: formatNumber(totalCables) })}</span>;
  }
  const adjustedTotal = Math.max(0, totalCables - removed + added);
  return (
    <span className="connection-count-diff">
      <b>{formatNumber(adjustedTotal)}</b>
      <small>
        (<em className="diff-removed">-{formatNumber(removed)}</em>/<em className="diff-changed">~{formatNumber(changed)}</em>/<em className="diff-added">+{formatNumber(added)}</em>)
      </small>
    </span>
  );
}

function changeOrderDiffStats(connection: CabinetConnection | DeviceConnection): ChangeOrderDiffStats | null {
  return "change_order_stats" in connection ? connection.change_order_stats ?? null : null;
}

function mergeChangeOrderDiffStats(left: ChangeOrderDiffStats | null, right: ChangeOrderDiffStats | null): ChangeOrderDiffStats | null {
  if (!left && !right) return null;
  return {
    removed: (left?.removed ?? 0) + (right?.removed ?? 0),
    changed: (left?.changed ?? 0) + (right?.changed ?? 0),
    added: (left?.added ?? 0) + (right?.added ?? 0),
  };
}

function DeviceConnectionCard({
  connection,
  onViewDeviceCables,
}: {
  connection: DeviceConnection;
  onViewDeviceCables: (targetDeviceUid: string) => void;
}) {
  const { formatNumber, t } = useI18n();
  const targetDeviceModel = connection.target_device_model.trim();
  return (
    <article className="connection-item">
      <div className="connection-heading">
        <strong>{connection.target_device_uid}</strong>
        <span>{t("connections.cableCount", { count: formatNumber(connection.total_cables) })}</span>
      </div>
      <StatusCompletion summary={connection.status_summary} />
      <div className="connection-meta">
        {[targetDeviceModel, t("connections.targetCabinetRu", {
          cabinetUid: connection.target_cabinet_uid,
          rackUnit: connection.target_rack_unit,
        })].filter(Boolean).join(" - ")}
      </div>
      <ul className="cable-types">
        {Object.entries(connection.cable_type_counts).map(([type, count]) => (
          <li key={type}>
            <span>{type}</span>
            <b>{formatNumber(count)}</b>
          </li>
        ))}
      </ul>
      <button className="detail-button" onClick={() => onViewDeviceCables(connection.target_device_uid)}>
        {t("connections.viewCables")}
      </button>
    </article>
  );
}

function aggregateExternalBuckets(buckets: DataHallCableBucket[]): DataHallCableBucket {
  const cableTypeCounts: Record<string, number> = {};
  const statusCounts: Record<string, number> = {};
  let totalCables = 0;
  let completed = 0;
  let total = 0;

  for (const bucket of buckets) {
    totalCables += bucket.total_cables;
    completed += bucket.status_summary.completed;
    total += bucket.status_summary.total;
    for (const [type, count] of Object.entries(bucket.cable_type_counts)) {
      cableTypeCounts[type] = (cableTypeCounts[type] ?? 0) + count;
    }
    for (const [status, count] of Object.entries(bucket.status_summary.status_counts)) {
      statusCounts[status] = (statusCounts[status] ?? 0) + count;
    }
  }

  return {
    scope: "external",
    target_data_hall: null,
    total_cables: totalCables,
    cable_type_counts: sortCounts(cableTypeCounts),
    status_summary: {
      completed,
      total,
      status_counts: sortCounts(statusCounts),
    },
  };
}

function sortCounts(counts: Record<string, number>): Record<string, number> {
  return Object.fromEntries(Object.entries(counts).sort(([left], [right]) => left.localeCompare(right)));
}

function DataHallCableBucketCard({
  bucket,
  isExpanded,
  onToggleExpanded,
  title,
  subtitle,
  peerCount,
  onViewDataHallCables,
}: {
  bucket: DataHallCableBucket;
  isExpanded?: boolean;
  onToggleExpanded?: () => void;
  peerCount?: number;
  title: string;
  subtitle: string;
  onViewDataHallCables?: (bucket: DataHallCableBucket, cableType: string) => void;
}) {
  const { formatNumber, t } = useI18n();
  return (
    <article className="connection-item">
      <div className="connection-heading">
        <strong>{title}</strong>
        <span>{t("connections.cableCount", { count: formatNumber(bucket.total_cables) })}</span>
      </div>
      <StatusCompletion summary={bucket.status_summary} />
      <div className="connection-meta">{subtitle}</div>
      <ul className={`cable-types ${onViewDataHallCables ? "cable-types-with-actions" : ""}`}>
        {Object.entries(bucket.cable_type_counts).map(([type, count]) => (
          <li key={type}>
            <span>{type}</span>
            <b>{formatNumber(count)}</b>
            {onViewDataHallCables ? (
              <button className="mini-detail-button" onClick={() => onViewDataHallCables(bucket, type)}>
                {t("connections.viewCables")}
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {onToggleExpanded ? (
        <button className={`expand-button ${isExpanded ? "is-expanded" : "is-collapsed"}`} onClick={onToggleExpanded}>
          {isExpanded
            ? t("connections.collapsePeers")
            : t("connections.expandPeers", { count: formatNumber(peerCount ?? 0) })}
        </button>
      ) : null}
    </article>
  );
}

function StatusCompletion({ summary }: { summary: CableStatusSummary }) {
  const { formatCableStatus, formatNumber, formatPercent, t } = useI18n();
  const completionRate = summary.total > 0 ? summary.completed / summary.total : 0;

  return (
    <div className="status-completion" title={statusTooltip(summary, formatCableStatus, formatNumber)}>
      <span>
        {t("completion.text", { completed: formatNumber(summary.completed), total: formatNumber(summary.total) })}
      </span>
      <meter min={0} max={summary.total || 1} value={summary.completed} aria-label={t("completion.aria")} />
      <b>{formatPercent(completionRate)}</b>
    </div>
  );
}

function statusTooltip(
  summary: CableStatusSummary,
  formatCableStatus: (status: string) => string,
  formatNumber: (value: number) => string,
) {
  return Object.entries(summary.status_counts)
    .map(([status, count]) => `${formatCableStatus(status)}: ${formatNumber(count)}`)
    .join("\n");
}

import type {
  CabinetDetailResponse,
  CableStatusSummary,
  DataHallCableBucket,
  DataHallCableSummaryResponse,
  DeviceConnectionResponse,
} from "../types";
import { useDragPan } from "../hooks/useDragPan";
import { useI18n } from "../i18n";

type CabinetConnectionsPanelProps = {
  detail: CabinetDetailResponse | null;
  deviceDetail: DeviceConnectionResponse | null;
  dataHallCableSummary: DataHallCableSummaryResponse | null;
  onViewCables: (targetCabinetUid: string) => void;
  onViewDeviceCables: (targetDeviceUid: string) => void;
  onViewDataHallCables: (bucket: DataHallCableBucket, cableType: string) => void;
};

export function CabinetConnectionsPanel({
  detail,
  deviceDetail,
  dataHallCableSummary,
  onViewCables,
  onViewDeviceCables,
  onViewDataHallCables,
}: CabinetConnectionsPanelProps) {
  const { formatNumber, t } = useI18n();
  const connectionListPan = useDragPan<HTMLDivElement>();
  if (deviceDetail) {
    return (
      <aside className="side-pane connections-pane">
        <span className="eyebrow">{t("connections.connectedDevices")}</span>
        <h2>{t("connections.connectedDevicesCount", { count: formatNumber(deviceDetail.connected_devices.length) })}</h2>
        <div className="connection-list drag-pan-surface" {...connectionListPan}>
          {deviceDetail.connected_devices.map((connection) => (
            <article className="connection-item" key={connection.target_device_uid}>
              <div className="connection-heading">
                <strong>{connection.target_device_uid}</strong>
                <span>{t("connections.cableCount", { count: formatNumber(connection.total_cables) })}</span>
              </div>
              <StatusCompletion summary={connection.status_summary} />
              <div className="connection-meta">
                {t("connections.targetCabinetRu", {
                  cabinetUid: connection.target_cabinet_uid,
                  rackUnit: connection.target_rack_unit,
                })}
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
          ))}
        </div>
      </aside>
    );
  }

  if (!detail) {
    return (
      <aside className="side-pane connections-pane">
        <span className="eyebrow">{t("connections.dataHallCables")}</span>
        <h2>{dataHallCableSummary?.data_hall_id ?? t("dataHall.fallback")}</h2>
        {dataHallCableSummary ? (
          <div className="connection-list drag-pan-surface" {...connectionListPan}>
            <DataHallCableBucketCard
              bucket={dataHallCableSummary.internal}
              title={t("connections.insideDataHall", { dataHall: dataHallCableSummary.data_hall_id })}
              subtitle={t("connections.intraDataHall")}
              onViewDataHallCables={onViewDataHallCables}
            />
            {dataHallCableSummary.external.map((bucket) => (
              <DataHallCableBucketCard
                bucket={bucket}
                key={bucket.target_data_hall ?? "external"}
                title={t("connections.toDataHall", { dataHall: bucket.target_data_hall ?? t("dataHall.fallback") })}
                subtitle={t("connections.crossDataHall")}
                onViewDataHallCables={onViewDataHallCables}
              />
            ))}
          </div>
        ) : (
          <p className="empty-state">{t("common.loading", { target: t("connections.dataHallCables") })}</p>
        )}
      </aside>
    );
  }

  return (
    <aside className="side-pane connections-pane">
      <span className="eyebrow">{t("connections.connectedCabinets")}</span>
      <h2>{t("connections.connectedCabinetsCount", { count: formatNumber(detail.stats.connected_cabinets) })}</h2>
      <div className="connection-list drag-pan-surface" {...connectionListPan}>
        {detail.intra_cabinet_connection ? (
          <article className="connection-item intra-connection">
            <div className="connection-heading">
              <strong>{t("connections.insideCabinet", { cabinetUid: detail.cabinet.cabinet_uid })}</strong>
              <span>{t("connections.cableCount", { count: formatNumber(detail.intra_cabinet_connection.total_cables) })}</span>
            </div>
            <StatusCompletion summary={detail.intra_cabinet_connection.status_summary} />
            <div className="connection-meta">{t("connections.intraCabinet")}</div>
            <ul className="cable-types">
              {Object.entries(detail.intra_cabinet_connection.cable_type_counts).map(([type, count]) => (
                <li key={type}>
                  <span>{type}</span>
                  <b>{formatNumber(count)}</b>
                </li>
              ))}
            </ul>
            <button className="detail-button" onClick={() => onViewCables(detail.cabinet.cabinet_uid)}>
              {t("connections.viewCables")}
            </button>
          </article>
        ) : null}
        {detail.connections.map((connection) => (
          <article className="connection-item" key={connection.target_cabinet_uid}>
            <div className="connection-heading">
              <strong>{connection.target_cabinet_uid}</strong>
              <span>{t("connections.cableCount", { count: formatNumber(connection.total_cables) })}</span>
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
        ))}
      </div>
    </aside>
  );
}

function DataHallCableBucketCard({
  bucket,
  title,
  subtitle,
  onViewDataHallCables,
}: {
  bucket: DataHallCableBucket;
  title: string;
  subtitle: string;
  onViewDataHallCables: (bucket: DataHallCableBucket, cableType: string) => void;
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
      <ul className="cable-types cable-types-with-actions">
        {Object.entries(bucket.cable_type_counts).map(([type, count]) => (
          <li key={type}>
            <span>{type}</span>
            <b>{formatNumber(count)}</b>
            <button className="mini-detail-button" onClick={() => onViewDataHallCables(bucket, type)}>
              {t("connections.viewCables")}
            </button>
          </li>
        ))}
      </ul>
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

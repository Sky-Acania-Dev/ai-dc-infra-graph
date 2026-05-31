import { useEffect, useState } from "react";
import type React from "react";
import { fetchValidationReport } from "../api";
import { useI18n } from "../i18n";
import type {
  DeviceModelFinding,
  DeviceModelRowExample,
  ModelCount,
  PortConnectionFinding,
  ValidationCableRowExample,
  ValidationResponse,
} from "../types";

type ValidationViewProps = {
  onJumpToDevice: (deviceUid: string) => void;
  onJumpToPort: (portUid: string) => void;
};

type OverlayState =
  | { title: string; examples: DeviceModelRowExample[] }
  | { title: string; examples: ValidationCableRowExample[] }
  | null;

export function ValidationView({ onJumpToDevice, onJumpToPort }: ValidationViewProps) {
  const { formatCableStatus, formatNumber, t } = useI18n();
  const [report, setReport] = useState<ValidationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<OverlayState>(null);

  useEffect(() => {
    fetchValidationReport()
      .then(setReport)
      .catch((requestError: Error) => setError(requestError.message));
  }, []);

  if (error) {
    return <div className="error-banner">{error}</div>;
  }

  if (!report) {
    return <section className="validation-view loading-pane">{t("common.loading", { target: t("validation.results") })}</section>;
  }

  return (
    <section className="validation-view">
      <div className="validation-header">
        <div>
          <span className="eyebrow">{t("validation.qa")}</span>
          <h2>{t("validation.results")}</h2>
        </div>
        <div className="validation-summary">
          <ValidationCounter label={t("validation.portCollisions")} value={report.summary.port_collision_findings} />
          <ValidationCounter label={t("validation.modelMismatches")} value={report.summary.device_model_mismatches} />
          <ValidationCounter label={t("validation.formatIssues")} value={report.summary.device_model_format_issues} />
        </div>
      </div>

      <ValidationSection title={t("validation.deviceModelMismatches")} count={report.device_model_mismatches.length}>
        <DeviceModelTable findings={report.device_model_mismatches} onJump={onJumpToDevice} onOpen={setOverlay} />
      </ValidationSection>
      <ValidationSection title={t("validation.deviceModelFormatIssues")} count={report.device_model_format_issues.length}>
        <DeviceModelTable findings={report.device_model_format_issues} onJump={onJumpToDevice} onOpen={setOverlay} />
      </ValidationSection>
      <ValidationSection title={t("validation.portCollisions")} count={report.port_collision_findings.length}>
        <PortCollisionTable findings={report.port_collision_findings} onJump={onJumpToPort} onOpen={setOverlay} />
      </ValidationSection>

      {overlay ? <ValidationOverlay overlay={overlay} onClose={() => setOverlay(null)} /> : null}
    </section>
  );
}

function ValidationCounter({ label, value }: { label: string; value: number }) {
  const { formatNumber } = useI18n();
  return (
    <div>
      <span>{label}</span>
      <b>{formatNumber(value)}</b>
    </div>
  );
}

function ValidationSection({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  const { formatNumber, t } = useI18n();
  return (
    <section className="validation-section">
      <div className="section-title">
        {title} ({formatNumber(count)})
      </div>
      {count ? children : <p className="empty-state">{t("common.noFindings")}</p>}
    </section>
  );
}

function DeviceModelTable({
  findings,
  onJump,
  onOpen,
}: {
  findings: DeviceModelFinding[];
  onJump: (deviceUid: string) => void;
  onOpen: (overlay: OverlayState) => void;
}) {
  const { formatNumber, t } = useI18n();
  if (!findings.length) return null;

  return (
    <div className="validation-table-scroll">
      <table className="validation-table">
        <thead>
          <tr>
            <th>{t("common.go")}</th>
            <th>{t("validation.device")}</th>
            <th>{t("validation.models")}</th>
            <th>{t("common.normalized")}</th>
            <th>{t("common.examples")}</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => (
            <tr
              key={`${finding.classification}-${finding.device_uid}`}
              onClick={() => onOpen({ title: finding.device_uid, examples: finding.examples })}
            >
              <td>
                <button
                  className="mini-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onJump(finding.device_uid);
                  }}
                >
                  {t("common.map")}
                </button>
              </td>
              <td>{finding.device_uid}</td>
              <td>{formatCounts(finding.models, formatNumber)}</td>
              <td>{formatCounts(finding.normalized_models, formatNumber)}</td>
              <td>{formatNumber(finding.examples.length)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PortCollisionTable({
  findings,
  onJump,
  onOpen,
}: {
  findings: PortConnectionFinding[];
  onJump: (portUid: string) => void;
  onOpen: (overlay: OverlayState) => void;
}) {
  const { formatNumber, t } = useI18n();
  if (!findings.length) return null;

  return (
    <div className="validation-table-scroll">
      <table className="validation-table">
        <thead>
          <tr>
            <th>{t("common.go")}</th>
            <th>{t("common.port")}</th>
            <th>{t("common.count")}</th>
            <th>{t("common.finding")}</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => (
            <tr key={finding.port_uid} onClick={() => onOpen({ title: finding.port_uid, examples: finding.examples })}>
              <td>
                <button
                  className="mini-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onJump(finding.port_uid);
                  }}
                >
                  {t("common.map")}
                </button>
              </td>
              <td>{finding.port_uid}</td>
              <td>{formatNumber(finding.count)}</td>
              <td>{finding.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ValidationOverlay({ overlay, onClose }: { overlay: OverlayState; onClose: () => void }) {
  const { formatCableStatus, t } = useI18n();
  if (!overlay) return null;
  const isDeviceExamples = overlay.examples.length > 0 && "device_model" in overlay.examples[0];
  const isCableExamples = overlay.examples.length > 0 && "a_port_uid" in overlay.examples[0];

  return (
    <div className="validation-overlay">
      <div className="overlay-header">
        <div>
          <span className="eyebrow">{t("validation.findingDetail")}</span>
          <h2>{overlay.title}</h2>
        </div>
        <button className="icon-button" onClick={onClose} aria-label={t("validation.closeDetail")}>
          X
        </button>
      </div>
      <div className="table-scroll">
        {isDeviceExamples ? (
          <table>
            <thead>
              <tr>
                <th>{t("common.side")}</th>
                <th>{t("common.status")}</th>
                <th>{t("common.group")}</th>
                <th>{t("common.port")}</th>
                <th>{t("common.type")}</th>
                <th>{t("validation.deviceName")}</th>
                <th>{t("common.model")}</th>
              </tr>
            </thead>
            <tbody>
              {(overlay.examples as DeviceModelRowExample[]).map((example, index) => (
                <tr key={`${example.port_uid}-${index}`}>
                  <td>{example.side.toUpperCase()}</td>
                  <td>{formatCableStatus(example.status)}</td>
                  <td>{example.group}</td>
                  <td>{example.port_uid}</td>
                  <td>{example.cable_type}</td>
                  <td>{example.device_name}</td>
                  <td>{example.device_model}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : isCableExamples ? (
          <table>
            <thead>
              <tr>
                <th>{t("common.status")}</th>
                <th>{t("common.group")}</th>
                <th>{t("common.type")}</th>
                <th>{t("cable.column.aPort")}</th>
                <th>{t("cable.column.zPort")}</th>
                <th>{t("validation.aModel")}</th>
                <th>{t("validation.zModel")}</th>
              </tr>
            </thead>
            <tbody>
              {(overlay.examples as ValidationCableRowExample[]).map((example, index) => (
                <tr key={`${example.a_port_uid}-${example.z_port_uid}-${index}`}>
                  <td>{formatCableStatus(example.status)}</td>
                  <td>{example.group}</td>
                  <td>{example.cable_type}</td>
                  <td>{example.a_port_uid}</td>
                  <td>{example.z_port_uid}</td>
                  <td>{example.a_device_model}</td>
                  <td>{example.z_device_model}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="empty-state">{t("common.noExamples")}</p>
        )}
      </div>
    </div>
  );
}

function formatCounts(counts: ModelCount[], formatNumber: (value: number) => string) {
  return counts
    .map(({ value, count }) => `${value}: ${formatNumber(count)}`)
    .join(", ");
}

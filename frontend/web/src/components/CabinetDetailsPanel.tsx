import type { CabinetDetailResponse } from "../types";
import { CabinetDeviceLayout } from "./CabinetDeviceLayout";

type CabinetDetailsPanelProps = {
  detail: CabinetDetailResponse | null;
};

export function CabinetDetailsPanel({ detail }: CabinetDetailsPanelProps) {
  if (!detail) {
    return (
      <aside className="side-pane">
        <span className="eyebrow">Cabinet Details</span>
        <p className="empty-state">Select a cabinet to inspect devices and rack-unit layout.</p>
      </aside>
    );
  }

  return (
    <aside className="side-pane">
      <span className="eyebrow">Cabinet Details</span>
      <h1>{detail.cabinet.cabinet_uid}</h1>
      <dl className="facts">
        <div>
          <dt>Type</dt>
          <dd>{detail.cabinet.category}</dd>
        </div>
        <div>
          <dt>Group</dt>
          <dd>{detail.cabinet.cabinet_group || "Unassigned"}</dd>
        </div>
        <div>
          <dt>Devices</dt>
          <dd>{detail.stats.devices.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Ports</dt>
          <dd>{detail.stats.ports.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Cables</dt>
          <dd>{detail.stats.cables.toLocaleString()}</dd>
        </div>
      </dl>
      <CabinetDeviceLayout devices={detail.devices} />
    </aside>
  );
}

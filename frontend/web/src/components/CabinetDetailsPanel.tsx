import type { CabinetDetailResponse, CabinetLayoutItem } from "../types";
import { CabinetDeviceLayout } from "./CabinetDeviceLayout";

type CabinetDetailsPanelProps = {
  detail: CabinetDetailResponse | null;
  dataHall: string;
  cabinets: CabinetLayoutItem[];
};

export function CabinetDetailsPanel({ detail, dataHall, cabinets }: CabinetDetailsPanelProps) {
  if (!detail) {
    const categories = categoryCounts(cabinets);
    return (
      <aside className="side-pane">
        <span className="eyebrow">Data Hall Summary</span>
        <h1>{dataHall}</h1>
        <dl className="facts">
          <div>
            <dt>Cabinets</dt>
            <dd>{cabinets.length.toLocaleString()}</dd>
          </div>
          <div>
            <dt>Categories</dt>
            <dd>{categories.length.toLocaleString()}</dd>
          </div>
        </dl>
        <section className="category-summary">
          <div className="section-title">Cabinet Types</div>
          {categories.map(([category, count]) => (
            <div className="category-row" key={category}>
              <span>{category}</span>
              <b>{count}</b>
            </div>
          ))}
        </section>
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

function categoryCounts(cabinets: CabinetLayoutItem[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const cabinet of cabinets) {
    counts.set(cabinet.category, (counts.get(cabinet.category) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

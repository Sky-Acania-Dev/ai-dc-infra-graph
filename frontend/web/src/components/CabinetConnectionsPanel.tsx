import type { CabinetDetailResponse } from "../types";

type CabinetConnectionsPanelProps = {
  detail: CabinetDetailResponse | null;
};

export function CabinetConnectionsPanel({ detail }: CabinetConnectionsPanelProps) {
  if (!detail) {
    return (
      <aside className="side-pane">
        <span className="eyebrow">Connections</span>
        <p className="empty-state">Graph-neighbor cabinets will appear here after selection.</p>
      </aside>
    );
  }

  return (
    <aside className="side-pane connections-pane">
      <span className="eyebrow">Connections</span>
      <h2>{detail.stats.connected_cabinets} Connected Cabinets</h2>
      <div className="connection-list">
        {detail.connections.map((connection) => (
          <article className="connection-item" key={connection.target_cabinet_uid}>
            <div className="connection-heading">
              <strong>{connection.target_cabinet_uid}</strong>
              <span>{connection.total_cables} cables</span>
            </div>
            <div className="connection-meta">
              {connection.target_category} {connection.target_cabinet_group ? `- ${connection.target_cabinet_group}` : ""}
            </div>
            <ul className="cable-types">
              {Object.entries(connection.cable_type_counts).map(([type, count]) => (
                <li key={type}>
                  <span>{type}</span>
                  <b>{count}</b>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </aside>
  );
}

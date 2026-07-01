import type { CableDetailResponse, CabinetCableDetail, EntityGroupRecord } from "../types";

type EntityGroupSummaryPanelProps = {
  groups: EntityGroupRecord[];
  selectedGroups: EntityGroupRecord[];
  cableDetails: CableDetailResponse[];
  isLoading: boolean;
  onViewCables: () => void;
};

type CableSummary = {
  total: number;
  selectedMemberTotal: number;
  cableTypeCounts: Record<string, number>;
  statusCounts: Record<string, number>;
};

export function EntityGroupSummaryPanel({
  groups,
  selectedGroups,
  cableDetails,
  isLoading,
  onViewCables,
}: EntityGroupSummaryPanelProps) {
  const summary = summarizeGroupCables(cableDetails, selectedGroups);
  const selectedGroupCount = selectedGroups.length;
  const totalGroupCount = groups.length;
  const selectedLabel = `${selectedGroupCount}/${totalGroupCount} groups selected`;

  return (
    <aside className="side-pane connections-pane entity-group-summary-panel">
      <span className="eyebrow">Group Scope</span>
      <h2>{selectedLabel}</h2>
      {selectedGroupCount > 0 ? (
        <div className="connection-list">
          <article className="connection-item intra-connection">
            <div className="connection-heading">
              <strong>{selectedGroupCount === 1 ? selectedGroups[0].name : "Selected groups"}</strong>
              <span>{summary.total}/{summary.selectedMemberTotal}</span>
            </div>
            <div className="connection-meta">
              {isLoading ? "Loading group cables" : `${summary.total} loaded cables from ${summary.selectedMemberTotal} group members`}
            </div>
            <ul className="cable-types">
              {Object.entries(summary.cableTypeCounts).map(([type, count]) => (
                <li key={type}>
                  <span>{type}</span>
                  <b>{count}</b>
                </li>
              ))}
              {!Object.keys(summary.cableTypeCounts).length ? (
                <li>
                  <span>No cables</span>
                  <b>0</b>
                </li>
              ) : null}
            </ul>
            <button className="detail-button" disabled={summary.total === 0 || isLoading} onClick={onViewCables} type="button">
              View Cables
            </button>
          </article>
          <article className="connection-item">
            <div className="connection-heading">
              <strong>Cabinet map selection</strong>
              <span>{uniqueCabinetCount(selectedGroups)}</span>
            </div>
            <div className="connection-meta">Cabinets associated with selected group members</div>
            <ul className="cable-types">
              {selectedGroups.map((group) => (
                <li key={group.uid}>
                  <span>{group.name}</span>
                  <b>{group.associated_cabinet_uids.length}</b>
                </li>
              ))}
            </ul>
          </article>
          <article className="connection-item">
            <div className="connection-heading">
              <strong>Status</strong>
              <span>{summary.total}</span>
            </div>
            <div className="connection-meta">Status counts for loaded group cables</div>
            <ul className="cable-types">
              {Object.entries(summary.statusCounts).map(([status, count]) => (
                <li key={status}>
                  <span>{status}</span>
                  <b>{count}</b>
                </li>
              ))}
              {!Object.keys(summary.statusCounts).length ? (
                <li>
                  <span>No status</span>
                  <b>0</b>
                </li>
              ) : null}
            </ul>
          </article>
        </div>
      ) : (
        <p className="empty-state">Select a group to view scoped cables.</p>
      )}
    </aside>
  );
}

function summarizeGroupCables(cableDetails: CableDetailResponse[], selectedGroups: EntityGroupRecord[]): CableSummary {
  const cables = uniqueCables(cableDetails.flatMap((detail) => detail.cables));
  const cableTypeCounts: Record<string, number> = {};
  const statusCounts: Record<string, number> = {};
  for (const cable of cables) {
    cableTypeCounts[cable.cable_type] = (cableTypeCounts[cable.cable_type] ?? 0) + 1;
    statusCounts[cable.status] = (statusCounts[cable.status] ?? 0) + 1;
  }
  return {
    total: cables.length,
    selectedMemberTotal: selectedGroups.reduce((total, group) => total + group.member_count, 0),
    cableTypeCounts: sortCounts(cableTypeCounts),
    statusCounts: sortCounts(statusCounts),
  };
}

function uniqueCables(cables: CabinetCableDetail[]): CabinetCableDetail[] {
  const byUid = new Map<string, CabinetCableDetail>();
  for (const cable of cables) byUid.set(cable.uid, cable);
  return [...byUid.values()];
}

function uniqueCabinetCount(groups: EntityGroupRecord[]): number {
  return new Set(groups.flatMap((group) => group.associated_cabinet_uids)).size;
}

function sortCounts(counts: Record<string, number>): Record<string, number> {
  return Object.fromEntries(Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])));
}
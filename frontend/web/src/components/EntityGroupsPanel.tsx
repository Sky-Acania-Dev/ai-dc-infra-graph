import { useEffect, useMemo, useState, type MouseEvent } from "react";
import type { SelectionGesture, SelectionMode } from "../App";
import type { CableGroupSourceRecord, EntityGroupRecord } from "../types";

type EntityGroupsPanelProps = {
  groups: EntityGroupRecord[];
  activeGroupUid: string | null;
  selectedGroupUids: string[];
  selectedCableUids: string[];
  selectionMode: SelectionMode;
  canManage: boolean;
  cableSourceGroups: CableGroupSourceRecord[];
  isLoading: boolean;
  removingGroupUids: string[];
  isCreatingFromCableGroup: boolean;
  isCreatingMissingCableGroups: boolean;
  onCreateGroup: (name: string, description: string) => void;
  onUpdateGroup: (groupUid: string, payload: { name?: string; description?: string; member_uids?: string[] }) => void;
  onDeleteGroup: (groupUid: string) => void;
  onSelectGroup: (groupUid: string, gesture: SelectionGesture) => void;
  onClearGroupSelection: () => void;
  onAddSelectedCables: () => void;
  onCreateFromCableGroup: (sourceGroup: string) => void;
  onCreateFromCableGroups: (sourceGroups: string[]) => void;
};

export function EntityGroupsPanel({
  groups,
  activeGroupUid,
  selectedGroupUids,
  selectedCableUids,
  selectionMode,
  canManage,
  cableSourceGroups,
  isLoading,
  removingGroupUids,
  isCreatingFromCableGroup,
  isCreatingMissingCableGroups,
  onCreateGroup,
  onUpdateGroup,
  onDeleteGroup,
  onSelectGroup,
  onClearGroupSelection,
  onAddSelectedCables,
  onCreateFromCableGroup,
  onCreateFromCableGroups,
}: EntityGroupsPanelProps) {
  const [isCreateExpanded, setIsCreateExpanded] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [sourceGroupValue, setSourceGroupValue] = useState("");
  const [editingUid, setEditingUid] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const activeGroup = groups.find((group) => group.uid === activeGroupUid) ?? null;
  const selectedGroups = selectedGroupUids.map((uid) => groups.find((group) => group.uid === uid)).filter((group): group is EntityGroupRecord => Boolean(group));
  const selectedActionCount = useMemo(() => {
    if (!selectedGroups.length) return 0;
    let count = 0;
    for (const cableUid of selectedCableUids) {
      const membershipCount = selectedGroups.filter((group) => group.members.some((member) => member.entity_type === "cable" && member.entity_uid === cableUid)).length;
      count += selectionMode === "remove" ? membershipCount : selectedGroups.length - membershipCount;
    }
    return count;
  }, [selectedCableUids, selectedGroups, selectionMode]);
  const selectedGroupSet = useMemo(() => new Set(selectedGroupUids), [selectedGroupUids]);
  const existingCableGroupNames = useMemo(() => new Set(groups.filter((group) => group.entity_type === "cable").map((group) => group.name)), [groups]);
  const missingSourceGroups = useMemo(
    () => cableSourceGroups.filter((sourceGroup) => !existingCableGroupNames.has(sourceGroup.group)),
    [cableSourceGroups, existingCableGroupNames],
  );
  const selectedSourceGroupExists = existingCableGroupNames.has(sourceGroupValue);
  const isSourceImportBusy = isLoading || isCreatingFromCableGroup || isCreatingMissingCableGroups;
  const isMutationBusy = isSourceImportBusy || removingGroupUids.length > 0;
  const sourceImportMessage = isCreatingMissingCableGroups
    ? "Creating missing groups..."
    : isCreatingFromCableGroup
      ? "Creating group..."
      : isLoading
        ? "loading group data..."
        : null;

  useEffect(() => {
    if (selectedGroupUids.length > 0) setIsCreateExpanded(false);
  }, [selectedGroupUids.length]);

  useEffect(() => {
    if (!sourceGroupValue && cableSourceGroups.length > 0) setSourceGroupValue(cableSourceGroups[0].group);
    if (sourceGroupValue && !cableSourceGroups.some((sourceGroup) => sourceGroup.group === sourceGroupValue)) {
      setSourceGroupValue(cableSourceGroups[0]?.group ?? "");
    }
  }, [cableSourceGroups, sourceGroupValue]);

  function submitCreate() {
    const name = draftName.trim();
    if (!name || !canManage || isMutationBusy) return;
    onCreateGroup(name, draftDescription.trim());
    setDraftName("");
    setDraftDescription("");
    setIsCreateExpanded(false);
  }

  function openCreateCard() {
    if (isMutationBusy) return;
    onClearGroupSelection();
    setIsCreateExpanded(true);
  }

  function submitCreateFromCableGroup() {
    const sourceGroup = sourceGroupValue.trim();
    if (!sourceGroup || !canManage || isSourceImportBusy) return;
    onCreateFromCableGroup(sourceGroup);
  }

  function submitCreateMissingCableGroups() {
    if (!missingSourceGroups.length || !canManage || isSourceImportBusy) return;
    onCreateFromCableGroups(missingSourceGroups.map((sourceGroup) => sourceGroup.group));
  }

  function startEdit(group: EntityGroupRecord) {
    setEditingUid(group.uid);
    setEditName(group.name);
    setEditDescription(group.description);
  }

  function saveEdit(group: EntityGroupRecord) {
    const name = editName.trim();
    if (!name || !canManage || isMutationBusy) return;
    onUpdateGroup(group.uid, { name, description: editDescription.trim() });
    setEditingUid(null);
  }

  function stopNestedClick(event: MouseEvent) {
    event.stopPropagation();
  }

  function shouldSuppressTextSelection(event: MouseEvent) {
    return selectionMode === "multi" || selectionMode === "remove" || event.shiftKey;
  }

  return (
    <section className="side-pane entity-groups-panel" aria-busy={isLoading}>
      <span className="eyebrow">Shared Planning</span>
      <h1>Entity Groups</h1>
      {canManage ? (
        isCreateExpanded ? (
          <div className="entity-group-create entity-group-create-accent is-expanded" onClick={onClearGroupSelection}>
            <input
              disabled={isMutationBusy}
              onChange={(event) => setDraftName(event.target.value)}
              placeholder="New cable group"
              value={draftName}
            />
            <textarea
              disabled={isMutationBusy}
              onChange={(event) => setDraftDescription(event.target.value)}
              placeholder="Description"
              rows={2}
              value={draftDescription}
            />
            <div className="entity-group-actions">
              <button disabled={!draftName.trim() || isMutationBusy} onClick={submitCreate} type="button">
                Add Group
              </button>
              <button disabled={isMutationBusy} onClick={() => setIsCreateExpanded(false)} type="button">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="entity-group-create entity-group-create-accent is-collapsed" onClick={openCreateCard}>
            <button disabled={isMutationBusy} onClick={openCreateCard} type="button">
              {draftName.trim() ? `Add ${draftName.trim()} Group` : "Add Group"}
            </button>
          </div>
        )
      ) : null}
      {canManage && (isLoading || cableSourceGroups.length > 0) ? (
        <div className="entity-group-create entity-group-source-import" aria-busy={isSourceImportBusy}>
          <select disabled={isSourceImportBusy || cableSourceGroups.length === 0} value={sourceGroupValue} onChange={(event) => setSourceGroupValue(event.target.value)}>
            {cableSourceGroups.map((sourceGroup) => (
              <option key={sourceGroup.group} value={sourceGroup.group}>
                {sourceGroup.group} ({sourceGroup.cable_count})
              </option>
            ))}
          </select>
          <button
            className="entity-group-heavy-action"
            disabled={!sourceGroupValue.trim() || selectedSourceGroupExists || isSourceImportBusy}
            onClick={submitCreateFromCableGroup}
            type="button"
          >
            {isCreatingFromCableGroup ? "Creating..." : selectedSourceGroupExists ? "Already Created" : "Create from GROUP"}
          </button>
          <button
            className="entity-group-heavy-action is-bulk"
            disabled={!missingSourceGroups.length || isSourceImportBusy}
            onClick={submitCreateMissingCableGroups}
            type="button"
          >
            {isCreatingMissingCableGroups ? "Creating..." : `Create Missing (${missingSourceGroups.length})`}
          </button>
          {sourceImportMessage ? <div className="entity-group-source-overlay">{sourceImportMessage}</div> : null}
        </div>
      ) : null}
      <div className="entity-group-list">
        {groups.map((group) => {
          const isActive = group.uid === activeGroup?.uid;
          const isSelected = selectedGroupSet.has(group.uid);
          const isEditing = editingUid === group.uid;
          const isExpanded = isSelected || isEditing;
          const isRemoving = removingGroupUids.includes(group.uid);
          return (
            <article
              aria-busy={isRemoving}
              className={`entity-group-card ${isActive ? "is-active" : ""} ${isSelected ? "is-selected" : ""} ${isRemoving ? "is-removing" : ""}`}
              key={group.uid}
              onClick={(event) => {
                if (isRemoving) return;
                onSelectGroup(group.uid, event);
              }}
              onMouseDown={(event) => {
                if (shouldSuppressTextSelection(event)) event.preventDefault();
              }}
            >
              {isEditing ? (
                <div className="entity-group-edit" onClick={stopNestedClick}>
                  <input value={editName} onChange={(event) => setEditName(event.target.value)} />
                  <textarea rows={2} value={editDescription} onChange={(event) => setEditDescription(event.target.value)} />
                  <div className="entity-group-actions">
                    <button onClick={() => saveEdit(group)} type="button">Save</button>
                    <button onClick={() => setEditingUid(null)} type="button">Cancel</button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="entity-group-main" role="button" tabIndex={0}>
                    <span>{group.name}</span>
                    <b>{group.member_count}</b>
                  </div>
                  {isExpanded ? (
                    <>
                      {group.description ? <p>{group.description}</p> : null}
                      <MemberSummary group={group} />
                      <div className="entity-group-meta">
                        <span>{group.entity_type}</span>
                        <span>{group.owner_user_uid ?? "shared"}</span>
                      </div>
                      {canManage ? (
                        <div className="entity-group-actions" onClick={stopNestedClick}>
                          <button disabled={isRemoving || isMutationBusy} onClick={() => startEdit(group)} type="button">Modify</button>
                          <button disabled={isRemoving || isMutationBusy} onClick={() => onDeleteGroup(group.uid)} type="button">Remove</button>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </>
              )}
              {isRemoving ? <div className="entity-group-card-overlay">Removing group...</div> : null}
              {isActive && canManage && selectedGroupUids.length > 0 ? (
                <div className="entity-group-members" onClick={stopNestedClick}>
                  <div className="entity-group-members-header">
                    <span>Group actions</span>
                    <button disabled={selectedActionCount === 0 || isMutationBusy} onClick={onAddSelectedCables} type="button">
                      {selectionMode === "remove" ? "Remove Selected" : "Add Selected"} {selectedActionCount ? `(${selectedActionCount})` : ""}
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
        {!groups.length ? <div className="entity-group-empty">No shared groups yet.</div> : null}
      </div>
      {isLoading ? <div className="entity-groups-loading-overlay">loading group data...</div> : null}
    </section>
  );
}

function MemberSummary({ group }: { group: EntityGroupRecord }) {
  const summaries = memberTypeSummary(group);
  if (!summaries.length) return <div className="entity-group-empty">No members yet.</div>;
  return (
    <div className="entity-group-member-summary">
      {summaries.map(({ entityType, count }) => (
        <span className="entity-group-member-chip" key={entityType}>
          <b>{count}</b> {count === 1 ? entityType : `${entityType}s`}
        </span>
      ))}
    </div>
  );
}

function memberTypeSummary(group: EntityGroupRecord): Array<{ entityType: string; count: number }> {
  const counts = new Map<string, number>();
  for (const member of group.members) {
    counts.set(member.entity_type, (counts.get(member.entity_type) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([entityType, count]) => ({ entityType, count }))
    .sort((left, right) => left.entityType.localeCompare(right.entityType));
}

import { useMemo, useState } from "react";
import type { SelectionMode } from "../App";
import type { EntityGroupRecord } from "../types";

type EntityGroupsPanelProps = {
  groups: EntityGroupRecord[];
  activeGroupUid: string | null;
  selectedCableUids: string[];
  selectionMode: SelectionMode;
  canManage: boolean;
  onCreateGroup: (name: string, description: string) => void;
  onUpdateGroup: (groupUid: string, payload: { name?: string; description?: string; member_uids?: string[] }) => void;
  onDeleteGroup: (groupUid: string) => void;
  onActivateGroup: (groupUid: string) => void;
  onAddSelectedCables: () => void;
};

export function EntityGroupsPanel({
  groups,
  activeGroupUid,
  selectedCableUids,
  selectionMode,
  canManage,
  onCreateGroup,
  onUpdateGroup,
  onDeleteGroup,
  onActivateGroup,
  onAddSelectedCables,
}: EntityGroupsPanelProps) {
  const [draftName, setDraftName] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [editingUid, setEditingUid] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const activeGroup = groups.find((group) => group.uid === activeGroupUid) ?? groups[0] ?? null;
  const selectedActionCount = useMemo(() => {
    if (!activeGroup) return 0;
    const existing = new Set(activeGroup.members.map((member) => member.entity_uid));
    if (selectionMode === "remove") return selectedCableUids.filter((uid) => existing.has(uid)).length;
    return selectedCableUids.filter((uid) => !existing.has(uid)).length;
  }, [activeGroup, selectedCableUids, selectionMode]);

  function submitCreate() {
    const name = draftName.trim();
    if (!name || !canManage) return;
    onCreateGroup(name, draftDescription.trim());
    setDraftName("");
    setDraftDescription("");
  }

  function startEdit(group: EntityGroupRecord) {
    setEditingUid(group.uid);
    setEditName(group.name);
    setEditDescription(group.description);
  }

  function saveEdit(group: EntityGroupRecord) {
    const name = editName.trim();
    if (!name || !canManage) return;
    onUpdateGroup(group.uid, { name, description: editDescription.trim() });
    setEditingUid(null);
  }

  function removeMember(group: EntityGroupRecord, memberUid: string) {
    onUpdateGroup(group.uid, {
      member_uids: group.members.map((member) => member.entity_uid).filter((uid) => uid !== memberUid),
    });
  }

  return (
    <section className="side-pane entity-groups-panel">
      <span className="eyebrow">Shared Planning</span>
      <h1>Entity Groups</h1>
      {canManage ? (
        <div className="entity-group-create">
          <input
            onChange={(event) => setDraftName(event.target.value)}
            placeholder="New cable group"
            value={draftName}
          />
          <textarea
            onChange={(event) => setDraftDescription(event.target.value)}
            placeholder="Description"
            rows={2}
            value={draftDescription}
          />
          <button disabled={!draftName.trim()} onClick={submitCreate} type="button">
            Add Group
          </button>
        </div>
      ) : null}
      <div className="entity-group-list">
        {groups.map((group) => {
          const isActive = group.uid === activeGroup?.uid;
          const isEditing = editingUid === group.uid;
          return (
            <article className={`entity-group-card ${isActive ? "is-active" : ""}`} key={group.uid}>
              {isEditing ? (
                <div className="entity-group-edit">
                  <input value={editName} onChange={(event) => setEditName(event.target.value)} />
                  <textarea rows={2} value={editDescription} onChange={(event) => setEditDescription(event.target.value)} />
                  <div className="entity-group-actions">
                    <button onClick={() => saveEdit(group)} type="button">Save</button>
                    <button onClick={() => setEditingUid(null)} type="button">Cancel</button>
                  </div>
                </div>
              ) : (
                <>
                  <button className="entity-group-main" onClick={() => onActivateGroup(group.uid)} type="button">
                    <span>{group.name}</span>
                    <b>{group.member_count}</b>
                  </button>
                  {group.description ? <p>{group.description}</p> : null}
                  <div className="entity-group-meta">
                    <span>{group.entity_type}</span>
                    <span>{group.owner_user_uid ?? "shared"}</span>
                  </div>
                  {canManage ? (
                    <div className="entity-group-actions">
                      <button onClick={() => startEdit(group)} type="button">Modify</button>
                      <button onClick={() => onDeleteGroup(group.uid)} type="button">Remove</button>
                    </div>
                  ) : null}
                </>
              )}
              {isActive ? (
                <div className="entity-group-members">
                  <div className="entity-group-members-header">
                    <span>Members</span>
                    {canManage ? (
                      <button disabled={selectedActionCount === 0} onClick={onAddSelectedCables} type="button">
                        {selectionMode === "remove" ? "Remove Selected" : "Add Selected"} {selectedActionCount ? `(${selectedActionCount})` : ""}
                      </button>
                    ) : null}
                  </div>
                  <div className="entity-group-member-list">
                    {group.members.map((member) => (
                      <div className="entity-group-member" key={`${member.entity_type}:${member.entity_uid}`}>
                        <code>{member.entity_uid}</code>
                        {canManage ? <button onClick={() => removeMember(group, member.entity_uid)} type="button">X</button> : null}
                      </div>
                    ))}
                    {!group.members.length ? <div className="entity-group-empty">No members yet.</div> : null}
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
        {!groups.length ? <div className="entity-group-empty">No shared groups yet.</div> : null}
      </div>
    </section>
  );
}
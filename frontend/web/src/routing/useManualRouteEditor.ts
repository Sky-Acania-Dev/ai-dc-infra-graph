import { useEffect, useMemo, useState } from "react";
import { routingApi } from "./api";
import { ManualRouteEngine, emptyDraft, sameRackPair } from "./manualRouteEngine";
import { formatInches } from "./dimensions";
import type { CableReview, ManualDraft, ReviewGroup } from "./types";

export function useManualRouteEditor(layoutUid: string | undefined, review: CableReview | null, replace: (data: CableReview) => void, reload: () => void) {
  const [selected, setSelected] = useState<string[]>([]);
  const [editing, setEditing] = useState(false);
  const [activeUid, setActiveUid] = useState("");
  const [drafts, setDrafts] = useState<Record<string, ManualDraft>>({});
  const [versions, setVersions] = useState<Record<string, string | null>>({});
  const [revision, setRevision] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {setSelected([]); setEditing(false); setDrafts({}); setMessage(""); setError("");}, [layoutUid, Boolean(review)]);
  const engine = useMemo(() => new ManualRouteEngine(review?.planning_segments ?? []), [review?.planning_segments]);
  const groups = review?.groups.filter(g => selected.includes(g.uid)) ?? [];
  const active = review?.groups.find(g => g.uid === activeUid);
  const draft = active ? drafts[active.uid] ?? emptyDraft(active) : null;
  const local = useMemo(() => {
    if (!editing || !active || !draft) return {preview: null, error: ""};
    try {return {preview: engine.preview(active, draft), error: ""};} catch (reason) {return {preview: null, error: String(reason).replace(/^Error: /, "")};}
  }, [editing, active, draft, engine]);
  const complete = (g: ReviewGroup) => {try {return Boolean(drafts[g.uid] && engine.isComplete(g, drafts[g.uid]));} catch {return false;}};
  const completed = groups.filter(complete).length;
  const topologyChanged = editing && revision !== review?.topology_revision;
  const change = (next: ManualDraft) => {if (active) {setDrafts(current => ({...current, [active.uid]: next})); setError(""); setMessage("");}};
  const append = (ids: string[]) => {
    if (!active || !draft || busy) return;
    const next = {...draft, ids: [...draft.ids, ...ids], checkpoints: [...draft.checkpoints, draft.ids.length]};
    try {engine.preview(active, next); change(next);} catch (reason) {setError(String(reason));}
  };
  const chooseSegment = (id: string) => {
    if (!editing || !active || !draft || busy || topologyChanged) return;
    try {
      const result = engine.connectSegment(active, draft, id);
      change(result.draft);
      setMessage(result.bridge.load_ids.length
        ? `Connected to ${result.segment.label} with a local A* bridge: ${formatInches(result.bridge.planar_length_in)} · ${result.bridge.vertical_transition_count} tier changes. Undo removes this whole choice.`
        : `Added ${result.segment.label} to the draft.`);
    } catch (reason) {setMessage(""); setError(String(reason).replace(/^Error: /, ""));}
  };
  const begin = () => {
    if (!review || !groups.length) return;
    setDrafts(Object.fromEntries(groups.map(g => [g.uid, emptyDraft(g)])));
    setVersions(Object.fromEntries(groups.map(g => [g.uid, g.manual_version])));
    setRevision(review.topology_revision); setActiveUid(groups[0].uid); setEditing(true); setError(""); setMessage(""); setNotes("");
  };
  const cancel = () => {setEditing(false); setError(""); setMessage("Draft discarded. Saved routes are unchanged.");};
  const save = async () => {
    if (!layoutUid || !review || busy || !editing) return;
    // Recheck every full chain locally immediately before making the only route-write request.
    if (!groups.length || groups.length !== selected.length || completed !== groups.length || topologyChanged) {setError("Complete every selected route against the current graph before saving."); return;}
    for (const g of groups) if (!engine.isComplete(g, drafts[g.uid])) return;
    setBusy(true); setError("");
    try {
      const result = await routingApi.manualBatch(layoutUid, {topology_revision: revision, notes,
        groups: groups.map(g => ({group_uid: g.uid, expected_version: versions[g.uid], segment_ids: drafts[g.uid].ids, start_tier: drafts[g.uid].startTier, end_tier: drafts[g.uid].endTier}))});
      replace(result.review); setEditing(false); setMessage(`Saved ${groups.length} manual group routes. A* defaults cannot overwrite them.`);
    } catch (reason) {setError(String(reason));} finally {setBusy(false);}
  };
  const reset = async () => {
    const manual = groups.filter(g => g.route_source === "MANUAL");
    if (!layoutUid || !review || busy || !manual.length || editing) return;
    setBusy(true); setError("");
    try {
      const result = await routingApi.manualBatch(layoutUid, {topology_revision: review.topology_revision,
        groups: manual.map(g => ({group_uid: g.uid, expected_version: g.manual_version, segment_ids: [], start_tier: g.start_tier, end_tier: g.end_tier}))}, true);
      replace(result.review); setMessage(`Reset ${manual.length} manual routes to defaults.`);
    } catch (reason) {setError(String(reason));} finally {setBusy(false);}
  };
  return {selected, editing, active, activeUid, setActiveUid, draft, preview: local.preview, error: error || local.error || (topologyChanged ? "Pathways changed. Reload before editing." : ""), message, notes, setNotes, busy, groups, completed, complete,
    canSave: Boolean(groups.length && groups.length === selected.length && completed === groups.length && !topologyChanged && !busy),
    toggle: (uid: string) => {if (!editing && !busy) setSelected(ids => ids.includes(uid) ? ids.filter(id => id !== uid) : [...ids, uid]);},
    selectShown: (shown: ReviewGroup[]) => {if (!editing && !busy) setSelected(ids => [...new Set([...ids, ...shown.map(g => g.uid)])]);},
    clearSelected: () => {if (!editing && !busy) setSelected([]);}, begin, cancel, append, chooseSegment, save, reset,
    reload: () => {cancel(); reload();},
    undo: () => {if (draft) change({...draft, ids: draft.ids.slice(0, draft.checkpoints.at(-1) ?? Math.max(0, draft.ids.length - 1)), checkpoints: draft.checkpoints.slice(0, -1)});},
    clearDraft: () => {if (draft) change({...draft, ids: [], checkpoints: []});},
    setTiers: (startTier: ManualDraft["startTier"], endTier: ManualDraft["endTier"]) => {if (draft) change({...draft, ids: [], checkpoints: [], startTier, endTier});},
    useCurrent: () => {if (active?.route) change({...emptyDraft(active), ids: [...active.route.load_ids], checkpoints: [0]});},
    copyToPair: () => {if (active && draft && local.preview?.complete) setDrafts(current => ({...current, ...Object.fromEntries(groups.filter(g => sameRackPair(active, g)).map(g => [g.uid, {...draft, ids: [...draft.ids], checkpoints: [0]}]))}));},
  };
}
export type ManualRouteEditor = ReturnType<typeof useManualRouteEditor>;

import { formatInches } from "./dimensions";
import { groupLabel, pointLabel, sameRackPair } from "./manualRouteEngine";
import type { ManualRouteEditor } from "./useManualRouteEditor";
import type { Tier } from "./types";

export function ManualRouteBatchPanel({editor: e, canManage}: {editor: ManualRouteEditor; canManage: boolean}) {
  if (!canManage || !e.editing) return null;
  const preview = e.preview;
  const samePairCount = e.active ? e.groups.filter(g => sameRackPair(e.active!, g)).length : 0;
  return <section className="manual-batch-panel" aria-label="Batch manual route editor">
    <h4>Route editor</h4>
    <>
      <p className="manual-edit-help">Click a teal next path, or any other segment to connect it with A*. Orange is your chosen chain; dashed cyan suggests the remainder. All clicks and suggestions stay local.</p>
      <label>Editing cable group<select aria-label="Editing cable group" value={e.activeUid} disabled={e.busy} onChange={event => e.setActiveUid(event.target.value)}>{e.groups.map(g => <option key={g.uid} value={g.uid}>{e.complete(g) ? "✓ " : "○ "}{groupLabel(g)}</option>)}</select></label>
      {e.draft && <div className="manual-endpoint-tiers">{(["Source", "Destination"] as const).map((label, index) => <label key={label}>{label} tier<select aria-label={`${label} route tier`} disabled={e.busy} value={index ? e.draft!.endTier : e.draft!.startTier}
        onChange={event => e.setTiers(index ? e.draft!.startTier : Number(event.target.value) as Tier, index ? Number(event.target.value) as Tier : e.draft!.endTier)}>{[1, 2, 3].map(t => <option key={t} value={t}>Tier {t}</option>)}</select></label>)}</div>}
      {preview && <>
        <div className="manual-progress" role="status">{preview.complete ? "Complete chain" : `Current endpoint: ${pointLabel(preview.prefix.points.at(-1)!)}`}<br />Planar pathway length: {formatInches(preview.prefix.planar_length_in)} · Vertical transitions: {preview.prefix.vertical_transition_count}</div>
        <div className="manual-actions"><button disabled={!e.draft?.ids.length || e.busy} onClick={e.undo}>Undo last choice</button><button disabled={e.busy} onClick={e.clearDraft}>Start over</button><button disabled={!e.active?.route || e.busy} onClick={e.useCurrent}>Use current route</button></div>
        {!preview.complete && <>
          <button className="manual-fill" disabled={!preview.suggestion || e.busy} onClick={() => preview.suggestion && e.append(preview.suggestion.load_ids)}>Fill remainder with A*</button>
          <p className="routing-notice">{preview.suggestion ? `Suggested remainder: ${formatInches(preview.suggestion.planar_length_in)} · ${preview.suggestion.vertical_transition_count} tier changes` : "No valid remainder is available. Undo or choose another path; a tier change needs an explicit opening."}</p>
          <div className="manual-next-choices" aria-label="Valid next paths">{preview.next_chains.map(chain => <button key={chain.id} disabled={e.busy} onClick={() => e.append(chain.load_ids)}>{chain.label} → {pointLabel(chain.points.at(-1)!)}<small>{formatInches(chain.planar_length_in)} · {chain.vertical_transition_count} tier changes</small></button>)}</div>
        </>}
        {samePairCount > 1 && <button disabled={!preview.complete || e.busy} onClick={e.copyToPair}>Copy completed path to {samePairCount} selected types on this rack pair</button>}
      </>}
      <label>Batch notes<textarea aria-label="Manual route batch notes" maxLength={2000} value={e.notes} disabled={e.busy} onChange={event => e.setNotes(event.target.value)} placeholder="Pattern, inventory constraint, or reason for this route" /></label>
      <p className="manual-complete-count">{e.completed} / {e.groups.length} selected group routes complete</p>
      <div className="manual-actions"><button className="manual-save" disabled={!e.canSave} onClick={() => void e.save()}>Save manual batch</button><button disabled={e.busy} onClick={e.cancel}>Cancel editing</button></div>
    </>
    {e.busy && <p role="status">Saving batch…</p>}
    {e.error && <div className="routing-error" role="alert">{e.error}<button disabled={e.busy} onClick={e.reload}>Reload cable review</button></div>}
    {e.message && <p className="manual-feedback" role="status">{e.message}</p>}
  </section>;
}

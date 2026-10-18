import type { CableReview, ReviewGroup } from "./types";
import type { RoutingCableTableRequest } from "./routingCableDetails";
import type { ManualRouteEditor } from "./useManualRouteEditor";
import { RackPairRouteCards } from "./RackPairRouteCards";
import { ManualRouteBatchPanel } from "./ManualRouteBatchPanel";

export function CableReviewPanel({review, groups, onViewCables, focusedPairKey = null, onFocusPair = () => {}, editor, canManage = false}: {
  review: CableReview; groups: ReviewGroup[]; onViewCables: (request: RoutingCableTableRequest) => void;
  focusedPairKey?: string | null; onFocusPair?: (key: string | null) => void; editor?: ManualRouteEditor; canManage?: boolean;
}) {
  return <section className="cable-review-panel" aria-label="Actual cable routing review">
    <h3>Actual cable review</h3><p className="routing-notice">Tier-aware routes · {review.manual_group_count ?? 0} manual groups. Defaults are suggestions; manual assignments take precedence. Sectional packing remains unassigned.</p>
    {editor?.editing ? <ManualRouteBatchPanel editor={editor} canManage={canManage} /> : <>
      <RackPairRouteCards review={{...review,groups:review.groups ?? groups}} groups={groups} focusedKey={focusedPairKey} onFocus={onFocusPair} editor={editor} canManage={canManage} onViewCables={onViewCables} />
      {editor?.busy && <p role="status">Saving batch…</p>}
      {editor?.error && <div className="routing-error" role="alert">{editor.error}<button disabled={editor.busy} onClick={editor.reload}>Reload cable review</button></div>}
      {editor?.message && <p className="manual-feedback" role="status">{editor.message}</p>}
      {editor?.groups.some(g=>g.route_source === "MANUAL") && <details className="route-default-reset"><summary>Restore default suggestions</summary><p className="routing-notice">Explicitly remove the selected manual assignments.</p><button disabled={editor.busy} onClick={()=>void editor.reset()}>Reset selected manual routes to defaults</button></details>}
    </>}
  </section>;
}

import { useMemo } from "react";
import type { CableReview, ReviewGroup } from "./types";
import type { RoutingCableTableRequest } from "./routingCableDetails";
import type { ManualRouteEditor } from "./useManualRouteEditor";
import { RackPairRouteCards } from "./RackPairRouteCards";
import { ManualRouteBatchPanel } from "./ManualRouteBatchPanel";
import { filterSummaryGroups, SUMMARY_FILTER_LABELS, type RoutingSummaryFilter, type CableTypeFilter } from "./routingSummaryFilter";
import { CABLE_STYLES } from "./RouteStroke";

export function CableReviewPanel({review, groups, onViewCables, focusedPairKey = null, onFocusPair = () => {}, editor, canManage = false, summaryFilter = null, onClearSummaryFilter, cableTypeFilter = null, onClearCableTypeFilter}: {
  review: CableReview; groups: ReviewGroup[]; onViewCables: (request: RoutingCableTableRequest) => void;
  focusedPairKey?: string | null; onFocusPair?: (key: string | null) => void; editor?: ManualRouteEditor; canManage?: boolean;
  summaryFilter?: RoutingSummaryFilter | null; onClearSummaryFilter?: () => void;
  cableTypeFilter?: CableTypeFilter | null; onClearCableTypeFilter?: () => void;
}) {
  const eligible = useMemo(()=>filterSummaryGroups(review.groups ?? groups, summaryFilter,cableTypeFilter), [review.groups,groups,summaryFilter,cableTypeFilter]);
  const scoped = useMemo(()=>filterSummaryGroups(groups, summaryFilter,cableTypeFilter), [groups,summaryFilter,cableTypeFilter]);
  const filteredCount = eligible.reduce((sum,group)=>sum+group.count,0);
  return <section className="cable-review-panel" aria-label="Actual cable routing review">
    <h3>Actual cable review</h3><p className="routing-notice">Tier-aware routes · {review.manual_group_count ?? 0} manual groups. Defaults are suggestions; manual assignments take precedence. Sectional packing remains unassigned.</p>
    {(summaryFilter || cableTypeFilter) && <div className="routing-summary-filter" role="status"><b>{[summaryFilter && SUMMARY_FILTER_LABELS[summaryFilter],cableTypeFilter && (cableTypeFilter==="OTHER" ? "Other types" : CABLE_STYLES[cableTypeFilter].label)].filter(Boolean).join(" · ")}</b><span>{filteredCount.toLocaleString()} mapped cables · {eligible.length.toLocaleString()} rack-pair/type groups</span>
      {summaryFilter==="UNROUTED" && <span>No assigned path to highlight. Other cables are greyed out.{!cableTypeFilter && Boolean(review.unmapped_cable_count) && ` Another ${review.unmapped_cable_count!.toLocaleString()} cables are included in the total but have unmapped endpoints; they cannot be placed on this map.`}</span>}
      {summaryFilter && <button disabled={editor?.editing || editor?.busy} onClick={onClearSummaryFilter}>Clear filter</button>}
      {cableTypeFilter && <button disabled={editor?.editing || editor?.busy} onClick={onClearCableTypeFilter}>Show all cable types</button>}</div>}
    {editor?.editing ? <ManualRouteBatchPanel editor={editor} canManage={canManage} /> : <>
      <RackPairRouteCards review={{...review,groups:eligible}} groups={scoped} summaryFiltered={Boolean(summaryFilter || cableTypeFilter)} focusedKey={focusedPairKey} onFocus={onFocusPair} editor={editor} canManage={canManage} onViewCables={onViewCables} />
      {editor?.busy && <p role="status">Saving batch…</p>}
      {editor?.error && <div className="routing-error" role="alert">{editor.error}<button disabled={editor.busy} onClick={editor.reload}>Reload cable review</button></div>}
      {editor?.message && <p className="manual-feedback" role="status">{editor.message}</p>}
      {editor?.groups.some(g=>g.route_source === "MANUAL") && <details className="route-default-reset"><summary>Restore default suggestions</summary><p className="routing-notice">Explicitly remove the selected manual assignments.</p><button disabled={editor.busy} onClick={()=>void editor.reset()}>Reset selected manual routes to defaults</button></details>}
    </>}
  </section>;
}

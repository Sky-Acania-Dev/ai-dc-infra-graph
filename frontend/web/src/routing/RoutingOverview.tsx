import { useMemo } from "react";
import { CABLE_STYLES, EMPTY_ROUTE_COLOR, UNUSABLE_ROUTE_COLOR } from "./RouteStroke";
import type { CableClass, CableReview } from "./types";
import { SUMMARY_FILTER_LABELS, type RoutingSummaryFilter } from "./routingSummaryFilter";

export function routingOverviewCounts(review: CableReview) {
  const colors = Object.fromEntries(Object.keys(CABLE_STYLES).map(key => [key,0])) as Record<CableClass,number>;
  let other=0, defaultRoutes=0, defaultCables=0, manualRoutes=0, manualCables=0, invalidManualRoutes=0;
  for (const [type,count] of Object.entries(review.cable_types)) {
    const value=type.toUpperCase();
    if (value.startsWith("CAT6")) colors.CAT6+=count;
    else if (value==="LC" || value.startsWith("LC-")) colors.LC+=count;
    else if (value.startsWith("MPO") || value.startsWith("MTP")) colors.MPO+=count;
    else other+=count;
  }
  for (const group of review.groups) {
    // Special route colors are disjoint subsets of their inventory cable families.
    const base=group.cable_class==="CROSS_SECTION_LC" ? "LC" : group.cable_class==="CROSS_SECTION_CAT6" ? "CAT6" : group.cable_class==="MPO_TRUNK_T2_T1_RO" ? "MPO" : null;
    if (base && group.cable_class) {colors[base]-=group.count; colors[group.cable_class]+=group.count;}
    if (group.route_source==="MANUAL") {
      manualRoutes++; manualCables+=group.count;
      if (!group.route) invalidManualRoutes++;
    } else if (group.route) {defaultRoutes++; defaultCables+=group.count;}
  }
  return {colors,other,defaultRoutes,defaultCables,manualRoutes,manualCables,invalidManualRoutes};
}

export function RoutingOverview({review,stale=false,savedAt=null,filter=null,onFilterChange,disabled=false}: {
  review:CableReview;stale?:boolean;savedAt?:number|null;filter?:RoutingSummaryFilter|null;
  onFilterChange?:(filter:RoutingSummaryFilter|null)=>void;disabled?:boolean;
}) {
  const totals=useMemo(()=>routingOverviewCounts(review),[review]);
  const number=(value:number)=>value.toLocaleString();
  return <section className="routing-overview" aria-label="Routing cable summary">
    <div className="routing-overview-heading"><h3>Cable summary</h3><b>{number(review.inventory_cable_count)}</b></div>
    <div className="routing-overview-stats">
      {(Object.keys(SUMMARY_FILTER_LABELS) as RoutingSummaryFilter[]).map(key=><button key={key} type="button" className="routing-overview-stat"
        aria-pressed={filter===key} disabled={disabled} onClick={()=>onFilterChange?.(filter===key ? null : key)}>
        <span>{SUMMARY_FILTER_LABELS[key]}</span>
        <strong>{number(key==="ROUTED" ? review.routed_cable_count : key==="UNROUTED" ? review.unrouted_cable_count : key==="DEFAULT" ? totals.defaultRoutes : totals.manualRoutes)}</strong>
        <small>{key==="ROUTED" ? "Inter-rack cables" : key==="UNROUTED" ? "Including unmapped endpoints" : `Groups · ${number(key==="DEFAULT" ? totals.defaultCables : totals.manualCables)} cables${key==="MANUAL" && totals.invalidManualRoutes ? ` · ${number(totals.invalidManualRoutes)} invalid` : ""}`}</small>
      </button>)}
    </div>
    {filter && <div className="routing-summary-filter" role="status"><b>{SUMMARY_FILTER_LABELS[filter]} selected</b><button type="button" disabled={disabled} onClick={()=>onFilterChange?.(null)}>Clear filter</button></div>}
    <div className="routing-overview-local"><span>Cabinet-local cables</span><b>{number(review.same_cabinet_count)}</b></div>
    <section className="routing-cable-key" aria-label="Cable counts by route color">
      <h4>Cable types</h4>
      <ul>{Object.entries(CABLE_STYLES).map(([key,style])=><li key={key}><span><i style={{background:style.color}} aria-hidden="true" />{style.label}</span><b>{number(totals.colors[key as CableClass])}</b></li>)}
        {totals.other>0 && <li><span><i style={{background:EMPTY_ROUTE_COLOR}} aria-hidden="true" />Other types</span><b>{number(totals.other)}</b></li>}
      </ul>
      <small>All inventory cables · cross-section and trunk counts shown separately.</small>
      <div className="routing-pathway-key"><span><i style={{borderColor:EMPTY_ROUTE_COLOR}} />Empty / unassigned</span><span><i style={{borderColor:UNUSABLE_ROUTE_COLOR}} />Unusable</span></div>
    </section>
    <details className="routing-overview-description">
      <summary>Description</summary>
      <div>
        <p>{review.label} · {number(review.groups.length)} rack-pair/type groups{review.build_ms!=null ? ` · server ${(review.build_ms/1000).toFixed(1)}s` : ""}.</p>
        {stale && <p>Saved overview{savedAt ? ` from ${new Date(savedAt).toLocaleString()}` : ""}. Viewing is available; route editing waits for current server data.</p>}
        <p>Default routes are suggestions. Manual routes are saved assignments, and A* never replaces them. Route counts refer to rack-pair/type groups, not individual cables.</p>
        <p>{review.notes}</p>
        {review.unmapped_cable_count!=null && <p>Unmapped endpoints: {number(review.unmapped_cable_count)} cables.</p>}
        {Object.entries(review.unrouted_reasons ?? {}).map(([reason,count])=><p key={reason}>{number(count)} · {reason}</p>)}
        <p>Rows/CENTRAL: 8′2″ / 9′2″ / 10′2″ AFF. NORTH/SOUTH: 8′2″ / 9′8″ AFF. Row Tier 3 uses the row-end opening to outer passage Tier 2. Sectional packing remains unassigned.</p>
      </div>
    </details>
  </section>;
}

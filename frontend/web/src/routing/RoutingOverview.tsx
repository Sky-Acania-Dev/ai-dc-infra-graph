import { useMemo } from "react";
import { CABLE_STYLES, EMPTY_ROUTE_COLOR, UNUSABLE_ROUTE_COLOR } from "./RouteStroke";
import type { CableClass, CableReview } from "./types";

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

export function RoutingOverview({review,stale=false,savedAt=null}: {review:CableReview;stale?:boolean;savedAt?:number|null}) {
  const totals=useMemo(()=>routingOverviewCounts(review),[review]);
  const number=(value:number)=>value.toLocaleString();
  return <section className="routing-overview" aria-label="Routing cable summary">
    <div className="routing-overview-heading"><h3>Cable summary</h3><b>{number(review.inventory_cable_count)}</b></div>
    <div className="routing-overview-stats">
      <div className="routing-overview-stat"><span>Routed cables</span><strong>{number(review.routed_cable_count)}</strong><small>Inter-rack cables</small></div>
      <div className="routing-overview-stat"><span>Unrouted cables</span><strong>{number(review.unrouted_cable_count)}</strong><small>Including unmapped endpoints</small></div>
      <div className="routing-overview-stat"><span>Default routes</span><strong>{number(totals.defaultRoutes)}</strong><small>Groups · {number(totals.defaultCables)} cables</small></div>
      <div className="routing-overview-stat"><span>Manual routes</span><strong>{number(totals.manualRoutes)}</strong><small>Groups · {number(totals.manualCables)} cables{totals.invalidManualRoutes ? ` · ${number(totals.invalidManualRoutes)} invalid` : ""}</small></div>
    </div>
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

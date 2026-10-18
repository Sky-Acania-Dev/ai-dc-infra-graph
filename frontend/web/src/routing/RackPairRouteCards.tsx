import { ConnectionCard } from "../components/ConnectionCard";
import { useMemo, useState } from "react";
import { groupRouteSummary, rackPairCards, reviewPairKey, routeActionLabel } from "./rackPairRoutes";
import type { CableReview, ReviewGroup } from "./types";
import type { ManualRouteEditor } from "./useManualRouteEditor";
import type { RoutingCableTableRequest } from "./routingCableDetails";

export function RackPairRouteCards({review, groups, focusedKey, onFocus, editor, canManage, onViewCables}: {
  review: CableReview; groups: ReviewGroup[]; focusedKey: string | null; onFocus: (key: string | null) => void;
  editor?: ManualRouteEditor; canManage: boolean; onViewCables: (request: RoutingCableTableRequest) => void;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const pairs = useMemo(()=>rackPairCards(groups, review.groups, focusedKey), [groups, review.groups, focusedKey]);
  const filtered = useMemo(()=>pairs.filter(pair=>pair.key === focusedKey || search.toLowerCase().trim().split(/\s+/).every(term=>`${pair.label} ${pair.groups.map(g=>g.cable_type).join(" ")}`.toLowerCase().includes(term))), [pairs, search, focusedKey]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / 40)), currentPage = Math.min(page, pageCount - 1);
  const shown = filtered.slice(currentPage * 40, (currentPage + 1) * 40);
  const selected = editor?.groups ?? [];
  const pairCount = new Set(selected.map(reviewPairKey)).size;
  return <section className="rack-pair-route-cards" aria-label="Rack-pair routes">
    <p className="routing-notice">Click a rack pair to focus its routes. Select cable types on the card to set or change their route.</p>
    <label className="route-pair-search">Find rack pair or cable type<input aria-label="Find rack pair or cable type" type="search" placeholder="801 811, LC, CAT6…" value={search} onChange={event=>{setSearch(event.target.value); setPage(0);}} /></label>
    <div className="route-pair-pagination"><span>{filtered.length.toLocaleString()} rack pairs · page {currentPage + 1} / {pageCount}</span><button aria-label="Previous rack pairs" disabled={!currentPage} onClick={()=>setPage(currentPage-1)}>Previous</button><button aria-label="Next rack pairs" disabled={currentPage + 1 >= pageCount} onClick={()=>setPage(currentPage+1)}>Next</button></div>
    {focusedKey && <button className="route-clear-focus" onClick={()=>onFocus(null)}>Show all routes</button>}
    {canManage && pairCount > 1 && <div className="route-selection-bar"><b>{selected.length} types across {pairCount} rack pairs</b>
      <button disabled={editor?.busy} onClick={()=>editor?.begin()}>{routeActionLabel(selected)} for all selected types</button>
      <button disabled={editor?.busy} onClick={editor?.clearSelected}>Clear selection</button></div>}
    {shown.length > 0 && <div className="connection-list segment-connection-list">{shown.map(pair=>{
      const focused = pair.key === focusedKey;
      const chosen = pair.groups.filter(g=>editor?.selected.includes(g.uid));
      const controls = canManage && editor && (focused || chosen.length > 0);
      const byType = new Map(pair.groups.map(g=>[g.cable_type,g]));
      return <ConnectionCard key={pair.key} className={`route-pair-card ${focused ? "is-focused" : ""} ${chosen.length ? "has-selected-types" : ""}`}
        title={pair.label} metric={<span>{pair.groups.reduce((n,g)=>n+g.count,0).toLocaleString()} cable{pair.groups.reduce((n,g)=>n+g.count,0) === 1 ? "" : "s"}</span>}
        subtitle={focused ? "Focused routes · all cable types for this rack pair" : "All cable types for this rack pair"}
        onSelect={()=>{onFocus(focused ? null : pair.key); setPage(0);}} selected={focused} selectLabel={`Focus rack pair ${pair.label}`}
        cableTypeCounts={Object.fromEntries(pair.groups.map(g=>[g.cable_type,g.count]))}
        cableTypeControl={controls ? type=>{const g=byType.get(type)!; return <input type="checkbox" className="route-type-toggle" aria-label={`Select ${type} route · ${pair.label}`} checked={editor.selected.includes(g.uid)} disabled={editor.busy}
          onChange={()=>{onFocus(pair.key); editor.toggle(g.uid);}} />;} : undefined}
        cableTypeLabel={type=><>{type}<small className={byType.get(type)!.manual_status === "INVALID" ? "routing-error" : ""}>{groupRouteSummary(byType.get(type)!)}</small>{byType.get(type)!.reason && <small className="routing-error">{byType.get(type)!.reason}</small>}{byType.get(type)!.occupation_hint && <small>Outer passage: INNER placement intent · footprint unassigned</small>}</>}
        onViewCableType={type=>{
          const group=byType.get(type)!, ids=new Set(group.cable_uids);
          onViewCables({source:group.source_cabinet_id,target:group.destination_cabinet_id,cableType:type,inventoryCables:review.cables.filter(c=>ids.has(c.uid)),fixtureCables:[], groupUid: group.uid,
            wholePair: review.scope === "hall" ? [group.source_cabinet_uid, group.destination_cabinet_uid] : undefined});
        }}
        actions={canManage && chosen.length > 0 && editor && <div className="route-card-actions"><span>{chosen.length} type{chosen.length === 1 ? "" : "s"} selected</span>
          <button className="route-card-edit" disabled={editor.busy} aria-label={`${routeActionLabel(chosen)} · ${pair.label}`} onClick={()=>editor.begin(chosen.map(g=>g.uid))}>{routeActionLabel(chosen)}</button>
          <button className="route-card-clear" disabled={editor.busy} aria-label={`Clear selected types · ${pair.label}`} onClick={()=>chosen.forEach(g=>editor.toggle(g.uid))}>Clear</button>
        </div>} />;
    })}</div>}
    {!shown.length && <p>No matching actual cable groups.</p>}
  </section>;
}

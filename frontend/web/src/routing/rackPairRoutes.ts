import { formatInches } from "./dimensions.ts";
import type { ReviewGroup } from "./types";
import { filterSummaryGroups, type RoutingSummaryFilter, type CableTypeFilter } from "./routingSummaryFilter.ts";

export function reviewPairKey(group: ReviewGroup) {
  return JSON.stringify([group.source_cabinet_uid ?? group.source_cabinet_id, group.destination_cabinet_uid ?? group.destination_cabinet_id].sort());
}
export function rackPairCards(scope: ReviewGroup[], all: ReviewGroup[], focusedKey: string | null) {
  const keys = new Set(scope.map(reviewPairKey));
  if (focusedKey) keys.add(focusedKey);
  const pairs = new Map<string, {key: string; label: string; groups: ReviewGroup[]}>();
  for (const group of all) {
    const key = reviewPairKey(group);
    if (!keys.has(key)) continue;
    if (!pairs.has(key)) pairs.set(key, {key, label: [group.source_cabinet_id, group.destination_cabinet_id].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).join(" ↔ "), groups: []});
    pairs.get(key)!.groups.push(group);
  }
  return [...pairs.values()].sort((a,b)=>Number(b.key === focusedKey)-Number(a.key === focusedKey) || a.label.localeCompare(b.label,undefined,{numeric:true}));
}
export function focusedRouteGroups(all: ReviewGroup[], groupUid: string | null, pairKey: string | null, cabinetUids?: ReadonlySet<string>, selectionGroupUids?: ReadonlySet<string> | null, summaryFilter: RoutingSummaryFilter | null = null, cableType: CableTypeFilter | null = null) {
  const groups = filterSummaryGroups(all, summaryFilter, cableType);
  return groupUid ? groups.filter(g=>g.uid === groupUid) : pairKey ? groups.filter(g=>reviewPairKey(g) === pairKey)
    : cabinetUids?.size ? groups.filter(g=>cabinetUids.has(g.source_cabinet_uid) || cabinetUids.has(g.destination_cabinet_uid))
    : selectionGroupUids != null ? groups.filter(g=>selectionGroupUids.has(g.uid)) : summaryFilter || cableType ? groups : [];
}
export function routeActionLabel(groups: ReviewGroup[]) {
  return groups.some(g=>g.route_source === "MANUAL") ? "Change route" : "Set route";
}
export function groupRouteSummary(group: ReviewGroup) {
  const source = group.route_source === "MANUAL" ? `Manual r${group.manual_revision}${group.manual_status === "INVALID" ? " · INVALID" : ""}` : group.route ? "Suggested" : "Unrouted";
  return `${source} · Tier ${group.start_tier ?? 1} → Tier ${group.end_tier ?? 1}${group.route ? ` · ${formatInches(group.route.planar_length_in)}` : ""}`;
}

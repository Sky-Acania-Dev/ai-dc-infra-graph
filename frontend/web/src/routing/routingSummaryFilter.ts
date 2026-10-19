import type { CableClass, ReviewGroup } from "./types";

export const SUMMARY_FILTER_LABELS = {
  ROUTED: "Routed cables",
  UNROUTED: "Unrouted cables",
  DEFAULT: "Default routes",
  MANUAL: "Manual routes",
} as const;
export type RoutingSummaryFilter = keyof typeof SUMMARY_FILTER_LABELS;
export type CableTypeFilter = CableClass | "OTHER";

export function filterSummaryGroups(groups: ReviewGroup[], filter: RoutingSummaryFilter | null, cableType: CableTypeFilter | null = null) {
  if (!filter && !cableType) return groups;
  return groups.filter(group => {
    if (cableType && (cableType === "OTHER" ? Boolean(group.cable_class) : group.cable_class !== cableType)) return false;
    if (!filter) return true;
    if (filter === "ROUTED") return Boolean(group.route);
    if (filter === "UNROUTED") return !group.route;
    // Saved manual assignments remain inspectable even if their chain is invalid.
    if (filter === "MANUAL") return group.route_source === "MANUAL";
    return group.route_source !== "MANUAL" && Boolean(group.route);
  });
}

import type { ResolvedLayout, ReviewGroup } from "./types";

export type RoutingSectionGroupCounts = {
  project: string;
  building: string;
  counts: ReadonlyMap<string, number>;
};

/** Count a group once per endpoint section, independently of its cable/edge count. */
export function sectionGroupCounts(data: ResolvedLayout, groups: ReviewGroup[]) {
  const counts = new Map<string,number>(data.geometry.sections.flatMap(section => section.data_hall_id ? [[section.data_hall_id, 0] as const] : []));
  const cabinets = new Map(data.cabinets.map(cabinet => [cabinet.cabinet_uid, cabinet.data_hall_id]));
  const seen = new Set<string>();
  for (const group of groups) {
    if (seen.has(group.uid)) continue;
    seen.add(group.uid);
    const halls = new Set([cabinets.get(group.source_cabinet_uid), cabinets.get(group.destination_cabinet_uid)]);
    for (const hall of halls) if (hall && counts.has(hall)) counts.set(hall, counts.get(hall)! + 1);
  }
  return counts;
}

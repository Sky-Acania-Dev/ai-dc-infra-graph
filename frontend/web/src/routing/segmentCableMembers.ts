import type { InventoryCable, PlacementCables } from "./types";

export function collectPlacementCables(results: PlacementCables[]) {
  const cables = new Map<string, InventoryCable>();
  const members: Record<string, string[]> = {};
  for (const result of results) {
    members[result.placement_uid] = result.cables.map(c => c.uid);
    for (const cable of result.cables) cables.set(cable.uid, cable);
  }
  return {cables: [...cables.values()].sort((a, b) => a.uid.localeCompare(b.uid)), members};
}

export function filterCableMembers<T extends {id: string}>(cables: T[], placementUid: string | null, members: Record<string, string[]>, fixtureIds?: string[]) {
  if (!placementUid) return cables;
  const ids = new Set(fixtureIds ?? members[placementUid] ?? []);
  return cables.filter(c => ids.has(c.id));
}

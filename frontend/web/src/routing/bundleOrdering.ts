import type { BundleContents, OrderUnit, OrderDraft } from "./bundleOrderTypes";

export function defaultRackBasis(units:OrderUnit[],preferred:"source"|"destination"="source") {
  const distinct=(key:"source_rack_position"|"destination_rack_position")=>new Set(units.map(u=>u[key]).filter(n=>n!=null)).size;
  const source=distinct("source_rack_position"),destination=distinct("destination_rack_position");
  return source<=1&&destination>1?"destination":destination<=1&&source>1?"source":preferred;
}

export function rackOrderDirection(units:OrderUnit[],basis:"source"|"destination"):"ASC"|"DESC"|"CUSTOM" {
  const key=basis==="source"?"source_rack_position":"destination_rack_position";
  const values=[...units].sort((a,b)=>a.layer-b.layer||a.position-b.position).map(u=>u[key]).filter((n):n is number=>n!=null);
  const ascending=values.every((n,i)=>i===0||n>=values[i-1]),descending=values.every((n,i)=>i===0||n<=values[i-1]);
  return ascending?"ASC":descending?"DESC":"CUSTOM";
}

export function orderProblem(units: OrderUnit[], columns: number, rows: number): string | null {
  if (![columns, rows].every(n => Number.isInteger(n) && n >= 1 && n <= 64)) return "Grid dimensions must be integers from 1 to 64.";
  const cells = new Set<string>(), ids = new Set<string>(), cables = new Set<string>();
  for (const u of units) {
    if (![u.layer, u.position, u.slot_width, u.slot_height].every(n => Number.isInteger(n) && n >= 1) || u.position + u.slot_width - 1 > columns || u.layer + u.slot_height - 1 > rows) return "A unit is outside the grid.";
    if (ids.has(u.unit_uid)) return "An atomic unit occurs more than once.";
    ids.add(u.unit_uid);
    if (u.kind === "CABLE_LIST") {
      if (!u.cable_uids?.length) return "A cable-list unit needs at least one actual cable ID.";
      for (const uid of u.cable_uids) { if (cables.has(uid)) return "A cable ID occurs more than once."; cables.add(uid); }
    }
    for (let y = u.layer; y < u.layer + u.slot_height; y++) for (let x = u.position; x < u.position + u.slot_width; x++) {
      const cell = `${x}:${y}`; if (cells.has(cell)) return "Unit footprints overlap. Move or swap the selected units."; cells.add(cell);
    }
  }
  return null;
}

export function rackOrderedUnits(units: OrderUnit[], basis: "source" | "destination", descending: boolean, columns: number, rows: number): OrderUnit[] {
  const key = basis === "source" ? "source_rack_position" : "destination_rack_position";
  const sorted = [...units].sort((a,b) => {
    const x=a[key],y=b[key];
    if (x == null || y == null) return x == null ? y == null ? a.unit_uid.localeCompare(b.unit_uid) : 1 : -1;
    return (descending ? -1 : 1)*(x-y) || a.unit_uid.localeCompare(b.unit_uid);
  });
  const occupied = new Set<string>();
  return sorted.map(unit => {
    for (let layer=1;layer<=rows-unit.slot_height+1;layer++) for(let position=1;position<=columns-unit.slot_width+1;position++) {
      const cells:string[]=[];
      for(let y=layer;y<layer+unit.slot_height;y++) for(let x=position;x<position+unit.slot_width;x++) cells.push(`${x}:${y}`);
      if(cells.every(c=>!occupied.has(c))) {cells.forEach(c=>occupied.add(c));return {...unit,layer,position};}
    }
    throw new Error("The ordered footprints do not fit this grid. Enlarge it or reduce footprints first.");
  });
}

export function unitSelector(u:OrderUnit) {
  return Object.fromEntries(["kind","cable_uids","source_cabinet_uid","destination_cabinet_uid","cable_type","layer","position","slot_width","slot_height","label"].filter(k=>k in u).map(k=>[k,u[k as keyof OrderUnit]]));
}

export function orderDraft(value: BundleContents, units=value.units, columns=value.grid_columns, rows=value.grid_rows): OrderDraft {
  return {expected_version:value.version,grid_columns:columns,grid_rows:rows,notes:value.notes,
    units:units.map(unitSelector)};
}

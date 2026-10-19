export type DataHallBadgeCounts = { count: number; added: number; removed: number };

export function DataHallSectionTabs({dataHall,dataHalls,label,connectedDataHallCounts,dataHallBadges,routingGroupCounts=null,onDataHallChange}: {
  dataHall:string;dataHalls:string[];label:string;connectedDataHallCounts:ReadonlyMap<string,number>;
  dataHallBadges?:ReadonlyMap<string,DataHallBadgeCounts>;routingGroupCounts?:ReadonlyMap<string,number>|null;
  onDataHallChange:(hall:string)=>void;
}) {
  return <div className="map-size-control" role="tablist" aria-label={label}>
    {dataHalls.map(hall=>{
      const routeCount=routingGroupCounts?.get(hall);
      const badgeCounts=routingGroupCounts ? undefined : dataHallBadges?.get(hall);
      const neighborCount=hall===dataHall ? 0 : connectedDataHallCounts.get(hall) ?? 0;
      const badgeLabel=routingGroupCounts ? String(routeCount ?? 0) : dataHallBadgeLabel(badgeCounts) ?? (neighborCount>0 ? String(neighborCount) : null);
      const hasBadge=routingGroupCounts ? (routeCount ?? 0)>0 : Boolean(badgeLabel);
      const title=routingGroupCounts ? `${routeCount ?? 0} filtered cable groups with a cabinet in ${hall}` : undefined;
      return <button key={hall} type="button" role="tab" aria-selected={hall===dataHall} title={title}
        className={`${hall===dataHall ? "is-active" : ""} ${routingGroupCounts ? "has-route-count" : ""} ${hasBadge ? "has-graph-neighbor" : ""} ${(badgeCounts?.added ?? 0)>0 ? "has-positive-delta" : ""} ${(badgeCounts?.removed ?? 0)>0 ? "has-negative-delta" : ""}`}
        onClick={()=>onDataHallChange(hall)}>
        <span>{hall}</span>{badgeLabel!==null && <b className="data-hall-graph-count" aria-label={routingGroupCounts ? `${routeCount ?? 0} filtered cable groups` : undefined}>{badgeLabel}</b>}
      </button>;
    })}
  </div>;
}

function dataHallBadgeLabel(counts:DataHallBadgeCounts|undefined) {
  if (!counts) return null;
  const parts:string[]=[];
  if (counts.count>0) parts.push(String(counts.count));
  if (counts.added>0) parts.push(`+${counts.added}`);
  if (counts.removed>0) parts.push(`-${counts.removed}`);
  return parts.length ? parts.join("") : null;
}

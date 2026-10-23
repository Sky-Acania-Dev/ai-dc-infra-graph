import { CABLE_STYLES } from "./RouteStroke";
import type { CardinalDirection, JunctionMovement, JunctionPreview } from "./types";

export function movementOrder(preview:JunctionPreview,below=false) {
  const map=new Map(preview.movements.map(m=>[m.uid,m]));
  const order=[...preview.movements].sort((a,b)=>(a.from_port?.occupation.offset_up_in??0)-(b.from_port?.occupation.offset_up_in??0)||a.uid.localeCompare(b.uid));
  const visited=new Set<string>(),result:JunctionMovement[]=[];
  function visit(m:JunctionMovement) {if(visited.has(m.uid))return;visited.add(m.uid);for(const c of preview.crossing_orders??[])if(c.above_connection_uid===m.uid){const lower=map.get(c.below_connection_uid);if(lower)visit(lower);}result.push(m);}
  order.forEach(visit);return below?result.reverse():result;
}

export function JunctionPlan({preview,selectedUid,onSelect,below,selectedUnitUid}:{preview:JunctionPreview;selectedUid:string|null;onSelect:(uid:string)=>void;below:boolean;selectedUnitUid?:string|null}) {
  const {bounds:b}=preview.area,pad=14,w=b.east_in-b.west_in+pad*2,h=b.south_in-b.north_in+pad*2;
  const color=(m:JunctionMovement)=>m.cable_class?CABLE_STYLES[m.cable_class].color:"#64748b";
  const x0=b.west_in-pad,y0=b.north_in-pad;
  const relevant=(m:JunctionMovement)=>selectedUnitUid?[m.from_port?.unit_uid,m.to_port?.unit_uid].includes(selectedUnitUid):!selectedUid||selectedUid===m.uid;
  return <svg className="junction-plan-svg" viewBox={`${x0} ${y0} ${w} ${h}`} role="img" aria-label="Junction top-down cable bundle plan">
    <g transform={below?`translate(${b.west_in+b.east_in} 0) scale(-1 1)`:undefined}>
      <g className="junction-tray-fill">
        {preview.area.display_tray_rectangles?.map((r,i)=><rect key={i} x={r.x_in} y={r.y_in} width={r.width_in} height={r.height_in}/>)}
      </g>
      <rect x={b.west_in} y={b.north_in} width={b.east_in-b.west_in} height={b.south_in-b.north_in} fill="none" stroke="#8290a2" strokeWidth={1} strokeDasharray="3 3" vectorEffect="non-scaling-stroke"/>
      {movementOrder(preview,below).map(m=>m.path&&<g key={m.uid} className="junction-movement" role="button" tabIndex={0} aria-label={`Select junction bundle ${m.label}`} opacity={relevant(m)?1:.16} onClick={e=>{e.stopPropagation();onSelect(m.uid);}} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(m.uid);}}}>
        <title>{`${m.label}${m.route_source?` · ${m.route_source} route`:""}`}</title>
        <path d={m.display_path??m.path} fill="none" stroke="#e8edf2" strokeWidth={(m.from_port?.occupation.occupied_width_in??1)+.5}/>
        <path d={m.display_path??m.path} fill="none" stroke={color(m)} strokeWidth={m.from_port?.occupation.occupied_width_in??1} strokeOpacity={.7}/>
        <path d={m.display_path??m.path} fill="none" stroke={color(m)} strokeWidth={1.2} vectorEffect="non-scaling-stroke"/>
        <path d={m.display_path??m.path} fill="none" stroke="transparent" strokeWidth={Math.max(2,m.from_port?.occupation.occupied_width_in??1)}/>
      </g>)}
      {preview.statistics.points.filter(p=>(!selectedUid&&!selectedUnitUid)||p.movement_uids.some(uid=>preview.movements.some(m=>m.uid===uid&&relevant(m)))).map((p,i)=><circle key={i} cx={p.x_in} cy={p.y_in} r={.45} fill="#111827" pointerEvents="none"><title>{`Intersection · ${p.movement_uids.length} movements`}</title></circle>)}
    </g>
    <text x={(b.west_in+b.east_in)/2} y={y0+2} textAnchor="middle" className="junction-plan-label">NORTH ↑</text>
    <text x={x0+1} y={b.north_in-1} className="junction-plan-label">{below?"EAST":"WEST"}</text>
    <text x={x0+w-1} y={b.north_in-1} textAnchor="end" className="junction-plan-label">{below?"WEST":"EAST"}</text>
    <text x={(b.west_in+b.east_in)/2} y={y0+h-1} textAnchor="middle" className="junction-plan-label">SOUTH ↓</text>
  </svg>;
}

export function JunctionPortSections({preview,selectedUid,onSelect,mode,selectedUnitUid}:{preview:JunctionPreview;selectedUid:string|null;onSelect:(uid:string)=>void;mode:"PHYSICAL"|"GRID";selectedUnitUid?:string|null}) {
  const ports=[...new Map(preview.area.ports.map(p=>[p.direction,p])).values()];
  return <section className="junction-port-sections" aria-label="Connected segment sectional diagrams">
    <h4>Connected segment sections</h4>
    {ports.map(port=>{
      const items=preview.movements.flatMap(m=>[m.from_port,m.to_port].filter(p=>p?.direction===port.direction&&(p.placement_tier??m.tier)===preview.area.tier).map(p=>({m,p:p!})));
      const height=preview.area.usable_height_in??Math.max(8,...items.map(({p})=>(p.occupation.offset_up_in??0)+(p.occupation.occupied_height_in??0)));
      const columns=items[0]?.p.grid_columns??12,rows=items[0]?.p.grid_rows??8;
      const physical=mode==="PHYSICAL",width=physical?port.width_in:columns,hh=physical?height:rows;
      const scale=240/width,ys=90/hh;
      const sides:Record<CardinalDirection,[string,string]>={WEST:["North","South"],EAST:["South","North"],NORTH:["East","West"],SOUTH:["West","East"]};
      return <div className="junction-port-section" key={port.direction}>
        <b>{port.direction} · {port.label}</b>
        <small>{physical?`${port.width_in} in wide · ${items.some(({p})=>p.ordinal_projection)?"schematic cell projection; packing unverified":preview.area.usable_height_in==null?"illustrative height window":"configured clearance"}`:`${columns} × ${rows} ordinal grid; physical dimensions independent`}</small>
        <svg viewBox="0 0 286 124" role="img" aria-label={`${port.direction} connection section`}>
          <path d="M23 8 V98 H263 V8" fill="none" stroke="#64748b" strokeWidth={2}/>
          {!physical&&Array.from({length:columns-1},(_,i)=><line key={`x${i}`} x1={23+(i+1)*240/columns} x2={23+(i+1)*240/columns} y1={8} y2={98} stroke="#dce2e9"/>)}
          {!physical&&Array.from({length:rows-1},(_,i)=><line key={`y${i}`} x1={23} x2={263} y1={98-(i+1)*90/rows} y2={98-(i+1)*90/rows} stroke="#dce2e9"/>)}
          {items.map(({m,p},i)=>{
            const o=p.occupation;
            if(physical?o.offset_across_in==null:o.position==null)return null;
            let across=physical?o.offset_across_in!:o.position!-1;
            const bw=physical?o.occupied_width_in!:o.slot_width??1,bh=physical?o.occupied_height_in!:o.slot_height??1,up=physical?o.offset_up_in!:o.layer!-1;
            // Physical stored offsets start at INNER (or NORTH/WEST when undefined).
            const left=sides[port.direction][0].toUpperCase();
            const reference=p.inner_direction??(port.direction==="WEST"||port.direction==="EAST"?"NORTH":"WEST");
            if(reference!==left)across=width-across-bw;
            const c=m.cable_class?CABLE_STYLES[m.cable_class].color:"#64748b";
            return <g key={`${m.uid}:${i}`} className="junction-section-bundle" role="button" tabIndex={0} aria-label={`Select sectional bundle ${m.label}`} opacity={(selectedUnitUid?p.unit_uid===selectedUnitUid:!selectedUid||selectedUid===m.uid)?1:.2} onClick={()=>onSelect(m.uid)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(m.uid);}}}><title>{`${m.label} · ${bw} × ${bh} ${physical?"in":"cells"}`}</title><rect x={23+across*scale} y={98-(up+bh)*ys} width={bw*scale} height={bh*ys} fill={c}/>{bw*scale>17&&<text x={23+(across+bw/2)*scale} y={98-(up+bh/2)*ys+3} textAnchor="middle" fontSize={8} fill="#fff">{i+1}</text>}</g>;
          })}
          <text x={23} y={116} fontSize={10}>{sides[port.direction][0]}</text><text x={263} y={116} fontSize={10} textAnchor="end">{sides[port.direction][1]}</text>
        </svg>
      </div>;
    })}
  </section>;
}

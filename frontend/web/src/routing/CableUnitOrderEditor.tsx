import { useEffect, useState } from "react";
import { CABLE_STYLES } from "./RouteStroke";
import { orderDraft, orderProblem, rackOrderedUnits, rackOrderDirection } from "./bundleOrdering";
import type { BundleContents, OrderDraft, OrderUnit } from "./bundleOrderTypes";

type Props = { value: BundleContents; canManage: boolean; onDraft?: (draft:OrderDraft|null)=>void; onSave:(draft:OrderDraft)=>Promise<void>;
  onSelectGroup?:(uid:string|null)=>void; onSelectUnit?:(unit:OrderUnit|null)=>void; title?:string; basis?:"source"|"destination"; reversed?:boolean; sortCommand?:{basis:"source"|"destination";descending:boolean};onDirty?:(dirty:boolean)=>void;onReload?:()=>void;onReset?:()=>Promise<void>;mode?:"GRID"|"PHYSICAL" };

export function CableUnitOrderEditor({value,canManage,onDraft,onSave,onSelectGroup,onSelectUnit,title="Bundle-local order",basis="source",reversed=false,sortCommand,onDirty,onReload,onReset,mode="GRID"}:Props) {
  const [units,setUnits]=useState(value.units),[columns,setColumns]=useState(value.grid_columns),[rows,setRows]=useState(value.grid_rows);
  const [selected,setSelected]=useState<string|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [sortBasis,setSortBasis]=useState(basis),[swap,setSwap]=useState("");
  const [cableIds,setCableIds]=useState("");
  useEffect(()=>{setUnits(value.units);setColumns(value.grid_columns);setRows(value.grid_rows);setError("");setSelected(null);},[value.version]);
  useEffect(()=>{setSortBasis(basis);},[basis]);
  const problem=orderProblem(units,columns,rows),unit=units.find(u=>u.unit_uid===selected);
  const dirty=JSON.stringify(orderDraft(value,units,columns,rows))!==JSON.stringify(orderDraft(value));
  useEffect(()=>{onDraft?.(dirty&&!problem?orderDraft(value,units,columns,rows):null);},[units,columns,rows,value.version]);
  useEffect(()=>{onDirty?.(dirty);},[dirty]);
  useEffect(()=>{if(sortCommand){try {setUnits(rackOrderedUnits(units,sortCommand.basis,sortCommand.descending,columns,rows));setSortBasis(sortCommand.basis);}catch(e){setError(String(e));}}},[sortCommand]);
  function choose(u:OrderUnit|null) {setSelected(u?.unit_uid??null);onSelectGroup?.(u?.kind==='RACK_PAIR'?u.review_group_uid??null:null);onSelectUnit?.(u?.kind==='CABLE_LIST'?u:null);}
  function change(next:OrderUnit[]) {setUnits(next);setError("");}
  const direction=rackOrderDirection(units,sortBasis),descending=direction==="DESC";
  function flip() {try {change(rackOrderedUnits(units,sortBasis,!descending,columns,rows));}catch(e){setError(String(e));}}
  function patch(values:Partial<OrderUnit>) {if(unit)change(units.map(u=>u.unit_uid===unit.unit_uid?{...u,...values}:u));}
  const reference=value.reference.column_1_direction;
  const opposite={NORTH:"SOUTH",SOUTH:"NORTH",WEST:"EAST",EAST:"WEST"}[reference];
  const first=`${value.reference.column_1_is_inner?"Inner · ":""}${reference}`,last=`${value.reference.column_1_is_inner?"Outer · ":""}${opposite}`;
  const color=(u:OrderUnit)=>u.cable_class?CABLE_STYLES[u.cable_class].color:"#64748b";
  return <section className="cable-unit-order-editor" aria-label={title}>
    <h4>{title}</h4>
    <small>{value.status}{value.inherited?` · inherits ${value.defined_end}`:""} · {units.length} units · {units.reduce((n,u)=>n+(u.cable_count??0),0).toLocaleString()} cables</small>
    {canManage&&<div className="order-default-controls"><label>Rack position at<select aria-label="Rack ordering endpoint" value={sortBasis} onChange={e=>setSortBasis(e.target.value as typeof sortBasis)}><option value="source">Source rack</option><option value="destination">Destination rack</option></select></label><button type="button" disabled={busy||!units.some(u=>u[sortBasis==="source"?"source_rack_position":"destination_rack_position"]!=null)} aria-label={`Flip ${sortBasis} rack position order`} aria-pressed={descending} onClick={flip}>{direction==="CUSTOM"?"Custom ↕":descending?"Descending ↓":"Ascending ↑"} · flip</button></div>}
    {unit&&<section className="section-bundle-detail" aria-label="Selected ordered cable unit"><div><b>{unit.resolved_label}</b><button onClick={()=>choose(null)} aria-label="Close ordered unit">×</button></div><small>{unit.cable_count??"Unknown"} actual cables · L{unit.layer} / P{unit.position} · {unit.slot_width} × {unit.slot_height} cells</small><svg viewBox="0 0 240 52" role="img" aria-label="Enlarged selected unit"><rect x={10} y={5} width={220} height={40} fill={color(unit)} opacity={.7}/><text x={120} y={30} textAnchor="middle" fill="white" fontSize={12}>{unit.kind==="CABLE_LIST"?`${unit.cable_uids?.length} cable IDs`:unit.cable_type}</text></svg></section>}
    <svg className="bundle-order-grid" viewBox="0 0 288 142" role="img" aria-label={mode==="GRID"?`${columns} by ${rows} bundle-local ordering grid`:"Ordered bundle sectional projection; physical packing unverified"}>
      <text x={25} y={13} fontSize={9}>{reversed?last:first}</text><text x={265} y={13} textAnchor="end" fontSize={9}>{reversed?first:last}</text>
      {Array.from({length:Math.min(64,rows)},(_,y)=>Array.from({length:Math.min(64,columns)},(_,x)=><rect key={`${x}:${y}`} x={25+(reversed?columns-x-1:x)*240/columns} y={22+(rows-y-1)*96/rows} width={240/columns} height={96/rows} fill="#fafcfe" stroke={mode==="GRID"?"#cbd5e1":"none"} strokeWidth={.4} onClick={()=>{if(canManage&&unit)patch({position:x+1,layer:y+1});}}/>))}
      {mode==="PHYSICAL"&&<path d="M25 22 V118 H265 V22" stroke="#64748b" strokeWidth={1} fill="none" pointerEvents="none"/>}
      {units.map((u,i)=><g key={u.unit_uid} role="button" tabIndex={0} aria-label={`Select ordered unit ${u.resolved_label}`} aria-pressed={u.unit_uid===selected} onClick={()=>choose(u)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(u);}}}>
        <title>{`${u.resolved_label} · L${u.layer} P${u.position}`}</title><rect x={25+(reversed?columns-u.position-u.slot_width+1:u.position-1)*240/columns+.5} y={22+(rows-u.layer-u.slot_height+1)*96/rows+.5} width={Math.max(1,u.slot_width*240/columns-1)} height={Math.max(1,u.slot_height*96/rows-1)} fill={color(u)} fillOpacity={(!selected||selected===u.unit_uid) ? .85 : .25} stroke={selected===u.unit_uid?"#111827":color(u)} strokeWidth={selected===u.unit_uid?2:.5}/>
        {240/columns>12&&<text x={25+(reversed?columns-u.position-u.slot_width/2+1:u.position-1+u.slot_width/2)*240/columns} y={22+(rows-u.layer-u.slot_height/2+1)*96/rows+3} textAnchor="middle" fontSize={8} fill="white" pointerEvents="none">{i+1}</text>}
      </g>)}<text x={25} y={134} fontSize={9}>L1 bottom · ordinal cells; packing unverified</text>
    </svg>
    <label className="routing-select-label">Cable unit<select aria-label="Ordered cable unit" value={selected??""} onChange={e=>choose(units.find(u=>u.unit_uid===e.target.value)??null)}><option value="">Select a rectangle or unit</option>{units.map((u,i)=><option key={u.unit_uid} value={u.unit_uid}>{i+1}. {u.resolved_label} · L{u.layer} P{u.position}</option>)}</select></label>
    {!units.length&&<p className="routing-notice">Empty section · no ordered cable units.</p>}
    {canManage&&<>
      {unit&&<div className="order-unit-fields">{([['layer','Layer'],['position','Position'],['slot_width','Cell width'],['slot_height','Cell height']] as const).map(([key,label])=><label key={key}>{label}<input aria-label={`Unit ${label.toLowerCase()}`} type="number" min={1} max={64} value={unit[key]} onChange={e=>patch({[key]:Number(e.target.value)})}/></label>)}<label className="order-unit-wide">Swap position with<select value={swap} onChange={e=>setSwap(e.target.value)}><option value="">Choose unit</option>{units.filter(u=>u.unit_uid!==selected).map(u=><option key={u.unit_uid} value={u.unit_uid}>{u.resolved_label}</option>)}</select></label><button disabled={!swap||busy} onClick={()=>{const other=units.find(u=>u.unit_uid===swap);if(other)change(units.map(u=>u.unit_uid===unit.unit_uid?{...u,layer:other.layer,position:other.position}:u.unit_uid===other.unit_uid?{...u,layer:unit.layer,position:unit.position}:u));}}>Swap</button><button onClick={()=>{change(units.filter(u=>u.unit_uid!==selected));choose(null);}}>Remove unit</button></div>}
      <details><summary>Grid / explicit cable list</summary><div className="order-unit-fields"><label>Columns<input type="number" min={1} max={64} value={columns} onChange={e=>setColumns(Number(e.target.value))}/></label><label>Layers<input type="number" min={1} max={64} value={rows} onChange={e=>setRows(Number(e.target.value))}/></label></div><label className="routing-select-label">Actual cable IDs (one per line)<textarea value={cableIds} onChange={e=>setCableIds(e.target.value)}/></label><button disabled={!cableIds.trim()} onClick={()=>{const ids=cableIds.split(/[\s,]+/).filter(Boolean),id=`draft:${ids.join(":")}`;const next:OrderUnit={kind:"CABLE_LIST",cable_uids:ids,unit_uid:id,resolved_label:`${ids.length} selected cable(s)`,cable_count:ids.length,layer:1,position:1,slot_width:1,slot_height:1};change([...units,next]);setCableIds("");choose(next);}}>Add one cable-list unit</button></details>
      {problem&&<p className="routing-error" role="alert">{problem}</p>}{error&&<p className="routing-error" role="alert">{error}{onReload&&<button onClick={onReload}>Reload saved order</button>}</p>}
      <div className="section-view-controls"><button disabled={!dirty||!!problem||busy} onClick={async()=>{setBusy(true);setError("");try {await onSave(orderDraft(value,units,columns,rows));}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}}>{busy?"Saving order…":"Save this end’s order"}</button><button disabled={!dirty||busy} onClick={()=>{change(value.units);setColumns(value.grid_columns);setRows(value.grid_rows);}}>Discard changes</button></div>
      {onReset&&<button disabled={dirty||busy} onClick={async()=>{setBusy(true);try {await onReset();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}}>Use inherited / generated order</button>}
      <small>{dirty?"Unsaved draft · valid changes update the crossing preview.":"Changing order does not change manual cable routes."}</small>
    </>}
    {value.errors?.map(e=><p role="alert" className="routing-error" key={e}>{e}</p>)}
  </section>;
}

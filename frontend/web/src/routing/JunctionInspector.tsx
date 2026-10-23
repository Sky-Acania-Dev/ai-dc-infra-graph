import type { OrderUnit } from "./bundleOrderTypes";
import { useEffect, useState } from "react";
import { routingApi } from "./api";
import { JunctionPlan, JunctionPortSections } from "./JunctionPlan";
import { BundleConnectionForm } from "./ConnectionSettings";
import { DimensionInput } from "./SectionSettings";
import { formatInches, formatDerivedInches, parseInches } from "./dimensions";
import type { GraphNode, JunctionArea, JunctionPreview, Mutate, ResolvedLayout, RoutingGraph, Tier } from "./types";
import { CableUnitOrderEditor } from "./CableUnitOrderEditor";
import { BundleContentsPanel } from "./BundleContentsPanel";
import type { SectionOrderRequest } from "./bundleOrderTypes";
import { defaultRackBasis, rackOrderDirection } from "./bundleOrdering";

export function JunctionInspector({data,graph,node,canManage,busy,mutate,onSelectGroup,onSelectUnit,sectionMode,onSectionModeChange}:{data:ResolvedLayout;graph:RoutingGraph;node:GraphNode;canManage:boolean;busy:boolean;mutate:Mutate;onSelectGroup?:(uid:string|null)=>void;onSelectUnit?:(unit:OrderUnit|null)=>void;sectionMode?:"PHYSICAL"|"GRID";onSectionModeChange?:(mode:"PHYSICAL"|"GRID")=>void}) {
  const [tier,setTier]=useState(node.tier);
  const [dirtyArms,setDirtyArms]=useState<Record<string,boolean>>({}),[draftEpoch,setDraftEpoch]=useState(0);
  const dirty=Object.values(dirtyArms).some(Boolean);
  const [selectedUnitUid,setSelectedUnitUid]=useState<string|null>(null);
  const [endFlips,setEndFlips]=useState<Record<string,{basis:"source"|"destination";descending:boolean}>>({});
  const nodes=graph.nodes.filter(n=>n.x_in===node.x_in&&n.y_in===node.y_in).sort((a,b)=>a.tier-b.tier);
  const active=nodes.find(n=>n.tier===tier)??node;
  const supportsActual=Boolean(data.layout.room_uid?.startsWith("LBB01:")&&data.layout.physical_hall_code==="DH1");
  const [actual,setActual]=useState((node.bundle_connection_uids?.length??0)===0&&supportsActual);
  const [preview,setPreview]=useState<JunctionPreview|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState("");
  const [baseline,setBaseline]=useState<JunctionPreview|null>(null),[overrides,setOverrides]=useState<Record<string,SectionOrderRequest>>({}),[updating,setUpdating]=useState(false);
  const [selectedUid,setSelectedUid]=useState<string|null>(null),[below,setBelow]=useState(false),[localMode,setLocalMode]=useState<"PHYSICAL"|"GRID">("PHYSICAL");
  const mode=sectionMode??localMode;
  const setMode=onSectionModeChange??setLocalMode;
  useEffect(()=>{setTier(node.tier);setSelectedUid(null);setSelectedUnitUid(null);onSelectGroup?.(null);onSelectUnit?.(null);},[node.x_in,node.y_in]);
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setPreview(null);setBaseline(null);setOverrides({});setEndFlips({});setDirtyArms({});setError("");setSelectedUid(null);setSelectedUnitUid(null);onSelectGroup?.(null);onSelectUnit?.(null);
    void routingApi.junction(data.layout.uid,active.id,actual,controller.signal).then(value=>{if(!controller.signal.aborted){setPreview(value);setBaseline(value);}}).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[data,active.id,actual]);
  useEffect(()=>{
    if(!baseline)return;
    const values=Object.values(overrides);
    if(!values.length){setPreview(baseline);setUpdating(false);return;}
    const controller=new AbortController();setUpdating(true);
    const timer=window.setTimeout(()=>{void routingApi.draftJunction(data.layout.uid,active.id,values,controller.signal).then(value=>{if(!controller.signal.aborted){setPreview(value);setError("");}}).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setUpdating(false);});},300);
    return()=>{controller.abort();window.clearTimeout(timer);};
  },[overrides,baseline,active.id]);
  const selected=preview?.movements.find(m=>m.uid===selectedUid)??preview?.movements.find(m=>m.parent_connection_uid===selectedUid);
  function clearMovement() {setSelectedUid(null);setSelectedUnitUid(null);onSelectGroup?.(null);onSelectUnit?.(null);}
  function selectUnit(unit:OrderUnit|null) {setSelectedUnitUid(unit?.unit_uid??null);if(unit)setSelectedUid(null);onSelectUnit?.(unit);}
  function select(uid:string) {setSelectedUnitUid(null);onSelectUnit?.(null);const next=selectedUid===uid?null:uid;setSelectedUid(next);onSelectGroup?.(preview?.movements.find(m=>m.uid===next)?.group_uid??null);}
  return <section className="junction-inspector" aria-label="Junction geometry and connected sections">
    <h3>{active.passage_code} junction · {formatInches(active.station_in)}</h3>
    <div className="section-view-controls"><label>Tier<select disabled={dirty} aria-label="Junction tier" value={active.tier} onChange={e=>setTier(Number(e.target.value) as Tier)}>{nodes.map(n=><option key={n.id} value={n.tier}>Tier {n.tier}</option>)}</select></label><button aria-pressed={below} onClick={()=>setBelow(v=>!v)}>{below?"Underside · looking up":"Plan · looking down"}</button></div>
    {supportsActual&&<label className="routing-cable-toggle"><input type="checkbox" disabled={dirty} checked={actual} onChange={e=>setActual(e.target.checked)}/>Actual cable groups · editable sectional order</label>}
    {loading&&<p role="status">Loading junction cable movements…</p>}
    {error&&<p role="alert" className="routing-error">{error}</p>}
    {preview&&<>
      <dl className="routing-generic-info"><div><dt>Intersection points</dt><dd>{preview.statistics.cable_intersection_point_count??"Unknown"} · {preview.statistics.intersection_count_status}</dd></div><div><dt>Bundle-pair crossings</dt><dd>{preview.statistics.bundle_pair_crossing_count??"Unknown"}</dd></div><div><dt>Movements / unresolved</dt><dd>{preview.movements.length} / {preview.statistics.unresolved_movement_count}</dd></div><div><dt>Working area</dt><dd>{formatInches(preview.area.bounds.east_in-preview.area.bounds.west_in)} × {formatInches(preview.area.bounds.south_in-preview.area.bounds.north_in)}</dd></div><div><dt>Height / source</dt><dd>{preview.area.usable_height_in==null?"Clearance unknown":formatInches(preview.area.usable_height_in)} · {preview.area.provenance}</dd></div></dl>
      <p className="routing-notice">Tier {active.tier} · {preview.area.elevation_in==null?"Elevation unknown":`${formatInches(preview.area.elevation_in)} AFF`}{actual?" · Ordinal order; route assignments unchanged.":""}</p>
      {actual&&<details><summary>About these occupations</summary><p>Actual groups follow their existing routes. Unsaved sections start in rack-position order. Saving an end persists only its ordinal unit positions. Width-normalized curves are schematic; physical bundle packing and bend limits remain unverified.</p></details>}
      <small>{actual?"Scope: actual routed groups with saved or default ordinal positions":"Scope: saved bundle connections; unassigned groups excluded"}. {preview.statistics.intersection_count_status==="UNKNOWN"?`${preview.statistics.observed_intersection_point_count} observed crossing points; remaining movement geometry is unknown.`:""}</small>
      <JunctionPlan preview={preview} below={below} selectedUnitUid={selectedUnitUid} selectedUid={selectedUid} onSelect={select}/>
      {actual&&canManage&&baseline?.sections&&<div className="junction-end-flips" role="group" aria-label="Default rack ordering at each junction end">{Object.entries(baseline.sections).map(([direction,section])=>{
        if(!section?.units.length)return null;
        const basis=defaultRackBasis(section.units,section.section_end==="END"?"destination":"source");
        const applicable=section.units.some(u=>u[basis==="source"?"source_rack_position":"destination_rack_position"]!=null);
        return <button key={direction} disabled={!applicable} aria-pressed={endFlips[direction]?.descending??(rackOrderDirection(section.units,basis)==="DESC")} title={applicable?`Flip by relative ${basis} rack position within its row`:"Rack positions are unavailable for this end"} onClick={()=>setEndFlips(current=>({...current,[direction]:{basis,descending:!(current[direction]?.descending??(rackOrderDirection(section.units,basis)==="DESC"))}}))}>{direction} · racks {(endFlips[direction]?.descending??(rackOrderDirection(section.units,basis)==="DESC"))?"↓":"↑"}</button>;
      })}</div>}
      {dirty&&<button onClick={()=>{setOverrides({});setEndFlips({});setDirtyArms({});setDraftEpoch(v=>v+1);}}>Discard all draft orders</button>}
      {updating&&<p role="status">Recalculating crossings for the draft order…</p>}
      {Object.keys(overrides).length>0&&<p className="routing-notice">Unsaved sectional order · {baseline?.statistics.cable_intersection_point_count??"?"} → {preview.statistics.cable_intersection_point_count??"?"} intersection points.</p>}
      <label>Bundle movement<select aria-label="Junction bundle movement" value={selectedUnitUid?"__unit__":selectedUid??""} onChange={e=>e.target.value==="__unit__"?undefined:e.target.value?select(e.target.value):clearMovement()}><option value="">All movements</option>{selectedUnitUid&&<option value="__unit__">Selected cable-list unit</option>}{preview.movements.map(m=><option key={m.uid} value={m.uid}>{m.label}{m.route_source?` · ${m.route_source}`:""}</option>)}</select></label>
      {selected&&<section className="section-bundle-detail" aria-label="Selected junction bundle"><b>{selected.label}</b><p>{selected.route_source?`${selected.route_source} route · `:""}{selected.centerline_radius_in==null?selected.geometry_status:`Centerline radius ${formatDerivedInches(selected.centerline_radius_in)}`}{selected.from_turn_start_in!=null?` · turn starts ${formatDerivedInches(selected.from_turn_start_in)} / ${formatDerivedInches(selected.to_turn_start_in!)}`:""}</p>{selected.checks.map(c=><small key={c}>{c}</small>)}</section>}
      {preview.statistics.overlapping_movement_pairs.length>0&&<p className="routing-notice">{preview.statistics.overlapping_movement_pairs.length} overlapping movement pairs; overlap is separate from intersection points. Packing and minimum bend limits remain unchecked.</p>}
      <div className="section-view-controls" role="group" aria-label="Junction section display mode"><button aria-pressed={mode==="PHYSICAL"} onClick={()=>setMode("PHYSICAL")}>Physical</button><button aria-pressed={mode==="GRID"} onClick={()=>setMode("GRID")}>Grid</button></div>
      {/* Keep every port section mounted; selection only changes emphasis. */}
      <JunctionPortSections preview={preview} selectedUnitUid={selectedUnitUid} selectedUid={selectedUid} onSelect={select} mode={mode}/>
      {actual&&baseline?.sections&&<section aria-label="Edit connected end ordering"><h4>Edit connected ends</h4><small>Each arm has an independent end order. Flip rack position or edit cells; the plan and crossing count preview valid drafts before saving.</small>{Object.entries(baseline.sections).map(([direction,section])=>section&&<details key={`${active.id}:${direction}`} className="section-configuration"><summary>{direction} · {section.section_end.toLowerCase()} end · {section.units.length} units</summary><CableUnitOrderEditor key={draftEpoch} value={section} canManage={canManage} onDirty={value=>setDirtyArms(current=>current[direction]===value?current:{...current,[direction]:value})} sortCommand={endFlips[direction]} title={`${direction} end order`} basis={defaultRackBasis(section.units,section.section_end==="END"?"destination":"source")} onSelectUnit={selectUnit} onSelectGroup={uid=>{onSelectGroup?.(uid);setSelectedUid(preview?.movements.find(m=>m.group_uid===uid)?.uid??null);}}
        onDraft={contents=>setOverrides(current=>{const next={...current};if(contents)next[direction]={span:section.span,section_end:section.section_end,contents};else delete next[direction];return JSON.stringify(next)===JSON.stringify(current)?current:next;})}
        onSave={async contents=>{await routingApi.saveSectionOrder(data.layout.uid,{span:section.span,section_end:section.section_end,contents});const fresh=await routingApi.junction(data.layout.uid,active.id,true);setBaseline(fresh);setPreview(fresh);setOverrides(current=>{const next={...current};delete next[direction];return next;});}}/></details>)}</section>}
      {!actual&&selected&&selected.from_port?.placement_uid&&<BundleContentsPanel key={selected.from_port.placement_uid} layout={data.layout.uid} placement={selected.from_port.placement_uid} initialEnd={selected.from_port.end} canManage={canManage} onSelectGroup={onSelectGroup} onSelectUnit={selectUnit} onSaved={()=>{void routingApi.junction(data.layout.uid,active.id,false).then(v=>{setPreview(v);setBaseline(v);});}}/>}
      {!actual&&selected?.to_port?.placement_uid&&<details className="section-configuration"><summary>Edit destination bundle contents</summary><BundleContentsPanel key={selected.to_port.placement_uid} layout={data.layout.uid} placement={selected.to_port.placement_uid} initialEnd={selected.to_port.end} canManage={canManage} onSelectGroup={onSelectGroup} onSelectUnit={selectUnit} onSaved={()=>{void routingApi.junction(data.layout.uid,active.id,false).then(v=>{setPreview(v);setBaseline(v);});}}/></details>}
      {!preview.movements.length&&<p className="routing-notice">No saved bundle movements at this junction. Empty connected sections remain visible.</p>}
      {canManage&&<details className="section-configuration"><summary>Configure junction working area</summary><JunctionAreaForm key={`${active.id}:${preview.area.uid}`} data={data} node={active} busy={busy} mutate={mutate}/></details>}
      {canManage&&!actual&&selected&&data.bundle_connections.some(c=>c.uid===(selected.parent_connection_uid??selected.uid))&&<details className="section-configuration"><summary>Edit selected turn / connection</summary><BundleConnectionForm key={selected.parent_connection_uid??selected.uid} data={data} record={data.bundle_connections.find(c=>c.uid===(selected.parent_connection_uid??selected.uid))} mutate={mutate} disabled={busy}/></details>}
    </>}
  </section>;
}

function JunctionAreaForm({data,node,busy,mutate}:{data:ResolvedLayout;node:GraphNode;busy:boolean;mutate:Mutate}) {
  const record=data.junction_areas?.find(a=>a.passage_band_uid===node.passage_band_uid&&a.tier===node.tier&&(a.station_in??data.geometry.cross_routes.find(r=>r.uid===a.cross_route_uid)?.station_in)===node.station_in);
  const [dimensions,setDimensions]=useState(Object.fromEntries(["west_extension_in","east_extension_in","north_extension_in","south_extension_in","usable_height_in"].map(k=>[k,record?.[k as keyof JunctionArea]==null?k==="usable_height_in"?"":"0":formatInches(record[k as keyof JunctionArea] as number)])));
  const [label,setLabel]=useState(record?.label??""),[notes,setNotes]=useState(record?.notes??""),[enabled,setEnabled]=useState(record?.enabled??true),[provenance,setProvenance]=useState(record?.provenance??"SCHEMATIC"),[error,setError]=useState("");
  return <form className="routing-form" onSubmit={async e=>{e.preventDefault();setError("");try {const values=Object.fromEntries(Object.entries(dimensions).map(([k,v])=>[k,v.trim()?parseInches(v):k==="usable_height_in"?null:0]));await mutate("junction-areas",{passage_band_uid:node.passage_band_uid,cross_route_uid:node.cross_route_uid,station_in:node.cross_route_uid?null:node.station_in,tier:node.tier,...values,label:label||null,notes:notes||null,enabled,provenance},record?.uid);}catch(e){setError(String(e));}}}>
    <label>Label<input value={label} onChange={e=>setLabel(e.target.value)}/></label>
    {Object.entries(dimensions).map(([k,v])=><DimensionInput key={k} label={k==="usable_height_in"?"Usable height (blank if unknown)":`${k.split("_")[0]} arm extension`} value={v} onChange={value=>setDimensions(d=>({...d,[k]:value}))}/>)}
    <label>Provenance<select value={provenance} onChange={e=>setProvenance(e.target.value as JunctionArea["provenance"])}>{["SCHEMATIC","MANUAL","FIELD_MEASURED"].map(p=><option key={p}>{p}</option>)}</select></label>
    <label>Notes<textarea value={notes} onChange={e=>setNotes(e.target.value)}/></label><label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Enabled</label>
    <button disabled={busy}>Save working area</button>{record&&<button type="button" disabled={busy} onClick={()=>void mutate("junction-areas",{},record.uid,true)}>Delete area configuration</button>}{error&&<p role="alert">{error}</p>}
  </form>;
}

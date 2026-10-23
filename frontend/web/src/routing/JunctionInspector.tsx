import { useEffect, useState } from "react";
import { routingApi } from "./api";
import { JunctionPlan, JunctionPortSections } from "./JunctionPlan";
import { BundleConnectionForm } from "./ConnectionSettings";
import { DimensionInput } from "./SectionSettings";
import { formatInches, formatDerivedInches, parseInches } from "./dimensions";
import type { GraphNode, JunctionArea, JunctionPreview, Mutate, ResolvedLayout, RoutingGraph, Tier } from "./types";

export function JunctionInspector({data,graph,node,canManage,busy,mutate,onSelectGroup,sectionMode,onSectionModeChange}:{data:ResolvedLayout;graph:RoutingGraph;node:GraphNode;canManage:boolean;busy:boolean;mutate:Mutate;onSelectGroup?:(uid:string|null)=>void;sectionMode?:"PHYSICAL"|"GRID";onSectionModeChange?:(mode:"PHYSICAL"|"GRID")=>void}) {
  const [tier,setTier]=useState(node.tier);
  const nodes=graph.nodes.filter(n=>n.x_in===node.x_in&&n.y_in===node.y_in).sort((a,b)=>a.tier-b.tier);
  const active=nodes.find(n=>n.tier===tier)??node;
  const supportsActual=Boolean(data.layout.room_uid?.startsWith("LBB01:")&&data.layout.physical_hall_code==="DH1");
  const [actual,setActual]=useState((node.bundle_connection_uids?.length??0)===0&&supportsActual);
  const [preview,setPreview]=useState<JunctionPreview|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState("");
  const [selectedUid,setSelectedUid]=useState<string|null>(null),[below,setBelow]=useState(false),[localMode,setLocalMode]=useState<"PHYSICAL"|"GRID">("PHYSICAL");
  const mode=sectionMode??localMode;
  const setMode=onSectionModeChange??setLocalMode;
  useEffect(()=>{setTier(node.tier);setSelectedUid(null);onSelectGroup?.(null);},[node.x_in,node.y_in]);
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setPreview(null);setError("");setSelectedUid(null);onSelectGroup?.(null);
    void routingApi.junction(data.layout.uid,active.id,actual,controller.signal).then(value=>{if(!controller.signal.aborted)setPreview(value);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[data,active.id,actual]);
  const selected=preview?.movements.find(m=>m.uid===selectedUid);
  function select(uid:string) {const next=selectedUid===uid?null:uid;setSelectedUid(next);onSelectGroup?.(preview?.movements.find(m=>m.uid===next)?.group_uid??null);}
  return <section className="junction-inspector" aria-label="Junction geometry and connected sections">
    <h3>{active.passage_code} junction · {formatInches(active.station_in)}</h3>
    <div className="section-view-controls"><label>Tier<select aria-label="Junction tier" value={active.tier} onChange={e=>setTier(Number(e.target.value) as Tier)}>{nodes.map(n=><option key={n.id} value={n.tier}>Tier {n.tier}</option>)}</select></label><button aria-pressed={below} onClick={()=>setBelow(v=>!v)}>{below?"Underside · looking up":"Plan · looking down"}</button></div>
    {supportsActual&&<label className="routing-cable-toggle"><input type="checkbox" checked={actual} onChange={e=>setActual(e.target.checked)}/>Actual cable groups · schematic occupations</label>}
    {loading&&<p role="status">Loading junction cable movements…</p>}
    {error&&<p role="alert" className="routing-error">{error}</p>}
    {preview&&<>
      <dl className="routing-generic-info"><div><dt>Intersection points</dt><dd>{preview.statistics.cable_intersection_point_count??"Unknown"} · {preview.statistics.intersection_count_status}</dd></div><div><dt>Bundle-pair crossings</dt><dd>{preview.statistics.bundle_pair_crossing_count??"Unknown"}</dd></div><div><dt>Movements / unresolved</dt><dd>{preview.movements.length} / {preview.statistics.unresolved_movement_count}</dd></div><div><dt>Working area</dt><dd>{formatInches(preview.area.bounds.east_in-preview.area.bounds.west_in)} × {formatInches(preview.area.bounds.south_in-preview.area.bounds.north_in)}</dd></div><div><dt>Height / source</dt><dd>{preview.area.usable_height_in==null?"Clearance unknown":formatInches(preview.area.usable_height_in)} · {preview.area.provenance}</dd></div></dl>
      <p className="routing-notice">Tier {active.tier} · {preview.area.elevation_in==null?"Elevation unknown":`${formatInches(preview.area.elevation_in)} AFF`}{actual?" · Display-only occupations; assignments unchanged.":""}</p>
      {actual&&<details><summary>About these occupations</summary><p>Actual groups and existing routes use suggested 2 × 1 in bundle rectangles and turn starts for this view. Occupations are schematic and are not saved.</p></details>}
      <small>{actual?"Scope: actual routed groups with schematic occupations":"Scope: saved bundle connections; unassigned groups excluded"}. {preview.statistics.intersection_count_status==="UNKNOWN"?`${preview.statistics.observed_intersection_point_count} observed crossing points; remaining movement geometry is unknown.`:""}</small>
      <JunctionPlan preview={preview} below={below} selectedUid={selectedUid} onSelect={select}/>
      <label>Bundle movement<select aria-label="Junction bundle movement" value={selectedUid??""} onChange={e=>e.target.value?select(e.target.value):(setSelectedUid(null),onSelectGroup?.(null))}><option value="">All movements</option>{preview.movements.map(m=><option key={m.uid} value={m.uid}>{m.label}{m.route_source?` · ${m.route_source}`:""}</option>)}</select></label>
      {selected&&<section className="section-bundle-detail" aria-label="Selected junction bundle"><b>{selected.label}</b><p>{selected.route_source?`${selected.route_source} route · `:""}{selected.centerline_radius_in==null?selected.geometry_status:`Centerline radius ${formatDerivedInches(selected.centerline_radius_in)}`}{selected.from_turn_start_in!=null?` · turn starts ${formatInches(selected.from_turn_start_in)} / ${formatInches(selected.to_turn_start_in!)}`:""}</p>{selected.checks.map(c=><small key={c}>{c}</small>)}</section>}
      {preview.statistics.overlapping_movement_pairs.length>0&&<p className="routing-notice">{preview.statistics.overlapping_movement_pairs.length} overlapping movement pairs; overlap is separate from intersection points. Packing and minimum bend limits remain unchecked.</p>}
      <div className="section-view-controls" role="group" aria-label="Junction section display mode"><button aria-pressed={mode==="PHYSICAL"} onClick={()=>setMode("PHYSICAL")}>Physical</button><button aria-pressed={mode==="GRID"} onClick={()=>setMode("GRID")}>Grid</button></div>
      {/* Keep every port section mounted; selection only changes emphasis. */}
      <JunctionPortSections preview={preview} selectedUid={selectedUid} onSelect={select} mode={mode}/>
      {!preview.movements.length&&<p className="routing-notice">No saved bundle movements at this junction. Empty connected sections remain visible.</p>}
      {canManage&&<details className="section-configuration"><summary>Configure junction working area</summary><JunctionAreaForm key={`${active.id}:${preview.area.uid}`} data={data} node={active} busy={busy} mutate={mutate}/></details>}
      {canManage&&!actual&&selected&&data.bundle_connections.some(c=>c.uid===selected.uid)&&<details className="section-configuration"><summary>Edit selected turn / connection</summary><BundleConnectionForm key={selected.uid} data={data} record={data.bundle_connections.find(c=>c.uid===selected.uid)} mutate={mutate} disabled={busy}/></details>}
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

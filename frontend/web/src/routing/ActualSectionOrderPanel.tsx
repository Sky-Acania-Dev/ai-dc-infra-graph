import type { OrderUnit } from "./bundleOrderTypes";
import { useEffect, useState } from "react";
import { defaultRackBasis } from "./bundleOrdering";
import { routingApi } from "./api";
import { CableUnitOrderEditor } from "./CableUnitOrderEditor";
import type { SectionEnd, SectionOrder } from "./bundleOrderTypes";
import type { ResolvedLayout, SegmentSpan, Tier } from "./types";

export function ActualSectionOrderPanel({data,span,canManage,onSelectGroup,onSelectUnit,reversed=false,mode="GRID"}:{data:ResolvedLayout;span:SegmentSpan;canManage:boolean;onSelectGroup?:(uid:string|null)=>void;onSelectUnit?:(unit:OrderUnit|null)=>void;reversed?:boolean;mode?:"GRID"|"PHYSICAL"}) {
  const records=span.passage_band_uid?data.passage_tiers.filter(t=>t.passage_band_uid===span.passage_band_uid&&t.enabled):data.cross_route_tiers.filter(t=>t.cross_route_uid===span.cross_route_uid&&t.enabled);
  records.sort((a,b)=>a.tier-b.tier);
  const [tier,setTier]=useState<Tier>(records[0]?.tier??1),[end,setEnd]=useState<SectionEnd>("SPAN"),[value,setValue]=useState<SectionOrder|null>(null);
  const [error,setError]=useState(""),[loading,setLoading]=useState(false),[reload,setReload]=useState(0);
  const [dirty,setDirty]=useState(false);
  const signature=JSON.stringify(span);
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setValue(null);setError("");
    void routingApi.sectionOrder(data.layout.uid,{span:{...span,tier},section_end:end},controller.signal).then(v=>{if(!controller.signal.aborted)setValue(v);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[data,signature,tier,end,reload]);
  if(!records.length)return null;
  return <section className="actual-section-order" aria-label="Actual cable group section">
    <h4>Actual cable group section</h4>
    <div className="section-view-controls"><label>Tier<select disabled={dirty} aria-label="Actual section tier" value={tier} onChange={e=>setTier(Number(e.target.value) as Tier)}>{records.map(t=><option key={t.uid} value={t.tier}>T{t.tier}</option>)}</select></label><label>Segment end<select disabled={dirty} aria-label="Segment ordering end" value={end} onChange={e=>setEnd(e.target.value as SectionEnd)}><option value="SPAN">Default · both ends</option><option value="START">Start end only</option><option value="END">End end only</option></select></label></div>
    <small>Start = lower station / NORTH end. End = higher station / SOUTH end. End overrides are independent.</small>
    {loading&&<p role="status">Loading actual sectional groups…</p>}{error&&<p role="alert" className="routing-error">{error} <button onClick={()=>setReload(v=>v+1)}>Reload order</button></p>}
    {dirty&&<small>Save or discard this draft before changing its tier or end.</small>}
    {value&&<CableUnitOrderEditor key={`${signature}:${tier}:${end}`} value={value} canManage={canManage} basis={defaultRackBasis(value.units,end==="END"?"destination":"source")} reversed={reversed} mode={mode} onReload={()=>setReload(v=>v+1)} onDirty={setDirty} onSelectGroup={onSelectGroup} onSelectUnit={onSelectUnit} title={`${end==="SPAN"?"Default":end==="START"?"Start":"End"} order · Tier ${tier}`}
      onReset={value.bundle_placement_uid&&value.defined_end===end?async()=>{const saved=await routingApi.bundleContents(data.layout.uid,value.bundle_placement_uid!,end);await routingApi.clearBundleContents(data.layout.uid,value.bundle_placement_uid!,end,saved.version);setReload(v=>v+1);}:undefined}
      onSave={async contents=>{setValue(await routingApi.saveSectionOrder(data.layout.uid,{span:{...span,tier},section_end:end,contents}));}}/>}
  </section>;
}

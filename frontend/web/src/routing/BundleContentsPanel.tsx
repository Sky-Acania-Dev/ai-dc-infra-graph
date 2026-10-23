import type { OrderUnit } from "./bundleOrderTypes";
import { useEffect, useState } from "react";
import { routingApi } from "./api";
import { CableUnitOrderEditor } from "./CableUnitOrderEditor";
import type { BundleContents, SectionEnd } from "./bundleOrderTypes";

export function BundleContentsPanel({layout,placement,canManage,onSelectGroup,onSelectUnit,onSaved,initialEnd="SPAN"}:{layout:string;placement:string;canManage:boolean;onSelectGroup?:(uid:string|null)=>void;onSelectUnit?:(unit:OrderUnit|null)=>void;onSaved?:()=>void;initialEnd?:SectionEnd}) {
  const [end,setEnd]=useState<SectionEnd>(initialEnd),[value,setValue]=useState<BundleContents|null>(null),[error,setError]=useState(""),[reload,setReload]=useState(0);
  useEffect(()=>{const controller=new AbortController();setValue(null);setError("");void routingApi.bundleContents(layout,placement,end,controller.signal).then(v=>{if(!controller.signal.aborted)setValue(v);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);});return()=>controller.abort();},[layout,placement,end,reload]);
  return <section aria-label="Edit bundle contents"><label className="routing-select-label">Bundle end<select aria-label="Bundle contents end" value={end} onChange={e=>setEnd(e.target.value as SectionEnd)}><option value="SPAN">Default · both ends</option><option value="START">Start end only</option><option value="END">End end only</option></select></label>
    {error?<p role="alert" className="routing-error">{error} <button onClick={()=>setReload(v=>v+1)}>Reload</button></p>:!value?<p role="status">Loading ordered bundle contents…</p>:<CableUnitOrderEditor key={`${placement}:${end}`} value={value} canManage={canManage} onReload={()=>setReload(v=>v+1)} onSelectGroup={onSelectGroup} onSelectUnit={onSelectUnit} onSave={async draft=>{setValue(await routingApi.saveBundleContents(layout,placement,end,draft));onSaved?.();}}/>}
  </section>;
}

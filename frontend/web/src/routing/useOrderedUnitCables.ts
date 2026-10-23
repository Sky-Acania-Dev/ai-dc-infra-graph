import { useEffect, useState } from "react";
import { routingApi } from "./api";
import { unitSelector } from "./bundleOrdering";
import type { OrderUnit } from "./bundleOrderTypes";
import type { InventoryCable } from "./types";

export function useOrderedUnitCables(layout:string|undefined,unit:OrderUnit|null) {
  const [cables,setCables]=useState<InventoryCable[]>([]),[loading,setLoading]=useState(false),[error,setError]=useState("");
  const selector=unit?JSON.stringify(unitSelector(unit)):"";
  useEffect(()=>{
    const controller=new AbortController();setCables([]);setError("");
    if(!layout||!selector){setLoading(false);return;}
    setLoading(true);
    void routingApi.unitCables(layout,JSON.parse(selector),controller.signal).then(v=>{if(!controller.signal.aborted)setCables(v.cables);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[layout,selector]);
  return {cables,loading,error};
}

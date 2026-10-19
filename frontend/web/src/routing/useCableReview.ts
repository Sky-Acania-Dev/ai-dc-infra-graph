import { useCallback, useEffect, useRef, useState } from "react";
import { routingApi } from "./api";
import type { CableReview, ResolvedLayout, ReviewScope } from "./types";
import {readReviewSummary,writeReviewSummary,SummaryLoadGate} from "./reviewSummaryCache";

export function useCableReview(data: ResolvedLayout | null, enabled: boolean, scope: ReviewScope = "pilot") {
  const [state, setState] = useState<{context:ResolvedLayout|null; scope: ReviewScope; data:CableReview|null; loading:boolean; error:string; stale:boolean; savedAt:number|null}>({context:null,scope,data:null,loading:false,error:"",stale:false,savedAt:null});
  const [reloadCount, setReloadCount] = useState(0);
  const active=useRef({data,scope,enabled});active.current={data,scope,enabled};
  const replace = useCallback((review:CableReview)=>{if(data && active.current.data===data && active.current.scope===scope && active.current.enabled){setState({context:data,scope,data:review,loading:false,error:"",stale:false,savedAt:Date.now()});void writeReviewSummary(data,review);}},[data,scope]);
  useEffect(() => {
    const controller=new AbortController(),gate=new SummaryLoadGate();
    if(!data || !enabled){setState({context:null,scope,data:null,loading:false,error:"",stale:false,savedAt:null});return;}
    setState(previous=>({context:data,scope,data:previous.context===data && previous.scope===scope ? previous.data : null,loading:true,error:"",stale:true,savedAt:previous.context===data && previous.scope===scope ? previous.savedAt : null}));
    if(scope==="hall") void readReviewSummary(data).then(saved=>{
      if(saved && gate.acceptSaved())setState(previous=>previous.data ? previous : {context:data,scope,data:saved.review,loading:previous.loading,error:previous.error,stale:true,savedAt:saved.savedAt});
    });
    void routingApi.cableReview(data.layout.uid,controller.signal,scope).then(result=>{
      if(gate.acceptCurrent()){setState({context:data,scope,data:result,loading:false,error:"",stale:false,savedAt:Date.now()});void writeReviewSummary(data,result);}
    })
      .catch(e => {if (!controller.signal.aborted) setState(previous=>({...previous,loading:false,error:String(e)}));});
    return ()=>{gate.dispose();controller.abort();};
  }, [data, enabled, reloadCount, scope]);
  return {...(enabled && state.context===data && state.scope===scope ? state : {data:null,loading:enabled && Boolean(data),error:"",stale:true,savedAt:null}),replace,reload:()=>setReloadCount(n=>n+1)};
}

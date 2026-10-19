import {decodeCableReview,encodeReviewSummary,type IndexedReview} from "./reviewEncoding.ts";
import type {CableReview,ResolvedLayout} from "./types";

const DATABASE="routing-overview",STORE="summaries",VERSION=1;
export const SUMMARY_MAX_AGE_MS=24*60*60*1000;
type Entry={key:string;signature:string;savedAt:number;version:1;summary:IndexedReview};
type CachedReview={review:CableReview;savedAt:number};

export function validSummary(entry:Entry|undefined,key:string,signature:string,now=Date.now()) {
  return Boolean(entry && entry.version===VERSION && entry.key===key && entry.signature===signature
    && entry.summary?.encoding==="indexed-v1" && entry.summary.scope==="hall"
    && Array.isArray(entry.summary.groups) && Array.isArray(entry.summary.loads) && Array.isArray(entry.summary.planning_segments)
    && [entry.summary.inventory_cable_count,entry.summary.routed_cable_count,entry.summary.unrouted_cable_count,entry.summary.same_cabinet_count].every(n=>Number.isInteger(n)&&n>=0)
    && entry.savedAt<=now && now-entry.savedAt<SUMMARY_MAX_AGE_MS);
}
// Compare the complete resolved geometry/configuration, including cabinet ordering and tiers.
export async function layoutSignature(data:ResolvedLayout) {
  const serialized=JSON.stringify(data);
  if (!globalThis.crypto?.subtle) return serialized;
  const hash=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(serialized));
  return [...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,"0")).join("");
}
function database():Promise<IDBDatabase> {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open(DATABASE,VERSION);
    request.onupgradeneeded=()=>request.result.createObjectStore(STORE,{keyPath:"key"});
    request.onerror=()=>reject(request.error);
    request.onblocked=()=>reject(new Error("Overview storage is unavailable."));
    request.onsuccess=()=>resolve(request.result);
  });
}
export async function readReviewSummary(data:ResolvedLayout):Promise<CachedReview|null> {
  let db:IDBDatabase|undefined;
  try {
    const signature=await layoutSignature(data),key=data.layout.uid;
    db=await database();
    const entry=await new Promise<Entry|undefined>((resolve,reject)=>{
      const transaction=db!.transaction(STORE,"readonly"),request=transaction.objectStore(STORE).get(key);
      request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
    });
    if(!validSummary(entry,key,signature)) return null;
    return {review:decodeCableReview(entry!.summary),savedAt:entry!.savedAt};
  } catch {return null;} finally {db?.close();}
}
export async function writeReviewSummary(data:ResolvedLayout,review:CableReview) {
  if(review.scope!=="hall") return;
  let db:IDBDatabase|undefined;
  try {
    const entry:Entry={key:data.layout.uid,signature:await layoutSignature(data),savedAt:Date.now(),version:1,summary:encodeReviewSummary(review)};
    db=await database();
    await new Promise<void>((resolve,reject)=>{
      const transaction=db!.transaction(STORE,"readwrite"),store=transaction.objectStore(STORE);
      store.put(entry);
      // Keep storage bounded even as more halls are introduced.
      const all=store.getAll();
      all.onsuccess=()=>{
        const entries=(all.result as Entry[]).sort((a,b)=>b.savedAt-a.savedAt);
        entries.forEach((item,index)=>{if(index>=2 || entry.savedAt-item.savedAt>=SUMMARY_MAX_AGE_MS) store.delete(item.key);});
      };
      transaction.oncomplete=()=>resolve();transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error);
    });
  } catch { /* Private browsing, quotas and corrupt storage must never block current API data. */ }
  finally {db?.close();}
}

/** A late disk result must not replace an authoritative network response. */
export class SummaryLoadGate {
  private current=false;
  private disposed=false;
  acceptCurrent(){if(this.disposed)return false;this.current=true;return true;}
  acceptSaved(){return !this.disposed && !this.current;}
  dispose(){this.disposed=true;}
}

// Optional full-inventory client audit. Inputs come from the read-only backend audit.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'esbuild';
import {decodeCableReview} from '../src/routing/reviewEncoding.ts';
import {ManualRouteEngine,emptyDraft} from '../src/routing/manualRouteEngine.ts';
import {conceptualLayout} from '../src/routing/conceptualLayout.ts';
import {placeRoutingCabinets} from '../src/routing/cabinetPlacement.ts';
import {reviewGroupsForPart} from '../src/routing/cableReviewProjection.ts';

const [reviewPath='../../tmp/routing-stability-audit-review.json',layoutPath='../../tmp/routing-stability-audit-layout.json',output='../../tmp/routing-client-audit.json']=process.argv.slice(2);
const raw=readFileSync(reviewPath,'utf8'),data=JSON.parse(readFileSync(layoutPath,'utf8'));
const started=performance.now(),review=decodeCableReview(JSON.parse(raw)),hydration=performance.now()-started;
const engineStarted=performance.now(),engine=new ManualRouteEngine(review.planning_segments),engineMs=performance.now()-engineStarted;
const sampled=review.groups.filter(g=>g.route).sort((a,b)=>b.route.planar_length_in-a.route.planar_length_in).slice(0,100);
const previews=[],bridges=[];
for(const group of sampled) {
  let now=performance.now();
  const preview=engine.preview(group,emptyDraft(group));
  assert.ok(preview.suggestion,'Missing local continuation');
  assert.ok(engine.isComplete(group,{...emptyDraft(group),ids:preview.suggestion.load_ids}));
  previews.push(performance.now()-now);
  const remote=preview.suggestion.load_ids[Math.floor(preview.suggestion.load_ids.length/2)];
  now=performance.now();
  const result=engine.connectPhysicalSegment(group,emptyDraft(group),[remote]);
  assert.ok(result.draft.ids.includes(remote));
  bridges.push(performance.now()-now);
}
const view=conceptualLayout(data,placeRoutingCabinets(data));
const compiled=await build({entryPoints:[resolve('src/routing/CableReviewLayer.tsx')],bundle:true,platform:'node',format:'cjs',packages:'external',write:false,logLevel:'silent'});
const mod={exports:{}};
new Function('require','module','exports',compiled.outputFiles[0].text)(createRequire(import.meta.url),mod,mod.exports);
const layer=mod.exports.CableReviewLayer;
const section=view.sections[0],common={data,view,review,scale:1,selectedGroupUid:null,onAttachment:()=>{},tiers:new Set([1,2,3])};
const summary=values=>{const sorted=[...values].sort((a,b)=>a-b);return {p50_ms:Math.round(sorted[Math.floor(sorted.length*.5)]),p95_ms:Math.round(sorted[Math.min(sorted.length-1,Math.floor(sorted.length*.95))]),max_ms:Math.round(sorted.at(-1))};};
const scopes={
  global:{},
  section1:{viewport:{x:-100,y:section.start-70,w:view.width+200,h:section.end-section.start+140}},
  segmentFocus:{selectionGroupUids:new Set(reviewGroupsForPart(review,sampled[0].route.segment_ids[0],null,null).map(g=>g.uid))},
};
const render={};
for(const [name,props] of Object.entries(scopes)) {
  const times=[];let html='';
  for(let i=0;i<3;i++){const now=performance.now();html=renderToStaticMarkup(React.createElement(layer,{...common,...props}));times.push(performance.now()-now);}
  assert.doesNotMatch(html,/NaN|undefined/);
  render[name]={...summary(times),svg_elements:(html.match(/<(?:g|line|path|circle|rect|text|title)\b/g)??[]).length};
}
const result={groups:review.groups.length,planning_segments:review.planning_segments.length,parse_and_hydrate_ms:Math.round(hydration),local_engine_init_ms:Math.round(engineMs),samples:sampled.length,local_preview:summary(previews),local_distant_segment_bridge:summary(bridges),server_render_only:render};
writeFileSync(output,JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));

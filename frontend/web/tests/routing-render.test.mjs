import assert from "node:assert/strict";
import test from "node:test";
import {createRequire} from "node:module";
import {resolve} from "node:path";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {build} from "esbuild";

const require = createRequire(import.meta.url);
async function component(file, name, withI18n = false) {
  const path = resolve(`src/routing/${file}.tsx`);
  const entry = withI18n ? {stdin: {contents: `import React from 'react'; import {${name} as Component} from ${JSON.stringify(path)}; import {I18nProvider} from ${JSON.stringify(resolve('src/i18n.tsx'))}; export function ${name}(props) {return React.createElement(I18nProvider, null, React.createElement(Component, props));}`, loader: "tsx", resolveDir: resolve(".")}} : {entryPoints: [path]};
  const result = await build({...entry, bundle: true, platform: "node", format: "cjs", packages: "external", write: false, logLevel: "silent", define: {"import.meta.env": "{}"}});
  const compiled = {exports: {}};
  new Function("require", "module", "exports", result.outputFiles[0].text)(require, compiled, compiled.exports);
  return compiled.exports[name];
}
const Section = await component("SectionOccupationDiagram", "SectionOccupationDiagram");
const Editor = await component("BundleSectionEditor", "BundleSectionEditor");
const Connections = await component("ConnectionSettings", "ConnectionSettings");
const TierEditor = await component("TierEditor", "TierEditor");
const TierSections = await component("TierSectionDiagrams", "TierSectionDiagrams");
const SegmentCables = await component("SegmentCables", "SegmentCables");
const CableReviewPanel = await component("CableReviewPanel", "CableReviewPanel");
const CableReviewLayer = await component("CableReviewLayer", "CableReviewLayer");
const OverviewStrokes = await component("OverviewStrokes", "OverviewStrokes");
const CabinetConnectionsPanel = await component("../components/CabinetConnectionsPanel", "CabinetConnectionsPanel", true);
const ManualBatchPanel = await component("ManualRouteBatchPanel", "ManualRouteBatchPanel");
const ManualLayer = await component("ManualRouteLayer", "ManualRouteLayer");
const RackPairCards = await component("RackPairRouteCards", "RackPairRouteCards");
const ConceptualGraph = await component("ConceptualGraph", "ConceptualGraph");
const PathwayInspector = await component("PathwayInspector", "PathwayInspector");
const ConceptualRoutingMap = await component("ConceptualRoutingMap", "ConceptualRoutingMap");
const RoutingOverview = await component("RoutingOverview", "RoutingOverview");
const routingOverviewCounts = await component("RoutingOverview", "routingOverviewCounts");
const DataHallSectionTabs = await component("../components/DataHallSectionTabs", "DataHallSectionTabs");
const routeStrokeLines = await component("RouteStroke", "routeStrokeLines");
const RoutingLoadStatus = await component("RoutingLoadStatus", "RoutingLoadStatus");

test("map loading notice distinguishes cold load, saved-route refresh, failure and ready state", () => {
  const props={loading:false,hasRoutes:false,error:'',onRetry:()=>{}};
  const render=values=>renderToStaticMarkup(React.createElement(RoutingLoadStatus,{...props,...values}));
  assert.equal(render({}),'');
  const cold=render({loading:true});
  assert.match(cold,/role="status" aria-live="polite" aria-atomic="true"/);
  assert.match(cold,/Loading cable route data/); assert.match(cold,/map-loading-spinner/);
  assert.doesNotMatch(cold,/Retry loading|\d+%/);
  assert.match(render({layoutLoading:true}),/Loading routing layout/);
  const refresh=render({loading:true,hasRoutes:true});
  assert.match(refresh,/Updating cable routes/); assert.match(refresh,/Saved routes remain visible/);
  assert.doesNotMatch(refresh,/could not be loaded/);
  const failure=render({error:'Request failed'});
  assert.match(failure,/Cable route data could not be loaded/); assert.match(failure,/Retry loading/);
  assert.doesNotMatch(failure,/map-loading-spinner/);
  const saved=render({hasRoutes:true,error:'Request failed'});
  assert.match(saved,/Showing saved cable routes/); assert.match(saved,/route editing is unavailable/);
  assert.match(saved,/Retry loading/);
});

test("route section tabs keep filtered counts through navigation, including active and empty sections", () => {
  const counts=new Map([['DH1-1',3],['DH1-2',0],['DH1-3',2]]);
  let hall='DH1-1';
  const props=()=>({dataHall:hall,dataHalls:[...counts.keys()],label:'Data-hall sections',routingGroupCounts:counts,
    connectedDataHallCounts:new Map([['DH1-3',999]]),dataHallBadges:new Map([['DH1-3',{count:999,added:2,removed:1}]]),onDataHallChange:next=>{hall=next;}});
  const tree=DataHallSectionTabs(props());
  tree.props.children[2].props.onClick();
  assert.equal(hall,'DH1-3');
  const html=renderToStaticMarkup(React.createElement(DataHallSectionTabs,props()));
  assert.match(html,/aria-selected="true" title="2 filtered cable groups with a cabinet in DH1-3"/);
  assert.match(html,/aria-label="3 filtered cable groups">3<\/b>/);
  assert.match(html,/aria-label="0 filtered cable groups">0<\/b>/);
  assert.doesNotMatch(html,/999|has-positive-delta|has-negative-delta/);
  assert.deepEqual([...counts],[['DH1-1',3],['DH1-2',0],['DH1-3',2]]);
  const cabinetMode=renderToStaticMarkup(React.createElement(DataHallSectionTabs,{...props(),routingGroupCounts:null,dataHall:'DH1-1'}));
  assert.match(cabinetMode,/999\+2-1/);
  assert.doesNotMatch(cabinetMode,/filtered cable groups/);
  const neighbors=renderToStaticMarkup(React.createElement(DataHallSectionTabs,{...props(),routingGroupCounts:null,dataHallBadges:undefined}));
  assert.doesNotMatch(neighbors,/data-hall-graph-count/,'Current hall still suppresses its ordinary neighbor badge');
});

test("overview counts include local inventory, split special colors once, and distinguish manual assignments", () => {
  const group=(cable_class,count,route_source='DEFAULT',route={})=>({cable_class,count,route_source,route});
  const review={label:'All five sections',inventory_cable_count:182,routed_cable_count:23,unrouted_cable_count:13,same_cabinet_count:146,
    cable_types:{LC:100,CAT6a:50,'MPO12-SMF':30,RJ12:2},
    groups:[group('LC',10),group('CROSS_SECTION_LC',5),group('MPO_TRUNK_T2_T1_RO',6),group('LC',2,'MANUAL'),group('MPO',1,'MANUAL',null)],
    loads:[{cable_count:999999}],notes:'Policy details'};
  const totals=routingOverviewCounts(review);
  assert.equal(totals.colors.LC,95); assert.equal(totals.colors.CROSS_SECTION_LC,5);
  assert.equal(totals.colors.MPO,24); assert.equal(totals.colors.MPO_TRUNK_T2_T1_RO,6);
  assert.equal(Object.values(totals.colors).reduce((a,b)=>a+b,totals.other),182);
  assert.deepEqual([totals.defaultRoutes,totals.defaultCables,totals.manualRoutes,totals.manualCables,totals.invalidManualRoutes],[3,21,2,3,1]);
  const html=renderToStaticMarkup(React.createElement(RoutingOverview,{review}));
  assert.match(html,/Routed cables/); assert.match(html,/Unrouted cables/);
  assert.match(html,/Default routes/); assert.match(html,/Manual routes/); assert.match(html,/1 invalid/);
  assert.match(html,/<details class="routing-overview-description"><summary>Description<\/summary>/);
  assert.match(html,/<span><i[^>]*><\/i>LC<\/span><b>95<\/b><\/button><\/li>/);
  assert.match(html,/All inventory cables/);
  assert.doesNotMatch(html,/Confirmed routes|NaN|undefined/);
  const selected=renderToStaticMarkup(React.createElement(RoutingOverview,{review,filter:'MANUAL',onFilterChange:()=>{}}));
  assert.equal((selected.match(/class="routing-overview-stat"/g)??[]).length,4);
  assert.equal((selected.match(/aria-pressed="true"/g)??[]).length,1);
  assert.match(selected,/aria-pressed="true"><span>Manual routes<\/span>/);
  assert.match(selected,/Manual routes selected/); assert.match(selected,/Clear filter/);
  const busy=renderToStaticMarkup(React.createElement(RoutingOverview,{review,disabled:true}));
  assert.equal((busy.match(/class="routing-overview-stat" aria-pressed="false" disabled=""/g)??[]).length,4);
  const legend=renderToStaticMarkup(React.createElement(RoutingOverview,{review,cableTypeFilter:'LC'}));
  assert.match(legend,/class="routing-legend-filter" aria-pressed="true"><span><i[^>]*><\/i>LC/);
  assert.equal((legend.match(/class="routing-legend-filter" aria-pressed="true"/g)??[]).length,1);
  assert.match(legend,/Show all cable types/);
});

test("zoomed-out strokes continue shrinking below the former minimum, including selected outlines", () => {
  const props={a:{x:0,y:0},b:{x:120,y:0},cableClasses:['LC','MPO','CAT6'],tier:2};
  const widths=[1,.4,.08,.02,.005].map(scale=>routeStrokeLines({...props,scale,selected:true}));
  for(let i=1;i<widths.length;i++) for(let lane=0;lane<widths[i].length;lane++) assert.ok(widths[i][lane].width<widths[i-1][lane].width);
  assert.ok(widths.at(-1)[1].width<.1);
  const full=routeStrokeLines({...props,scale:1});
  assert.equal(full.length,3); assert.equal(full[0].width,5);
  assert.deepEqual(full.map(line=>line.cableClass),['LC','MPO','CAT6']);
});

test("legend filtering removes other colors on shared routes and keeps map and cable cards consistent", () => {
  const p=x=>({x_in:x,y_in:382,tier:1,passage_band_uid:'central',cabinet_uid:null});
  const base={source_cabinet_uid:'a',destination_cabinet_uid:'b',source_cabinet_id:'801',destination_cabinet_id:'811',start_tier:1,end_tier:1,count:2,cable_uids:[],route_source:'DEFAULT'};
  const group=(uid,cable_class)=>({...base,uid,cable_class,cable_type:cable_class,route:{points:[p(0),p(120)],planar_length_in:120}});
  const groups=[group('lc','LC'),group('mpo','MPO'),group('cat6','CAT6')];
  const load=(id,group_uids,cable_classes,x)=>({id,source:p(x),target:p(x+120),group_uids,cable_classes,cable_count:4,tier:1,edge_type:'PASSAGE'});
  const review={groups,cables:[],loads:[load('shared',['lc','mpo'],['LC','MPO'],0),load('lc-rest',['lc'],['LC'],120),load('excluded',['cat6'],['CAT6'],240)]};
  const props={data:{geometry:{bands:[],cabinet_rows:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},review,selectedGroupUid:null,onAttachment:()=>{}};
  for(const scale of [1,.08]) {
    const html=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,scale,cableTypeFilter:'LC'}));
    assert.match(html,/data-cable-class="LC"/); assert.doesNotMatch(html,/data-cable-class="MPO"|data-cable-class="CAT6"/);
    assert.doesNotMatch(html,/#ffcc66|data-route-muted=/,'Legend filters do not highlight every remaining segment or draw excluded cables');
    const status=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,scale,summaryFilter:'ROUTED'}));
    assert.doesNotMatch(status,/#ffcc66/,'Summary-wide filtering must not add thousands of selection halos');
    const focused=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,scale,cableTypeFilter:'LC',focusedPairKey:JSON.stringify(['a','b'])}));
    assert.match(focused,/#ffcc66/,'An explicit rack-pair selection still has a route highlight');
  }
  const panel=renderToStaticMarkup(React.createElement(CableReviewPanel,{review,groups,cableTypeFilter:'LC',focusedPairKey:JSON.stringify(['a','b']),onViewCables:()=>{}}));
  assert.match(panel,/View LC cable details/); assert.doesNotMatch(panel,/View MPO cable details|View CAT6 cable details/);
  assert.match(panel,/Show all cable types/); assert.match(panel,/2 mapped cables/);
});

test("summary-filtered rack cards cannot expand to unrelated statuses on the same pair", () => {
  const base={source_cabinet_uid:'a',destination_cabinet_uid:'b',source_cabinet_id:'801',destination_cabinet_id:'811',start_tier:1,end_tier:1,count:2,cable_uids:[]};
  const groups=[{...base,uid:'default',cable_type:'LC',route_source:'DEFAULT',route:{planar_length_in:120}},
    {...base,uid:'manual',cable_type:'MPO',route_source:'MANUAL',route:{planar_length_in:120}},
    {...base,uid:'unrouted',cable_type:'CAT6a',route_source:'DEFAULT',route:null}];
  const props={review:{groups,cables:[],unmapped_cable_count:8},groups,focusedPairKey:JSON.stringify(['a','b']),onViewCables:()=>{}};
  const manual=renderToStaticMarkup(React.createElement(CableReviewPanel,{...props,summaryFilter:'MANUAL'}));
  assert.match(manual,/View MPO cable details/);
  assert.doesNotMatch(manual,/View LC cable details|View CAT6a cable details/);
  assert.match(manual,/Matching cable types for this rack pair/);
  const unrouted=renderToStaticMarkup(React.createElement(CableReviewPanel,{...props,summaryFilter:'UNROUTED'}));
  assert.match(unrouted,/View CAT6a cable details/);
  assert.doesNotMatch(unrouted,/View LC cable details|View MPO cable details/);
  assert.match(unrouted,/2 mapped cables · 1 rack-pair\/type groups/);
  assert.match(unrouted,/Another 8 cables.*unmapped endpoints/);
  assert.match(unrouted,/No assigned path to highlight/);
});

test("summary map filters keep complete matching paths colored and unrouted focus mutes all paths", () => {
  const p=x=>({x_in:x,y_in:382,tier:1,passage_band_uid:'central',cabinet_uid:null});
  const group=(uid,cable_class,route_source,route)=>({uid,cable_class,source_cabinet_uid:'a',destination_cabinet_uid:'b',route_source,route:route ? {points:[p(0),p(120)]} : null});
  const load=(id,ids,classes,x)=>({id,source:p(x),target:p(x+120),group_uids:ids,cable_classes:classes,cable_count:4,tier:1,edge_type:'PASSAGE'});
  const review={groups:[group('default','LC','DEFAULT',{}),group('manual','MPO','MANUAL',{}),group('unrouted','CAT6','DEFAULT',null)],loads:[
    load('shared',['default','manual'],['LC','MPO'],0),load('default-rest',['default'],['LC'],120),load('manual-rest',['manual'],['MPO'],240)]};
  const props={data:{geometry:{bands:[],cabinet_rows:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},review,scale:1,selectedGroupUid:null,onAttachment:()=>{}};
  for (const scale of [1,.1]) {
    const defaults=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,scale,summaryFilter:'DEFAULT'}));
    assert.match(defaults,/data-cable-class="LC"/); assert.doesNotMatch(defaults,/data-cable-class="MPO"/);
    assert.match(defaults,scale<.12 ? /stroke="#cbd2d9"/ : /stroke="#4b5057"/);
    const unrouted=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,scale,summaryFilter:'UNROUTED'}));
    assert.doesNotMatch(unrouted,/data-cable-class=/); assert.match(unrouted,scale<.12 ? /stroke="#cbd2d9"/ : /stroke="#4b5057"/);
    const manual=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,scale,summaryFilter:'MANUAL',focusedPairKey:JSON.stringify(['a','b'])}));
    assert.match(manual,/data-cable-class="MPO"/); assert.doesNotMatch(manual,/data-cable-class="LC"/);
  }
});

test("pathway user guide is collapsed without hiding geometry", () => {
  const data={layout:{physical_hall_code:'DH1',row_pair_module_in:264,section_extra_gap_in:216},
    bands:[],cabinets:[],cross_routes:[],cabinet_rows:[],sections:[],vertical_transitions:[],
    geometry:{cabinet_rows:[],cross_routes:[],sections:[],gaps:[],bands:[],total_width_in:788,hall_length_in:11544}};
  const html=renderToStaticMarkup(React.createElement(PathwayInspector,{data,graph:{nodes:[],edges:[]},selection:null,segment:null,
    attachmentUid:null,canManage:false,busy:false,mutate:async()=>true,onSelect:()=>{},onOpenRouting:()=>{},selectedPlacementUid:null,onSelectPlacement:()=>{}}));
  assert.match(html,/<details class="routing-guide"><summary>Inspect a pathway<\/summary>/);
  assert.match(html,/<details class="routing-geometry-summary" open="">/);
});

test("conceptual viewport keeps direct zoom controls and collapses section options instead of a tall toolbar", () => {
  const data={layout:{cabinets_per_row:10,cabinet_row_depth_in:24},cabinets:[],vertical_transitions:[],segment_annotations:[],
    geometry:{bands:[],sections:[],gaps:[],row_pairs:[],cabinet_rows:[],cross_routes:[],hall_length_in:0}};
  const html=renderToStaticMarkup(React.createElement(ConceptualRoutingMap,{data,graph:{nodes:[],edges:[]},tiers:new Set([1,2,3]),selection:null,
    onSelect:()=>{},initialSectionUid:'',cabinetInteraction:{selected:new Set(),connected:new Set()},
    settings:{cellWidth:46,cellHeight:30,hotAisleGap:10},renderCabinets:()=>null,segments:[],selectedSegmentId:null,onSelectSegment:()=>{}}));
  assert.match(html,/class="conceptual-map-controls"/);
  assert.match(html,/aria-label="Zoom in"/);
  assert.match(html,/Fit \/ reset view/);
  assert.match(html,/<details class="conceptual-view-options"><summary>Sections \/ focus/);
  assert.match(html,/class="routing-svg conceptual-svg"/);
  assert.doesNotMatch(html,/routing-view-footer|Geometric routing map|Review cable groups|NaN|undefined/);
});

test("physical junction inspection shows every tier instead of one graph node's tier", () => {
  const band={uid:'central',kind:'PASSAGE',code:'CENTRAL',width_in:24,center_in:382,ordinal:2};
  const nodes=[1,2,3].map(tier=>({id:`node${tier}`,tier,passage_code:'CENTRAL',passage_band_uid:'central',station_in:900,x_in:900,y_in:382,label:null}));
  const data={layout:{physical_hall_code:'DH1',longitudinal_direction:'EAST',bottom_basket_elevation_in:98},
    bands:[band],geometry:{bands:[band],cabinet_rows:[],cross_routes:[],sections:[],gaps:[],hall_length_in:1000,total_width_in:788},
    passage_tiers:[1,2,3].map(tier=>({tier,passage_band_uid:'central',enabled:true,pathway_type:tier===1?'BASKET_TRAY':'LADDER_RACK',effective_elevation_in:98+(tier-1)*12})),
    cross_route_tiers:[],vertical_transitions:[],segment_annotations:[],bundle_placements:[],bundle_connections:[],cabinet_attachments:[],section_occupations:[],cabinets:[],cross_routes:[],cabinet_rows:[],sections:[]};
  const html=renderToStaticMarkup(React.createElement(PathwayInspector,{data,graph:{nodes,edges:[]},selection:{kind:'node',uid:'node1'},segment:null,attachmentUid:null,canManage:false,busy:false,mutate:async()=>true,onSelect:()=>{},onOpenRouting:()=>{},selectedPlacementUid:null,onSelectPlacement:()=>{},reviewGroupCount:406}));
  assert.match(html,/CENTRAL junction/);
  for(const tier of [1,2,3]) assert.match(html,new RegExp(`aria-label="T${tier} 12 by 8 occupation grid`));
  assert.match(html,/406 actual type\/rack-pair groups/);
  assert.doesNotMatch(html,/Junction.*Tier 1<\/h3>|Stable node ID/);
});

test("unselected pathway summary carries overview status without requiring a cable inspector", () => {
  const data={layout:{physical_hall_code:'DH1',row_pair_module_in:264,section_extra_gap_in:216},
    bands:[],cabinets:[],cross_routes:[],cabinet_rows:[],sections:[],vertical_transitions:[],
    geometry:{cabinet_rows:[],cross_routes:[],sections:[],gaps:[],bands:[],total_width_in:788,hall_length_in:11544}};
  const html=renderToStaticMarkup(React.createElement(PathwayInspector,{data,graph:{nodes:[],edges:[]},selection:null,segment:null,
    attachmentUid:null,canManage:false,busy:false,mutate:async()=>true,onSelect:()=>{},onOpenRouting:()=>{},selectedPlacementUid:null,onSelectPlacement:()=>{},
    overview:React.createElement('p',{className:'actual-review-notice',role:'status'},'Full hall cable summary')}));
  assert.match(html,/Pathway metadata and geometry/);
  assert.match(html,/Full hall cable summary/);
  assert.match(html,/Geometric summary/);
  assert.doesNotMatch(html,/NaN|undefined/);
});

test("conceptual junctions have one click target across three graph tiers", () => {
  const nodes=[1,2,3].map(tier=>({id:`n${tier}`,tier,node_type:'JUNCTION',x_in:120,y_in:382,station_in:120,passage_code:'CENTRAL',passage_band_uid:'central'}));
  const html=renderToStaticMarkup(React.createElement(ConceptualGraph,{data:{vertical_transitions:[]},graph:{nodes,edges:[]},view:{projectNode:()=>({x:10,y:120})},scale:1,tiers:new Set([1,2,3]),selection:null,onSelect:()=>{}}));
  assert.equal((html.match(/data-physical-junction=/g)??[]).length,1);
  assert.equal((html.match(/role="button"/g)??[]).length,1);
  assert.match(html,/Tier 1 \/ Tier 2 \/ Tier 3/);
  assert.doesNotMatch(html,/Select node n[123]/);
});

test("manual pathway targets combine tiers while retaining each physical opening", () => {
  const p=(x,tier)=>({node_id:`${x}:${tier}`,x_in:x,y_in:382,tier,passage_band_uid:'central',cabinet_uid:null});
  const segments=[1,2,3].map(tier=>({id:`edge${tier}`,segment_id:'physical',label:'Central R1–2',source:p(0,tier),target:p(120,tier),tier,edge_type:'PASSAGE'}));
  const html=renderToStaticMarkup(React.createElement(ManualLayer,{data:{geometry:{bands:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},segments,preview:null,scale:1,onAppend:()=>{},onSegments:()=>{},disabled:false,tiers:new Set([1,2,3])}));
  assert.equal((html.match(/class="manual-segment-target"/g)??[]).length,1);
  assert.match(html,/aria-label="Route via Central R1–2"/);
});

test("full inventory rack cards paginate and expose search instead of rendering the whole hall", () => {
  const groups = Array.from({length:500},(_,i)=>({uid:`g${i}`,source_cabinet_uid:`s${i}`,destination_cabinet_uid:`z${i}`,source_cabinet_id:String(i),destination_cabinet_id:String(i+801),cable_type:'LC',count:100,cable_uids:[],route:null,start_tier:2,end_tier:2,route_source:'DEFAULT'}));
  const html = renderToStaticMarkup(React.createElement(RackPairCards,{review:{groups,cables:[],scope:'hall'},groups,focusedKey:null,onFocus:()=>{},canManage:false,onViewCables:()=>{}}));
  assert.equal((html.match(/<article class="connection-item/g) ?? []).length,40);
  assert.match(html,/Find rack pair or cable type/);
  assert.match(html,/500 rack pairs · page 1 \/ 13/);
  assert.match(html,/Next rack pairs/);
});
const box = {uid: "g", tier: 1, label: "G1", cable_class: "LC", sourceAvailable: true, layer: 1, position: 1, slot_width: 3, slot_height: 2, offset_across_in: 0, offset_up_in: 0, occupied_width_in: 4, occupied_height_in: 2};
const span = {id: "span", passage_band_uid: "north", cross_route_uid: null, start_station_in: 0, end_station_in: 108, from_passage_band_uid: null, to_passage_band_uid: null};

const directions = {inner: "SOUTH", hasInner: true, axisStart: "NORTH"};
const sectionModel = {blocks: [box], parents: [], occupations: [], width_in: 34, reference: "Saved section", directions};

test("manual editor shows local next choices and disables incomplete batch saves", () => {
  const p = {node_id:'start',x_in:0,y_in:382,tier:1,passage_band_uid:'central',cabinet_uid:'s'};
  const path = {method:'MANUAL',points:[p],load_ids:[],segment_ids:[],planar_length_in:0,vertical_transition_count:0};
  const group = {uid:'g',source_cabinet_uid:'s',destination_cabinet_uid:'z',source_cabinet_id:'801',destination_cabinet_id:'811',cable_type:'LC',count:4,route_source:'DEFAULT',start_tier:1,end_tier:1};
  const editor = {selected:['g'],editing:true,active:group,activeUid:'g',groups:[group],complete:()=>false,completed:0,canSave:false,
    draft:{ids:[],startTier:1,endTier:1},preview:{complete:false,prefix:path,suggestion:{...path,planar_length_in:120},next_chains:[]},notes:'',busy:false,error:'',message:''};
  const html = renderToStaticMarkup(React.createElement(ManualBatchPanel,{editor,shownGroups:[group],canManage:true}));
  assert.match(html,/All clicks and suggestions stay local/);
  assert.match(html,/class="manual-save" disabled=""/);
  assert.match(html,/Fill remainder with A\*/);
  assert.match(html,/Source route tier/);
  assert.match(html,/Destination route tier/);
  const complete = renderToStaticMarkup(React.createElement(ManualBatchPanel,{editor:{...editor,canSave:true,completed:1,preview:{...editor.preview,complete:true,suggestion:null}},shownGroups:[group],canManage:true}));
  assert.match(complete,/Complete chain/);
  assert.doesNotMatch(complete,/class="manual-save" disabled=""/);
});

test("manual SVG provides keyboard-accessible connected chain choices", () => {
  const p = x => ({node_id:`n-${x}`,x_in:x,y_in:382,tier:1,passage_band_uid:'central',passage_code:'CENTRAL',cabinet_uid:null});
  const chain = {id:'choice',label:'Central R1–2',points:[p(0),p(120)],load_ids:['edge'],vertical_transition_count:0,planar_length_in:120};
  const html = renderToStaticMarkup(React.createElement(ManualLayer,{data:{geometry:{bands:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},segments:[],preview:{prefix:{points:[p(0)]},suggestion:chain,next_chains:[chain],destination:p(120)},scale:1,onAppend:()=>{},disabled:false}));
  assert.match(html,/Append Central R1–2 to CENTRAL · Tier 1/);
  assert.match(html,/role="button" tabindex="0"/);
  assert.match(html,/stroke-dasharray="7 6"/);
  assert.match(html,/no request is sent/);
});
test("manual SVG makes distant enabled segments accessible and locks them after completion", () => {
  const p = (x,tier=1) => ({node_id:`n-${x}-${tier}`,x_in:x,y_in:382,tier,passage_band_uid:'central',passage_code:'CENTRAL',cabinet_uid:null});
  const segment={id:'remote',label:'Central R3–4',source:p(240),target:p(360),edge_type:'PASSAGE'};
  const props={data:{geometry:{bands:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},segments:[segment,{...segment,id:'hidden',source:p(240,2),target:p(360,2)}],
    preview:{complete:false,prefix:{points:[p(0)]},next_chains:[],destination:p(480)},scale:1,onAppend:()=>{},onSegment:()=>{},disabled:false,tiers:new Set([1])};
  const html=renderToStaticMarkup(React.createElement(ManualLayer,props));
  assert.match(html,/data-planning-segment-id="remote" data-physical-pathway="[^"]+" role="button" tabindex="0"/);
  assert.match(html,/aria-label="Route via Central R3–4"/);
  assert.match(html,/local A\* connects the closer reachable endpoint/);
  assert.match(html,/<rect x="1" y="231" width="18" height="138" fill="transparent"/);
  assert.doesNotMatch(html,/data-planning-segment-id="hidden"/);
  const complete=renderToStaticMarkup(React.createElement(ManualLayer,{...props,preview:{...props.preview,complete:true}}));
  assert.match(complete,/data-planning-segment-id="remote" data-physical-pathway="[^"]+" role="button" tabindex="-1"/);
  assert.match(complete,/aria-disabled="true"/);
});

test("section display mode renders only the selected representation", () => {
  const props = {tier: 1, model: sectionModel, mode: "GRID", reversed: false, onSelectPlacement: () => {}};
  const html = renderToStaticMarkup(React.createElement(Section, props));
  assert.match(html, /12W × 8H grid/);
  assert.doesNotMatch(html, /Physical rectangles/);
  assert.match(html, /3×2 cells/);
  assert.equal((html.match(/stroke="#cbd5e1"/g) ?? []).length, 96);
  assert.doesNotMatch(html, /NaN|undefined|null/);
  const physical = renderToStaticMarkup(React.createElement(Section, {...props, mode: "PHYSICAL"}));
  assert.match(physical, /Physical rectangles/);
  assert.match(physical, /Section height unknown/);
  assert.doesNotMatch(physical, /DEMO|Display.only/);
  assert.doesNotMatch(physical, /occupation grid|stroke="#cbd5e1"/);
  assert.match(physical, /Inspect rectangle G1/);
});

test("section grid displays the saved multi-cell bundle matrix without generating demo placement", () => {
  const cells=Array.from({length:8},(_,y)=>Array.from({length:12},(_,x)=>y<2 && x<3 ? 1 : 0));
  const model={...sectionModel,parents:[{uid:'section',tier:null,grid_columns:12,grid_rows:8}],occupations:[{segment_annotation_uid:'section',tier:1,cells,occupants:[{placement_uid:'g',value:1}]}]};
  const before=structuredClone(model);
  const html=renderToStaticMarkup(React.createElement(Section,{tier:1,model,mode:'GRID',reversed:false,onSelectPlacement:()=>{}}));
  assert.equal((html.match(/fill="#246bfe25"/g)??[]).length,6);
  assert.equal((html.match(/Inspect G1/g)??[]).length,1);
  assert.doesNotMatch(html,/DEMO|Display.only/);
  assert.deepEqual(model,before);
});

test("empty unconfigured segments still show an empty section in both display modes", () => {
  for (const mode of ["GRID", "PHYSICAL"]) {
    const html = renderToStaticMarkup(React.createElement(Section, {tier: null, model: {...sectionModel, blocks: []}, mode, reversed: false, onSelectPlacement: () => {}}));
    assert.match(html, /Unassigned tier section/);
    assert.match(html, /Empty section/);
    assert.match(html, /<svg/);
    assert.doesNotMatch(html, /T1 section|NaN|undefined/);
  }
});

test("reverse view mirrors a footprint and cardinal labels, without mirroring text", () => {
  const props = {tier: 1, model: sectionModel, mode: "PHYSICAL", onSelectPlacement: () => {}};
  const forward = renderToStaticMarkup(React.createElement(Section, {...props, reversed: false}));
  const reverse = renderToStaticMarkup(React.createElement(Section, {...props, reversed: true}));
  assert.match(forward, /Inner · South to Outer · North/);
  assert.match(reverse, /Outer · North to Inner · South/);
  assert.match(forward, /<rect x="45"/);
  assert.doesNotMatch(reverse, /<rect x="45"/);
  const central = renderToStaticMarkup(React.createElement(Section, {...props, model: {...sectionModel, directions: {...directions, inner: null, hasInner: false}}, reversed: false}));
  assert.match(central, /North to South/);
  assert.doesNotMatch(central, /Inner ·|Outer ·|Inner side not assigned/);
});

test("selected group opens the enlarged section above the main section and exposes view controls", () => {
  const html = renderToStaticMarkup(React.createElement(TierSections, {data: {bands: []}, model: {...sectionModel, tiers: [1], records: [], markedClasses: {}, openings: []}, mode: "GRID", reversed: false, selectedPlacementUid: "g", onSelectPlacement: () => {}, onModeChange: () => {}, onReverse: () => {}}));
  assert.match(html, /Reverse section viewing direction/);
  assert.match(html, /Section display mode/);
  assert.ok(html.indexOf("Enlarged bundle section") < html.indexOf("T1 section"));
  assert.match(html, /Individual cable positions inside the bundle are not yet recorded/);
});


test("actual review groups show type detail actions and configured endpoint tiers without inline cables", () => {
  const group = {uid: 'g', source_cabinet_id: '001', destination_cabinet_id: '011', cable_type: 'LC-TO-LC SMF', cable_uids: ['actual-1'], count: 1, route: {method: 'ASTAR', planar_length_in: 120}};
  const cables = [{uid: 'actual-1', cable_type: 'LC-TO-LC SMF', cable_class: 'LC', source_cabinet_id: '001', destination_cabinet_id: '011', source_port_name: 'P1', destination_port_name: 'P2', source_label: 'A01', destination_label: 'Z01', notes: ''}];
  const html = renderToStaticMarkup(React.createElement(CableReviewPanel, {review: {cables}, groups: [group], selectedGroupUid: 'g', onGroup: () => {}, onViewCables: () => {}}));
  assert.match(html, /Suggested/);
  assert.match(html, /View LC-TO-LC SMF cable details/);
  assert.doesNotMatch(html, /actual-1|A01|connection-cable-row|Cable details/);
  assert.match(html, /unassigned/); assert.doesNotMatch(html, /fixture cable|Fake review/);
  assert.match(html, /Tier 1 → Tier 1/);
});

test("focused rack-pair cards expose type squares and Set/Change actions without the old picker", () => {
  const base={source_cabinet_uid:'a',destination_cabinet_uid:'b',source_cabinet_id:'801',destination_cabinet_id:'811',start_tier:1,end_tier:1,count:4,route_source:'DEFAULT',manual_status:null,cable_uids:[]};
  const groups=[{...base,uid:'lc',cable_type:'LC'},{...base,uid:'mpo',cable_type:'MPO',route_source:'MANUAL',manual_revision:2}];
  const editor={selected:['lc'],groups:[groups[0]],busy:false};
  const props={review:{groups,cables:[]},groups:[groups[0]],focusedKey:JSON.stringify(['a','b']),onFocus:()=>{},editor,canManage:true,onViewCables:()=>{}};
  const html=renderToStaticMarkup(React.createElement(RackPairCards,props));
  assert.match(html,/Focus rack pair 801 ↔ 811" aria-pressed="true"/);
  assert.match(html,/Select LC route · 801 ↔ 811/);
  assert.match(html,/Select MPO route · 801 ↔ 811/);
  assert.match(html,/aria-label="Set route · 801 ↔ 811"/);
  assert.match(html,/View LC cable details/);
  assert.match(html,/View MPO cable details/);
  assert.doesNotMatch(html,/manual-group-picker|Actual cable group|Edit selected routes/);
  const changed=renderToStaticMarkup(React.createElement(RackPairCards,{...props,editor:{...editor,selected:['lc','mpo'],groups}}));
  assert.match(changed,/aria-label="Change route · 801 ↔ 811"/);
  assert.match(changed,/2 types selected/);
  const viewer=renderToStaticMarkup(React.createElement(RackPairCards,{...props,canManage:false}));
  assert.match(viewer,/Focus rack pair/);
  assert.doesNotMatch(viewer,/type="checkbox"|route-card-edit/);
});

test("rack-pair map focus keeps its cable classes and renders unrelated shared routes grey", () => {
  const p=x=>({x_in:x,y_in:382,tier:1,passage_band_uid:'central',cabinet_uid:null});
  const group=(uid,cable_class,destination='b')=>({uid,cable_class,source_cabinet_uid:'a',destination_cabinet_uid:destination});
  const load=(id,group_uids,cable_classes,x)=>({id,source:p(x),target:p(x+120),group_uids,cable_classes,cable_count:4,tier:1,edge_type:'PASSAGE'});
  const review={groups:[group('lc','LC'),group('mpo','MPO'),group('other','CAT6','c')],cabinet_uids:[],loads:[load('shared',['lc','other'],['LC','CAT6'],0),load('mpo',['mpo'],['MPO'],120),load('other',['other'],['CAT6'],240)]};
  const props={data:{geometry:{bands:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},review,scale:1,selectedGroupUid:null,selectedLoadId:'other',focusedPairKey:JSON.stringify(['a','b']),onLoad:()=>{},onAttachment:()=>{}};
  const html=renderToStaticMarkup(React.createElement(CableReviewLayer,props));
  assert.equal((html.match(/data-route-muted="true"/g)??[]).length,1);
  assert.match(html,/data-cable-class="LC"/);
  assert.match(html,/data-cable-class="MPO"/);
  assert.doesNotMatch(html,/data-cable-class="CAT6"/);
  assert.match(html,/stroke="#4b5057"/);
  const all=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,focusedPairKey:null}));
  assert.doesNotMatch(all,/data-route-muted/);
  assert.match(all,/data-cable-class="CAT6"/);
});

test("selecting cabinets mutes unrelated cable types even on shared route segments", () => {
  const p=x=>({x_in:x,y_in:382,tier:2,passage_band_uid:'central',cabinet_uid:null});
  const groups=[{uid:'selected',cable_class:'LC',source_cabinet_uid:'801',destination_cabinet_uid:'811'},
    {uid:'incoming',cable_class:'MPO',source_cabinet_uid:'820',destination_cabinet_uid:'801'},
    {uid:'other',cable_class:'CAT6',source_cabinet_uid:'021',destination_cabinet_uid:'031'}];
  const load=(id,ids,classes,x)=>({id,source:p(x),target:p(x+120),group_uids:ids,cable_classes:classes,cable_count:10,tier:2,edge_type:'PASSAGE'});
  const props={data:{geometry:{bands:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},
    review:{groups,cabinet_uids:[],loads:[load('shared',['selected','other'],['LC','CAT6'],0),load('incoming',['incoming'],['MPO'],120),load('other',['other'],['CAT6'],240)]},
    scale:1,selectedGroupUid:null,selectedLoadId:null,onLoad:()=>{},onAttachment:()=>{},selectedCabinetUids:new Set(['801'])};
  const selected=renderToStaticMarkup(React.createElement(CableReviewLayer,props));
  assert.equal((selected.match(/data-route-muted="true"/g)??[]).length,1);
  assert.match(selected,/data-cable-class="LC"/); assert.match(selected,/data-cable-class="MPO"/); assert.doesNotMatch(selected,/data-cable-class="CAT6"/);
  const multi=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,selectedCabinetUids:new Set(['801','021'])}));
  assert.doesNotMatch(multi,/data-route-muted/); assert.match(multi,/data-cable-class="CAT6"/);
  const empty=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,selectedCabinetUids:new Set(['missing'])}));
  assert.equal((empty.match(/data-route-muted="true"/g)??[]).length,3); assert.doesNotMatch(empty,/data-cable-class=/);
});

test("large real cable groups stay summarized until their detail table is requested", () => {
  const cables = Array.from({length: 200}, (_, i) => ({uid: `actual-${i}`, cable_type: 'CAT6a', source_cabinet_id: '001', destination_cabinet_id: '002'}));
  const html = renderToStaticMarkup(React.createElement(SegmentCables, {inventoryCables: cables, onViewCables: () => {}}));
  assert.match(html, /200 cables/);
  assert.match(html, /View CAT6a cable details/);
  assert.doesNotMatch(html, /connection-cable-row|actual-\d|Show 60 more/);
});

test("pathway summaries combine both A/Z directions and defer individual cable lists", () => {
  const inventoryCables = [
    {uid: "a", cable_type: "LC", source_cabinet_id: "801", destination_cabinet_id: "811"},
    {uid: "b", cable_type: "LC", source_cabinet_id: "811", destination_cabinet_id: "801"},
    {uid: "c", cable_type: "CAT6a", source_cabinet_id: "801", destination_cabinet_id: "820"},
  ];
  const props = {inventoryCables, onViewCables: () => {}};
  const html = renderToStaticMarkup(React.createElement(SegmentCables, props));
  assert.match(html, /3 cables/);
  assert.match(html, /2 rack pairs/);
  assert.match(html, /<span>LC<\/span><b>2<\/b>/);
  assert.match(html, /Show rack pairs \(2\)/);
  assert.doesNotMatch(html, /connection-cable-row|meter|complete/);
  const pair = renderToStaticMarkup(React.createElement(SegmentCables, {...props, inventoryCables: inventoryCables.slice(0, 2)}));
  assert.match(pair, /801 ↔ 811/);
  assert.match(pair, /2 cables/);
  assert.equal((pair.match(/View LC cable details/g) ?? []).length, 1);
});

test("saved bundle membership cannot leak other segment cables into the detail list", () => {
  const inventoryCables = ["included", "excluded"].map(uid => ({uid, cable_type: "LC", source_cabinet_id: "021", destination_cabinet_id: "031"}));
  const html = renderToStaticMarkup(React.createElement(SegmentCables, {inventoryCables, members: {bundle: ["included"]}, bundleFilter: {uid: "bundle", label: "Saved bundle"}, onViewCables: () => {}}));
  assert.match(html, /1 cable in group/);
  assert.match(html, /View LC cable details/);
  assert.doesNotMatch(html, /excluded|fixture cable/);
  const empty = renderToStaticMarkup(React.createElement(SegmentCables, {inventoryCables, members: {}, bundleFilter: {uid: "missing", label: "Empty bundle"}, onViewCables: () => {}}));
  assert.match(empty, /0 cables in group/);
  assert.match(empty, /No actual cable members linked/);
  assert.doesNotMatch(empty, /connection-cable-row/);
});

test("cabinet cards preserve completion, type totals and cable actions after sharing presentation", () => {
  const previousWindow = globalThis.window;
  globalThis.window = {localStorage: {getItem: () => "en"}};
  try {
    const connection = {target_cabinet_uid: "LBB01:811", target_category: "Rack", target_cabinet_group: "Test", total_cables: 4, cable_type_counts: {LC: 4}, status_summary: {completed: 1, total: 4, status_counts: {}}};
    const detail = {cabinet: {cabinet_uid: "LBB01:801"}, stats: {connected_cabinets: 1}, intra_cabinet_connection: null, connections: [connection]};
    const html = renderToStaticMarkup(React.createElement(CabinetConnectionsPanel, {detail, selectedCabinetDetails: [], selectedDeviceDetails: [], deviceDetail: null, dataHallCableSummary: null, onViewCables: () => {}}));
    assert.match(html, /LBB01:811/);
    assert.match(html, /1\/4 complete/);
    assert.match(html, /<span>LC<\/span><b>4<\/b>/);
    assert.match(html, /class="detail-button"/);
    assert.equal((html.match(/class="connection-item/g) ?? []).length, 2);
  } finally {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});

test("actual tier strokes defer selection to the shared physical pathway target", () => {
  const point = x => ({x_in:x, y_in:382, passage_band_uid:'central', cabinet_uid:null});
  const review = {groups:[], cabinet_uids:[], loads:[{id:'load', source:point(0), target:point(120), cable_classes:['LC'], group_uids:[], cable_count:4}]};
  const view = {cabinets:[], passageX:new Map([['central',10]]), stationY:x=>x};
  const html = renderToStaticMarkup(React.createElement(CableReviewLayer, {data:{geometry:{bands:[]}}, view, review, scale:1, selectedGroupUid:null, selectedLoadId:null, onLoad:()=>{}, onAttachment:()=>{}}));
  assert.match(html, /pointer-events="none"/);
  assert.doesNotMatch(html, /role="button"|tabindex=|Inspect actual cable segment/);
});

test("rectangle editor accepts feet/inches and does not treat rectangle-only records as grid placements", () => {
  const parent = {...span, uid: "a", tier: 1, grid_columns: 12, grid_rows: 8, section_height_in: 8, section_reference: "Toward NORTH", updated_at: "now"};
  const placement = {...box, segment_annotation_uid: "a", layer: null, position: null, slot_width: null, slot_height: null, source_kind: "MANUAL", source_uid: null};
  const data = {layout: {uid: "l"}, passage_tiers: [{uid: "t", passage_band_uid: "north", tier: 1, enabled: true}], cross_route_tiers: [], segment_annotations: [parent]};
  const html = renderToStaticMarkup(React.createElement(Editor, {data, segment: span, placement, busy: false, mutate: async () => true}));
  assert.match(html, /value="RECTANGLE" selected=""/);
  assert.match(html, /Across offset from inner edge/);
  assert.match(html, /101.6 mm/);
  assert.doesNotMatch(html, /Width in cells/);
  assert.match(html, /separate from elevation above finished floor/);
});

test("configuration handles empty connection and attachment inventories without inventing entries", () => {
  const data = {bundle_connections: [], cabinet_attachments: [], bundle_placements: [], segment_annotations: [], vertical_transitions: [], cabinets: []};
  const html = renderToStaticMarkup(React.createElement(Connections, {data, disabled: false, mutate: async () => true}));
  assert.match(html, /Bundle connections at junctions/);
  assert.match(html, /does not split the graph or add a node/);
  assert.match(html, /Select a saved placement/);
  assert.doesNotMatch(html, /NaN|undefined/);
});

test("measured bottom/top elevation controls respect pathway scope and preserve unknown heights", () => {
  const layout = {bottom_basket_elevation_in: 98, north_south_top_elevation_in: 116};
  const records = [{uid: "bottom", tier: 1, pathway_type: "BASKET_TRAY", enabled: true, elevation_in: null, elevation_reference: "BOTTOM_BASKET", effective_elevation_in: 98}, {uid: "top", tier: 3, pathway_type: "LADDER_RACK", enabled: true, elevation_in: null, elevation_reference: null, effective_elevation_in: null}];
  const props = {kind: "passage", owner: "north", records, layout, disabled: false, mutate: async () => true};
  const north = renderToStaticMarkup(React.createElement(TierEditor, {...props, passageCode: "NORTH"}));
  assert.match(north, /Measured NORTH\/SOUTH top/);
  assert.match(north, /8&#x27;-2/);
  const central = renderToStaticMarkup(React.createElement(TierEditor, {...props, passageCode: "CENTRAL"}));
  assert.doesNotMatch(central, /value="NORTH_SOUTH_TOP"/);
  const unknown = renderToStaticMarkup(React.createElement(TierEditor, {...props, layout: {}, records: [records[0]]}));
  assert.match(unknown, /height unset/);
  assert.doesNotMatch(unknown, /value="0&#x27;-0/);
});

test("physical pathway focus highlights complete cable routes, both attachments, and only relevant types", () => {
  const p=(x,tier=2)=>({x_in:x,y_in:382,tier,passage_band_uid:'central',cabinet_uid:null});
  const group=(uid,cable_class,source,destination,points)=>({uid,cable_class,source_cabinet_uid:source,destination_cabinet_uid:destination,start_tier:2,end_tier:2,route:{points}});
  const groups=[group('lc','LC','a','b',[p(0),p(120),p(240),p(360)]),group('mpo','MPO','c','d',[p(120),p(480)]),group('cat6','CAT6','e','f',[p(240),p(600)])];
  const load=(id,ids,classes,a,b)=>({id,source:p(a),target:p(b),group_uids:ids,cable_classes:classes,cable_count:10,tier:2,edge_type:'PASSAGE'});
  const loads=[load('before',['lc'],['LC'],0,120),load('selected',['lc'],['LC'],120,240),load('after-shared',['lc','cat6'],['LC','CAT6'],240,360),load('junction-other-tier',['mpo'],['MPO'],120,480),load('unrelated',['cat6'],['CAT6'],480,600)];
  const tiles=groups.flatMap(g=>[g.source_cabinet_uid,g.destination_cabinet_uid]).map((uid,i)=>({cabinet:{cabinet_uid:uid},rowUid:'row',x:20+i*40,y:0,width:30,height:20}));
  const props={data:{geometry:{bands:[],cabinet_rows:[{uid:'row',position_in_pair:'A'}]},cabinets:tiles.map(t=>({...t.cabinet,cabinet_id:t.cabinet.cabinet_uid}))},view:{cabinets:tiles,passageX:new Map([['central',10]]),stationY:x=>x},review:{groups,loads},scale:1,selectedGroupUid:null,onAttachment:()=>{}};
  const render=selectionGroupUids=>renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,selectionGroupUids}));
  const segment=render(new Set(['lc']));
  // Three disjoint spans of the complete LC route, plus both cabinet takeoffs, remain colored.
  assert.equal((segment.match(/data-cable-class="LC"/g)??[]).length,5);
  assert.doesNotMatch(segment,/data-cable-class="CAT6"|data-cable-class="MPO"/);
  assert.equal((segment.match(/data-route-muted="true"/g)??[]).length,6);
  const junction=render(new Set(['lc','mpo']));
  assert.equal((junction.match(/data-cable-class="LC"/g)??[]).length,5);
  assert.equal((junction.match(/data-cable-class="MPO"/g)??[]).length,3);
  assert.doesNotMatch(junction,/data-cable-class="CAT6"/);
  const empty=render(new Set());
  assert.doesNotMatch(empty,/data-cable-class=/);
  assert.equal((empty.match(/data-route-muted="true"/g)??[]).length,11);
  const cleared=render(null);
  assert.doesNotMatch(cleared,/data-route-muted=/);
  assert.match(cleared,/data-cable-class="CAT6"/);
});

test("overview batches thousands of independent bundle strokes without connecting their gaps",()=>{
  const strokes=Array.from({length:2000},(_,i)=>({a:{x:i*20,y:0},b:{x:i*20+10,y:0},tier:2,cableClasses:['LC'],selected:false,muted:false}));
  const html=renderToStaticMarkup(React.createElement(OverviewStrokes,{strokes,scale:.08}));
  assert.equal((html.match(/<path /g)??[]).length,1);
  assert.equal((html.match(/M/g)??[]).length,2000);
  assert.match(html,/stroke-dasharray="9 5"/);
  assert.match(html,/vector-effect="non-scaling-stroke"/);
  assert.doesNotMatch(html,/NaN|Infinity|<line /);
});

test("compact overview preserves complete-route focus and greys unrelated types on shared spans",()=>{
  const p=x=>({x_in:x,y_in:382,tier:2,passage_band_uid:'central',cabinet_uid:null});
  const groups=[{uid:'lc',cable_class:'LC'},{uid:'other',cable_class:'CAT6'}];
  const load=(id,ids,x)=>({id,source:p(x),target:p(x+120),tier:2,edge_type:'PASSAGE',group_uids:ids,cable_classes:['LC','CAT6'],cable_count:4});
  const props={data:{geometry:{bands:[]}},view:{cabinets:[],passageX:new Map([['central',10]]),stationY:x=>x},review:{groups,loads:[load('selected',['lc','other'],0),load('tail',['lc'],120),load('unrelated',['other'],480)]},scale:.08,selectedGroupUid:null,selectionGroupUids:new Set(['lc']),onAttachment:()=>{}};
  const html=renderToStaticMarkup(React.createElement(CableReviewLayer,props));
  assert.match(html,/data-overview-mode="summary"/);assert.match(html,/data-cable-class="LC"/);assert.doesNotMatch(html,/data-cable-class="CAT6"/);
  assert.match(html,/data-route-muted="true"/);
  assert.match(html,/stroke="#ffcc66"/);
  const empty=renderToStaticMarkup(React.createElement(CableReviewLayer,{...props,selectionGroupUids:new Set()}));
  assert.doesNotMatch(empty,/data-cable-class=/);
});

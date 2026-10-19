import assert from "node:assert/strict";
import test from "node:test";
import { formatInches, parseInches, formatMillimeters } from "../src/routing/dimensions.ts";
import { placeRoutingCabinets } from "../src/routing/cabinetPlacement.ts";
import { conceptualLayout } from "../src/routing/conceptualLayout.ts";
import { conceptualSegments, annotationFor, rowName, passageName } from "../src/routing/conceptualSegments.ts";
import { segmentTierModel } from "../src/routing/segmentTierModel.ts";
import { sectionDirections, sectionView } from "../src/routing/sectionDirections.ts";
import { collectPlacementCables, filterCableMembers } from "../src/routing/segmentCableMembers.ts";
import { projectReviewPoint, reviewConnector, reviewGroupsForPart } from "../src/routing/cableReviewProjection.ts";
import { loadRoutingCableTable } from "../src/routing/routingCableDetails.ts";
import { ManualRouteEngine } from "../src/routing/manualRouteEngine.ts";
import { reviewPairKey, rackPairCards, focusedRouteGroups, routeActionLabel } from "../src/routing/rackPairRoutes.ts";
import { decodeCableReview } from "../src/routing/reviewEncoding.ts";
import {physicalJunctions,physicalPlanningTargets} from "../src/routing/physicalTargets.ts";

test("physical targets combine plan locations without merging distinct tier openings", () => {
  const p=(x,tier)=>({id:`${x}:${tier}`,x_in:x,y_in:382,tier});
  assert.equal(physicalJunctions([p(0,1),p(0,2),p(0,3),p(120,1)],new Set([1,2,3])).length,2);
  assert.deepEqual(physicalJunctions([p(0,1),p(0,2),p(0,3)],new Set([2]))[0].members.map(p=>p.tier),[2]);
  const horizontal=[1,2,3].map(tier=>({id:`e${tier}`,segment_id:'physical',edge_type:'PASSAGE',source:p(0,tier),target:p(120,tier)}));
  const openings=[{id:'v12',edge_type:'VERTICAL',vertical_transition_uid:'opening12',source:p(0,1),target:p(0,2)},{id:'v23',edge_type:'VERTICAL',vertical_transition_uid:'opening23',source:p(0,2),target:p(0,3)}];
  const result=physicalPlanningTargets([...horizontal,...openings],new Set([1,2,3]));
  assert.deepEqual(result.map(t=>t.members.length),[3,1,1]);
});

test("physical segment and junction inspection include all tiers without unrelated cables", () => {
  const p=(x,tier)=>({x_in:x,y_in:382,tier});
  const group=(uid,tier,segment='physical')=>({uid,route:{segment_ids:[segment],points:[p(0,tier),p(120,tier)]}});
  const review={groups:[group('bottom',1),group('middle',2),group('top',3),{uid:'away',route:{segment_ids:['elsewhere'],points:[p(240,1),p(360,1)]}}],loads:[]};
  assert.deepEqual(reviewGroupsForPart(review,'physical',null,null).map(g=>g.uid),['bottom','middle','top']);
  assert.deepEqual(reviewGroupsForPart(review,null,null,null,p(0,1)).map(g=>g.uid),['bottom','middle','top']);
});

test("manual physical clicks choose a reachable tier locally and keep one undo action", () => {
  const {segments,group,draft}=manualFixture();
  const unavailable={...segments[2],id:'upper',source:{...segments[2].source,tier:2},target:{...segments[2].target,tier:2}};
  const engine=new ManualRouteEngine([...segments,unavailable]);
  const oldFetch=globalThis.fetch;globalThis.fetch=()=>assert.fail('No request during physical pathway selection');
  try {
    const result=engine.connectPhysicalSegment(group,draft,['upper','n-ne']);
    assert.equal(result.segment.id,'n-ne');
    assert.deepEqual(result.draft.checkpoints,[0]);
    assert.equal(result.bridge.vertical_transition_count,0);
    assert.throws(()=>engine.connectPhysicalSegment(group,draft,['upper']),/No visible tier/);
  } finally {globalThis.fetch=oldFetch;}
});

test("physical manual targets prefer fewer tier changes and require an actual opening for another tier", () => {
  const {segments,group,draft}=manualFixture(), base=segments.find(e=>e.id === 'n-ne');
  const upper={...base,id:'upper',source:{...base.source,tier:2},target:{...base.target,tier:2},tier:2};
  const opening={id:'opening',segment_id:'opening',label:'Physical T1-T2 opening',source:base.source,target:upper.source,
    edge_type:'VERTICAL',lower_tier:1,upper_tier:2,tier:null,vertical_transition_uid:'hole',planar_length_in:0};
  const engine=new ManualRouteEngine([...segments,upper,opening]);
  assert.equal(engine.connectPhysicalSegment(group,draft,['upper','n-ne']).segment.id,'n-ne');
  const changed=engine.connectPhysicalSegment(group,draft,['upper']);
  assert.equal(changed.segment.id,'upper');
  assert.ok(changed.draft.ids.includes('opening'));
  assert.equal(changed.bridge.vertical_transition_count,1);
  assert.equal(opening.planar_length_in,0);
});

test("full inventory hydrates indexed tier paths without fetching individual cables", () => {
  const {segments} = manualFixture();
  const group = {uid:'g',source_cabinet_uid:'source',destination_cabinet_uid:'destination',cable_uids:[],count:9000,
    route:{method:'ASTAR',start:segments[0].source,edge_indices:[0,1,2,4],planar_length_in:30,vertical_transition_count:0,length_label:'Planar pathway length'}};
  const wire = {encoding:'indexed-v1',scope:'hall',planning_segments:segments,groups:[group],cables:[],loads:[{edge_index:0,group_indices:[0],cable_classes:['LC'],cable_count:9000}]};
  const original = structuredClone(wire), result = decodeCableReview(wire);
  assert.deepEqual(result.groups[0].route.load_ids,['s-i','i-n','n-ne','ne-end']);
  assert.equal(result.groups[0].route.points.length,5);
  assert.equal(result.groups[0].route.points[1],segments[0].target);
  assert.deepEqual(result.loads[0].group_uids,['g']);
  assert.deepEqual(result.cables,[]);
  assert.deepEqual(wire,original);
  assert.throws(()=>decodeCableReview({...wire,groups:[{...group,route:{...group.route,edge_indices:[2]}}]}),/disconnected/);
});

test("full inventory detail loads exactly the selected actual rack pair and type on demand", async () => {
  const calls=[];
  const result=await loadRoutingCableTable({source:'801',target:'811',cableType:'LC',inventoryCables:[],wholePair:['rack-801','rack-811']},async(a,b)=>{calls.push([a,b]); return {cables:[{uid:'actual-lc',cable_type:'LC',progress:{ran:'Complete'}},{uid:'actual-cat6',cable_type:'CAT6'}]};});
  assert.deepEqual(calls,[['rack-801','rack-811']]);
  assert.deepEqual(result.cables.map(c=>c.uid),['actual-lc']);
  assert.deepEqual(result.cables[0].progress,{ran:'Complete'});
});

test("rack-pair focus includes every type even when the selected segment carries only one", () => {
  const base={source_cabinet_uid:'rack-801',destination_cabinet_uid:'rack-811',source_cabinet_id:'801',destination_cabinet_id:'811',route_source:'DEFAULT'};
  const cat6={...base,uid:'cat6',cable_type:'CAT6a'}, lc={...base,uid:'lc',cable_type:'LC'}, mpo={...base,uid:'mpo',cable_type:'MPO'};
  const other={...base,uid:'other',destination_cabinet_uid:'rack-820',destination_cabinet_id:'820'};
  const all=[cat6,lc,mpo,other], key=reviewPairKey(cat6);
  assert.equal(reviewPairKey({...lc,source_cabinet_uid:base.destination_cabinet_uid,destination_cabinet_uid:base.source_cabinet_uid}),key);
  assert.deepEqual(rackPairCards([cat6],all,key).map(p=>[p.label,p.groups.map(g=>g.uid)]),[['801 ↔ 811',['cat6','lc','mpo']]]);
  assert.equal(rackPairCards([other],all,key)[0].key,key);
  assert.deepEqual(focusedRouteGroups(all,null,key).map(g=>g.uid),['cat6','lc','mpo']);
  assert.deepEqual(focusedRouteGroups(all,'lc',key).map(g=>g.uid),['lc']);
  assert.deepEqual(focusedRouteGroups(all,null,null),[]);
  assert.equal(routeActionLabel([cat6,lc]),'Set route');
  assert.equal(routeActionLabel([cat6,{...lc,route_source:'MANUAL'}]),'Change route');
});

test("cabinet focus keeps the union of incoming and outgoing groups and clears with selection", () => {
  const group=(uid,a,b)=>({uid,source_cabinet_uid:a,destination_cabinet_uid:b});
  const groups=[group('outgoing','801','811'),group('incoming','820','801'),group('second','021','031'),group('unrelated','100','110')];
  assert.deepEqual(focusedRouteGroups(groups,null,null,new Set(['801'])).map(g=>g.uid),['outgoing','incoming']);
  assert.deepEqual(focusedRouteGroups(groups,null,null,new Set(['801','031'])).map(g=>g.uid),['outgoing','incoming','second']);
  assert.deepEqual(focusedRouteGroups(groups,null,null,new Set(['missing'])),[]);
  assert.deepEqual(focusedRouteGroups(groups,null,null,new Set()),[]);
  assert.deepEqual(focusedRouteGroups(groups,'second',null,new Set(['801'])).map(g=>g.uid),['second']);
});

function manualFixture() {
  const point = (name, x, y, tier = 1, cabinet = null) => ({node_id: `${name}-T${tier}`, x_in: x, y_in: y, tier, cabinet_uid: cabinet, passage_band_uid: cabinet ? null : name, passage_code: name});
  const s = point('S', 0, 5, 1, 'source'), i = point('I', 0, 3, 1, 'middle'), n = point('NORTH', 0, 0), c = point('CENTRAL', 0, 10), ne = point('NORTH', 20, 0), ce = point('CENTRAL', 20, 10), end = point('E', 20, 5, 1, 'destination');
  const edge = (id, source, target) => ({id, segment_id: id, source, target, edge_type: 'PASSAGE', tier: source.tier, planar_length_in: Math.abs(source.x_in-target.x_in)+Math.abs(source.y_in-target.y_in), label: id, vertical_transition_uid: null});
  const segments = [edge('s-i', s, i), edge('i-n', i, n), edge('n-ne', n, ne), edge('n-tail', n, point('tail',0,-5)), edge('ne-end', ne, end), edge('s-c', s, c), edge('c-ce', c, ce), edge('ce-end', ce, end)];
  return {segments, group: {uid:'g',source_cabinet_uid:'source',destination_cabinet_uid:'destination'}, draft:{ids:[],checkpoints:[],startTier:1,endTier:1}};
}

test("manual clicks, chain validation, and A* remainders work locally without requests", () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = () => {assert.fail('Incomplete route editing must not make network requests');};
  try {
    const {segments, group, draft} = manualFixture(), engine = new ManualRouteEngine(segments);
    const first = engine.preview(group, draft);
    assert.equal(first.complete, false);
    const north = first.next_chains.find(c => c.load_ids.includes('i-n'));
    assert.deepEqual(north.load_ids, ['s-i','i-n']);
    const prefix = {...draft,ids:north.load_ids};
    const next = engine.preview(group, prefix);
    assert.deepEqual(next.prefix.points.at(-1), next.suggestion.points[0]);
    assert.equal(engine.isComplete(group, prefix), false);
    const full = {...draft,ids:[...prefix.ids,...next.suggestion.load_ids]};
    assert.equal(engine.isComplete(group, full), true);
    assert.equal(engine.preview(group, full).suggestion, null);
    assert.deepEqual(engine.preview(group, full).next_chains, []);
    assert.throws(() => engine.preview(group, {...draft,ids:['n-ne']}), /connected/);
    assert.throws(() => engine.preview(group, {...draft,ids:['s-i','s-i']}), /loop|backtrack/);
    assert.throws(() => engine.preview(group, {...draft,ids:['disabled']}), /unavailable/);
    assert.deepEqual(engine.preview(group, draft).suggestion, new ManualRouteEngine([...segments].reverse()).preview(group, draft).suggestion);
  } finally {globalThis.fetch = previousFetch;}
});

test("disconnected segment clicks bridge locally, include the clicked edge, and preserve a single undo checkpoint", () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = () => {assert.fail('Segment bridging must stay local');};
  try {
    const {segments,group,draft} = manualFixture(), engine = new ManualRouteEngine(segments);
    const prefix = {...draft,ids:['s-i'],checkpoints:[0]}, before = structuredClone(prefix);
    const result = engine.connectSegment(group,prefix,'n-ne');
    assert.deepEqual(result.bridge.load_ids,['i-n']);
    assert.deepEqual(result.draft.ids,['s-i','i-n','n-ne']);
    assert.deepEqual(result.draft.checkpoints,[0,1]);
    assert.deepEqual(result.draft.ids.slice(0,result.draft.checkpoints.at(-1)),prefix.ids);
    assert.deepEqual(prefix,before);
    const preview = engine.preview(group,result.draft);
    assert.equal(preview.complete,false);
    assert.deepEqual(preview.suggestion.load_ids,['ne-end']);
    assert.equal(engine.isComplete(group,{...result.draft,ids:[...result.draft.ids,...preview.suggestion.load_ids]}),true);
    const reversed = new ManualRouteEngine([...segments].reverse().map(e=>e.id==='n-ne'?{...e,source:e.target,target:e.source}:e));
    assert.deepEqual(reversed.connectSegment(group,prefix,'n-ne').draft,result.draft);
    const connected = engine.connectSegment(group,{...draft,ids:['s-i','i-n']},'n-ne');
    assert.deepEqual(connected.bridge.load_ids,[]);
    assert.deepEqual(connected.draft.ids,['s-i','i-n','n-ne']);
  } finally {globalThis.fetch = previousFetch;}
});

test("segment bridging compares routed costs to both endpoints instead of straight-line proximity", () => {
  const p = (name,x,y,cabinet=null) => ({node_id:name,x_in:x,y_in:y,tier:1,cabinet_uid:cabinet});
  const s=p('s',0,0,'source'), a=p('a',10,0), b=p('b',10,20), c=p('c',0,20), u=p('u',-10,0), v=p('v',-10,30), w=p('w',10,30), z=p('z',30,0,'destination');
  const edge = (id,source,target) => ({id,segment_id:id,source,target,edge_type:'PASSAGE',planar_length_in:Math.abs(source.x_in-target.x_in)+Math.abs(source.y_in-target.y_in),label:id});
  const segments=[edge('s-u',s,u),edge('u-v',u,v),edge('v-w',v,w),edge('w-a',w,a),edge('s-c',s,c),edge('c-b',c,b),edge('clicked',a,b),edge('a-z',a,z)];
  const {group,draft}=manualFixture(), result=new ManualRouteEngine(segments).connectSegment(group,draft,'clicked');
  assert.deepEqual(result.bridge.load_ids,['s-c','c-b']);
  assert.equal(result.bridge.planar_length_in,30);
  assert.deepEqual(result.draft.ids,['s-c','c-b','clicked']);
  assert.equal(new ManualRouteEngine(segments).preview(group,result.draft).prefix.points.at(-1).node_id,'a');
});

test("segment bridging rejects unreachable, already-used and post-destination paths without changing the draft", () => {
  const {segments,group,draft}=manualFixture(), engine=new ManualRouteEngine(segments);
  const north={...draft,ids:['s-i','i-n']}, before=structuredClone(north);
  assert.throws(()=>engine.connectSegment(group,north,'s-i'),/Cannot connect/);
  assert.deepEqual(north,before);
  assert.throws(()=>engine.connectSegment(group,draft,'missing'),/unavailable/);
  // The only alternative approach would revisit the source or pass the final destination.
  assert.throws(()=>engine.connectSegment(group,{...draft,ids:['s-c']},'n-ne'),/Cannot connect/);
  const full={...draft,ids:['s-i','i-n','n-ne','ne-end']};
  assert.throws(()=>engine.connectSegment(group,full,'c-ce'),/complete/);
  const remote={...segments[0],id:'island',source:{...segments[0].source,x_in:100},target:{...segments[0].target,x_in:100}};
  assert.throws(()=>new ManualRouteEngine([...segments,remote]).connectSegment(group,draft,'island'),/Cannot connect/);
});

test("bridging to another tier requires its physical opening and never invents vertical distance", () => {
  const {segments,group,draft}=manualFixture();
  const layered=[...segments,...segments.map(e=>({...e,id:`${e.id}-T2`,tier:2,source:{...e.source,tier:2},target:{...e.target,tier:2}}))];
  assert.throws(()=>new ManualRouteEngine(layered).connectSegment(group,{...draft,endTier:2},'n-ne-T2'),/Cannot connect/);
  const n=segments.find(e=>e.id==='n-ne').source;
  layered.push({id:'hole',segment_id:'hole',label:'N opening',edge_type:'VERTICAL',source:n,target:{...n,tier:2},planar_length_in:0,vertical_transition_uid:'vt-1-2'});
  const engine=new ManualRouteEngine(layered), result=engine.connectSegment(group,{...draft,endTier:2},'n-ne-T2');
  assert.deepEqual(result.bridge.load_ids,['s-i','i-n','hole']);
  assert.equal(result.bridge.vertical_transition_count,1);
  assert.equal(result.bridge.planar_length_in,5);
  assert.equal(engine.preview(group,result.draft).prefix.planar_length_in,25);
});

test("local tier-aware A* needs separate adjacent-tier physical openings and adds no vertical length", () => {
  const {segments,group,draft} = manualFixture();
  const layered = [...segments];
  for (const tier of [2,3]) layered.push(...segments.map(e => ({...e,id:`${e.id}-T${tier}`,tier,source:{...e.source,tier},target:{...e.target,tier}})));
  let engine = new ManualRouteEngine(layered);
  assert.equal(engine.preview(group,{...draft,endTier:2}).suggestion,null);
  const north = segments.find(e=>e.id==='n-ne').source;
  const hole = (lower,upper) => ({id:`hole-${lower}-${upper}`,segment_id:'opening',label:'Physical opening',edge_type:'VERTICAL',tier:null,source:{...north,tier:lower},target:{...north,tier:upper},planar_length_in:0,vertical_transition_uid:`vt-${lower}-${upper}`});
  layered.push(hole(1,2)); engine = new ManualRouteEngine(layered);
  assert.equal(engine.preview(group,{...draft,endTier:2}).suggestion.vertical_transition_count,1);
  assert.equal(engine.preview(group,{...draft,endTier:3}).suggestion,null);
  layered.push(hole(2,3)); engine = new ManualRouteEngine(layered);
  const result=engine.preview(group,{...draft,endTier:3}).suggestion;
  assert.equal(result.vertical_transition_count,2);
  assert.equal(result.planar_length_in,30);
  assert.equal(engine.preview(group,draft).suggestion.vertical_transition_count,0);
  assert.throws(()=>new ManualRouteEngine([...segments,hole(1,3)]),/Invalid tier opening/);
  assert.throws(()=>new ManualRouteEngine([{...segments[0],target:{...segments[0].target,tier:2}}]),/requires a physical opening/);
});

test("route cable table loads real detail fields and strictly filters membership and type", async () => {
  const member = (uid, reverse = false) => ({uid, source_cabinet_uid: reverse ? "cab-b" : "cab-a", destination_cabinet_uid: reverse ? "cab-a" : "cab-b"});
  const selected = {uid: "member-1", cable_type: "LC", progress: {pulled: "complete"}, status: "Cable Is Ran: Complete", length_used_meters: 12, group: "Actual group", a_port_uid: "actual-a", z_port_uid: "actual-z"};
  const request = {source: "801", target: "811", cableType: "LC", inventoryCables: [member("member-1"), member("changed-type", true)]};
  const calls = [];
  const response = await loadRoutingCableTable(request, async (a, z) => {
    calls.push([a, z]);
    return {cables: [selected, {...selected, uid: "not-on-segment"}, {...selected, uid: "changed-type", cable_type: "MPO"}]};
  });
  assert.deepEqual(calls, [["cab-a", "cab-b"]]);
  assert.deepEqual(response.cables, [selected]);
  assert.equal(response.source_cabinet_uid, "801");
  assert.equal(response.target_cabinet_uid, "811");
});

test("route cable tables do not truncate large groups and propagate load errors", async () => {
  const inventoryCables = Array.from({length: 288}, (_, n) => ({uid: `mpo-${n}`, source_cabinet_uid: "a", destination_cabinet_uid: "z"}));
  const request = {source: "801", target: "810", cableType: "MPO", inventoryCables};
  const response = await loadRoutingCableTable(request, async () => ({cables: inventoryCables.map(c => ({uid: c.uid, cable_type: "MPO"}))}));
  assert.equal(response.cables.length, 288);
  await assert.rejects(loadRoutingCableTable(request, async () => {throw new Error("API unavailable");}), /API unavailable/);
  await assert.rejects(loadRoutingCableTable({...request, inventoryCables: [{uid: "missing-cabinet"}]}, async () => {assert.fail("No invented cabinet lookup");}), /Cabinet references are missing/);
});


test("formats integer inches without feet rounding", () => {
  for (const [value, text] of [[24, `2'-0"`], [34, `2'-10"`], [96, `8'-0"`], [120, `10'-0"`], [264, `22'-0"`], [336, `28'-0"`], [360, `30'-0"`], [788, `65'-8"`]]) {
    assert.equal(formatInches(value), text);
    assert.equal(parseInches(text), value);
  }
});
test("parses field feet/inches input", () => {
  for (const text of [`2'-10"`, `2' 10"`, "2ft 10in", "2′10″", "34", "34 in"]) assert.equal(parseInches(text), 34);
  assert.equal(parseInches("22ft"), 264);
  assert.equal(parseInches("0"), 0);
});
test("rejects invalid and fractional dimensions", () => {
  for (const text of ["", "-1", "2.5ft", `2'-12"`, "abc", "1.5", "2 10"]) assert.throws(() => parseInches(text));
  assert.throws(() => formatInches(34.5));
});

function inventoryFixture() {
  const cabinets = [
    { cabinet_uid: "a1", cabinet_id: "001", source_col: 7 },
    { cabinet_uid: "a2", cabinet_id: "002", source_col: 8 },
    { cabinet_uid: "a10", cabinet_id: "010", source_col: 16 },
    { cabinet_uid: "b11", cabinet_id: "011", source_col: 16 },
    { cabinet_uid: "b20", cabinet_id: "020", source_col: 7 },
  ];
  return { layout: { cabinets_per_row: 10 }, cabinets, geometry: {
    bands: [{ uid: "south", start_in: 394, end_in: 754, width_in: 360 }],
    cabinet_rows: [
      { uid: "a", row_field_band_uid: "south", start_in: 120, end_in: 144, cabinet_number_start: 1, cabinet_number_end: 10, existing_cabinet_uids: ["a1", "a2", "a10"] },
      { uid: "b", row_field_band_uid: "south", start_in: 240, end_in: 264, cabinet_number_start: 11, cabinet_number_end: 20, existing_cabinet_uids: ["b11", "b20"] },
    ],
  } };
}
test("cabinet tiles preserve imported serpentine ordering and cabinet-row bounds", () => {
  const tiles = placeRoutingCabinets(inventoryFixture());
  const byId = new Map(tiles.map(t => [t.cabinet.cabinet_id, t]));
  assert.equal(tiles.length, 5);
  assert.equal(byId.get("001").y, 718); // leftmost when the map is rotated to match the cabinet map
  assert.equal(byId.get("010").y, 394);
  assert.equal(byId.get("020").y, 718);
  assert.equal(byId.get("011").y, 394);
  assert.ok(tiles.every(t => t.width === 24 && t.height === 36));
  assert.equal(byId.get("001").x, 120);
  assert.equal(byId.get("011").x, 240);
});
test("missing cabinets retain their empty display slots", () => {
  const data = inventoryFixture();
  data.cabinets = data.cabinets.filter(c => c.cabinet_id !== "002");
  const tiles = placeRoutingCabinets(data);
  assert.equal(tiles.length, 4);
  assert.equal(tiles.find(t => t.cabinet.cabinet_id === "010").y, 394);
  assert.ok(!tiles.some(t => t.rowUid === "a" && t.y === 682));
});
test("unmapped and ambiguous inventory does not create invented cabinet tiles", () => {
  const data = inventoryFixture();
  data.cabinets.forEach(c => c.source_col = null);
  assert.deepEqual(placeRoutingCabinets(data), []);
  data.cabinets = [];
  assert.deepEqual(placeRoutingCabinets(data), []);
});

function conceptualFixture() {
  const data = inventoryFixture();
  data.layout.cabinet_row_depth_in = 24;
  data.geometry.bands = [
    { uid: "north-passage", ordinal: 0, kind: "PASSAGE", code: "NORTH", start_in: 0, end_in: 34, width_in: 34 },
    { uid: "north", ordinal: 1, kind: "ROW_FIELD", start_in: 34, end_in: 370, width_in: 336 },
    { uid: "central", ordinal: 2, kind: "PASSAGE", code: "CENTRAL", start_in: 370, end_in: 394, width_in: 24 },
    { uid: "south", ordinal: 3, kind: "ROW_FIELD", start_in: 394, end_in: 754, width_in: 360 },
    { uid: "south-passage", ordinal: 4, kind: "PASSAGE", code: "SOUTH", start_in: 754, end_in: 788, width_in: 34 },
  ];
  data.geometry.sections = Array.from({ length: 5 }, (_, i) => ({ uid: `s${i + 1}`, ordinal: i + 1, name: `Section ${i + 1}`, start_in: i * 480, end_in: i * 480 + 264 }));
  data.geometry.row_pairs = data.geometry.sections.map(s => ({ uid: `pair-${s.uid}`, routing_section_uid: s.uid, row_field_band_uid: "south", start_in: s.start_in, end_in: s.end_in, hot_aisle_start_in: s.start_in + 144, hot_aisle_end_in: s.start_in + 240 }));
  data.geometry.cabinet_rows.forEach((row, i) => Object.assign(row, { row_pair_uid: "pair-s1", position_in_pair: i ? "B" : "A", name: i ? "Rack 11-20" : "Rack 1-10", enabled: true }));
  data.geometry.gaps = data.geometry.sections.slice(0, 4).map(s => ({ after_section_uid: s.uid, start_in: s.end_in, end_in: s.end_in + 216, center_in: s.end_in + 108 }));
  data.geometry.hall_length_in = 2304;
  return data;
}
const conceptual = data => conceptualLayout(data, placeRoutingCabinets(data));
test("conceptual map keeps five sections, four gaps, cabinet ordering and continuous passages", () => {
  const data = conceptualFixture(), view = conceptual(data);
  assert.equal(view.sections.length, 5);
  assert.equal(view.gaps.length, 4);
  assert.deepEqual(view.passages.map(p => p.code), ["SOUTH", "CENTRAL", "NORTH"]);
  assert.equal(view.cabinets.length, 5);
  assert.ok(view.cabinets.find(c => c.cabinet.cabinet_id === "001").x < view.cabinets.find(c => c.cabinet.cabinet_id === "010").x);
  assert.ok(view.cabinets.find(c => c.cabinet.cabinet_id === "020").x < view.cabinets.find(c => c.cabinet.cabinet_id === "011").x);
  const stations = data.geometry.gaps.map(g => g.center_in);
  for (let i = 1; i < stations.length; i++) assert.ok(view.stationY(stations[i]) > view.stationY(stations[i - 1]));
  assert.equal(view.projectNode({ passage_band_uid: "central", station_in: stations[2] }).x, view.passages[1].x);
});
test("conceptual spacing is independent of physical dimensions and does not mutate model data", () => {
  const data = conceptualFixture(), before = structuredClone(data), first = conceptual(data);
  assert.deepEqual(data, before);
  const scaled = structuredClone(data);
  scaled.layout.cabinet_row_depth_in *= 2;
  for (const group of [scaled.geometry.bands, scaled.geometry.sections, scaled.geometry.row_pairs, scaled.geometry.cabinet_rows, scaled.geometry.gaps]) {
    for (const record of group) for (const key of Object.keys(record)) if (key.endsWith("_in") && typeof record[key] === "number") record[key] *= 2;
  }
  scaled.geometry.hall_length_in *= 2;
  const second = conceptual(scaled);
  assert.deepEqual(first.passages, second.passages);
  assert.deepEqual(first.sections, second.sections);
  assert.deepEqual(first.gaps, second.gaps);
  assert.deepEqual(first.cabinets, second.cabinets);
  assert.equal(first.stationY(372), second.stationY(744));
  assert.equal(data.geometry.bands[0].width_in, 34);
});
test("conceptual station projection preserves the same tier station and all empty section gaps", () => {
  const data = conceptualFixture();
  data.geometry.row_pairs = [];
  data.geometry.cabinet_rows = [];
  data.cabinets = [];
  data.geometry.sections.forEach((section, i) => { section.start_in = i * 216; section.end_in = i * 216; });
  data.geometry.gaps.forEach((gap, i) => { gap.start_in = i * 216; gap.end_in = (i + 1) * 216; gap.center_in = i * 216 + 108; });
  data.geometry.hall_length_in = 864;
  const view = conceptual(data);
  assert.equal(view.sections.length, 5);
  assert.equal(view.gaps.length, 4);
  assert.deepEqual(view.projectNode({ passage_band_uid: "central", station_in: 600, tier: 1 }), view.projectNode({ passage_band_uid: "central", station_in: 600, tier: 2 }));
  assert.ok(view.height > 0);
});

function segmentFixture() {
  const data = conceptualFixture();
  data.geometry.bands.forEach(b => b.center_in = (b.start_in + b.end_in) / 2);
  data.geometry.bands[1].code = "NORTH_FIELD";
  data.geometry.bands[3].code = "SOUTH_FIELD";
  data.bands = data.geometry.bands;
  data.vertical_transitions = [];
  data.segment_annotations = [];
  data.cabinet_rows = data.geometry.cabinet_rows;
  data.geometry.cross_routes = data.geometry.cabinet_rows.map((r, i) => ({ uid: `cold${i}`, kind: "CABINET_COLD_AISLE", cabinet_row_uid: r.uid,
    station_in: i ? 276 : 108, width_in: 24, effective_enabled: true }));
  data.geometry.cross_routes.push({ uid: "gap1", kind: "SECTION_GAP", section_boundary_after_section_uid: "s1", label: "Section 1-2 gap route", station_in: 372, width_in: 24, effective_enabled: true });
  return data;
}
test("conceptual spans retain physical lengths/widths and select their cabinet field without duplicate continuations", () => {
  const data = segmentFixture();
  const segments = conceptualSegments(data);
  const cold = segments.filter(s => s.cross_route_uid === "cold0");
  assert.equal(cold.length, 1);
  assert.equal(cold[0].from_passage_band_uid, "central");
  assert.equal(cold[0].planar_length_in, 389);
  assert.equal(cold[0].width_in, 24);
  assert.deepEqual(segments.filter(s => s.cross_route_uid === "gap1").map(s => s.planar_length_in), [365, 389]);
  for (const passage of data.bands.filter(b => b.kind === "PASSAGE")) {
    assert.equal(segments.filter(s => s.passage_band_uid === passage.uid).reduce((sum, s) => sum + s.planar_length_in, 0), data.geometry.hall_length_in);
  }
  data.geometry.cross_routes[0].effective_enabled = false;
  assert.ok(!conceptualSegments(data).some(s => s.cross_route_uid === "cold0"));
});
test("manual interval endpoints split guides and markings match only their tier and covered span", () => {
  const data = segmentFixture();
  const marking = { uid: "manual", passage_band_uid: "central", start_station_in: 50, end_station_in: 150, tier: 1, usable: false, cable_classes: [] };
  data.segment_annotations = [marking];
  const segments = conceptualSegments(data).filter(s => s.passage_band_uid === "central");
  assert.ok(segments.some(s => s.start_station_in === 50));
  assert.ok(segments.some(s => s.end_station_in === 150));
  const covered = segments.find(s => s.start_station_in === 50);
  assert.equal(annotationFor(data, covered, 1), marking);
  assert.equal(annotationFor(data, covered, 2), undefined);
  assert.equal(annotationFor(data, covered, null), undefined);
  assert.equal(annotationFor(data, segments.find(s => s.start_station_in === 150), 1), undefined);
});
test("conceptual view retains original cabinet dimensions, adds spacing, and uses a narrower hot gap", () => {
  const data = conceptualFixture();
  const view = conceptualLayout(data, placeRoutingCabinets(data), { cellWidth: 46, cellHeight: 30, hotAisleGap: 10 });
  assert.ok(view.cabinets.every(t => t.width === 46 && t.height === 30));
  const first = view.cabinets.find(t => t.cabinet.cabinet_id === "001"), next = view.cabinets.find(t => t.cabinet.cabinet_id === "002");
  assert.ok(next.x - first.x > first.width);
  assert.equal(view.hotAisles[0].height, 10);
  assert.ok(view.rows.get("b").y - view.rows.get("a").y - first.height < 56);
});

function cabinetRunFixture() {
  const data = segmentFixture();
  data.geometry.sections.forEach((section, i) => Object.assign(section, { start_in: i ? 528 + i * 216 : 0, end_in: i ? 528 + i * 216 : 528, data_hall_id: `DH1-${i + 1}` }));
  data.geometry.gaps = data.geometry.sections.slice(0, 4).map(s => ({ after_section_uid: s.uid, start_in: s.end_in, end_in: s.end_in + 216, center_in: s.end_in + 108 }));
  data.geometry.hall_length_in = 1512;
  data.geometry.row_pairs = [data.geometry.row_pairs[0], { uid: "pair-s1-2", routing_section_uid: "s1", row_field_band_uid: "south", start_in: 264, end_in: 528, hot_aisle_start_in: 408, hot_aisle_end_in: 504 }];
  data.geometry.cabinet_rows.forEach(r => r.section_uid = "s1");
  data.cabinets.push(...[
    { cabinet_uid: "c021", cabinet_id: "021", source_col: 7 }, { cabinet_uid: "c030", cabinet_id: "030", source_col: 16 },
    { cabinet_uid: "c031", cabinet_id: "031", source_col: 16 }, { cabinet_uid: "c040", cabinet_id: "040", source_col: 7 },
  ].map(c => ({ ...c, data_hall_id: "DH1-1" })));
  for (const [uid, position, first, start, cabinets] of [["row21", "A", 21, 384, ["c021", "c030"]], ["row31", "B", 31, 504, ["c031", "c040"]]]) {
    data.geometry.cabinet_rows.push({ uid, row_pair_uid: "pair-s1-2", row_field_band_uid: "south", section_uid: "s1", position_in_pair: position,
      cabinet_number_start: first, cabinet_number_end: first + 9, start_in: start, end_in: start + 24, center_in: start + 12,
      existing_cabinet_uids: cabinets, enabled: true, name: `Rack ${first}-${first + 9}` });
    data.geometry.cross_routes.push({ uid: `route-${uid}`, kind: "CABINET_COLD_AISLE", cabinet_row_uid: uid, station_in: position === "A" ? 372 : 540,
      station_source: "DERIVED", width_in: 24, effective_enabled: true });
  }
  data.cabinet_rows = data.geometry.cabinet_rows;
  return data;
}

function tierFixture() {
  const data = cabinetRunFixture();
  data.cross_route_tiers = [];
  data.passage_tiers = [];
  data.bundle_placements = [];
  data.geometry.cabinet_rows.forEach((r, i) => { r.row_number = i + 1; r.display_name = `Row ${i + 1}`; });
  data.geometry.cross_routes.forEach(r => { if (r.cabinet_row_uid) r.display_label = rowName(data, r.cabinet_row_uid); });
  data.geometry.station_labels = data.bands.filter(b => b.kind === "PASSAGE").flatMap(b => [[108, "R1"], [276, "R2"], [372, "R3"], [540, "R4"]].map(([station, token]) => ({ passage_band_uid: b.uid, station_in: station, token })));
  return data;
}
test("row and passage labels use backend row numbers and station tokens", () => {
  const data = tierFixture();
  assert.equal(rowName(data, "row21"), "Row 3");
  assert.equal(passageName(data, "south-passage", 108, 276), "South R1–2");
  assert.equal(passageName(data, "central", 108, 276), "Central R1–2");
  assert.equal(passageName(data, "north-passage", 108, 372), "North R1–3");
  assert.equal(conceptualSegments(data).find(s => s.cross_route_uid === "route-row21").label, "Row 3");
});
test("saved sectional positions and AFF elevations filter openings to the selected span", () => {
  const data = tierFixture(), segments = conceptualSegments(data), selected = segments.find(s => s.passage_band_uid === "central" && s.start_station_in === 372);
  data.passage_tiers = [1, 2, 3].map(tier => ({ uid: `t${tier}`, passage_band_uid: "central", tier, enabled: true, pathway_type: "LADDER_RACK", elevation_in: 96 + tier * 24 }));
  data.segment_annotations = [{ uid: "section", passage_band_uid: "central", start_station_in: 372, end_station_in: 540, tier: null, section_reference: "Inner toward NORTH_FIELD; viewing +X", cable_classes: [], usable: true }];
  data.bundle_placements = [{ uid: "bundle", segment_annotation_uid: "section", tier: 2, layer: 2, position: 3, enabled: true, cable_class: "LC", resolved_label: "LC group A", source_available: true }];
  data.vertical_transitions = [
    { uid: "hole12", passage_band_uid: "central", station_in: 372, lower_tier: 1, upper_tier: 2, enabled: true },
    { uid: "hole23", passage_band_uid: "central", station_in: 372, lower_tier: 2, upper_tier: 3, enabled: true },
    { uid: "outside", passage_band_uid: "central", station_in: 541, lower_tier: 1, upper_tier: 2, enabled: true },
    { uid: "other", passage_band_uid: "south-passage", station_in: 400, lower_tier: 1, upper_tier: 2, enabled: true },
  ];
  const model = segmentTierModel(data, selected);
  assert.deepEqual(model.openings.map(o => o.uid), ["hole12", "hole23"]);
  assert.deepEqual(model.records.map(t => t.elevation_in), [120, 144, 168]);
  assert.deepEqual([model.blocks[0].tier, model.blocks[0].layer, model.blocks[0].position], [2, 2, 3]);
});
test("cross-route sections show only openings at their passage junctions and keep disabled records distinct", () => {
  const data = tierFixture(), selected = conceptualSegments(data).find(s => s.cross_route_uid === "route-row21");
  data.vertical_transitions = [
    { uid: "central", passage_band_uid: "central", station_in: 372, lower_tier: 1, upper_tier: 2, enabled: true },
    { uid: "south", passage_band_uid: "south-passage", station_in: 372, lower_tier: 2, upper_tier: 3, enabled: false },
    { uid: "north", passage_band_uid: "north-passage", station_in: 372, lower_tier: 1, upper_tier: 2, enabled: true },
  ];
  const model = segmentTierModel(data, selected);
  assert.deepEqual(model.openings.map(o => o.uid), ["central", "south"]);
  assert.deepEqual(model.tiers, []);
  assert.deepEqual(model.blocks, []);
});

test("tier markings show cable types without inventing sectional bundle positions", () => {
  const data = tierFixture(), selected = conceptualSegments(data).find(s => s.passage_band_uid === "central" && s.start_station_in === 372);
  data.passage_tiers = [1, 2].map(tier => ({ uid: `t${tier}`, passage_band_uid: "central", tier, enabled: true, pathway_type: "LADDER_RACK", elevation_in: null }));
  data.segment_annotations = [{ uid: "types", passage_band_uid: "central", start_station_in: 372, end_station_in: 540, tier: 1, cable_classes: ["LC", "MPO"], usable: true }];
  const model = segmentTierModel(data, selected);
  assert.deepEqual(model.markedClasses[1], ["LC", "MPO"]);
  assert.deepEqual(model.markedClasses[2], []);
  assert.deepEqual(model.blocks, []);
});

test("metric display converts integer inches exactly and feet/inches remain canonical inches", () => {
  assert.equal(formatMillimeters(1), "25.4 mm");
  assert.equal(formatMillimeters(parseInches(`1'-0"`)), "304.8 mm");
  assert.equal(formatMillimeters(10), "254 mm");
  assert.throws(() => formatMillimeters(1.5));
});

test("physical-only rectangles do not manufacture grid slots or modify physical dimensions", () => {
  const data = tierFixture(), segment = conceptualSegments(data).find(s => s.cross_route_uid === "route-row21");
  data.segment_annotations = [{...segment, uid:"annotation", tier:null}];
  data.bundle_placements = [{uid:"rect",segment_annotation_uid:"annotation",tier:1,enabled:true,source_available:true,layer:null,position:null,slot_width:null,slot_height:null,offset_across_in:2,offset_up_in:1,occupied_width_in:6,occupied_height_in:3}];
  const before = structuredClone(data), model = segmentTierModel(data,segment);
  assert.equal(model.blocks.length,1);
  assert.deepEqual([model.blocks[0].layer,model.blocks[0].position,model.blocks[0].slot_width,model.blocks[0].slot_height],[null,null,null,null]);
  assert.deepEqual([model.blocks[0].offset_across_in,model.blocks[0].offset_up_in,model.blocks[0].occupied_width_in,model.blocks[0].occupied_height_in],[2,1,6,3]);
  assert.deepEqual(data,before);
});


test("inner faces cabinets/hot aisle; CENTRAL never receives inner/outer labels", () => {
  const data = tierFixture(); data.layout.longitudinal_direction = "EAST";
  const segments = conceptualSegments(data);
  const a = segments.find(s => s.cross_route_uid === "route-row21");
  const b = segments.find(s => s.cross_route_uid === "route-row31");
  assert.equal(sectionDirections(data, a).inner, "EAST");
  assert.equal(sectionDirections(data, b).inner, "WEST");
  const north = {passage_band_uid: "north-passage"}, south = {passage_band_uid: "south-passage"};
  assert.equal(sectionDirections(data, north).inner, "SOUTH");
  assert.equal(sectionDirections(data, south).inner, "NORTH");
  const central = sectionDirections(data, {passage_band_uid: "central"});
  assert.equal(central.inner, null); assert.equal(central.hasInner, false);
  assert.deepEqual([sectionView(central, "SOUTH", false).left, sectionView(central, "SOUTH", false).right], ["North", "South"]);
});

test("reversing a section swaps cardinal sides and viewing direction without changing occupations", () => {
  const data = tierFixture(); data.layout.longitudinal_direction = "EAST";
  const segments = conceptualSegments(data);
  const model = segmentTierModel(data, segments.find(s => s.cross_route_uid === "route-row21")), before = structuredClone(model);
  const a = sectionView(model.directions, null, false), b = sectionView(model.directions, null, true);
  assert.equal(a.left, b.right); assert.equal(a.right, b.left);
  assert.equal(a.from, b.to); assert.equal(a.to, b.from);
  assert.deepEqual(model, before);
});

test("real cable membership deduplicates overlapping placements and filters by reference, not cable type", () => {
  const a = {uid: "actual-1", cable_type: "LC"}, b = {uid: "actual-2", cable_type: "LC"};
  const {cables, members} = collectPlacementCables([{placement_uid: "group-a", cables: [a]}, {placement_uid: "group-b", cables: [a, b]}]);
  assert.deepEqual(cables.map(c => c.uid), ["actual-1", "actual-2"]);
  const visible = cables.map(c => ({...c, id: c.uid}));
  assert.deepEqual(filterCableMembers(visible, "group-a", members).map(c => c.id), ["actual-1"]);
  assert.deepEqual(filterCableMembers(visible, "manual-label", members), []);
  assert.equal(filterCableMembers(visible, null, members).length, 2);
});

test("actual review projection uses cabinet tile centers and cold faces without changing inches", () => {
  const data = conceptualFixture(), view = conceptualLayout(data, placeRoutingCabinets(data));
  const before = structuredClone(data), tile = view.cabinets.find(c => c.cabinet.cabinet_uid === 'a1');
  const point = {cabinet_uid: 'a1', passage_band_uid: null, x_in: 108, y_in: 736};
  assert.equal(projectReviewPoint(data, view, point).x, tile.x + (tile.width - 2) / 2);
  const connector = reviewConnector(data, view, 'a1', point);
  assert.equal(connector.a.y, tile.y);
  assert.equal(connector.a.x, connector.b.x);
  assert.equal(projectReviewPoint(data, view, {...point, cabinet_uid: null, passage_band_uid: 'central'}).x, view.passageX.get('central'));
  assert.equal(projectReviewPoint(data, view, {...point, cabinet_uid: null, passage_band_uid: null, y_in: -1}), null);
  assert.deepEqual(data, before);
});

test("actual review filters precise used subsegments and preserves real member references", () => {
  const a = {uid: 'a', source_cabinet_uid: 'c1', destination_cabinet_uid: 'c2', cable_uids: ['real1'], route: {segment_ids: ['s1', 's2']}};
  const b = {uid: 'b', source_cabinet_uid: 'c2', destination_cabinet_uid: 'c3', cable_uids: ['real2'], route: {segment_ids: ['s1']}};
  const review = {groups: [a,b], loads: [{id: 'partial-s1', segment_id: 's1', group_uids: ['a']}]};
  assert.deepEqual(reviewGroupsForPart(review, 's1', 'partial-s1', null), [a]);
  assert.deepEqual(reviewGroupsForPart(review, 's1', null, null), [a,b]);
  assert.deepEqual(reviewGroupsForPart(review, null, null, 'c3'), [b]);
  assert.deepEqual(reviewGroupsForPart(review, null, null, null), [a,b]);
});

test("pathway focus includes whole groups and lets explicit cable, pair and cabinet focus narrow it", () => {
  const groups = [
    {uid:'a',source_cabinet_uid:'1',destination_cabinet_uid:'2'},
    {uid:'b',source_cabinet_uid:'3',destination_cabinet_uid:'4'},
    {uid:'c',source_cabinet_uid:'1',destination_cabinet_uid:'5'},
  ];
  const selected = new Set(['a','b']);
  assert.deepEqual(focusedRouteGroups(groups,null,null,undefined,selected),groups.slice(0,2));
  assert.deepEqual(focusedRouteGroups(groups,null,null,undefined,new Set()),[]);
  assert.deepEqual(focusedRouteGroups(groups,null,null,undefined,null),[]);
  assert.deepEqual(focusedRouteGroups(groups,'b',reviewPairKey(groups[0]),new Set(['1']),selected),[groups[1]]);
  assert.deepEqual(focusedRouteGroups(groups,null,reviewPairKey(groups[0]),new Set(['1']),selected),[groups[0]]);
  assert.deepEqual(focusedRouteGroups(groups,null,null,new Set(['1']),selected),[groups[0],groups[2]]);
});

test("physical segment and junction scope selects groups across tiers without truncating their routes", () => {
  const p=(x,tier)=>({x_in:x,y_in:382,tier});
  const route=(segments,points)=>({segment_ids:segments,points});
  const groups=[
    {uid:'a',route:route(['lead','selected','tail'],[p(0,1),p(120,1),p(240,1)])},
    {uid:'b',route:route(['selected','remote'],[p(120,3),p(360,3)])},
    {uid:'c',route:route(['other'],[p(480,1),p(600,1)])},
    {uid:'unrouted',route:null},
  ];
  const review={groups,loads:[]}, before=structuredClone(review);
  for(const selected of [reviewGroupsForPart(review,'selected',null,null),reviewGroupsForPart(review,null,null,null,p(120,2))]) {
    assert.deepEqual(selected.map(g=>g.uid),['a','b']);
    assert.equal(selected[0],groups[0]);
    assert.deepEqual(selected[0].route.segment_ids,['lead','selected','tail']);
  }
  assert.deepEqual(reviewGroupsForPart(review,'empty',null,null),[]);
  assert.deepEqual(review,before);
});

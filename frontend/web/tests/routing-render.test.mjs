import assert from "node:assert/strict";
import test from "node:test";
import {createRequire} from "node:module";
import {resolve} from "node:path";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {build} from "esbuild";

const require = createRequire(import.meta.url);
async function component(file, name) {
  const result = await build({entryPoints: [resolve(`src/routing/${file}.tsx`)], bundle: true, platform: "node", format: "cjs", packages: "external", write: false, logLevel: "silent", define: {"import.meta.env": "{}"}});
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
const box = {uid: "g", tier: 1, label: "G1", cable_class: "LC", sourceAvailable: true, demo: true, layer: 1, position: 1, slot_width: 3, slot_height: 2, offset_across_in: 0, offset_up_in: 0, occupied_width_in: 4, occupied_height_in: 2};
const span = {id: "span", passage_band_uid: "north", cross_route_uid: null, start_station_in: 0, end_station_in: 108, from_passage_band_uid: null, to_passage_band_uid: null};

const directions = {inner: "SOUTH", hasInner: true, axisStart: "NORTH"};
const sectionModel = {blocks: [box], parents: [], occupations: [], demoMode: true, width_in: 34, reference: "Demo only", directions};
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
  assert.match(physical, /DEMO dimensions/);
  assert.doesNotMatch(physical, /occupation grid|stroke="#cbd5e1"/);
  assert.match(physical, /Inspect rectangle G1/);
});

test("empty unconfigured segments still show an empty section in both display modes", () => {
  for (const mode of ["GRID", "PHYSICAL"]) {
    const html = renderToStaticMarkup(React.createElement(Section, {tier: null, model: {...sectionModel, blocks: [], demoMode: false}, mode, reversed: false, onSelectPlacement: () => {}}));
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

test("right panel filters fixtures by member ID and shows type count and rack pair", () => {
  const cables = ["a", "b"].map(id => ({id, cableClass: "LC", sourceCabinetId: "021", destinationCabinetId: "031"}));
  const html = renderToStaticMarkup(React.createElement(SegmentCables, {cables, selectedCableId: null, onSelect: () => {}, bundleFilter: {uid: "demo-group", label: "Group A", fixtureCableIds: ["a"]}}));
  assert.match(html, /1 fixture cable in group/);
  assert.match(html, /LC × 1 · 021 → 031/);
  assert.equal((html.match(/class="segment-cable-card/g) ?? []).length, 1);
  assert.match(html, /Show all segment cables/);
});

test("actual review group selection shows inventory cables and provisional routing without fake tiers", () => {
  const group = {uid: 'g', source_cabinet_id: '001', destination_cabinet_id: '011', cable_type: 'LC-TO-LC SMF', cable_uids: ['actual-1'], count: 1, route: {method: 'ASTAR', planar_length_in: 120}};
  const cables = [{uid: 'actual-1', cable_type: 'LC-TO-LC SMF', cable_class: 'LC', source_cabinet_id: '001', destination_cabinet_id: '011', source_port_name: 'P1', destination_port_name: 'P2', source_label: 'A01', destination_label: 'Z01', notes: ''}];
  const html = renderToStaticMarkup(React.createElement(CableReviewPanel, {review: {cables}, groups: [group], selectedGroupUid: 'g', onGroup: () => {}, selectedCableId: null, onCable: () => {}}));
  assert.match(html, /A\* cross-row placeholder/); assert.match(html, /actual-1/); assert.match(html, /A01/);
  assert.match(html, /border-left-color:#246bfe/);
  assert.match(html, /unassigned/); assert.doesNotMatch(html, /fixture cable|Fake review|Tier 1/);
});

test("large real cable lists render an initial page without hiding the actual total", () => {
  const cables = Array.from({length: 200}, (_, i) => ({uid: `actual-${i}`, cable_type: 'CAT6a', source_cabinet_id: '001', destination_cabinet_id: '002'}));
  const html = renderToStaticMarkup(React.createElement(SegmentCables, {cables: [], inventoryCables: cables, selectedCableId: null, onSelect: () => {}}));
  assert.match(html, /200 cables/);
  assert.equal((html.match(/class="segment-cable-card/g) ?? []).length, 60);
  assert.match(html, /Show 60 more cables/);
});

test("a straight actual-cable segment has a nonzero rectangular mouse target", () => {
  const point = x => ({x_in:x, y_in:382, passage_band_uid:'central', cabinet_uid:null});
  const review = {groups:[], cabinet_uids:[], loads:[{id:'load', source:point(0), target:point(120), cable_classes:['LC'], group_uids:[], cable_count:4}]};
  const view = {cabinets:[], passageX:new Map([['central',10]]), stationY:x=>x};
  const html = renderToStaticMarkup(React.createElement(CableReviewLayer, {data:{geometry:{bands:[]}}, view, review, scale:1, selectedGroupUid:null, selectedLoadId:null, onLoad:()=>{}, onAttachment:()=>{}}));
  assert.match(html, /<rect x="2" y="-8" width="16" height="136" fill="transparent"/);
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

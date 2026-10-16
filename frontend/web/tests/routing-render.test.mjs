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
const box = {uid: "g", tier: 1, label: "G1", cable_class: "LC", sourceAvailable: true, demo: true, layer: 1, position: 1, slot_width: 3, slot_height: 2, offset_across_in: 0, offset_up_in: 0, occupied_width_in: 4, occupied_height_in: 2};
const span = {id: "span", passage_band_uid: "north", cross_route_uid: null, start_station_in: 0, end_station_in: 108, from_passage_band_uid: null, to_passage_band_uid: null};

test("section SVG renders the default 12x8 grid and independent physical rectangle", () => {
  const html = renderToStaticMarkup(React.createElement(Section, {tier: 1, model: {blocks: [box], parents: [], occupations: [], demoMode: true, width_in: 34, reference: "Demo only"}, onSelectPlacement: () => {}}));
  assert.match(html, /12W × 8H grid/);
  assert.match(html, /Physical rectangles/);
  assert.match(html, /3×2 cells/);
  assert.match(html, /DEMO dimensions/);
  assert.equal((html.match(/stroke="#cbd5e1"/g) ?? []).length, 96);
  assert.doesNotMatch(html, /NaN|undefined|null/);
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

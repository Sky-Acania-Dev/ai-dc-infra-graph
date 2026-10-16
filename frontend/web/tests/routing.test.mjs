import assert from "node:assert/strict";
import test from "node:test";
import { formatInches, parseInches, formatMillimeters } from "../src/routing/dimensions.ts";
import { occupationGrid } from "../src/routing/sectionGrid.ts";
import { placeRoutingCabinets } from "../src/routing/cabinetPlacement.ts";
import { conceptualLayout } from "../src/routing/conceptualLayout.ts";
import { conceptualSegments, annotationFor, styleFixtures, rowName, passageName } from "../src/routing/conceptualSegments.ts";
import { segmentTierModel } from "../src/routing/segmentTierModel.ts";
import { sectionDirections, sectionView } from "../src/routing/sectionDirections.ts";
import { collectPlacementCables, filterCableMembers } from "../src/routing/segmentCableMembers.ts";
import { cabinetFixtureRun, projectFixtureRun, offsetPolyline } from "../src/routing/cabinetFixtureRun.ts";

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
test("style fixtures demonstrate all six cable classes and an unusable segment without mutating saved data", () => {
  const data = segmentFixture();
  for (let i = 2; i < 7; i++) {
    const row = { ...data.geometry.cabinet_rows[0], uid: `fixture-row${i}`, section_uid: "s1" };
    data.geometry.cabinet_rows.push(row);
    data.geometry.cross_routes.push({ uid: `cold${i}`, kind: "CABINET_COLD_AISLE", cabinet_row_uid: row.uid, station_in: 300 + i * 10, width_in: 24, effective_enabled: true });
  }
  data.geometry.cabinet_rows.forEach(row => row.section_uid = "s1");
  const before = structuredClone(data);
  const segments = conceptualSegments(data), examples = styleFixtures(data, segments);
  assert.deepEqual(new Set([...examples.values()].flatMap(s => s.cable_classes)), new Set(["LC", "CAT6", "MPO", "MPO_TRUNK_T2_T1_RO", "CROSS_SECTION_CAT6", "CROSS_SECTION_LC"]));
  assert.equal([...examples.values()].filter(s => !s.usable).length, 1);
  assert.ok([...examples.values()].some(s => s.cable_classes.length === 3));
  assert.deepEqual(styleFixtures(data, segments), examples);
  assert.deepEqual(data, before);
  assert.deepEqual(data.segment_annotations, []);
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
test("fixture preview handles layouts with no configured cabinet rows", () => {
  const data = segmentFixture();
  data.geometry.cabinet_rows = [];
  data.cabinet_rows = [];
  data.geometry.cross_routes = data.geometry.cross_routes.filter(r => r.kind === "SECTION_GAP");
  const fixtures = styleFixtures(data, conceptualSegments(data));
  assert.equal(fixtures.size, 2);
  assert.deepEqual(data.segment_annotations, []);
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
test("021 to 031 review cables use both cold routes and CENTRAL without changing saved data or creating tiers", () => {
  const data = cabinetRunFixture(), before = structuredClone(data), segments = conceptualSegments(data);
  const run = cabinetFixtureRun(data, segments);
  assert.ok(run);
  assert.equal(run.sourceCabinetUid, "c021");
  assert.equal(run.destinationCabinetUid, "c031");
  assert.deepEqual(run.cables.map(c => c.cableClass), ["LC", "MPO", "CAT6"]);
  assert.equal(new Set(run.cables.map(c => c.id)).size, 3);
  assert.equal(run.passageBandUid, "central");
  assert.equal(segments.find(s => s.id === run.segmentIds[0]).cross_route_uid, "route-row21");
  assert.equal(segments.find(s => s.id === run.segmentIds.at(-1)).cross_route_uid, "route-row31");
  assert.deepEqual([run.startStation, run.endStation], [372, 540]);
  assert.deepEqual(data, before);
  assert.deepEqual(data.segment_annotations, []);
});
test("fixture attachments touch cabinet edge centers on their explicit cold sides and preserve the serpentine columns", () => {
  const data = cabinetRunFixture(), segments = conceptualSegments(data), run = cabinetFixtureRun(data, segments);
  const view = conceptualLayout(data, placeRoutingCabinets(data)), geometry = projectFixtureRun(data, view, run, segments);
  const source = view.cabinets.find(t => t.cabinet.cabinet_uid === "c021"), destination = view.cabinets.find(t => t.cabinet.cabinet_uid === "c031");
  assert.ok(source.x < destination.x);
  assert.deepEqual(geometry.points[0], { x: source.x + (source.width - 2) / 2, y: source.y });
  assert.deepEqual(geometry.points.at(-1), { x: destination.x + (destination.width - 2) / 2, y: destination.y + destination.height - 2 });
  assert.ok(geometry.points[1].y < source.y);
  assert.ok(geometry.points.at(-2).y > destination.y + destination.height);
  assert.equal(geometry.parts.filter(p => p.kind === "attachment").length, 2);
  assert.equal(geometry.points[2].x, view.passageX.get("central"));
  assert.equal(geometry.points[3].x, view.passageX.get("central"));
});
test("parallel fixture lanes keep connected rectilinear corners across the cabinet connectors and shared corridor", () => {
  const points = [{ x: 0, y: 10 }, { x: 0, y: 0 }, { x: 20, y: 0 }, { x: 20, y: 20 }, { x: 10, y: 20 }, { x: 10, y: 10 }];
  assert.deepEqual(offsetPolyline(points, 2), [{ x: 2, y: 10 }, { x: 2, y: 2 }, { x: 18, y: 2 }, { x: 18, y: 18 }, { x: 12, y: 18 }, { x: 12, y: 10 }]);
  for (const offset of [-2, 0, 2]) {
    const lane = offsetPolyline(points, offset);
    assert.ok(lane.slice(1).every((p, i) => p.x === lane[i].x || p.y === lane[i].y));
  }
  assert.deepEqual(offsetPolyline([points[0], points[0], points[1]], 0), points.slice(0, 2));
});
test("endpoint fixtures disappear when a cabinet or its configured cold route is unavailable", () => {
  const data = cabinetRunFixture();
  data.cabinets = data.cabinets.filter(c => c.cabinet_uid !== "c031");
  assert.equal(cabinetFixtureRun(data, conceptualSegments(data)), null);
  const disabled = cabinetRunFixture();
  disabled.geometry.cross_routes.find(r => r.uid === "route-row31").effective_enabled = false;
  assert.equal(cabinetFixtureRun(disabled, conceptualSegments(disabled)), null);
  const unmapped = cabinetRunFixture();
  unmapped.cabinets.forEach(c => c.source_col = null);
  const segments = conceptualSegments(unmapped), run = cabinetFixtureRun(unmapped, segments);
  assert.equal(projectFixtureRun(unmapped, conceptualLayout(unmapped, placeRoutingCabinets(unmapped)), run, segments), null);
});

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
test("tier section demo positions are explicit, unique, and do not create heights, placements, or openings", () => {
  const data = tierFixture(), segments = conceptualSegments(data), run = cabinetFixtureRun(data, segments), before = structuredClone(data);
  const selected = segments.find(s => s.id === run.segmentIds[0]);
  const model = segmentTierModel(data, selected, run.cables);
  assert.equal(model.demoMode, true);
  assert.deepEqual(model.tiers, [1, 2, 3]);
  assert.equal(model.records.length, 0);
  assert.equal(model.openings.length, 0);
  const lc = model.blocks.find(b => b.cable_class === "LC");
  assert.deepEqual([lc.tier, lc.layer, lc.position, lc.demo], [1, 1, 1, true]);
  assert.equal(new Set(model.blocks.map(b => `${b.tier}:${b.layer}:${b.position}`)).size, 3);
  assert.deepEqual(data, before);
});
test("saved sectional positions and AFF elevations replace demo placements and filter openings to the selected span", () => {
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
  const model = segmentTierModel(data, selected, [{ id: "fake", cableClass: "MPO" }]);
  assert.equal(model.demoMode, false);
  assert.deepEqual(model.openings.map(o => o.uid), ["hole12", "hole23"]);
  assert.deepEqual(model.records.map(t => t.elevation_in), [120, 144, 168]);
  assert.deepEqual([model.blocks[0].tier, model.blocks[0].layer, model.blocks[0].position], [2, 2, 3]);
  assert.ok(model.blocks.every(b => !b.demo));
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
  assert.equal(model.demoMode, false);
});

test("metric display converts integer inches exactly and feet/inches remain canonical inches", () => {
  assert.equal(formatMillimeters(1), "25.4 mm");
  assert.equal(formatMillimeters(parseInches(`1'-0"`)), "304.8 mm");
  assert.equal(formatMillimeters(10), "254 mm");
  assert.throws(() => formatMillimeters(1.5));
});

test("12 by 8 integer occupation grid repeats one bundle across its multi-cell footprint", () => {
  const a = {uid: "a", layer: 1, position: 2, slot_width: 3, slot_height: 2};
  const b = {uid: "b", layer: 4, position: 6, slot_width: 4, slot_height: 2};
  const {cells, occupants} = occupationGrid(12, 8, [b, a]);
  assert.equal(cells.length, 8); assert.equal(cells[0].length, 12);
  assert.deepEqual(cells[0].slice(1, 4), [1, 1, 1]);
  assert.equal(cells[1][2], 1); assert.equal(cells[3][5], 2);
  assert.equal(cells.flat().filter(v => v !== 0).length, 14);
  assert.deepEqual(occupants.map(p => p.uid), ["a", "b"]);
  assert.deepEqual(cells, occupationGrid(12, 8, [a, b]).cells);
  assert.throws(() => occupationGrid(12, 8, [a, {...b, layer: 2, position: 3}]), /overlap/);
  assert.throws(() => occupationGrid(12, 8, [{...a, position: 12}]), /outside/);
});

test("physical-only rectangles do not manufacture grid slots or modify physical dimensions", () => {
  const p = {uid: "rect", layer: null, position: null, slot_width: null, slot_height: null, offset_across_in: 2, offset_up_in: 1, occupied_width_in: 6, occupied_height_in: 3};
  const before = structuredClone(p);
  assert.ok(occupationGrid(12, 8, [p]).cells.flat().every(v => v === 0));
  occupationGrid(24, 16, [p]);
  assert.deepEqual(p, before);
});

test("021 to 031 demonstrations include rectangular and multi-cell occupations without persistence", () => {
  const data = tierFixture(), segments = conceptualSegments(data), run = cabinetFixtureRun(data, segments), before = structuredClone(data);
  const model = segmentTierModel(data, segments.find(s => s.id === run.segmentIds[0]), run.cables);
  const lc = model.blocks.find(b => b.cable_class === "LC");
  assert.deepEqual([lc.slot_width, lc.slot_height, lc.occupied_width_in, lc.occupied_height_in], [3, 2, 4, 2]);
  assert.equal(occupationGrid(12, 8, model.blocks.filter(b => b.tier === 1)).cells.flat().filter(v => v > 0).length, 12);
  assert.deepEqual(data, before);
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
  const segments = conceptualSegments(data), run = cabinetFixtureRun(data, segments);
  const model = segmentTierModel(data, segments.find(s => s.id === run.segmentIds[0]), run.cables), before = structuredClone(model);
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
  assert.deepEqual(filterCableMembers([{id: "fake-a"}, {id: "fake-b"}], "demo-a", {}, ["fake-b"]), [{id: "fake-b"}]);
});

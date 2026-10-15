import assert from "node:assert/strict";
import test from "node:test";
import { formatInches, parseInches } from "../src/routing/dimensions.ts";
import { placeRoutingCabinets } from "../src/routing/cabinetPlacement.ts";
import { conceptualLayout } from "../src/routing/conceptualLayout.ts";
import { conceptualSegments, annotationFor, styleFixtures } from "../src/routing/conceptualSegments.ts";

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

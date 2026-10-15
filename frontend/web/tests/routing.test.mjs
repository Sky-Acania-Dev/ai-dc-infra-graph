import assert from "node:assert/strict";
import test from "node:test";
import { formatInches, parseInches } from "../src/routing/dimensions.ts";
import { placeRoutingCabinets } from "../src/routing/cabinetPlacement.ts";
import { conceptualLayout } from "../src/routing/conceptualLayout.ts";

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

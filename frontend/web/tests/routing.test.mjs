import assert from "node:assert/strict";
import test from "node:test";
import { formatInches, parseInches } from "../src/routing/dimensions.ts";
import { placeRoutingCabinets } from "../src/routing/cabinetPlacement.ts";

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

import unittest

import json

from backend.ingest.cutsheet import cutsheet_result_to_json, ingest_cutsheet_rows, parse_loc_cab_ru
from backend.validation import BreakoutFanoutRule


class CutsheetIngestionTests(unittest.TestCase):
    def test_parse_loc_cab_ru(self) -> None:
        location = parse_loc_cab_ru("dh1:001:10")

        self.assertEqual(location.data_hall_id, "DH1")
        self.assertEqual(location.cabinet_id, "001")
        self.assertEqual(location.rack_unit, 10)

    def test_infers_group_and_extracts_side_fields(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "OOB-FW"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-SIDE-DNS-NAME": "oob-fw-01",
                    "A-MODEL": "PA-1420",
                    "A-PORT": "ethernet1/21",
                    "A-OPTIC": "SFP-BASE-10G-LR",
                    "Z-LOC:CAB:RU": "dh1:002:42",
                    "Z-SIDE-DNS-NAME": "10G OOB DIA",
                    "Z-MODEL": "FDP",
                    "Z-PORT": "Mod B - LC #12 (23/24)",
                    "Z-OPTIC": "SFP-BASE-10G-LR",
                    "CABLE": "LC-TO-LC SMF",
                },
                {"STATUS": "Backbone"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "1/1/c13",
                    "A-BREAKOUT\nLOC:CAB:RU": "dh1:001:26",
                    "A-BREAKOUT\nSLOT:PORT": "1:1:1",
                    "Z-LOC:CAB:RU": "dh1:003:42",
                    "Z-PORT": "swp25",
                    "CABLE": "LC-TO-LC SMF",
                },
            ]
        )

        self.assertEqual(result.rows[0].group, "OOB-FW")
        self.assertEqual(result.rows[0].a_data_hall_id, "DH1")
        self.assertEqual(result.rows[0].a_cabinet_id, "001")
        self.assertEqual(result.rows[0].a_rack_unit, 10)
        self.assertEqual(result.rows[0].cable_type, "LC-TO-LC SMF")
        self.assertEqual(result.rows[1].group, "Backbone")
        self.assertEqual(result.cables[0].a_optic.model, "SFP-BASE-10G-LR")

    def test_breakout_allows_two_connections_from_same_port(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "Backbone"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "1/1/c13",
                    "A-BREAKOUT\nLOC:CAB:RU": "dh1:001:26",
                    "A-BREAKOUT\nSLOT:PORT": "1:1:1",
                    "Z-LOC:CAB:RU": "dh1:003:42",
                    "Z-PORT": "swp25",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "1/1/c13",
                    "A-BREAKOUT\nLOC:CAB:RU": "dh1:001:26",
                    "A-BREAKOUT\nSLOT:PORT": "1:1:2",
                    "Z-LOC:CAB:RU": "dh1:004:42",
                    "Z-PORT": "swp25",
                    "CABLE": "LC-TO-LC SMF",
                },
            ]
        )

        self.assertEqual(result.findings, [])

    def test_breakout_allows_unique_slot_port_fanout(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "Backbone"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "1/1/c15",
                    "A-BREAKOUT\nLOC:CAB:RU": "dh1:001:26",
                    "A-BREAKOUT\nSLOT:PORT": "1:3:1",
                    "Z-LOC:CAB:RU": "dh1:001:8",
                    "Z-PORT": "ens1f0np0",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "1/1/c15",
                    "A-BREAKOUT\nLOC:CAB:RU": "dh1:001:26",
                    "A-BREAKOUT\nSLOT:PORT": "1:3:2",
                    "Z-LOC:CAB:RU": "dh1:002:8",
                    "Z-PORT": "ens1f0np0",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "1/1/c15",
                    "A-BREAKOUT\nLOC:CAB:RU": "dh1:001:26",
                    "A-BREAKOUT\nSLOT:PORT": "1:3:3",
                    "Z-LOC:CAB:RU": "dh1:001:6",
                    "Z-PORT": "ens1f0np0",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "1/1/c15",
                    "A-BREAKOUT\nLOC:CAB:RU": "dh1:001:26",
                    "A-BREAKOUT\nSLOT:PORT": "1:3:4",
                    "Z-LOC:CAB:RU": "dh1:002:6",
                    "Z-PORT": "ens1f0np0",
                    "CABLE": "LC-TO-LC SMF",
                },
            ],
            breakout_rules=[BreakoutFanoutRule(max_child_connections=4)],
        )

        self.assertEqual(result.findings, [])

    def test_non_breakout_flags_duplicate_port_connections(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "OOB-FW"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "ethernet1/21",
                    "Z-LOC:CAB:RU": "dh1:002:42",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "ethernet1/21",
                    "Z-LOC:CAB:RU": "dh1:003:42",
                    "Z-PORT": "swp2",
                    "CABLE": "CAT6a",
                },
            ]
        )

        self.assertEqual(len(result.findings), 1)
        self.assertIn("only breakout or 2x2 shuffle rows", result.findings[0].message)

    def test_ingests_cable_not_run_rows(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "Backbone"},
                {
                    "STATUS": "Cable Not Run",
                    "A-LOC:CAB:RU": "dh1:006:35",
                    "A-PORT": "swp1",
                    "Z-LOC:CAB:RU": "dh1:006:44",
                    "Z-PORT": "swp59",
                    "CABLE": "LC-TO-LC SMF",
                },
            ]
        )

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].status, "Cable Not Run")
        self.assertEqual(result.rows[0].group, "Backbone")

    def test_accepts_valid_cable_row_with_blank_status(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {
                    "STATUS": "",
                    "A-LOC:CAB:RU": "dh1:030:38",
                    "A-PORT": "swp33s0",
                    "Z-LOC:CAB:RU": "dh2:182:39",
                    "Z-PORT": "swp1s0",
                    "CABLE": "MPO12 2x2",
                },
            ]
        )

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].status, "")
        self.assertEqual(result.rows[0].cable_type, "MPO12 2x2")

    def test_converts_roce_node_to_tier_rows(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {
                    "STATUS": "",
                    "A-SIDE-DNS-NAME": "dh1-r023-node-01-us-central-10a",
                    "A-LOC:CAB:RU": "dh1:023:37",
                    "A-MODEL": "GPU-GB300-02",
                    "A-MPO": "A1",
                    "A-PORT": "gpu0",
                    "A-INTERFACE": "ibs0p0",
                    "A-OPTIC": "MMS4X00-NM-FLT",
                    "Z-SIDE-DNS-NAME": "dh1-t0a-01-rail1-r030-us-central-10a",
                    "Z-LOC:CAB:RU": "dh1:030:38",
                    "Z-MODEL": "SN5610",
                    "Z-MPO": "B1",
                    "Z-PORT": "swp1",
                    "Z-INTERFACE": "swp1s0",
                    "Z-OPTIC": "MMS4X00-NM-T",
                },
                {
                    "STATUS": "",
                    "A-SIDE-DNS-NAME": "dh1-r023-node-01-us-central-10a",
                    "A-LOC:CAB:RU": "dh1:023:37",
                    "A-MODEL": "GPU-GB300-02",
                    "A-MPO": "A1",
                    "A-PORT": "gpu0",
                    "A-INTERFACE": "ibs0p1",
                    "A-OPTIC": "MMS4X00-NM-FLT",
                    "Z-SIDE-DNS-NAME": "dh1-t0b-01-rail1-r030-us-central-10a",
                    "Z-LOC:CAB:RU": "dh1:030:39",
                    "Z-MODEL": "SN5610",
                    "Z-MPO": "B1",
                    "Z-PORT": "swp1",
                    "Z-INTERFACE": "swp1s1",
                    "Z-OPTIC": "MMS4X00-NM-T",
                },
            ]
        )

        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0].a_port_id, "ibs0p0")
        self.assertEqual(result.rows[0].z_port_id, "swp1s0")
        self.assertEqual(result.rows[0].cable_type, "MPO12 2x2")
        self.assertEqual(result.rows[1].a_port_id, "ibs0p1")
        self.assertEqual(result.findings, [])

    def test_json_report_has_summary_and_explicit_collision_findings(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "OOB-FW"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "ethernet1/21",
                    "Z-LOC:CAB:RU": "dh1:002:42",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
            ]
        )

        payload = json.loads(cutsheet_result_to_json(result))

        self.assertEqual(payload["summary"]["rows"], 1)
        self.assertEqual(payload["summary"]["port_collision_findings"], 0)
        self.assertIn("port_collision_findings", payload)
        self.assertNotIn("findings", payload)


if __name__ == "__main__":
    unittest.main()

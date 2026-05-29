import unittest

from backend.api.validation import PortCollisionRequest, find_port_collisions
from backend.validation import detect_port_collisions


class PortCollisionTests(unittest.TestCase):
    def test_detects_non_breakout_duplicate_port(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "a_port_uid": "DH1:001:10:ethernet1/1",
                    "z_port_uid": "DH1:002:10:swp1",
                },
                {
                    "a_port_uid": "DH1:001:10:ethernet1/1",
                    "z_port_uid": "DH1:003:10:swp1",
                },
            ]
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].port_uid, "DH1:001:10:ethernet1/1")

    def test_allows_breakout_with_unique_slot_ports(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "a_port_uid": "DH1:001:28:1/1/c15",
                    "a_breakout_loc_cab_ru": "dh1:001:26",
                    "a_breakout_slot_port": "1:3:1",
                    "z_port_uid": "DH1:001:8:ens1f0np0",
                },
                {
                    "a_port_uid": "DH1:001:28:1/1/c15",
                    "a_breakout_loc_cab_ru": "dh1:001:26",
                    "a_breakout_slot_port": "1:3:2",
                    "z_port_uid": "DH1:002:8:ens1f0np0",
                },
            ]
        )

        self.assertEqual(findings, [])

    def test_flags_breakout_with_duplicate_slot_port(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "a_port_uid": "DH1:001:28:1/1/c15",
                    "a_breakout_loc_cab_ru": "dh1:001:26",
                    "a_breakout_slot_port": "1:3:1",
                    "z_port_uid": "DH1:001:8:ens1f0np0",
                },
                {
                    "a_port_uid": "DH1:001:28:1/1/c15",
                    "a_breakout_loc_cab_ru": "dh1:001:26",
                    "a_breakout_slot_port": "1:3:1",
                    "z_port_uid": "DH1:002:8:ens1f0np0",
                },
            ]
        )

        self.assertEqual(len(findings), 1)
        self.assertIn("unique breakout slot/port", findings[0].message)

    def test_port_collision_api(self) -> None:
        findings = find_port_collisions(
            PortCollisionRequest(
                rows=[
                    {
                        "group": "OOB-FW",
                        "status": "Cable Is Ran: Complete",
                        "cable_type": "CAT6a",
                        "a_data_hall_id": "DH1",
                        "a_cabinet_id": "001",
                        "a_rack_unit": 10,
                        "a_port_id": "ethernet1/1",
                        "a_port_uid": "DH1:001:10:ethernet1/1",
                        "z_data_hall_id": "DH1",
                        "z_cabinet_id": "002",
                        "z_rack_unit": 10,
                        "z_port_id": "swp1",
                        "z_port_uid": "DH1:002:10:swp1",
                    },
                    {
                        "group": "OOB-FW",
                        "status": "Cable Is Ran: Complete",
                        "cable_type": "CAT6a",
                        "a_data_hall_id": "DH1",
                        "a_cabinet_id": "001",
                        "a_rack_unit": 10,
                        "a_port_id": "ethernet1/1",
                        "a_port_uid": "DH1:001:10:ethernet1/1",
                        "z_data_hall_id": "DH1",
                        "z_cabinet_id": "003",
                        "z_rack_unit": 10,
                        "z_port_id": "swp1",
                        "z_port_uid": "DH1:003:10:swp1",
                    },
                ]
            )
        )

        self.assertEqual(findings[0].port_uid, "DH1:001:10:ethernet1/1")


if __name__ == "__main__":
    unittest.main()

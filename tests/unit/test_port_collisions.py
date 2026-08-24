import unittest

from backend.api.validation import PortCollisionRequest, find_port_collisions
from backend.validation import BreakoutFanoutRule, detect_port_collisions


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

    def test_breakout_rule_defaults_to_four_way_fanout(self) -> None:
        rows = [
            {
                "a_port_uid": "DH1:001:28:1/1/c15",
                "a_breakout_loc_cab_ru": "dh1:001:26",
                "a_breakout_slot_port": f"1:3:{index}",
                "z_port_uid": f"DH1:00{index}:8:ens1f0np0",
            }
            for index in range(1, 5)
        ]

        default_findings = detect_port_collisions(rows)
        strict_findings = detect_port_collisions(
            rows,
            breakout_rules=[BreakoutFanoutRule(name="Strict 2-way breakout", max_child_connections=2)],
        )

        self.assertEqual(default_findings, [])
        self.assertEqual(len(strict_findings), 1)

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

    def test_allows_two_connections_for_2x2_shuffle_ports(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "cable_type": "MPO12 2x2",
                    "a_port_uid": "DH1:023:37:ibs0p0",
                    "z_port_uid": "DH1:030:38:swp1s0",
                },
                {
                    "cable_type": "MPO12 2x2",
                    "a_port_uid": "DH1:023:37:ibs0p0",
                    "z_port_uid": "DH1:031:38:swp1s0",
                },
            ]
        )

        self.assertEqual(findings, [])

    def test_flags_2x2_shuffle_port_used_more_than_twice(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "cable_type": "MPO12 2x2",
                    "a_port_uid": "DH1:023:37:ibs0p0",
                    "z_port_uid": f"DH1:03{index}:38:swp1s0",
                }
                for index in range(3)
            ]
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].port_uid, "DH1:023:37:ibs0p0")

    def test_allows_sixteen_connections_for_4x4_shuffle_ports(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "cable_type": "MPO12 4x4",
                    "a_port_uid": "DH1:023:37:ibs0p0",
                    "z_port_uid": f"DH1:03{index}:38:swp1s0",
                }
                for index in range(16)
            ]
        )

        self.assertEqual(findings, [])

    def test_flags_4x4_shuffle_port_used_more_than_sixteen_times(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "cable_type": "MPO12 4 x 4",
                    "a_port_uid": "DH1:023:37:ibs0p0",
                    "z_port_uid": f"DH1:03{index}:38:swp1s0",
                }
                for index in range(17)
            ]
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].port_uid, "DH1:023:37:ibs0p0")

    def test_flags_mixed_2x2_and_non_shuffle_duplicate_port(self) -> None:
        findings = detect_port_collisions(
            [
                {
                    "cable_type": "MPO12 2x2",
                    "a_port_uid": "DH1:023:37:ibs0p0",
                    "z_port_uid": "DH1:030:38:swp1s0",
                },
                {
                    "cable_type": "CAT6a",
                    "a_port_uid": "DH1:023:37:ibs0p0",
                    "z_port_uid": "DH1:031:38:swp1s0",
                },
            ]
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].port_uid, "DH1:023:37:ibs0p0")

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

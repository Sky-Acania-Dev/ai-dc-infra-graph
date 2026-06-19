import unittest

from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.services import build_topology_database_from_results
from backend.services.topology_change_list import compare_topology_databases


class TopologyChangeListTests(unittest.TestCase):
    def test_compares_topology_databases_by_construction_phase_and_port_pair(self) -> None:
        overhead_result = OverheadIngestionResult(
            summary=OverheadIngestionSummary(cabinets=3, data_halls=1, unknown_category_cabinets=0),
            cabinets=[
                CabinetInventoryRecord(
                    cabinet_uid="DH1:001",
                    data_hall_id="DH1",
                    cabinet_id="001",
                    category="DPR-H1",
                    source_row=1,
                    source_col=1,
                ),
                CabinetInventoryRecord(
                    cabinet_uid="DH1:002",
                    data_hall_id="DH1",
                    cabinet_id="002",
                    category="DPR-H1",
                    source_row=1,
                    source_col=2,
                ),
                CabinetInventoryRecord(
                    cabinet_uid="DH1:003",
                    data_hall_id="DH1",
                    cabinet_id="003",
                    category="DPR-H1",
                    source_row=1,
                    source_col=3,
                ),
            ],
        )
        old_database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A-MODEL": "Old Switch",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "CABLE": "LC",
                    },
                    {
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh1:001:11",
                        "A-PORT": "swp3",
                        "Z-LOC:CAB:RU": "dh1:002:21",
                        "Z-PORT": "swp4",
                        "CABLE": "LC",
                    },
                ]
            ),
            overhead_result=overhead_result,
        )
        new_database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A-MODEL": "New Switch",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "CABLE": "LC",
                    },
                    {
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh1:001:12",
                        "A-PORT": "swp5",
                        "Z-LOC:CAB:RU": "dh1:003:21",
                        "Z-PORT": "swp6",
                        "CABLE": "LC",
                    },
                ]
            ),
            overhead_result=overhead_result,
        )

        change_list = compare_topology_databases(old_database, new_database, identity="port_pair")

        self.assertEqual(change_list.added, 1)
        self.assertEqual(change_list.removed, 1)
        self.assertEqual(change_list.changed, 1)
        changed = [change for change in change_list.changes if change.change_type == "changed"][0]
        self.assertIn("status", changed.fields)
        self.assertIn("a_device_model", changed.fields)

    def test_compares_topology_databases_by_cable_uid(self) -> None:
        overhead_result = OverheadIngestionResult(
            summary=OverheadIngestionSummary(cabinets=2, data_halls=1, unknown_category_cabinets=0),
            cabinets=[
                CabinetInventoryRecord(
                    cabinet_uid="DH1:001",
                    data_hall_id="DH1",
                    cabinet_id="001",
                    category="DPR-H1",
                    source_row=1,
                    source_col=1,
                ),
                CabinetInventoryRecord(
                    cabinet_uid="DH1:002",
                    data_hall_id="DH1",
                    cabinet_id="002",
                    category="DPR-H1",
                    source_row=1,
                    source_col=2,
                ),
            ],
        )
        old_database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "CABLE UID": "CW-001",
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "CABLE": "LC",
                    }
                ]
            ),
            overhead_result=overhead_result,
        )
        new_database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "CABLE UID": "CW-001",
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:11",
                        "A-PORT": "swp3",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "CABLE": "MPO12",
                    }
                ]
            ),
            overhead_result=overhead_result,
        )

        change_list = compare_topology_databases(old_database, new_database, identity="cable_uid")

        self.assertEqual(change_list.added, 0)
        self.assertEqual(change_list.removed, 0)
        self.assertEqual(change_list.changed, 1)
        changed = change_list.changes[0]
        self.assertEqual(changed.key, "CW-001")
        self.assertEqual(changed.old_cable_uid, "CW-001")
        self.assertEqual(changed.new_cable_uid, "CW-001")
        self.assertIn("port_pair_key", changed.fields)
        self.assertIn("cable_type", changed.fields)

    def test_can_filter_changed_records_to_significant_fields(self) -> None:
        overhead_result = OverheadIngestionResult(
            summary=OverheadIngestionSummary(cabinets=2, data_halls=1, unknown_category_cabinets=0),
            cabinets=[
                CabinetInventoryRecord(
                    cabinet_uid="DH1:001",
                    data_hall_id="DH1",
                    cabinet_id="001",
                    category="DPR-H1",
                    source_row=1,
                    source_col=1,
                ),
                CabinetInventoryRecord(
                    cabinet_uid="DH1:002",
                    data_hall_id="DH1",
                    cabinet_id="002",
                    category="DPR-H1",
                    source_row=1,
                    source_col=2,
                ),
            ],
        )
        old_database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "CABLE UID": "CW-001",
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "CABLE": "LC",
                    }
                ]
            ),
            overhead_result=overhead_result,
        )
        new_database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "CABLE UID": "CW-001",
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "CABLE": "LC",
                    }
                ]
            ),
            overhead_result=overhead_result,
        )

        change_list = compare_topology_databases(
            old_database,
            new_database,
            identity="cable_uid",
            significant_fields={"cable_type"},
        )

        self.assertEqual(change_list.changed, 0)


if __name__ == "__main__":
    unittest.main()

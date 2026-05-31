import unittest

from backend.api.topology import (
    cabinet_connection_cables,
    cabinet_detail,
    cabinet_layout,
    device_connection_cables,
    device_connections,
    validation_report,
)
from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.persistence import save_topology_database
from backend.services import build_topology_database_from_results
from tests.unit.test_json_database import _test_paths


class TopologyApiTests(unittest.TestCase):
    def test_cabinet_detail_includes_devices_and_connections(self) -> None:
        _, runtime_path = _test_paths()
        database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {"STATUS": "Backbone"},
                    {
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A_MODEL": "NVIDIA Spectrum SN5600",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp1",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "CAT6a",
                    },
                    {
                        "STATUS": "Cable Is Ran: Not Terminated",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp2",
                        "A_MODEL": "NVIDIA Spectrum SN5600",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "CAT6a",
                    },
                ]
            ),
            overhead_result=OverheadIngestionResult(
                summary=OverheadIngestionSummary(cabinets=2, data_halls=1, unknown_category_cabinets=0),
                cabinets=[
                    CabinetInventoryRecord(
                        cabinet_uid="DH1:001",
                        data_hall_id="DH1",
                        cabinet_id="001",
                        category="DPR-H1",
                        cabinet_group="Fabric Core",
                        source_row=7,
                        source_col=5,
                    ),
                    CabinetInventoryRecord(
                        cabinet_uid="DH1:002",
                        data_hall_id="DH1",
                        cabinet_id="002",
                        category="DPR-H2",
                        cabinet_group="Fabric Core",
                        source_row=7,
                        source_col=6,
                    ),
                ],
            ),
        )
        save_topology_database(database, runtime_path)

        layout = cabinet_layout(data_hall="DH1", database_path=str(runtime_path))
        detail = cabinet_detail("DH1:001", database_path=str(runtime_path))
        cable_detail = cabinet_connection_cables("DH1:001", "DH1:002", database_path=str(runtime_path))

        self.assertEqual(len(layout), 2)
        self.assertEqual(detail.stats.devices, 1)
        self.assertEqual(detail.cabinet.max_rack_unit, 48)
        self.assertEqual(detail.devices[0].device_model, "NVIDIA Spectrum SN5600")
        self.assertEqual(detail.connections[0].target_cabinet_uid, "DH1:002")
        self.assertEqual(detail.connections[0].status_summary.completed, 1)
        self.assertEqual(detail.connections[0].status_summary.total, 2)
        self.assertEqual(detail.connections[0].status_summary.status_counts["Cable Is Ran: Not Terminated"], 1)
        self.assertEqual(len(cable_detail.cables), 2)
        self.assertEqual(cable_detail.cables[0].uid, "CBL-000001")
        self.assertIsNone(cable_detail.cables[0].length_meters)
        self.assertEqual(cable_detail.cables[0].a_port_uid, "DH1:001:10:swp1")

        device_detail = device_connections("DH1:001", 10, database_path=str(runtime_path))
        device_cable_detail = device_connection_cables("DH1:001:10", "DH1:002:20", database_path=str(runtime_path))

        self.assertEqual(device_detail.source_device_uid, "DH1:001:10")
        self.assertEqual(device_detail.connected_devices[0].target_device_uid, "DH1:002:20")
        self.assertEqual(device_detail.connected_cabinet_uids, ["DH1:002"])
        self.assertEqual(device_detail.connected_devices[0].status_summary.completed, 1)
        self.assertEqual(device_detail.connected_devices[0].status_summary.total, 2)
        self.assertEqual(device_cable_detail.source_device_uid, "DH1:001:10")
        self.assertEqual(device_cable_detail.target_device_uid, "DH1:002:20")
        self.assertEqual(len(device_cable_detail.cables), 2)
        self.assertEqual(device_cable_detail.cables[0].a_port_uid, "DH1:001:10:swp1")

        validation = validation_report(database_path=str(runtime_path))

        self.assertEqual(validation.summary.port_collision_findings, 0)
        self.assertEqual(validation.summary.device_model_mismatches, 0)
        self.assertEqual(validation.summary.device_model_format_issues, 0)

    def test_cabinet_detail_includes_intra_cabinet_cables(self) -> None:
        _, runtime_path = _test_paths()
        database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A_MODEL": "Switch",
                        "Z-LOC:CAB:RU": "dh1:001:20",
                        "Z-PORT": "swp2",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "LC",
                    },
                ]
            ),
            overhead_result=OverheadIngestionResult(
                summary=OverheadIngestionSummary(cabinets=1, data_halls=1, unknown_category_cabinets=0),
                cabinets=[
                    CabinetInventoryRecord(
                        cabinet_uid="DH1:001",
                        data_hall_id="DH1",
                        cabinet_id="001",
                        category="DPR-H1",
                        cabinet_group="Fabric Core",
                        source_row=7,
                        source_col=5,
                    ),
                ],
            ),
        )
        save_topology_database(database, runtime_path)

        detail = cabinet_detail("DH1:001", database_path=str(runtime_path))
        cable_detail = cabinet_connection_cables("DH1:001", "DH1:001", database_path=str(runtime_path))

        self.assertIsNotNone(detail.intra_cabinet_connection)
        self.assertEqual(detail.intra_cabinet_connection.total_cables, 1)
        self.assertEqual(cable_detail.cables[0].z_port_uid, "DH1:001:20:swp2")

        device_detail = device_connections("DH1:001", 10, database_path=str(runtime_path))
        device_cable_detail = device_connection_cables("DH1:001:10", "DH1:001:20", database_path=str(runtime_path))

        self.assertEqual(device_detail.connected_devices[0].target_device_uid, "DH1:001:20")
        self.assertEqual(device_detail.connected_cabinet_uids, ["DH1:001"])
        self.assertEqual(len(device_cable_detail.cables), 1)
        self.assertEqual(device_cable_detail.cables[0].z_port_uid, "DH1:001:20:swp2")


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.api.topology import cabinet_connection_cables, cabinet_detail, cabinet_layout
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
        self.assertEqual(detail.devices[0].device_model, "NVIDIA Spectrum SN5600")
        self.assertEqual(detail.connections[0].target_cabinet_uid, "DH1:002")
        self.assertEqual(len(cable_detail.cables), 1)
        self.assertEqual(cable_detail.cables[0].a_port_uid, "DH1:001:10:swp1")


if __name__ == "__main__":
    unittest.main()

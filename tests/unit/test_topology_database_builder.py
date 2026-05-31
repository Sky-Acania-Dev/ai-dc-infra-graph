import unittest

from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.graph import build_cabinet_graph
from backend.models import LifecycleStatus
from backend.services import build_topology_database_from_results
from backend.services.status_overrides import DeviceStatusOverride, StatusOverrides


class TopologyDatabaseBuilderTests(unittest.TestCase):
    def test_combines_overhead_cabinets_with_cutsheet_connectivity(self) -> None:
        cutsheet_result = ingest_cutsheet_rows(
            [
                {"STATUS": "Backbone"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "swp1",
                    "Z-LOC:CAB:RU": "dh1:002:20",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
            ]
        )
        overhead_result = OverheadIngestionResult(
            summary=OverheadIngestionSummary(cabinets=3, data_halls=1, unknown_category_cabinets=0),
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
                CabinetInventoryRecord(
                    cabinet_uid="DH1:003",
                    data_hall_id="DH1",
                    cabinet_id="003",
                    category="RES",
                    cabinet_group="Fabric Core",
                    source_row=7,
                    source_col=7,
                ),
            ],
        )

        database = build_topology_database_from_results(
            cutsheet_result,
            overhead_result,
            status_overrides=StatusOverrides(
                cabinets={"DH1:002": LifecycleStatus.NOT_POWERED},
                cabinet_max_rack_units={"DH1:002": 42},
                devices={
                    "DH1:001:06": DeviceStatusOverride(
                        device_uid="DH1:001:06",
                        lifecycle_status=LifecycleStatus.NOT_INSTALLED,
                        device_model="Manual Device Placeholder",
                    )
                },
            ),
        )

        self.assertEqual(database.summary.cabinets, 3)
        self.assertEqual(database.summary.cables, 1)
        self.assertEqual(database.cabinets[0].category, "DPR-H1")
        self.assertEqual(database.cabinets[0].cabinet_group, "Fabric Core")
        self.assertEqual(database.cabinets[0].lifecycle_status, LifecycleStatus.NOT_INSTALLED)
        self.assertEqual(database.cabinets[0].max_rack_unit, 48)
        self.assertEqual(len(database.cabinets[0].devices), 2)
        self.assertEqual(database.cabinets[0].devices[0].rack_unit, 6)
        self.assertEqual(database.cabinets[0].devices[0].device_model, "Manual Device Placeholder")
        self.assertEqual(database.cabinets[0].devices[0].lifecycle_status, LifecycleStatus.NOT_INSTALLED)
        self.assertEqual(database.cabinets[0].devices[1].rack_unit, 10)
        self.assertEqual(database.cabinets[1].lifecycle_status, LifecycleStatus.NOT_POWERED)
        self.assertEqual(database.cabinets[1].max_rack_unit, 42)
        self.assertEqual(database.data_halls[0].cabinets[2].category, "RES")
        self.assertEqual(database.data_halls[0].cabinets[2].lifecycle_status, LifecycleStatus.NOT_PLANNED)

        graph = build_cabinet_graph(database)

        self.assertEqual(graph.nodes["DH1:001"]["category"], "DPR-H1")
        self.assertEqual(graph.nodes["DH1:001"]["visualization_category"], "DPR-H1")
        self.assertEqual(graph.nodes["DH1:001"]["cabinet_group"], "Fabric Core")

    def test_merges_device_aliases_by_physical_rack_unit(self) -> None:
        cutsheet_result = ingest_cutsheet_rows(
            [
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "swp1",
                    "A_SIDE_DNS_NAME": "leaf-a",
                    "A_MODEL": "SN5600",
                    "Z-LOC:CAB:RU": "dh1:002:20",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "swp2",
                    "A_SIDE_DNS_NAME": "leaf-a.alt",
                    "A_MODEL": "NVIDIA SN5600",
                    "Z-LOC:CAB:RU": "dh1:002:21",
                    "Z-PORT": "swp2",
                    "CABLE": "CAT6a",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:18",
                    "A-PORT": "swp31",
                    "A_SIDE_DNS_NAME": "core-a",
                    "A_MODEL": "SN3700",
                    "Z-LOC:CAB:RU": "dh1:002:18",
                    "Z-PORT": "swp31",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:18",
                    "A-PORT": "swp32",
                    "A_SIDE_DNS_NAME": "core-a",
                    "A_MODEL": "SN4700",
                    "Z-LOC:CAB:RU": "dh1:002:18",
                    "Z-PORT": "swp32",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "swp1",
                    "A_MODEL": "7750-SR-1SE",
                    "Z-LOC:CAB:RU": "dh1:002:28",
                    "Z-PORT": "swp1",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:28",
                    "A-PORT": "swp2",
                    "A_MODEL": "NOKIA-7750-SR-1se",
                    "Z-LOC:CAB:RU": "dh1:002:28",
                    "Z-PORT": "swp2",
                    "CABLE": "LC-TO-LC SMF",
                },
            ]
        )
        overhead_result = OverheadIngestionResult(
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
        )

        database = build_topology_database_from_results(cutsheet_result, overhead_result)
        device = database.cabinets[0].devices[0]

        self.assertEqual(len(database.cabinets[0].devices), 3)
        self.assertEqual(device.rack_unit, 10)
        self.assertEqual(device.aliases, ["leaf-a", "leaf-a.alt"])
        self.assertEqual(device.device_model, "NVIDIA SN5600")
        self.assertEqual(device.model_aliases, ["SN5600"])
        self.assertEqual(len(device.ports_by_type), 1)
        self.assertEqual(len(device.ports_by_type["CAT6"]), 2)
        self.assertEqual(
            [finding.device_uid for finding in database.device_model_format_issues],
            ["DH1:001:10", "DH1:001:28"],
        )
        self.assertEqual(_counts_to_dict(database.device_model_format_issues[0].normalized_models), {"SN5600": 2})
        self.assertEqual(_counts_to_dict(database.device_model_format_issues[1].normalized_models), {"7750SR1SE": 2})
        self.assertEqual(database.device_model_mismatches[0].device_uid, "DH1:001:18")
        self.assertEqual(_counts_to_dict(database.device_model_mismatches[0].models), {"SN3700": 1, "SN4700": 1})
        self.assertEqual(_counts_to_dict(database.device_model_mismatches[0].normalized_models), {"SN3700": 1, "SN4700": 1})

def _counts_to_dict(counts):
    return {item.value: item.count for item in counts}


if __name__ == "__main__":
    unittest.main()

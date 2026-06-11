import unittest
from unittest.mock import patch

from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.graph import build_cabinet_graph
from backend.models import ConstructionPhase, LifecycleStatus
from backend.services import build_topology_database_from_results, build_topology_database_from_sources
from backend.services.status_overrides import DeviceModelOverride, DeviceStatusOverride, StatusOverrides


class TopologyDatabaseBuilderTests(unittest.TestCase):
    def test_build_from_sources_expands_multiple_roce_sheet_names(self) -> None:
        with (
            patch("backend.services.topology_database_builder.ingest_cutsheet_sources") as ingest_sources,
            patch("backend.services.topology_database_builder.ingest_overhead") as ingest_overhead,
            patch("backend.services.topology_database_builder.build_topology_database_from_pipeline_result") as build_from_pipeline,
        ):
            ingest_sources.return_value = object()
            ingest_overhead.return_value = object()
            build_from_pipeline.return_value = object()

            database = build_topology_database_from_sources(
                cutsheet_path="management.ods",
                roce_cutsheet_path="roce.ods",
                overhead_path="overhead.ods",
                roce_cutsheet_sheet_name=["DH1 NODE TO TIER-0", "DH2 NODE TO TIER-0"],
            )

        self.assertIs(database, build_from_pipeline.return_value)
        sources = ingest_sources.call_args.args[0]
        self.assertEqual([source.source_name for source in sources], ["management", "roce:DH1 NODE TO TIER-0", "roce:DH2 NODE TO TIER-0"])
        self.assertEqual([source.path for source in sources], ["management.ods", "roce.ods", "roce.ods"])
        self.assertEqual([source.sheet_name for source in sources], [None, "DH1 NODE TO TIER-0", "DH2 NODE TO TIER-0"])
        self.assertEqual(
            [source.construction_phase for source in sources],
            [ConstructionPhase.MANAGEMENT_ETHERNET, ConstructionPhase.ROCE, ConstructionPhase.ROCE],
        )

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
            summary=OverheadIngestionSummary(cabinets=4, data_halls=1, unknown_category_cabinets=0),
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
                CabinetInventoryRecord(
                    cabinet_uid="DH1:004",
                    data_hall_id="DH1",
                    cabinet_id="004",
                    category="HD-GB3c",
                    cabinet_group="Fabric Core",
                    source_row=7,
                    source_col=8,
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
                device_models={
                    "MANUAL-DEVICE-PLACEHOLDER": DeviceModelOverride(
                        model_name="Manual Device Placeholder",
                        manufacturer="Manual",
                        rack_units=2,
                    )
                },
            ),
        )

        self.assertEqual(database.summary.cabinets, 4)
        self.assertEqual(database.summary.cables, 1)
        self.assertEqual(database.cabinets[0].category, "DPR-H1")
        self.assertEqual(database.cabinets[0].cabinet_group, "Fabric Core")
        self.assertEqual(database.cabinets[0].lifecycle_status, LifecycleStatus.NOT_INSTALLED)
        self.assertEqual(database.cabinets[0].construction_phase, ConstructionPhase.MANAGEMENT_ETHERNET)
        self.assertEqual(database.cabinets[0].max_rack_unit, 48)
        self.assertEqual(len(database.cabinets[0].devices), 2)
        self.assertEqual(database.cabinets[0].devices[0].rack_unit, 6)
        self.assertEqual(database.cabinets[0].devices[0].device_model, "Manual Device Placeholder")
        self.assertEqual(database.cabinets[0].devices[0].device_model_uid, "MANUAL-DEVICE-PLACEHOLDER")
        self.assertEqual(database.cabinets[0].devices[0].rack_units, 2)
        self.assertEqual(database.cabinets[0].devices[0].lifecycle_status, LifecycleStatus.NOT_INSTALLED)
        self.assertEqual(database.cabinets[0].devices[0].construction_phase, ConstructionPhase.MANAGEMENT_ETHERNET)
        self.assertEqual(database.cabinets[0].devices[1].rack_unit, 10)
        self.assertEqual(database.device_models[0].manufacturer, "Manual")
        self.assertEqual(database.device_models[0].rack_units, 2)
        self.assertEqual(database.cabinets[1].lifecycle_status, LifecycleStatus.NOT_POWERED)
        self.assertEqual(database.cabinets[1].max_rack_unit, 42)
        self.assertEqual(database.data_halls[0].construction_phase, ConstructionPhase.MANAGEMENT_ETHERNET)
        self.assertEqual(database.data_halls[0].cabinets[2].category, "RES")
        self.assertEqual(database.data_halls[0].cabinets[2].lifecycle_status, LifecycleStatus.NOT_PLANNED)
        self.assertEqual(database.data_halls[0].cabinets[3].category, "HD-GB3c")
        self.assertEqual(database.data_halls[0].cabinets[3].construction_phase, ConstructionPhase.ROCE)
        self.assertEqual(database.cables[0].construction_phase, ConstructionPhase.MANAGEMENT_ETHERNET)

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

    def test_combines_management_and_roce_cutsheets(self) -> None:
        management_result = ingest_cutsheet_rows(
            [
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "mgmt1",
                    "A_MODEL": "SN5610",
                    "Z-LOC:CAB:RU": "dh1:002:20",
                    "Z-PORT": "mgmt1",
                    "Z_MODEL": "SN5610",
                    "CABLE": "CAT6a",
                },
            ]
        )
        roce_result = ingest_cutsheet_rows(
            [
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:003:30",
                    "A-PORT": "eth1",
                    "A_MODEL": "GB300-NVLINK-SW",
                    "Z-LOC:CAB:RU": "dh1:004:31",
                    "Z-PORT": "eth1",
                    "Z_MODEL": "GPU-GB300-02",
                    "CABLE": "MPO12-SMF",
                },
            ]
        )
        overhead_result = OverheadIngestionResult(
            summary=OverheadIngestionSummary(cabinets=4, data_halls=1, unknown_category_cabinets=0),
            cabinets=[
                CabinetInventoryRecord(cabinet_uid="DH1:001", data_hall_id="DH1", cabinet_id="001", category="DPR-H1", cabinet_group="Core", source_row=1, source_col=1),
                CabinetInventoryRecord(cabinet_uid="DH1:002", data_hall_id="DH1", cabinet_id="002", category="DPR-H2", cabinet_group="Core", source_row=1, source_col=2),
                CabinetInventoryRecord(cabinet_uid="DH1:003", data_hall_id="DH1", cabinet_id="003", category="HD-GB3c", cabinet_group="GPU", source_row=1, source_col=3),
                CabinetInventoryRecord(cabinet_uid="DH1:004", data_hall_id="DH1", cabinet_id="004", category="HD-GB3c", cabinet_group="GPU", source_row=1, source_col=4),
            ],
        )

        database = build_topology_database_from_results(
            cutsheet_result=management_result,
            roce_cutsheet_result=roce_result,
            overhead_result=overhead_result,
        )

        self.assertEqual(database.summary.rows, 2)
        self.assertEqual(database.summary.cables, 2)
        self.assertEqual(database.cables[0].uid, "CBL-000001")
        self.assertEqual(database.cables[0].construction_phase, ConstructionPhase.MANAGEMENT_ETHERNET)
        self.assertEqual(database.cables[1].uid, "CBL-000002")
        self.assertEqual(database.cables[1].construction_phase, ConstructionPhase.ROCE)
        self.assertEqual(database.cabinets[2].devices[0].construction_phase, ConstructionPhase.ROCE)

def _counts_to_dict(counts):
    return {item.value: item.count for item in counts}


if __name__ == "__main__":
    unittest.main()

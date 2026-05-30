import unittest

from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.graph import build_cabinet_graph
from backend.services import build_topology_database_from_results


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

        database = build_topology_database_from_results(cutsheet_result, overhead_result)

        self.assertEqual(database.summary.cabinets, 3)
        self.assertEqual(database.summary.cables, 1)
        self.assertEqual(database.cabinets[0].category, "DPR-H1")
        self.assertEqual(database.cabinets[0].cabinet_group, "Fabric Core")
        self.assertEqual(len(database.cabinets[0].devices), 1)
        self.assertEqual(database.cabinets[0].devices[0].rack_unit, 10)
        self.assertEqual(database.data_halls[0].cabinets[2].category, "RES")

        graph = build_cabinet_graph(database)

        self.assertEqual(graph.nodes["DH1:001"]["category"], "DPR-H1")
        self.assertEqual(graph.nodes["DH1:001"]["visualization_category"], "DPR-H1")
        self.assertEqual(graph.nodes["DH1:001"]["cabinet_group"], "Fabric Core")


if __name__ == "__main__":
    unittest.main()

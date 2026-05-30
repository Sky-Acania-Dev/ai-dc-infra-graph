import unittest

from backend.graph import cabinet_layout_svg, distance_shell_layout
from backend.ingest.cutsheet import CutsheetSummary
from backend.models import Cabinet
from backend.persistence import TopologyDatabase
from tests.unit.test_cabinet_graph import _database_from_rows
from backend.graph import build_cabinet_graph


class GraphRenderingTests(unittest.TestCase):
    def test_distance_shell_layout_includes_all_nodes(self) -> None:
        database = _database_from_rows(
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
        graph = build_cabinet_graph(database)

        position = distance_shell_layout(graph)

        self.assertEqual(set(position), set(graph.nodes))

    def test_cabinet_layout_svg_uses_overhead_coordinates_and_category_colors(self) -> None:
        database = TopologyDatabase(
            project_uid="MSK01",
            building_id="A",
            summary=CutsheetSummary(
                rows=0,
                data_halls=0,
                cabinets=2,
                ports=0,
                cables=0,
                port_collision_findings=0,
            ),
            cabinets=[
                Cabinet(
                    building_id="A",
                    data_hall_id="DH1",
                    cabinet_id="001",
                    category="T0-RO-v1a",
                    cabinet_group="OOB",
                    source_row=10,
                    source_col=5,
                ),
                Cabinet(
                    building_id="A",
                    data_hall_id="DH1",
                    cabinet_id="002",
                    category="RES",
                    cabinet_group="RES",
                    source_row=10,
                    source_col=6,
                ),
            ],
        )

        svg = cabinet_layout_svg(database)

        self.assertIn("AI DC Infra Graph Cabinet Layout", svg)
        self.assertIn('class="cabinet"', svg)
        self.assertEqual(svg.count('class="cabinet"'), 2)
        self.assertIn("T0-RO-v1a", svg)
        self.assertIn("#2563EB", svg)
        self.assertIn("DH1:001", svg)


if __name__ == "__main__":
    unittest.main()

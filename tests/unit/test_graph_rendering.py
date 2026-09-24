import unittest

from backend.graph import cabinet_layout_svg, distance_shell_layout
from backend.graph.rendering import _cabinet_grid_layout
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

    def test_cabinet_layout_svg_uses_updated_rack_type_colors(self) -> None:
        categories = {
            "FDP-B1": "#06B6D4",
            "T2-RO-v1a": "#67E8F9",
            "FCR-FE-v1a": "#FDBA74",
        }
        database = TopologyDatabase(
            project_uid="LBB01",
            building_id="A",
            summary=CutsheetSummary(
                rows=0,
                data_halls=0,
                cabinets=len(categories),
                ports=0,
                cables=0,
                port_collision_findings=0,
            ),
            cabinets=[
                Cabinet(
                    building_id="A",
                    data_hall_id="DH1-1",
                    cabinet_id=f"{index:03d}",
                    category=category,
                    source_row=10,
                    source_col=index,
                )
                for index, category in enumerate(categories, start=1)
            ],
        )

        svg = cabinet_layout_svg(database)

        for category, color in categories.items():
            with self.subTest(category=category):
                self.assertIn(category, svg)
                self.assertIn(color, svg)

    def test_cabinet_layout_merges_adjacent_complementary_half_rows(self) -> None:
        cabinets = [
            Cabinet(
                building_id="A",
                data_hall_id="DH1-1",
                cabinet_id=f"{cabinet_id:03d}",
                source_row=source_row,
                source_col=source_col,
            )
            for cabinet_id, source_row, source_col in (
                (81, 37, 7),
                (90, 37, 16),
                (881, 36, 25),
                (890, 36, 34),
                (91, 39, 16),
                (900, 39, 25),
            )
        ]

        positions = {
            cabinet.cabinet_id: position
            for cabinet, position in _cabinet_grid_layout(cabinets)
        }

        self.assertEqual(positions["081"], {"block": 0, "row": 0, "col": 0})
        self.assertEqual(positions["090"], {"block": 0, "row": 0, "col": 9})
        self.assertEqual(positions["881"], {"block": 1, "row": 0, "col": 0})
        self.assertEqual(positions["890"], {"block": 1, "row": 0, "col": 9})
        self.assertEqual(positions["091"], {"block": 0, "row": 1, "col": 9})
        self.assertEqual(positions["900"], {"block": 1, "row": 1, "col": 0})

    def test_cabinet_layout_merges_complementary_half_rows_in_reverse_order(self) -> None:
        cabinets = [
            Cabinet(
                building_id="A",
                data_hall_id="DH1-2",
                cabinet_id=cabinet_id,
                source_row=source_row,
                source_col=source_col,
            )
            for cabinet_id, source_row, source_col in (
                ("221", 89, 7),
                ("230", 89, 16),
                ("1021", 90, 25),
                ("1030", 90, 34),
                ("231", 92, 16),
                ("1040", 92, 25),
            )
        ]

        positions = {
            cabinet.cabinet_id: position
            for cabinet, position in _cabinet_grid_layout(cabinets)
        }

        self.assertEqual(positions["221"], {"block": 0, "row": 0, "col": 0})
        self.assertEqual(positions["230"], {"block": 0, "row": 0, "col": 9})
        self.assertEqual(positions["1021"], {"block": 1, "row": 0, "col": 0})
        self.assertEqual(positions["1030"], {"block": 1, "row": 0, "col": 9})
        self.assertEqual(positions["231"], {"block": 0, "row": 1, "col": 9})
        self.assertEqual(positions["1040"], {"block": 1, "row": 1, "col": 0})


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.graph import build_cabinet_graph, load_cabinet_graph, save_cabinet_graph
from backend.ingest.cutsheet import cutsheet_result_to_json, ingest_cutsheet_rows
from backend.persistence import load_topology_database
from tests.unit.test_json_database import _test_paths


class CabinetGraphTests(unittest.TestCase):
    def test_builds_cabinet_graph_with_cable_type_counts_and_distances(self) -> None:
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
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:11",
                    "A-PORT": "swp2",
                    "Z-LOC:CAB:RU": "dh1:002:21",
                    "Z-PORT": "swp2",
                    "CABLE": "LC-TO-LC SMF",
                },
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:002:22",
                    "A-PORT": "swp3",
                    "Z-LOC:CAB:RU": "dh1:003:30",
                    "Z-PORT": "swp3",
                    "CABLE": "CAT6a",
                },
            ]
        )

        graph = build_cabinet_graph(database)

        self.assertEqual(graph.number_of_nodes(), 3)
        self.assertEqual(graph.number_of_edges(), 2)
        self.assertEqual(graph.edges["DH1:001", "DH1:002"]["total_cables"], 2)
        self.assertEqual(graph.edges["DH1:001", "DH1:002"]["cable_type_counts"]["CAT6a"], 1)
        self.assertEqual(graph.edges["DH1:001", "DH1:002"]["cable_type_counts"]["LC-TO-LC SMF"], 1)
        self.assertEqual(graph.nodes["DH1:001"]["distance_category"], "root")
        self.assertEqual(graph.nodes["DH1:001"]["hop_count"], 0)
        self.assertEqual(graph.nodes["DH1:001"]["category"], "")
        self.assertEqual(graph.nodes["DH1:001"]["visualization_category"], "")
        self.assertEqual(graph.nodes["DH1:002"]["distance_category"], "hop_1")
        self.assertEqual(graph.nodes["DH1:002"]["hop_count"], 1)
        self.assertEqual(graph.nodes["DH1:003"]["distance_category"], "hop_2")
        self.assertEqual(graph.nodes["DH1:003"]["hop_count"], 2)

    def test_marks_disconnected_cabinets_unreachable(self) -> None:
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
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:010:10",
                    "A-PORT": "swp1",
                    "Z-LOC:CAB:RU": "dh1:011:20",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
            ]
        )

        graph = build_cabinet_graph(database)

        self.assertEqual(graph.nodes["DH1:010"]["distance_category"], "unreachable")
        self.assertEqual(graph.nodes["DH1:011"]["distance_category"], "unreachable")

    def test_saves_and_loads_cabinet_graph(self) -> None:
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
        _, graph_path = _test_paths()
        graph = build_cabinet_graph(database)

        save_cabinet_graph(graph, graph_path)
        loaded_graph = load_cabinet_graph(graph_path)

        self.assertEqual(loaded_graph.number_of_nodes(), 2)
        self.assertEqual(loaded_graph.edges["DH1:001", "DH1:002"]["cable_type_counts"]["CAT6a"], 1)


def _database_from_rows(rows: list[dict[str, str]]):
    result = ingest_cutsheet_rows(rows)
    source_path, _ = _test_paths()
    source_path.write_text(cutsheet_result_to_json(result), encoding="utf-8")
    return load_topology_database(source_path)


if __name__ == "__main__":
    unittest.main()

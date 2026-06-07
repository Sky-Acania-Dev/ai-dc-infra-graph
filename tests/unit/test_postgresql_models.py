import unittest

from backend.persistence.postgresql.models import Base


class PostgreSQLModelTests(unittest.TestCase):
    def test_metadata_includes_core_and_pathway_tables(self) -> None:
        expected_tables = {
            "projects",
            "buildings",
            "rooms",
            "cabinets",
            "device_models",
            "device_variants",
            "devices",
            "ports",
            "cables",
            "ladder_rack_junctions",
            "ladder_rack_segments",
            "cable_bundles",
            "cable_bundle_cables",
            "cable_bundle_ladder_rack_segments",
            "users",
            "operation_log",
        }

        self.assertTrue(expected_tables.issubset(Base.metadata.tables))

    def test_new_pathway_tables_have_expected_graph_and_bundle_columns(self) -> None:
        segment_columns = Base.metadata.tables["ladder_rack_segments"].columns
        bundle_cable_columns = Base.metadata.tables["cable_bundle_cables"].columns

        self.assertIn("junction_a_uid", segment_columns)
        self.assertIn("junction_z_uid", segment_columns)
        self.assertIn("polyline", segment_columns)
        self.assertIn("design_length_meters", segment_columns)
        self.assertIn("actual_length_meters", segment_columns)
        self.assertIn("cable_bundle_uid", bundle_cable_columns)
        self.assertIn("cable_uid", bundle_cable_columns)


if __name__ == "__main__":
    unittest.main()

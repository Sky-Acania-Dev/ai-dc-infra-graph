import unittest

from backend.ingest.overhead import ingest_overhead


OVERHEAD_PATH = r"C:\Personal Folder\Work\Megawatt\OK Muskogee\OVERHEAD.ods"


class OverheadIngestionTests(unittest.TestCase):
    def test_ingests_800_cabinets_from_overhead(self) -> None:
        result = ingest_overhead(OVERHEAD_PATH, sheet_name="Sheet1")

        self.assertEqual(result.summary.cabinets, 800)
        self.assertEqual(result.summary.data_halls, 2)
        self.assertEqual(len([cab for cab in result.cabinets if cab.data_hall_id == "DH1"]), 400)
        self.assertEqual(len([cab for cab in result.cabinets if cab.data_hall_id == "DH2"]), 400)

    def test_preserves_reserved_and_infers_edge_categories(self) -> None:
        result = ingest_overhead(OVERHEAD_PATH, sheet_name="Sheet1")
        by_uid = {cabinet.cabinet_uid: cabinet for cabinet in result.cabinets}
        categories = {cabinet.category for cabinet in result.cabinets}

        self.assertIn("RES", categories)
        self.assertEqual(result.summary.unknown_category_cabinets, 0)
        self.assertEqual(by_uid["DH1:030"].category, "T0-RO-v1a")
        self.assertEqual(by_uid["DH1:110"].category, "T0-RO-v1a")
        self.assertEqual(by_uid["DH1:150"].category, "T0-RO-v1a")
        self.assertEqual(by_uid["DH1:029"].category, "HD-GB3c")
        self.assertEqual(by_uid["DH1:109"].category, "HD-GB3c")
        self.assertEqual(by_uid["DH1:187"].category, "HD-GB3c")
        self.assertEqual(by_uid["DH1:228"].category, "HD-GB3c")
        self.assertEqual(by_uid["DH1:229"].category, "HD-GB3c")

    def test_extracts_cabinet_group_and_source_location(self) -> None:
        result = ingest_overhead(OVERHEAD_PATH, sheet_name="Sheet1")
        by_uid = {cabinet.cabinet_uid: cabinet for cabinet in result.cabinets}

        self.assertEqual(by_uid["DH1:001"].category, "DPR-H1")
        self.assertEqual(by_uid["DH1:001"].cabinet_group, "Fabric Core")
        self.assertGreater(by_uid["DH1:001"].source_row, 0)
        self.assertGreater(by_uid["DH1:001"].source_col, 0)

    def test_extracts_plane_group_labels(self) -> None:
        result = ingest_overhead(OVERHEAD_PATH, sheet_name="Sheet1")
        by_uid = {cabinet.cabinet_uid: cabinet for cabinet in result.cabinets}

        self.assertEqual(by_uid["DH2:188"].cabinet_group, "PLANE-A RAIL-4")
        self.assertEqual(by_uid["DH2:382"].cabinet_group, "PLANE-C RAIL-1")


if __name__ == "__main__":
    unittest.main()

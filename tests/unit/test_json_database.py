import json
import unittest
import uuid
from pathlib import Path

from backend.api.database import LoadJsonDatabaseRequest, load_json_database
from backend.ingest.cutsheet import cutsheet_result_to_json, ingest_cutsheet_rows
from backend.persistence import load_topology_database, save_topology_database


TEST_RUNTIME_DIR = Path("data/runtime")


class JsonDatabaseTests(unittest.TestCase):
    def test_loads_exported_cutsheet_json(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "OOB-FW"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "ethernet1/21",
                    "Z-LOC:CAB:RU": "dh1:002:42",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
            ]
        )

        source_path, _ = _test_paths()
        source_path.write_text(cutsheet_result_to_json(result), encoding="utf-8")

        database = load_topology_database(source_path)

        self.assertEqual(database.project_uid, "MSK01")
        self.assertEqual(database.summary.rows, 1)
        self.assertEqual(database.summary.cabinets, 2)
        self.assertFalse(database.has_port_collisions)

    def test_saves_runtime_database_snapshot(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "OOB-FW"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "ethernet1/21",
                    "Z-LOC:CAB:RU": "dh1:002:42",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
            ]
        )

        source_path, runtime_path = _test_paths()
        source_path.write_text(cutsheet_result_to_json(result), encoding="utf-8")
        database = load_topology_database(source_path)

        saved_path = save_topology_database(database, runtime_path)
        saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))

        self.assertEqual(saved_payload["summary"]["rows"], 1)
        self.assertEqual(saved_payload["port_collision_findings"], [])

    def test_load_json_database_api_handler(self) -> None:
        result = ingest_cutsheet_rows(
            [
                {"STATUS": "OOB-FW"},
                {
                    "STATUS": "Cable Is Ran: Complete",
                    "A-LOC:CAB:RU": "dh1:001:10",
                    "A-PORT": "ethernet1/21",
                    "Z-LOC:CAB:RU": "dh1:002:42",
                    "Z-PORT": "swp1",
                    "CABLE": "CAT6a",
                },
            ]
        )

        source_path, runtime_path = _test_paths()
        source_path.write_text(cutsheet_result_to_json(result), encoding="utf-8")

        response = load_json_database(
            LoadJsonDatabaseRequest(
                json_path=str(source_path),
                runtime_path=str(runtime_path),
            )
        )

        self.assertEqual(response.summary.rows, 1)
        self.assertFalse(response.has_port_collisions)


def _test_paths() -> tuple[Path, Path]:
    TEST_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    unique_id = uuid.uuid4()
    return (
        TEST_RUNTIME_DIR / f"test-cutsheet-{unique_id}.json",
        TEST_RUNTIME_DIR / f"test-runtime-{unique_id}.json",
    )


if __name__ == "__main__":
    unittest.main()

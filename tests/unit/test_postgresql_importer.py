import unittest

from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.persistence.postgresql.importer import _cable_record, _port_record
from backend.services import build_topology_database_from_results


class PostgreSQLImporterTests(unittest.TestCase):
    def test_import_records_map_domain_identifiers_to_scoped_database_rows(self) -> None:
        database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A_MODEL": "Switch",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "LC",
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
        building_uid = f"{database.project_uid}:{database.building_id}".upper()

        port_record = _port_record(database, building_uid, database.ports[0])
        cable_record = _cable_record(database, building_uid, database.cables[0])

        self.assertEqual(port_record.project_uid, "MSK01")
        self.assertEqual(port_record.building_uid, "MSK01:A")
        self.assertEqual(port_record.room_uid, "MSK01:A:DH1")
        self.assertEqual(port_record.cabinet_uid, "DH1:001")
        self.assertEqual(port_record.device_uid, "DH1:001:10")
        self.assertEqual(cable_record.a_port_uid, "DH1:001:10:swp1")
        self.assertEqual(cable_record.z_port_uid, "DH1:002:20:swp2")
        self.assertEqual(cable_record.room_uid, "MSK01:A:DH1")


if __name__ == "__main__":
    unittest.main()

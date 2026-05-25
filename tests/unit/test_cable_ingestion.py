import unittest

from backend.ingest.cables import ingest_cable_connection_rows, parse_cable_endpoint
from backend.models import ConnectorType


class CableIngestionTests(unittest.TestCase):
    def test_parse_cable_endpoint(self) -> None:
        endpoint = parse_cable_endpoint("DH1:001:Eth1/1")

        self.assertEqual(endpoint.data_hall_id, "DH1")
        self.assertEqual(endpoint.cabinet_id, "001")
        self.assertEqual(endpoint.port_id, "Eth1/1")

    def test_ingests_unique_data_halls_cabinets_and_ports(self) -> None:
        result = ingest_cable_connection_rows(
            [
                {
                    "A Side Port ID": "DH1:001:Eth1/1",
                    "Z Side Port ID": "DH1:002:Eth1/49",
                    "Cable Type": "OS2",
                    "a_type": "LC",
                    "z_type": "LC",
                },
                {
                    "A Side Port ID": "DH1:001:Eth1/2",
                    "Z Side Port ID": "DH2:003:Eth1/10",
                    "Cable Type": "OS2",
                    "a_type": "LC",
                    "z_type": "LC",
                },
            ]
        )

        self.assertEqual(result.project_uid, "MSK01")
        self.assertEqual([room.room_id for room in result.data_halls], ["DH1", "DH2"])
        self.assertEqual(
            [(cabinet.data_hall_id, cabinet.cabinet_id) for cabinet in result.cabinets],
            [("DH1", "001"), ("DH1", "002"), ("DH2", "003")],
        )
        self.assertEqual(len(result.ports), 4)
        self.assertEqual(len(result.cables), 2)
        self.assertEqual(result.ports[0].type, ConnectorType.LC)
        self.assertEqual(result.cables[0].cable_type, "OS2")


if __name__ == "__main__":
    unittest.main()

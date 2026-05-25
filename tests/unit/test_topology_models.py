import unittest

from backend.models import (
    Building,
    Cabinet,
    Cable,
    ConnectorType,
    Device,
    PortConnector,
    Project,
    Room,
)


class TopologyModelTests(unittest.TestCase):
    def test_basic_topology_model_composition(self) -> None:
        project = Project(uid="MSK01", full_name="CoreWeave-Muskogee-001")
        port_a = PortConnector(uid="CAB-A01:LEAF-01:Eth1/1", type=ConnectorType.LC)
        port_z = PortConnector(uid="CAB-B01:SPINE-01:Eth1/17", type=ConnectorType.LC)
        device = Device(
            cabinet_id="CAB-A01",
            rack_unit=42,
            device_model="NVIDIA Spectrum SN5600",
            ports_by_type={ConnectorType.LC: [port_a]},
            note="Initial model placeholder",
        )
        cabinet = Cabinet(
            building_id="A",
            data_hall_id="DH1",
            cabinet_id="CAB-A01",
            devices=[device],
        )
        room = Room(building_id="A", room_id="DH1", cabinets=[cabinet])
        building = Building(project_uid=project.uid, building_id="A", rooms=[room])
        cable = Cable(a_side=port_a, z_side=port_z, cable_type="OS2 fiber")

        self.assertEqual(
            building.rooms[0].cabinets[0].devices[0].ports_by_type[ConnectorType.LC][0],
            port_a,
        )
        self.assertEqual(cable.a_side.uid, "CAB-A01:LEAF-01:Eth1/1")
        self.assertEqual(cable.z_side.uid, "CAB-B01:SPINE-01:Eth1/17")


if __name__ == "__main__":
    unittest.main()

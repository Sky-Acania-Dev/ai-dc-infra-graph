import os
import unittest

from backend.api.auth import AuthUser, UserRole
from backend.api.topology import (
    cabinet_connection_cables,
    cabinet_detail,
    cabinet_layout,
    data_hall_cable_summary,
    data_hall_cables,
    device_connection_cables,
    device_connections,
    list_operations,
    topology_enums,
    undo_operation,
    update_cabinet_status,
    update_cable,
    update_device_status,
    UpdateCableRequest,
    UpdateLifecycleStatusRequest,
    validation_report,
)
from backend.core.enums import CableProgressState, CableProgressStep, LifecycleStatus
from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.persistence import save_topology_database
from backend.services import build_topology_database_from_results
from tests.unit.test_json_database import _test_paths


class TopologyApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_storage_backend = os.environ.get("TOPOLOGY_STORAGE_BACKEND")
        os.environ["TOPOLOGY_STORAGE_BACKEND"] = "json"

    def tearDown(self) -> None:
        if self._previous_storage_backend is None:
            os.environ.pop("TOPOLOGY_STORAGE_BACKEND", None)
        else:
            os.environ["TOPOLOGY_STORAGE_BACKEND"] = self._previous_storage_backend

    def test_cabinet_detail_includes_devices_and_connections(self) -> None:
        _, runtime_path = _test_paths()
        database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {"STATUS": "Backbone"},
                    {
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A_MODEL": "NVIDIA Spectrum SN5600",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp1",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "CAT6a",
                    },
                    {
                        "STATUS": "Cable Is Ran: Not Terminated",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp2",
                        "A_MODEL": "NVIDIA Spectrum SN5600",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "CAT6a",
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
        save_topology_database(database, runtime_path)

        layout = cabinet_layout(data_hall="DH1", database_path=str(runtime_path))
        detail = cabinet_detail("DH1:001", database_path=str(runtime_path))
        cable_detail = cabinet_connection_cables("DH1:001", "DH1:002", database_path=str(runtime_path))

        self.assertEqual(len(layout), 2)
        self.assertEqual(detail.stats.devices, 1)
        self.assertEqual(detail.cabinet.max_rack_unit, 48)
        self.assertEqual(detail.devices[0].device_model, "NVIDIA Spectrum SN5600")
        self.assertEqual(detail.connections[0].target_cabinet_uid, "DH1:002")
        self.assertEqual(detail.connections[0].status_summary.completed, 1)
        self.assertEqual(detail.connections[0].status_summary.total, 2)
        self.assertEqual(detail.connections[0].status_summary.status_counts["Cable Is Ran: Not Terminated"], 1)
        self.assertEqual(len(cable_detail.cables), 2)
        self.assertEqual(cable_detail.cables[0].uid, "CBL-000001")
        self.assertEqual(cable_detail.cables[0].length_used_meters, 0)
        self.assertEqual(cable_detail.cables[0].a_port_uid, "DH1:001:10:swp1")

        device_detail = device_connections("DH1:001", 10, database_path=str(runtime_path))
        device_cable_detail = device_connection_cables("DH1:001:10", "DH1:002:20", database_path=str(runtime_path))

        self.assertEqual(device_detail.source_device_uid, "DH1:001:10")
        self.assertEqual(device_detail.connected_devices[0].target_device_uid, "DH1:002:20")
        self.assertEqual(device_detail.connected_devices[0].target_device_model, "Patch Panel")
        self.assertEqual(device_detail.connected_cabinet_uids, ["DH1:002"])
        self.assertEqual(device_detail.connected_devices[0].status_summary.completed, 1)
        self.assertEqual(device_detail.connected_devices[0].status_summary.total, 2)
        self.assertEqual(device_cable_detail.source_device_uid, "DH1:001:10")
        self.assertEqual(device_cable_detail.target_device_uid, "DH1:002:20")
        self.assertEqual(len(device_cable_detail.cables), 2)
        self.assertEqual(device_cable_detail.cables[0].a_port_uid, "DH1:001:10:swp1")

        validation = validation_report(database_path=str(runtime_path))

        self.assertEqual(validation.summary.port_collision_findings, 0)
        self.assertEqual(validation.summary.device_model_mismatches, 0)
        self.assertEqual(validation.summary.device_model_format_issues, 0)

    def test_data_hall_external_cables_filter_to_target_hall(self) -> None:
        _, runtime_path = _test_paths()
        database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A_MODEL": "Switch",
                        "Z-LOC:CAB:RU": "dh1:002:20",
                        "Z-PORT": "swp2",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "LC",
                    },
                    {
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp3",
                        "A_MODEL": "Switch",
                        "Z-LOC:CAB:RU": "dh2:003:20",
                        "Z-PORT": "swp4",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "MPO12",
                    },
                    {
                        "STATUS": "Cable Not Run",
                        "A-LOC:CAB:RU": "dh2:003:20",
                        "A-PORT": "swp5",
                        "A_MODEL": "Patch Panel",
                        "Z-LOC:CAB:RU": "dh2:004:20",
                        "Z-PORT": "swp6",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "MPO12",
                    },
                ]
            ),
            overhead_result=OverheadIngestionResult(
                summary=OverheadIngestionSummary(cabinets=4, data_halls=2, unknown_category_cabinets=0),
                cabinets=[
                    CabinetInventoryRecord(
                        cabinet_uid="DH1:001",
                        data_hall_id="DH1",
                        cabinet_id="001",
                        category="DPR-H1",
                        cabinet_group="Core",
                        source_row=1,
                        source_col=1,
                    ),
                    CabinetInventoryRecord(
                        cabinet_uid="DH1:002",
                        data_hall_id="DH1",
                        cabinet_id="002",
                        category="DPR-H2",
                        cabinet_group="Core",
                        source_row=1,
                        source_col=2,
                    ),
                    CabinetInventoryRecord(
                        cabinet_uid="DH2:003",
                        data_hall_id="DH2",
                        cabinet_id="003",
                        category="DPR-H1",
                        cabinet_group="Core",
                        source_row=1,
                        source_col=3,
                    ),
                    CabinetInventoryRecord(
                        cabinet_uid="DH2:004",
                        data_hall_id="DH2",
                        cabinet_id="004",
                        category="DPR-H2",
                        cabinet_group="Core",
                        source_row=1,
                        source_col=4,
                    ),
                ],
            ),
        )
        save_topology_database(database, runtime_path)

        summary = data_hall_cable_summary("DH1", database_path=str(runtime_path))
        external_detail = data_hall_cables(
            "DH1",
            scope="external",
            target_data_hall="DH2",
            cable_type="MPO12",
            database_path=str(runtime_path),
        )

        self.assertEqual([bucket.target_data_hall for bucket in summary.external], ["DH2"])
        self.assertEqual(summary.external[0].total_cables, 1)
        self.assertEqual(external_detail.target_cabinet_uid, "DH2")
        self.assertEqual([cable.uid for cable in external_detail.cables], ["CBL-000002"])

    def test_cabinet_detail_includes_intra_cabinet_cables(self) -> None:
        _, runtime_path = _test_paths()
        database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows(
                [
                    {
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": "dh1:001:10",
                        "A-PORT": "swp1",
                        "A_MODEL": "Switch",
                        "Z-LOC:CAB:RU": "dh1:001:20",
                        "Z-PORT": "swp2",
                        "Z_MODEL": "Patch Panel",
                        "CABLE": "LC",
                    },
                ]
            ),
            overhead_result=OverheadIngestionResult(
                summary=OverheadIngestionSummary(cabinets=1, data_halls=1, unknown_category_cabinets=0),
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
                ],
            ),
        )
        save_topology_database(database, runtime_path)

        detail = cabinet_detail("DH1:001", database_path=str(runtime_path))
        cable_detail = cabinet_connection_cables("DH1:001", "DH1:001", database_path=str(runtime_path))

        self.assertIsNotNone(detail.intra_cabinet_connection)
        self.assertEqual(detail.intra_cabinet_connection.total_cables, 1)
        self.assertEqual(cable_detail.cables[0].z_port_uid, "DH1:001:20:swp2")

        device_detail = device_connections("DH1:001", 10, database_path=str(runtime_path))
        device_cable_detail = device_connection_cables("DH1:001:10", "DH1:001:20", database_path=str(runtime_path))

        self.assertEqual(device_detail.connected_devices[0].target_device_uid, "DH1:001:20")
        self.assertEqual(device_detail.connected_devices[0].target_device_model, "Patch Panel")
        self.assertEqual(device_detail.connected_cabinet_uids, ["DH1:001"])
        self.assertEqual(len(device_cable_detail.cables), 1)
        self.assertEqual(device_cable_detail.cables[0].z_port_uid, "DH1:001:20:swp2")

    def test_editor_can_persist_status_and_cable_updates(self) -> None:
        _, runtime_path = _test_paths()
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
                        category="HD-GB3c",
                        cabinet_group="GPU",
                        source_row=7,
                        source_col=6,
                    ),
                ],
            ),
        )
        save_topology_database(database, runtime_path)
        editor = AuthUser(uid="editor", display_name="Editor", role=UserRole.EDITOR)

        cabinet = update_cabinet_status(
            "DH1:001",
            UpdateLifecycleStatusRequest(lifecycle_status=LifecycleStatus.POWERED),
            database_path=str(runtime_path),
            user=editor,
        )
        device = update_device_status(
            "DH1:001:10",
            UpdateLifecycleStatusRequest(lifecycle_status=LifecycleStatus.INSTALLED),
            database_path=str(runtime_path),
            user=editor,
        )
        cable = update_cable(
            "CBL-000001",
            UpdateCableRequest(
                status="Cable Is Ran: Not Terminated",
                progress={CableProgressStep.PULLED: CableProgressState.COMPLETE},
                current_phase={
                    "name": "dress_termination",
                    "task_values": {
                        "routing_dress": {"task_type": "percent", "value": 40},
                        "a_side": {"task_type": "enum", "value": "terminated"},
                        "z_side": {"task_type": "enum", "value": "dressed"},
                    },
                },
                length_used_meters=12.5,
            ),
            database_path=str(runtime_path),
            user=editor,
        )

        self.assertTrue(cabinet.ok)
        self.assertEqual(cabinet.operation.entityType, "cabinet")
        self.assertEqual(cabinet.operation.after["lifecycle_status"], LifecycleStatus.POWERED.value)
        self.assertTrue(device.ok)
        self.assertEqual(device.operation.after["lifecycle_status"], LifecycleStatus.INSTALLED.value)
        self.assertTrue(cable.ok)
        self.assertEqual(cable.operation.after["status"], "Cable Is Ran: Not Terminated")
        self.assertEqual(cable.operation.after["progress"]["pulled"], "complete")
        self.assertEqual(cable.operation.after["current_phase"]["name"], "dress_termination")
        self.assertEqual(cable.operation.after["current_phase"]["phase_type"], "parallel_percent")
        self.assertEqual(cable.operation.after["current_phase"]["task_values"]["routing_dress"]["value"], 40)
        self.assertEqual(cable.operation.after["current_phase"]["task_values"]["a_side"]["value"], "terminated")
        self.assertEqual(cable.operation.after["current_phase"]["task_values"]["z_side"]["value"], "dressed")
        self.assertEqual(cable.operation.after["length_used_meters"], 12.5)

        updated_cable = cabinet_connection_cables("DH1:001", "DH1:002", database_path=str(runtime_path)).cables[0]
        self.assertEqual(updated_cable.status, "Cable Is Ran: Not Terminated")
        self.assertEqual(updated_cable.current_phase.name, "dress_termination")
        self.assertEqual(updated_cable.length_used_meters, 12.5)

        undo_response = undo_operation(database_path=str(runtime_path), user=editor)
        self.assertTrue(undo_response.ok)
        undone_cable = cabinet_connection_cables("DH1:001", "DH1:002", database_path=str(runtime_path)).cables[0]
        self.assertEqual(undone_cable.status, "Cable Not Run")

        operations = list_operations(database_path=str(runtime_path))
        self.assertEqual(operations.version, undo_response.version)
        self.assertEqual([operation.entityType for operation in operations.operations], ["cabinet", "device", "cable", "cable"])

        enums = topology_enums(database_path=str(runtime_path))
        termination = next(phase for phase in enums.cable_progress_phases if phase.name == "dress_termination")
        self.assertEqual([task.name for task in termination.tasks], ["routing_dress", "a_side", "z_side"])
        self.assertEqual(termination.tasks[0].task_type, "percent")
        self.assertEqual(termination.tasks[1].enum_values, ["not_terminated", "terminated", "dressed"])

    def test_stale_json_write_is_rejected(self) -> None:
        _, runtime_path = _test_paths()
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
                        "CABLE": "MPO",
                    }
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
                        cabinet_group="A",
                        source_row=7,
                        source_col=5,
                    ),
                    CabinetInventoryRecord(
                        cabinet_uid="DH1:002",
                        data_hall_id="DH1",
                        cabinet_id="002",
                        category="DPR-H2",
                        cabinet_group="A",
                        source_row=7,
                        source_col=6,
                    ),
                ],
            ),
        )
        cable_uid = database.cables[0].uid
        save_topology_database(database, runtime_path)
        editor = AuthUser(uid="editor", display_name="Editor", role=UserRole.EDITOR)

        first = update_cable(
            cable_uid,
            UpdateCableRequest(status="Cable Is Ran: Not Terminated", expected_version=0),
            database_path=str(runtime_path),
            user=editor,
        )

        with self.assertRaisesRegex(Exception, "stale version 0") as context:
            update_cable(
                cable_uid,
                UpdateCableRequest(status="Cable Is Ran: Complete", expected_version=0),
                database_path=str(runtime_path),
                user=editor,
            )

        self.assertEqual(context.exception.status_code, 409)
        updated_cable = cabinet_connection_cables("DH1:001", "DH1:002", database_path=str(runtime_path)).cables[0]
        self.assertEqual(first.version, 1)
        self.assertEqual(updated_cable.status, "Cable Is Ran: Not Terminated")

    def test_stale_operation_log_does_not_block_topology_reads(self) -> None:
        _, runtime_path = _test_paths()
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
                        category="HD-GB3c",
                        cabinet_group="GPU",
                        source_row=7,
                        source_col=6,
                    ),
                ],
            ),
        )
        save_topology_database(database, runtime_path)
        runtime_path.with_name(f"{runtime_path.stem}.operations.jsonl").write_text(
            '{"opId":99,"type":"update","entityType":"cable","entityId":"MISSING",'
            '"before":{"status":"Cable Not Run"},"after":{"status":"Cable Is Ran: Complete"},'
            '"timestamp":"2026-06-04T00:00:00+00:00"}\n',
            encoding="utf-8",
        )

        enums = topology_enums(database_path=str(runtime_path))
        operations = list_operations(database_path=str(runtime_path))

        self.assertIn("Cable Not Run", enums.cable_import_statuses)
        self.assertEqual(operations.version, 99)


if __name__ == "__main__":
    unittest.main()

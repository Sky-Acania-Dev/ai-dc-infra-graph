import os
import unittest

from sqlalchemy import select

from backend.core.enums import CableProgressState, CableProgressStep, LifecycleStatus
from backend.api import topology as topology_api
from backend.api.auth import AuthUser, UserRole
from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.persistence.postgresql.importer import replace_project_topology
from backend.persistence.postgresql.queries import (
    CabinetFilter,
    cabinet_graph_edges,
    cabinet_stats,
    data_hall_cable_summary,
    device_connections,
    filter_cabinets,
    search_topology,
)
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.mutations import MutationUser, RowLockedConflict, StaleWriteConflict, _acquire_write_gate
from backend.persistence.postgresql.repository import PostgresTopologyRepository
from backend.persistence.postgresql.session import session_factory
from backend.services import build_topology_database_from_results


@unittest.skipUnless(os.environ.get("RUN_POSTGRESQL_TESTS") == "1", "set RUN_POSTGRESQL_TESTS=1 to run PostgreSQL integration tests")
class PostgreSQLQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = session_factory()
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
                        "Z-LOC:CAB:RU": "dh1:001:20",
                        "Z-PORT": "swp4",
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
        with self.factory() as session:
            with session.begin():
                replace_project_topology(session, database)

    def test_search_filter_graph_and_aggregations(self) -> None:
        with self.factory() as session:
            search_results = search_topology(session, project_uid="MSK01", query="DPR")
            filtered = filter_cabinets(session, CabinetFilter(project_uid="MSK01", room_uid="MSK01:A:DH1"))
            stats = cabinet_stats(session, cabinet_uid="DH1:001")
            summary = data_hall_cable_summary(session, room_uid="MSK01:A:DH1")
            edges = cabinet_graph_edges(session, project_uid="MSK01")
            device_summary = device_connections(session, source_device_uid="DH1:001:10")

        self.assertEqual([item.uid for item in search_results], ["DH1:001", "DH1:002"])
        self.assertEqual([cabinet.uid for cabinet in filtered], ["DH1:001", "DH1:002"])
        self.assertEqual(stats.devices, 2)
        self.assertEqual(stats.ports, 3)
        self.assertEqual(stats.cables, 2)
        self.assertEqual(stats.connected_cabinets, 1)
        self.assertEqual(stats.cable_type_counts, {"CAT6a": 1, "LC": 1})
        self.assertEqual(stats.status_summary.completed, 1)
        self.assertEqual(summary.internal.total_cables, 2)
        self.assertEqual([(edge.source_cabinet_uid, edge.target_cabinet_uid, edge.total_cables) for edge in edges], [("DH1:001", "DH1:002", 1)])
        self.assertEqual(device_summary.connected_cabinet_uids, ["DH1:001", "DH1:002"])
        self.assertEqual([connection.target_device_uid for connection in device_summary.connected_devices], ["DH1:001:20", "DH1:002:20"])

    def test_repository_saves_and_loads_topology_database_shape(self) -> None:
        repository = PostgresTopologyRepository(project_uid="MSK01", building_id="A")

        loaded = repository.load()

        self.assertEqual(loaded.project_uid, "MSK01")
        self.assertEqual(loaded.building_id, "A")
        self.assertEqual(loaded.summary.cabinets, 2)
        self.assertEqual(sum(len(cabinet.devices) for cabinet in loaded.cabinets), 3)
        self.assertEqual(loaded.summary.ports, 4)
        self.assertEqual(loaded.summary.cables, 2)
        self.assertEqual(len(loaded.rows), 2)
        self.assertEqual(loaded.cables[0].a_side.uid, "DH1:001:10:swp1")
        self.assertEqual(loaded.cables[0].status, "Cable Is Ran: Complete")

    def test_repository_persists_status_progress_and_operation_log(self) -> None:
        repository = PostgresTopologyRepository(project_uid="MSK01", building_id="A")
        user = MutationUser(uid="editor", display_name="Editor", role="editor")

        cabinet_operation = repository.update_cabinet_status("DH1:001", LifecycleStatus.POWERED, user=user)
        device_operation = repository.update_device_status("DH1:001:10", LifecycleStatus.INSTALLED, user=user)
        cable_operation = repository.update_cable(
            "CBL-000001",
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
            note="updated in postgres",
            user=user,
        )
        loaded = repository.load()
        operations = repository.list_operations()

        cabinet = next(item for item in loaded.cabinets if item.data_hall_id == "DH1" and item.cabinet_id == "001")
        device = next(item for item in cabinet.devices if item.rack_unit == 10)
        cable = next(item for item in loaded.cables if item.uid == "CBL-000001")

        self.assertLess(cabinet_operation.version, device_operation.version)
        self.assertLess(device_operation.version, cable_operation.version)
        self.assertEqual(cabinet.lifecycle_status, LifecycleStatus.POWERED)
        self.assertEqual(device.lifecycle_status, LifecycleStatus.INSTALLED)
        self.assertEqual(cable.status, "Cable Is Ran: Not Terminated")
        self.assertEqual(cable.progress[CableProgressStep.PULLED], CableProgressState.COMPLETE)
        self.assertEqual(cable.current_phase.name, "dress_termination")
        self.assertEqual(cable.current_phase.task_values["routing_dress"].value, 40)
        self.assertEqual(cable.current_phase.task_values["a_side"].value, "terminated")
        self.assertEqual(cable.current_phase.task_values["z_side"].value, "dressed")
        self.assertEqual(cable.length_used_meters, 12.5)
        self.assertEqual(cable.note, "updated in postgres")
        self.assertEqual([operation.entity_type for operation in operations], ["cabinet", "device", "cable"])
        self.assertEqual(operations[-1].after["status"], "Cable Is Ran: Not Terminated")
        self.assertEqual(operations[-1].user_uid, "editor")

    def test_repository_rejects_stale_row_update(self) -> None:
        repository = PostgresTopologyRepository(project_uid="MSK01", building_id="A")
        user = MutationUser(uid="editor", display_name="Editor", role="editor")

        first_operation = repository.update_cable(
            "CBL-000001",
            status="Cable Is Ran: Not Terminated",
            expected_version=0,
            user=user,
        )

        with self.assertRaises(StaleWriteConflict):
            repository.update_cable(
                "CBL-000001",
                status="Cable Is Ran: Complete",
                expected_version=0,
                user=user,
            )

        loaded = repository.load()
        cable = next(item for item in loaded.cables if item.uid == "CBL-000001")
        self.assertEqual(cable.status, "Cable Is Ran: Not Terminated")
        self.assertEqual(repository.list_operations()[-1].version, first_operation.version)

    def test_manager_can_override_stale_editor_row_update(self) -> None:
        repository = PostgresTopologyRepository(project_uid="MSK01", building_id="A")
        editor = MutationUser(uid="editor", display_name="Editor", role="editor")
        manager = MutationUser(uid="manager", display_name="Manager", role="manager")

        editor_operation = repository.update_cable(
            "CBL-000001",
            status="Cable Is Ran: Not Terminated",
            expected_version=0,
            user=editor,
        )
        manager_operation = repository.update_cable(
            "CBL-000001",
            status="Cable Is Ran: Complete",
            expected_version=0,
            user=manager,
        )

        loaded = repository.load()
        cable = next(item for item in loaded.cables if item.uid == "CBL-000001")
        self.assertLess(editor_operation.version, manager_operation.version)
        self.assertEqual(cable.status, "Cable Is Ran: Complete")
        self.assertEqual(repository.list_operations()[-1].user_role, "manager")

    def test_locked_row_fails_without_waiting(self) -> None:
        repository = PostgresTopologyRepository(project_uid="MSK01", building_id="A")
        user = MutationUser(uid="editor", display_name="Editor", role="editor")

        with self.factory() as locking_session:
            with locking_session.begin():
                locking_session.execute(
                    select(db.Cable)
                    .where(db.Cable.uid == "CBL-000001", db.Cable.deleted_at.is_(None))
                    .with_for_update()
                ).scalar_one()
                with self.assertRaises(RowLockedConflict):
                    repository.update_cable(
                        "CBL-000001",
                        status="Cable Is Ran: Not Terminated",
                        expected_version=0,
                        user=user,
                    )

    def test_same_tier_edit_gate_fails_without_waiting(self) -> None:
        repository = PostgresTopologyRepository(project_uid="MSK01", building_id="A")
        user = MutationUser(uid="editor", display_name="Editor", role="editor")

        with self.factory() as locking_session:
            with locking_session.begin():
                _acquire_write_gate(locking_session, entity_type="cable", entity_uid="CBL-000001", user=user)
                with self.assertRaises(RowLockedConflict):
                    repository.update_cable(
                        "CBL-000001",
                        status="Cable Is Ran: Not Terminated",
                        expected_version=0,
                        user=user,
                    )

    def test_fastapi_mutations_use_postgresql_and_operations_cursor_in_db_mode(self) -> None:
        editor = AuthUser(uid="api-editor", display_name="API Editor", role=UserRole.EDITOR)
        previous_backend = os.environ.get("TOPOLOGY_STORAGE_BACKEND")
        os.environ["TOPOLOGY_STORAGE_BACKEND"] = "postgresql"
        try:
            response = topology_api.update_cabinet_status(
                "DH1:001",
                topology_api.UpdateLifecycleStatusRequest(lifecycle_status=LifecycleStatus.POWERED),
                user=editor,
            )
            after_previous = topology_api.list_operations(after=response.version - 1)
            after_current = topology_api.list_operations(after=response.version)
        finally:
            if previous_backend is None:
                os.environ.pop("TOPOLOGY_STORAGE_BACKEND", None)
            else:
                os.environ["TOPOLOGY_STORAGE_BACKEND"] = previous_backend

        self.assertTrue(response.ok)
        self.assertEqual(response.operation.entityType, "cabinet")
        self.assertEqual(response.operation.userUid, "api-editor")
        self.assertEqual([operation.opId for operation in after_previous.operations], [response.version])
        self.assertEqual(after_previous.version, response.version)
        self.assertEqual(after_current.operations, [])
        self.assertEqual(after_current.version, response.version)

    def test_fastapi_reads_use_postgresql_in_db_mode(self) -> None:
        editor = AuthUser(uid="api-editor", display_name="API Editor", role=UserRole.EDITOR)
        previous_backend = os.environ.get("TOPOLOGY_STORAGE_BACKEND")
        os.environ["TOPOLOGY_STORAGE_BACKEND"] = "postgresql"
        try:
            response = topology_api.update_cabinet_status(
                "DH1:001",
                topology_api.UpdateLifecycleStatusRequest(lifecycle_status=LifecycleStatus.POWERED),
                user=editor,
            )
            layout = topology_api.cabinet_layout(data_hall="DH1")
            detail = topology_api.cabinet_detail("DH1:001")
            cable_detail = topology_api.cabinet_connection_cables("DH1:001", "DH1:002")
            summary = topology_api.data_hall_cable_summary("DH1")
            enums = topology_api.topology_enums()
            validation = topology_api.validation_report()
        finally:
            if previous_backend is None:
                os.environ.pop("TOPOLOGY_STORAGE_BACKEND", None)
            else:
                os.environ["TOPOLOGY_STORAGE_BACKEND"] = previous_backend

        updated_cabinet = next(cabinet for cabinet in layout if cabinet.cabinet_uid == "DH1:001")
        self.assertEqual(updated_cabinet.lifecycle_status, LifecycleStatus.POWERED)
        self.assertEqual(updated_cabinet.source_row, 7)
        self.assertEqual(updated_cabinet.source_col, 5)
        self.assertEqual(detail.cabinet.lifecycle_status, LifecycleStatus.POWERED)
        self.assertEqual(detail.cabinet.source_row, 7)
        self.assertEqual(cable_detail.cables[0].uid, "CBL-000001")
        self.assertGreater(summary.internal.total_cables, 0)
        self.assertIn("Cable Is Ran: Complete", enums.cable_import_statuses)
        self.assertTrue(response.ok)
        self.assertEqual(validation.summary.port_collision_findings, 0)


if __name__ == "__main__":
    unittest.main()

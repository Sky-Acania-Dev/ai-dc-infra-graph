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
            "personnel",
            "crews",
            "crew_members",
            "tasks",
            "task_entities",
            "task_events",
            "operation_log",
            "topology_versions",
            "entity_history",
            "source_imports",
            "filter_presets",
            "change_orders",
            "change_order_items",
            "change_order_task_links",
            "change_order_events",
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

    def test_filter_presets_have_expected_payload_and_scope_columns(self) -> None:
        columns = Base.metadata.tables["filter_presets"].columns

        self.assertIn("project_uid", columns)
        self.assertIn("owner_user_uid", columns)
        self.assertIn("entity_type", columns)
        self.assertIn("visibility", columns)
        self.assertIn("filter_payload", columns)
        self.assertIn("sort_payload", columns)
        self.assertIn("column_payload", columns)

    def test_task_resource_tables_separate_iam_from_field_crews(self) -> None:
        personnel_columns = Base.metadata.tables["personnel"].columns
        crew_member_columns = Base.metadata.tables["crew_members"].columns
        task_columns = Base.metadata.tables["tasks"].columns
        task_entity_columns = Base.metadata.tables["task_entities"].columns
        task_event_columns = Base.metadata.tables["task_events"].columns
        operation_log_columns = Base.metadata.tables["operation_log"].columns

        self.assertIn("user_uid", personnel_columns)
        self.assertIn("employee_uid", personnel_columns)
        self.assertIn("personnel_uid", crew_member_columns)
        self.assertIn("role_in_crew", crew_member_columns)
        self.assertIn("task_type", task_columns)
        self.assertIn("entity_filter_payload", task_columns)
        self.assertIn("target_payload", task_columns)
        self.assertIn("submission_payload", task_columns)
        self.assertIn("assigned_crew_uid", task_columns)
        self.assertIn("assigned_personnel_uid", task_columns)
        self.assertIn("started_at", task_columns)
        self.assertIn("applied_by_user_uid", task_columns)
        self.assertIn("applied_at", task_columns)
        self.assertIn("cancelled_at", task_columns)
        self.assertIn("entity_uid", task_entity_columns)
        self.assertIn("event_type", task_event_columns)
        self.assertIn("operation_group_uid", operation_log_columns)
        self.assertIn("source_type", operation_log_columns)
        self.assertIn("source_uid", operation_log_columns)
        self.assertIn("source_operator", operation_log_columns)

    def test_topology_versions_and_entity_history_capture_import_lifecycle(self) -> None:
        version_columns = Base.metadata.tables["topology_versions"].columns
        history_columns = Base.metadata.tables["entity_history"].columns
        source_import_columns = Base.metadata.tables["source_imports"].columns

        self.assertIn("version_name", version_columns)
        self.assertIn("version_date", version_columns)
        self.assertIn("source_operator", version_columns)
        self.assertIn("source_import_uid", version_columns)
        self.assertIn("first_version_uid", history_columns)
        self.assertIn("first_operation_id", history_columns)
        self.assertIn("last_version_uid", history_columns)
        self.assertIn("last_operation_id", history_columns)
        self.assertIn("version_name", source_import_columns)
        self.assertIn("version_date", source_import_columns)
        self.assertIn("source_operator", source_import_columns)

    def test_change_order_tables_have_expected_payload_and_link_columns(self) -> None:
        cable_columns = Base.metadata.tables["cables"].columns
        order_columns = Base.metadata.tables["change_orders"].columns
        item_columns = Base.metadata.tables["change_order_items"].columns
        link_columns = Base.metadata.tables["change_order_task_links"].columns
        event_columns = Base.metadata.tables["change_order_events"].columns

        self.assertIn("a_label_text", cable_columns)
        self.assertIn("z_label_text", cable_columns)
        self.assertIn("change_order_number", order_columns)
        self.assertIn("items_payload", order_columns)
        self.assertIn("summary", order_columns)
        self.assertIn("intent", item_columns)
        self.assertIn("before_definition", item_columns)
        self.assertIn("after_definition", item_columns)
        self.assertIn("task_plan", item_columns)
        self.assertIn("task_uid", link_columns)
        self.assertIn("effect_type", link_columns)
        self.assertIn("event_type", event_columns)

if __name__ == "__main__":
    unittest.main()

import unittest

from backend.services.change_orders import _default_task_plan, _definition_with_default_labels, _is_active_status, _label_position


class ChangeOrderPlanningTests(unittest.TestCase):
    def test_label_change_generates_label_task_that_marks_cable_relabeled(self) -> None:
        plan = _default_task_plan(
            "label_change",
            {"a_label_text": "old-a", "z_label_text": "old-z"},
            {"a_label_text": "new-a", "z_label_text": "new-z"},
        )

        self.assertEqual(plan, [{"task_type": "cable_label", "effect_type": "label_update", "target_status": "relabeled"}])

    def test_port_change_generates_label_termination_and_dress_work_when_cabinet_changes(self) -> None:
        plan = _default_task_plan(
            "port_change",
            {"a_port_uid": "DH1:001:10:swp1", "z_port_uid": "DH1:002:20:swp2", "a_label_text": "old"},
            {"a_port_uid": "DH1:003:10:swp1", "z_port_uid": "DH1:002:20:swp2", "a_label_text": "new"},
        )

        self.assertEqual([item["task_type"] for item in plan], ["cable_label", "cable_termination", "cable_dress"])
        self.assertTrue(all(item["target_status"] == "relabeled" for item in plan))

    def test_retire_remove_and_add_have_expected_task_shapes(self) -> None:
        self.assertEqual(_default_task_plan("retire_cable", {}, {})[0]["target_status"], "retired")
        self.assertEqual(_default_task_plan("remove_cable", {}, {})[0]["target_status"], "removed")
        self.assertEqual(
            [item["task_type"] for item in _default_task_plan("add_cable", {}, {})],
            ["cable_pull", "cable_dress", "cable_termination", "cable_test", "cable_label"],
        )
    def test_default_label_text_uses_this_side_then_other_side(self) -> None:
        definition = _definition_with_default_labels(
            {
                "a_port_uid": "DH1:1:10:swp1",
                "z_port_uid": "DH2:022:7:Ethernet1/1",
            }
        )

        self.assertEqual(definition["a_label_text"], "dh1:001:10:swp1\ndh2:022:07:Ethernet1/1")
        self.assertEqual(definition["z_label_text"], "dh2:022:07:Ethernet1/1\ndh1:001:10:swp1")

    def test_label_position_formats_datahall_and_cabinet_without_touching_port_name(self) -> None:
        self.assertEqual(_label_position("DH3:4:01:Eth:1"), "dh3:004:01:Eth:1")

    def test_active_status_classifier_treats_co_terminal_statuses_as_inactive(self) -> None:
        for status in ["removed", "retired", "replaced", "canceled", "cancelled"]:
            self.assertFalse(_is_active_status(status))
        self.assertTrue(_is_active_status("Cable Is Ran: Complete"))
        self.assertTrue(_is_active_status("relabeled"))

if __name__ == "__main__":
    unittest.main()

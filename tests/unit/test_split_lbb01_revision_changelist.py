import unittest

from scripts.split_lbb01_revision_changelist import split_changes


class SplitLbb01RevisionChangelistTests(unittest.TestCase):
    def test_splits_normal_history_fields_from_change_order_fields(self) -> None:
        changes = [
            {"change_type": "added", "key": "added"},
            {"change_type": "removed", "key": "removed"},
            {
                "change_type": "changed",
                "key": "mixed",
                "fields": {
                    "status": {"old": "Cable Not Run", "new": "Cable Is Ran: Complete"},
                    "a_device_name": {"old": "old-name", "new": "new-name"},
                    "a_device_model": {"old": "OLD", "new": "NEW"},
                },
            },
        ]

        change_order, history = split_changes(changes)

        self.assertEqual([change["change_type"] for change in change_order], ["added", "removed", "changed"])
        self.assertEqual(set(change_order[-1]["fields"]), {"a_device_model"})
        self.assertEqual(len(history), 1)
        self.assertEqual(set(history[0]["fields"]), {"status", "a_device_name"})


if __name__ == "__main__":
    unittest.main()

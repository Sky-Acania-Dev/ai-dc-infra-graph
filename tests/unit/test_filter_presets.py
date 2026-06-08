import unittest

from backend.persistence.postgresql.filter_presets import validate_filter_payload


class FilterPresetValidationTests(unittest.TestCase):
    def test_validates_supported_cable_filter_payload(self) -> None:
        payload = validate_filter_payload(
            "cable",
            {
                "version": 1,
                "logic": "and",
                "rules": [
                    {"field": "status", "operator": "contains", "value": "Complete"},
                    {"field": "length_used_meters", "operator": "between", "value": [10, 80]},
                    {"field": "cable_type", "operator": "in", "value": ["MPO", "LC"]},
                    {"field": "note", "operator": "is_blank"},
                ],
            },
        )

        self.assertEqual(payload.logic, "and")
        self.assertEqual(len(payload.rules), 4)

    def test_rejects_numeric_operator_on_string_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "not valid for text field 'status'"):
            validate_filter_payload(
                "cable",
                {
                    "version": 1,
                    "rules": [
                        {"field": "status", "operator": "gte", "value": "Complete"},
                    ],
                },
            )

    def test_rejects_string_value_for_numeric_comparison(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a numeric value"):
            validate_filter_payload(
                "cable",
                {
                    "version": 1,
                    "rules": [
                        {"field": "length_used_meters", "operator": "gte", "value": "50"},
                    ],
                },
            )

    def test_rejects_invalid_between_value_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "two-item numeric list"):
            validate_filter_payload(
                "cabinet",
                {
                    "version": 1,
                    "rules": [
                        {"field": "source_row", "operator": "between", "value": [1]},
                    ],
                },
            )

    def test_rejects_contains_on_enum_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "not valid for enum field 'lifecycle_status'"):
            validate_filter_payload(
                "cabinet",
                {
                    "version": 1,
                    "rules": [
                        {"field": "lifecycle_status", "operator": "contains", "value": "active"},
                    ],
                },
            )

    def test_rejects_unknown_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported filter field"):
            validate_filter_payload(
                "device",
                {
                    "version": 1,
                    "rules": [
                        {"field": "missing", "operator": "equals", "value": "x"},
                    ],
                },
            )


if __name__ == "__main__":
    unittest.main()

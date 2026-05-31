from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, load_topology_database, save_topology_database
from backend.services import apply_status_overrides, load_status_overrides


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply manual lifecycle status overrides to a topology database JSON.")
    parser.add_argument("--database-path", default=str(DEFAULT_RUNTIME_DATABASE_PATH))
    parser.add_argument("--status-overrides-path", default="data/status_overrides.json")
    parser.add_argument("--output-path", default=str(DEFAULT_RUNTIME_DATABASE_PATH))
    args = parser.parse_args()

    database = load_topology_database(args.database_path)
    overrides = load_status_overrides(args.status_overrides_path)
    updated_database = apply_status_overrides(database, overrides)
    saved_path = save_topology_database(updated_database, args.output_path)

    overridden_devices = sum(len(cabinet.devices) for cabinet in updated_database.cabinets)
    print(f"runtime_database={saved_path}")
    print(f"data_hall_overrides={len(overrides.data_halls)}")
    print(f"cabinet_overrides={len(overrides.cabinets)}")
    print(f"cabinet_max_rack_unit_overrides={len(overrides.cabinet_max_rack_units)}")
    print(f"device_overrides={len(overrides.devices)}")
    print(f"devices={overridden_devices}")
    print(f"device_model_mismatches={len(updated_database.device_model_mismatches)}")
    print(f"device_model_format_issues={len(updated_database.device_model_format_issues)}")


if __name__ == "__main__":
    main()

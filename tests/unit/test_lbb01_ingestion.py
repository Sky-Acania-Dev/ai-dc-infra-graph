import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from backend.ingest.cutsheet import CutsheetCableRow
from backend.ingest.cleaners.lbb01 import (
    apply_lbb01_rack_unit_rule,
    ingest_lbb01_non_roce_cutsheet,
    ingest_lbb01_overhead,
    ingest_lbb01_roce_cutsheets,
    ingest_lbb01_vr_roce_cutsheets,
    ingest_lbb01_workbook,
)
from backend.models import Cabinet


LBB_WORKBOOK = Path(r"C:\Personal Folder\Work\Megawatt\003. TX Lubbock\1. Data\LBB01- IB sketch (1).xlsx")
LBB_NON_ROCE_WORKBOOK = Path(r"C:\Personal Folder\Work\Megawatt\003. TX Lubbock\1. Data\Lubbanon 8.16.xlsx")
LBB_VR_ROCE_WORKBOOK = Path(r"C:\Personal Folder\Work\Megawatt\003. TX Lubbock\1. Data\Updated VR RoCe.xlsx")
LBB_DH1_ROCE_WORKBOOK = Path(r"C:\Personal Folder\Work\Megawatt\003. TX Lubbock\1. Data\DH1 RoCe 9.4.xlsx")
LBB_DH2_ROCE_WORKBOOK = Path(r"C:\Personal Folder\Work\Megawatt\003. TX Lubbock\1. Data\DH2 RoCe 9.4.xlsx")
LBB_DH4_ROCE_WORKBOOK = Path(r"C:\Personal Folder\Work\Megawatt\003. TX Lubbock\1. Data\RoCe DH4 9.2.xlsx")
LBB_DH5_ROCE_WORKBOOK = Path(r"C:\Personal Folder\Work\Megawatt\003. TX Lubbock\1. Data\RoCe DH5 9.2.xlsx")


class Lbb01SectionTests(unittest.TestCase):
    def test_overhead_keeps_hot_aisle_groups_in_one_section(self) -> None:
        with patch("backend.ingest.cleaners.lbb01.read_xlsx_sheet_rows", return_value=[list(range(1, 1601))]):
            result = ingest_lbb01_overhead("overhead.xlsx")

        cabinets = {int(cabinet.cabinet_id): cabinet for cabinet in result.cabinets}
        self.assertEqual(set(cabinets), set(range(1, 1601)))
        self.assertEqual(len(result.cabinets), 1600)
        self.assertEqual(
            Counter(cabinet.data_hall_id for cabinet in result.cabinets),
            {"DH1-1": 320, "DH1-2": 320, "DH1-3": 320, "DH1-4": 320, "DH1-5": 320},
        )
        for start in range(1, 801, 20):
            with self.subTest(group_start=start):
                section = cabinets[start].data_hall_id
                for rack in range(start, start + 20):
                    self.assertEqual(cabinets[rack].data_hall_id, section)
                    self.assertEqual(cabinets[rack + 800].data_hall_id, section)

    def test_cutsheet_endpoints_use_new_section_boundaries(self) -> None:
        boundaries = ((160, 161), (320, 321), (480, 481), (640, 641))
        for section, (last, first) in enumerate(boundaries, start=1):
            for offset in (0, 800):
                with self.subTest(section=section, offset=offset):
                    row = {
                        "STATUS": "Cable Is Ran: Complete",
                        "A-LOC:CAB:RU": f"dh1:{last + offset}:10",
                        "A-PORT": "swp1",
                        "Z-LOC:CAB:RU": f"dh1:{first + offset}:20",
                        "Z-PORT": "swp2",
                        "CABLE": "LC",
                    }
                    with patch("backend.ingest.cleaners.lbb01.dict_rows_from_header_sheet", return_value=[row]):
                        result = ingest_lbb01_non_roce_cutsheet("cutsheet.xlsx")
                    cable = result.cables[0]
                    self.assertEqual(cable.a_side.uid, f"DH1-{section}:{last + offset:03d}:10:swp1")
                    self.assertEqual(cable.z_side.uid, f"DH1-{section + 1}:{first + offset:03d}:20:swp2")
                    self.assertEqual(result.rows[0].status, "Cable Is Ran: Complete")


class Lbb01RackUnitTests(unittest.TestCase):
    def test_apply_lbb01_rack_unit_rule_resets_stale_72u_imports(self) -> None:
        cabinets = [
            Cabinet(building_id="A", data_hall_id="DH1-3", cabinet_id="1141", category="HD-GB3c", max_rack_unit=72),
            Cabinet(building_id="A", data_hall_id="DH1-3", cabinet_id="1142", category="VR-NVL72-v1", max_rack_unit=72),
            Cabinet(building_id="A", data_hall_id="DH1-3", cabinet_id="1143", category="T0-RO-v3a", max_rack_unit=72),
            Cabinet(building_id="A", data_hall_id="DH1-3", cabinet_id="349", category="XDR x8a", max_rack_unit=72),
        ]
        rows = [
            _vr_row("DH1-3", "1142", 36, "DH1-3", "1143", 38),
            _vr_row("DH1-3", "1142", 50, "DH1-3", "1143", 55),
            _vr_row("DH1-3", "349", 72, "DH1-3", "1141", 10),
        ]

        apply_lbb01_rack_unit_rule(cabinets, rows)

        self.assertEqual([cabinet.max_rack_unit for cabinet in cabinets], [48, 54, 55, 48])


@unittest.skipUnless(LBB_WORKBOOK.exists(), "LBB01 source workbook is not available.")
class Lbb01IngestionTests(unittest.TestCase):
    def test_ingest_lbb01_workbook_extracts_overhead_and_node_to_leaf(self) -> None:
        result = ingest_lbb01_workbook(LBB_WORKBOOK)

        self.assertEqual(result.summary.overhead_cabinets, 1600)
        self.assertEqual(result.summary.cable_rows, 1152)
        self.assertEqual(result.summary.ports, 2304)
        self.assertEqual(result.summary.cables, 1152)
        self.assertEqual(result.summary.port_collision_findings, 0)
        self.assertEqual(
            result.summary.data_halls,
            {"DH1-1": 320, "DH1-2": 320, "DH1-3": 320, "DH1-4": 320, "DH1-5": 320},
        )
        self.assertEqual(result.summary.status_counts, {"Blocked": 288, "Cable Not Run": 864})
        self.assertEqual(result.cutsheet.rows[0].a_port_uid, "DH1-3:342:1:IBP3:P2")
        self.assertEqual(result.cutsheet.rows[0].z_port_uid, "DH1-3:349:45:L349.1.1-DH3:1/1")
        self.assertEqual(result.cutsheet.rows[575].z_port_uid, "DH1-3:349:10:L349.1.8-DH3:36/2")
        self.assertEqual(result.cutsheet.rows[576].a_port_uid, "DH1-3:349:45:L349.1.1-DH3:37/1")
        self.assertEqual(result.cutsheet.rows[576].z_port_uid, "DH1-3:350:45:S1:1/1")

    @unittest.skipUnless(LBB_NON_ROCE_WORKBOOK.exists(), "LBB01 non-RoCE workbook is not available.")
    def test_ingest_lbb01_non_roce_cutsheet_normalizes_physical_hall_to_sections(self) -> None:
        result = ingest_lbb01_non_roce_cutsheet(LBB_NON_ROCE_WORKBOOK)

        self.assertEqual(len(result.rows), 120804)
        self.assertEqual(result.rows[0].a_port_uid, "DH1-3:421:10:eth1/15")
        self.assertEqual(result.rows[0].z_port_uid, "DH1-3:425:35:swp30")

    @unittest.skipUnless(LBB_NON_ROCE_WORKBOOK.exists(), "LBB01 main workbook is not available.")
    def test_ingest_lbb01_overhead_uses_main_workbook_layout(self) -> None:
        result = ingest_lbb01_overhead(LBB_NON_ROCE_WORKBOOK)

        self.assertEqual(result.summary.cabinets, 1600)
        self.assertEqual(result.summary.unknown_category_cabinets, 0)
        self.assertEqual(result.cabinets[0].category, "RES")
        self.assertEqual(result.cabinets[-1].category, "T0-RO-v1a")

    @unittest.skipUnless(LBB_VR_ROCE_WORKBOOK.exists(), "LBB01 VR RoCE workbook is not available.")
    def test_ingest_lbb01_vr_roce_cutsheets_normalizes_physical_hall_to_sections(self) -> None:
        result = ingest_lbb01_vr_roce_cutsheets(LBB_VR_ROCE_WORKBOOK)

        self.assertEqual(len(result.rows), 4352)
        self.assertEqual(len(result.cables), 4352)
        self.assertEqual(result.rows[0].a_port_uid, "DH1-3:1142:36:gpu0")
        self.assertEqual(result.rows[0].z_port_uid, "DH1-3:1149:38:swp1")

    @unittest.skipUnless(LBB_DH1_ROCE_WORKBOOK.exists(), "LBB01 DH1 RoCE workbook is not available.")
    def test_ingest_lbb01_roce_cutsheets_imports_dh1_source(self) -> None:
        result = ingest_lbb01_roce_cutsheets(
            LBB_DH1_ROCE_WORKBOOK,
            sheet_names=("SP1 DH1 NODE TO TIER-0", "SP1 DH1 TIER-0 TO TIER-1"),
        )

        self.assertEqual(len(result.rows), 108288)
        self.assertEqual(len(result.cables), 108288)
        self.assertEqual(len(result.findings), 0)
        self.assertEqual(result.rows[0].group, "LBB01 RoCE")
        self.assertEqual(result.rows[0].a_port_uid, "DH1-1:013:37:ibs0p0")
        self.assertEqual(result.rows[0].z_port_uid, "DH1-1:020:38:swp1s0")

    @unittest.skipUnless(LBB_DH2_ROCE_WORKBOOK.exists(), "LBB01 DH2 RoCE workbook is not available.")
    def test_ingest_lbb01_roce_cutsheets_imports_dh2_source_without_vr_sheets(self) -> None:
        result = ingest_lbb01_roce_cutsheets(
            LBB_DH2_ROCE_WORKBOOK,
            sheet_names=("SP2 DH1 NODE TO TIER-0", "SP2 DH1 TIER-0 TO TIER-1"),
        )

        self.assertEqual(len(result.rows), 112640)
        self.assertEqual(len(result.cables), 112640)
        self.assertEqual(len(result.findings), 0)
        self.assertEqual(result.rows[0].group, "LBB01 RoCE")
        self.assertEqual(result.rows[0].a_port_uid, "DH1-2:163:37:ibs0p0")
        self.assertEqual(result.rows[0].z_port_uid, "DH1-2:170:38:swp1s0")

    @unittest.skipUnless(LBB_DH4_ROCE_WORKBOOK.exists(), "LBB01 DH4 RoCE workbook is not available.")
    def test_ingest_lbb01_roce_cutsheets_imports_dh4_source(self) -> None:
        result = ingest_lbb01_roce_cutsheets(
            LBB_DH4_ROCE_WORKBOOK,
            sheet_names=("SP3 DH1 NODE TO TIER-0", "SP3 DH1 TIER-0 TO TIER-1"),
        )

        self.assertEqual(len(result.rows), 112640)
        self.assertEqual(len(result.cables), 112640)
        self.assertEqual(len(result.findings), 0)
        self.assertEqual(result.rows[0].a_port_uid, "DH1-4:483:37:ibs0p0")
        self.assertEqual(result.rows[0].z_port_uid, "DH1-4:490:38:swp1s0")
        self.assertEqual(
            sum(1 for row in result.rows if row.a_cabinet_id == "1343" or row.z_cabinet_id == "1343"),
            1792,
        )

    @unittest.skipUnless(LBB_DH5_ROCE_WORKBOOK.exists(), "LBB01 DH5 RoCE workbook is not available.")
    def test_ingest_lbb01_roce_cutsheets_imports_dh5_source(self) -> None:
        result = ingest_lbb01_roce_cutsheets(
            LBB_DH5_ROCE_WORKBOOK,
            sheet_names=("SP4 DH1 NODE TO TIER-0", "SP4 DH1 TIER-0 TO TIER-1"),
        )

        self.assertEqual(len(result.rows), 108288)
        self.assertEqual(len(result.cables), 108288)
        self.assertEqual(len(result.findings), 0)
        self.assertEqual(result.rows[0].a_port_uid, "DH1-5:643:37:ibs0p0")
        self.assertEqual(result.rows[0].z_port_uid, "DH1-5:650:38:swp1s0")


def _vr_row(a_data_hall_id: str, a_cabinet_id: str, a_rack_unit: int, z_data_hall_id: str, z_cabinet_id: str, z_rack_unit: int) -> CutsheetCableRow:
    return CutsheetCableRow(
        group="VR RoCE",
        status="Cable Not Run",
        cable_type="MPO12-SMF",
        a_data_hall_id=a_data_hall_id,
        a_cabinet_id=a_cabinet_id,
        a_rack_unit=a_rack_unit,
        a_port_id="gpu0",
        a_port_uid=f"{a_data_hall_id}:{a_cabinet_id}:{a_rack_unit}:gpu0",
        z_data_hall_id=z_data_hall_id,
        z_cabinet_id=z_cabinet_id,
        z_rack_unit=z_rack_unit,
        z_port_id="swp1",
        z_port_uid=f"{z_data_hall_id}:{z_cabinet_id}:{z_rack_unit}:swp1",
    )


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.core.enums import ConstructionPhase
from backend.ingest.cutsheet_pipeline import CutsheetSourceSpec, ingest_cutsheet_sources
from tests.unit.test_json_database import _test_paths


class CutsheetPipelineTests(unittest.TestCase):
    def test_pipeline_ingests_multiple_cut_sheet_sources_with_phase_metadata(self) -> None:
        cutsheet_path, _ = _test_paths()
        cutsheet_path.write_text(
            "\n".join(
                [
                    "STATUS,A-LOC:CAB:RU,A-PORT,A_MODEL,Z-LOC:CAB:RU,Z-PORT,Z_MODEL,CABLE",
                    "Cable Not Run,dh1:001:10,swp1,Switch,dh1:002:20,swp2,Patch Panel,LC",
                ]
            ),
            encoding="utf-8",
        )

        result = ingest_cutsheet_sources(
            [
                CutsheetSourceSpec(
                    source_name="management",
                    path=str(cutsheet_path),
                    construction_phase=ConstructionPhase.MANAGEMENT_ETHERNET,
                ),
                CutsheetSourceSpec(
                    source_name="roce",
                    path=str(cutsheet_path),
                    construction_phase=ConstructionPhase.ROCE,
                ),
            ]
        )

        self.assertEqual([source.source_name for source in result.sources], ["management", "roce"])
        self.assertEqual(
            [source.construction_phase for source in result.sources],
            [ConstructionPhase.MANAGEMENT_ETHERNET, ConstructionPhase.ROCE],
        )
        self.assertEqual([len(source.result.cables) for source in result.sources], [1, 1])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from backend.core.projects import get_project, load_project_catalog


class ProjectCatalogTests(unittest.TestCase):
    def test_load_project_catalog_includes_lubbock_project(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            catalog = load_project_catalog()
            project = get_project("lbb01")

        self.assertEqual(catalog.default_project_uid, "LBB01")
        self.assertIsNotNone(project)
        self.assertEqual(project.location.state, "TX")
        self.assertEqual(project.data_halls, ["DH1-1", "DH1-2", "DH1-3", "DH1-4", "DH1-5"])
        self.assertEqual(project.source_files[0].kind, "roce_sample")
        self.assertEqual(project.source_files[1].kind, "non_roce_cutsheet")
        self.assertEqual(project.source_files[2].kind, "roce_cutsheet")
        self.assertEqual(project.source_files[3].kind, "vr_roce_cutsheet")

    def test_active_project_env_sets_single_active_project(self) -> None:
        with patch.dict("os.environ", {"ACTIVE_PROJECT_UID": "LBB01"}):
            catalog = load_project_catalog()

        statuses = {project.uid: project.status for project in catalog.projects}
        self.assertEqual(catalog.default_project_uid, "LBB01")
        self.assertEqual(statuses["LBB01"], "active")
        self.assertEqual(statuses["MSK01"], "standby")


if __name__ == "__main__":
    unittest.main()

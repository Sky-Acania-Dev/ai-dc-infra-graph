import unittest
from unittest.mock import MagicMock, patch

from backend.api.auth import AuthUser, UserRole
from backend.api.entity_groups import list_source_cable_groups


class SourceCableGroupTests(unittest.TestCase):
    def test_source_groups_load_counts_for_the_requested_project(self):
        session = MagicMock()
        row = MagicMock(cable_group='POD-DIST-B 3')
        row.__getitem__.return_value = 4
        session.execute.return_value.all.return_value = [row]
        factory = MagicMock()
        factory.return_value.return_value.__enter__.return_value = session
        with patch('backend.api.entity_groups._require_postgresql'), patch('backend.api.entity_groups.session_factory', factory):
            result = list_source_cable_groups('LBB01', AuthUser(uid='viewer',display_name='Viewer',role=UserRole.VIEWER))
        self.assertEqual([(r.group,r.cable_count) for r in result],[('POD-DIST-B 3',4)])
        statement = session.execute.call_args.args[0]
        compiled = statement.compile()
        self.assertIn('count(cables.uid)', str(compiled))
        self.assertIn('LBB01', compiled.params.values())
        self.assertIn('cables.deleted_at IS NULL', str(compiled))


if __name__ == '__main__':
    unittest.main()

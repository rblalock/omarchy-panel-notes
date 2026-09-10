import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core.setup import BINDING, MARKER, PLUGIN_ID, setup, remove_shortcut


class Setup(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.target = self.home / '.config/omarchy/plugins' / PLUGIN_ID / 'panel-notes'
        self.target.parent.mkdir(parents=True)
        self.target.write_text('fixture')
        self.bindings = self.home / '.config/hypr/bindings.lua'
        self.bindings.parent.mkdir(parents=True)
        self.original = '-- Personal bindings\no.bind("SUPER + T", "Terminal", "ghostty")\n'
        self.bindings.write_text(self.original)
        self.patches = [patch('pathlib.Path.home', return_value=self.home),
                        patch('core.setup.check_dependencies'), patch('core.setup.environment', return_value={}),
                        patch('core.setup.hypr', return_value=[]),
                        patch('core.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'ok\n', ''))]
        for mock in self.patches: mock.start()
        self.addCleanup(self.temporary.cleanup)
        for mock in self.patches: self.addCleanup(mock.stop)

    def test_setup_repeat_remove_retains_personal_config(self):
        setup()
        first = self.bindings.read_text()
        setup()
        self.assertEqual(first, self.bindings.read_text())
        self.assertEqual(first.count(MARKER), 1)
        self.assertIn(BINDING, first)
        remove_shortcut()
        self.assertEqual(self.bindings.read_text().rstrip(), self.original.rstrip())
        self.assertFalse((self.home / '.local/bin/panel-notes').is_symlink())
        self.assertTrue(list((self.home / '.local/state/panel-notes/config-backups').glob('*.lua')))

    def test_conflict_and_unowned_launcher_are_untouched(self):
        with patch('core.setup.hypr', return_value=[{'modmask':72, 'key':'N', 'description':'Other app'}]):
            with self.assertRaisesRegex(RuntimeError, 'already in use'): setup()
        self.assertEqual(self.bindings.read_text(), self.original)
        link = self.home / '.local/bin/panel-notes'
        link.parent.mkdir(parents=True)
        link.write_text('mine')
        with self.assertRaisesRegex(RuntimeError, 'not our launcher'): setup()
        self.assertEqual(link.read_text(), 'mine')
        self.assertEqual(self.bindings.read_text(), self.original)

    def test_invalid_reload_rolls_back_and_legacy_binding_upgrades(self):
        with patch('core.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'Bad configuration', '')):
            with self.assertRaises(RuntimeError): setup()
        self.assertEqual(self.bindings.read_text(), self.original)
        self.bindings.write_text(self.original + MARKER + 'o.bind("SUPER + ALT + N", "Panel Notes", "/old/bin/panel-notes toggle")\n')
        with patch('core.setup.hypr', return_value=[{'modmask':72, 'key':'N', 'description':'Panel Notes'}]): setup()
        self.assertIn(BINDING, self.bindings.read_text())
        self.assertNotIn('/old/bin', self.bindings.read_text())

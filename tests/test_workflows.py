"""Keep remote action references immutable in repository CI definitions."""
from pathlib import Path
import re
import unittest


class WorkflowReferences(unittest.TestCase):
    def test_remote_actions_use_full_commit_pins(self):
        root = Path(__file__).resolve().parent.parent / '.github'
        files = sorted([*root.rglob('*.yml'), *root.rglob('*.yaml')])
        self.assertTrue(files, 'No workflow definitions found')
        for path in files:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                match = re.match(r'\s*(?:-\s+)?uses:\s*(\S+)', line)
                if not match:
                    continue
                reference = match[1].strip("\"'")
                if reference.startswith('./'):
                    continue
                with self.subTest(path=str(path.relative_to(root)), line=number):
                    self.assertRegex(reference, r'^[\w.-]+/[\w./-]+@[0-9a-f]{40}$',
                                     'Pin remote actions to full commit SHAs, not branches or version tags')

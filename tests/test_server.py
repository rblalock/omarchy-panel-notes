"""Exercise a packaged service with isolated storage and runtime sockets."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest


class Service(unittest.TestCase):
    def test_update_reloads_code_and_idle_service_exits(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            package = base / 'plugin'
            shutil.copytree(root, package, ignore=shutil.ignore_patterns('.git', '.test-output', 'build', '__pycache__'))
            env = {**os.environ, 'PANEL_NOTES_ROOT':str(base / 'notes'),
                   'PANEL_NOTES_RECOVERY':str(base / 'recovery'), 'XDG_RUNTIME_DIR':str(base / 'runtime'),
                   'XDG_CONFIG_HOME':str(base / 'config')}
            def cli(command):
                return json.loads(subprocess.check_output(['python3', str(package / 'panel-notes'), command], env=env, text=True, timeout=10))
            address = cli('ensure')['socket']
            def request(data):
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(address)
                    client.sendall((json.dumps(data) + '\n').encode())
                    response = json.loads(client.makefile('rb').readline())
                    self.assertTrue(response['ok'], response)
                    return response['result']
            try:
                revision = request({'op':'ping'})['codeRevision']
                note = request({'op':'scope', 'scope':{'kind':'app', 'key':'app:test', 'title':'Test'}})
                request({'op':'save', 'noteId':note['meta']['id'], 'text':'Keep through update', 'revision':note['revision']})
                with (package / 'core/backend.py').open('a') as stream: stream.write('\n# candidate update\n')
                self.assertEqual(cli('ensure')['socket'], address)
                self.assertNotEqual(request({'op':'ping'})['codeRevision'], revision)
                self.assertEqual(request({'op':'load', 'noteId':note['meta']['id']})['text'], 'Keep through update')
                deadline = time.monotonic() + 14
                while Path(address).exists() and time.monotonic() < deadline: time.sleep(.1)
                self.assertFalse(Path(address).exists(), 'Unloaded panel left an idle service behind')
                self.assertEqual(cli('ensure')['socket'], address)
                self.assertEqual(request({'op':'load', 'noteId':note['meta']['id']})['text'], 'Keep through update')
            finally:
                subprocess.run(['python3', str(package / 'panel-notes'), 'shutdown'], env=env, check=True, timeout=6)

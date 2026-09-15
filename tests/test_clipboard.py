import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from core.backend import Backend, PROJECT
from core.registry import Registry
from core.storage import MAX_ASSET_BYTES
from core.server import call, runtime


class Clipboard(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.environment = patch.dict(os.environ, {
            'PANEL_NOTES_ROOT': str(self.base / 'notes'),
            'PANEL_NOTES_RECOVERY': str(self.base / 'state/recovery'),
            'PANEL_NOTES_EXTENSIONS': str(self.base / 'extensions'),
            'XDG_CONFIG_HOME': str(self.base / 'config'),
            'PATH': str(self.base) + os.pathsep + os.environ['PATH'],
            'CLIPBOARD_MODE': 'png',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        environment = patch('core.backend.environment', side_effect=lambda: os.environ.copy())
        environment.start()
        self.addCleanup(environment.stop)
        executable = self.base / 'wl-paste'
        executable.write_text(f'''#!{sys.executable}
import os, sys
from pathlib import Path
mode = os.environ['CLIPBOARD_MODE']
if os.environ.get('CLIPBOARD_MODE_FILE'): mode = Path(os.environ['CLIPBOARD_MODE_FILE']).read_text()
if '--list-types' in sys.argv:
    if mode == 'types-overflow':
        while True: os.write(1, b'image/png\\n'*8192)
    if mode == 'invalid-types': os.write(1, b'\\xff'); sys.exit(0)
    mime = {{'text': 'text/plain', 'jpg': 'image/jpeg', 'webp': 'image/webp'}}.get(mode, 'image/png')
    print(mime)
else:
    if mode == 'image-overflow':
        while True: os.write(1, b'x'*65536)
    if mode == 'failure': os.write(1, b'partial'); sys.exit(1)
    data = {{'png': b'\\x89PNG\\r\\n\\x1a\\nfixture', 'jpg': b'\\xff\\xd8\\xfffixture',
             'webp': b'RIFF1234WEBPfixture', 'invalid-image': b'bad'}}.get(mode, b'\\x89PNG\\r\\n\\x1a\\n')
    if mode in ('exact-limit', 'one-over'):
        size = {MAX_ASSET_BYTES} + (mode == 'one-over')
        data += b'x'*(size - len(data))
    sys.stdout.buffer.write(data)
''')
        executable.chmod(0o700)
        self.backend = Backend(self.base / 'runtime')
        self.backend.runtime.mkdir()
        self.note = self.backend.dispatch({'op': 'scope', 'scope': {'kind': 'app', 'key': 'app:test', 'title': 'Test'}})
        self.request = {'op': 'clipboard-image', 'noteId': self.note['meta']['id']}

    def paste(self, mode):
        with patch.dict(os.environ, {'CLIPBOARD_MODE': mode}):
            return self.backend.dispatch(self.request)

    def test_supported_formats_and_text_fallback(self):
        self.assertEqual(self.paste('text'), {'isImage': False})
        for mode in ('png', 'jpg', 'webp'):
            with self.subTest(mode=mode):
                result = self.paste(mode)
                self.assertTrue(result['isImage'])
                self.assertTrue(result['path'].endswith('.' + mode))
                self.assertTrue((Path(self.note['path']).parent / result['path']).is_file())

    def test_exact_image_limit_is_accepted(self):
        result = self.paste('exact-limit')
        self.assertEqual((Path(self.note['path']).parent / result['path']).stat().st_size, MAX_ASSET_BYTES)

    def test_overflow_and_failed_producers_never_import_partial_images(self):
        for mode in ('types-overflow', 'image-overflow', 'one-over', 'failure', 'invalid-types'):
            with self.subTest(mode=mode):
                with patch.object(self.backend.store, 'import_asset') as import_asset:
                    with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                        self.paste(mode)
                    import_asset.assert_not_called()
                self.assertEqual(self.backend.store.load(self.note['meta']['id'])['text'], '')
                # A rejected producer must not strand the paste lock/service.
                self.assertTrue(self.paste('png')['isImage'])

    def test_invalid_image_is_rejected_without_asset_write(self):
        with self.assertRaisesRegex(ValueError, 'supported image'):
            self.paste('invalid-image')
        self.assertEqual(self.backend.store.load(self.note['meta']['id'])['meta']['assets'], [])

    def test_concurrent_paste_is_rejected_before_launch(self):
        with self.backend.clipboard_lock, patch('core.backend.bounded_output') as launch:
            with self.assertRaisesRegex(ValueError, 'already in progress'):
                self.paste('png')
            launch.assert_not_called()

    def test_snapshot_reads_are_bounded_and_reject_special_files(self):
        path = self.backend.runtime / 'capture-test.png'
        request = {'op': 'import-capture', 'noteId': self.note['meta']['id'], 'path': str(path)}
        path.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        result = self.backend.dispatch(request)
        self.assertTrue((Path(self.note['path']).parent / result['path']).exists())
        self.assertFalse(path.exists())
        with path.open('wb') as stream:
            stream.write(b'\x89PNG\r\n\x1a\n')
            stream.truncate(MAX_ASSET_BYTES * 4)  # Sparse oversized file.
        with self.assertRaisesRegex(ValueError, '25 MB'):
            self.backend.dispatch(request)
        self.assertFalse(path.exists())
        os.mkfifo(path)
        with self.assertRaisesRegex(ValueError, 'Invalid capture file'):
            self.backend.dispatch(request)
        self.assertFalse(path.exists())
        path.symlink_to(self.note['path'])
        with self.assertRaisesRegex(ValueError, 'Invalid capture path'):
            self.backend.dispatch(request)
        self.assertEqual(Path(self.note['path']).read_text(), '')

    def test_noisy_external_provider_preserves_app_notes(self):
        provider = self.base / 'extensions/noisy'
        provider.mkdir(parents=True)
        (provider / 'extension.json').write_text(json.dumps({
            'id': 'example.noisy', 'apiVersion': 1, 'kind': 'context', 'entry': 'provider.py'}))
        (provider / 'provider.py').write_text('import os\nwhile True: os.write(1, b"x"*65536)\n')
        registry = Registry([PROJECT / 'providers', provider.parent])
        result = registry.resolve({'app': 'test'}, {})
        self.assertEqual(result['scopes'][0]['kind'], 'app')
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('exceeds 131072 bytes', result['errors'][0]['error'])

    def test_running_service_survives_endless_clipboard_and_saves_notes(self):
        mode = self.base / 'clipboard-mode'
        mode.write_text('png')
        with patch.dict(os.environ, {
            'XDG_RUNTIME_DIR': str(self.backend.runtime),
            'HYPRLAND_INSTANCE_SIGNATURE': 'test-session',
            'CLIPBOARD_MODE_FILE': str(mode),
        }):
            address = runtime() / 'bridge.sock'
            service = subprocess.Popen([sys.executable, '-B', str(PROJECT / 'panel-notes'), 'serve'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 5
                while not address.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                call({'op': 'ping'}, address)
                for producer in ('types-overflow', 'image-overflow'):
                    mode.write_text(producer)
                    with self.assertRaisesRegex(RuntimeError, 'exceeds'):
                        call(self.request, address)
                    self.assertEqual(call({'op': 'ping'}, address)['version'], 1)
                mode.write_text('png')
                asset = call(self.request, address)
                self.assertTrue(asset['isImage'])
                call({'op': 'save', 'noteId': self.note['meta']['id'], 'revision': self.note['revision'],
                      'text': 'Still working\n' + asset['markdown']}, address)
                loaded = call({'op': 'load', 'noteId': self.note['meta']['id']}, address)
                self.assertEqual(loaded['text'], 'Still working\n' + asset['markdown'])
                call({'op': 'shutdown'}, address)
                service.wait(timeout=3)
                self.assertEqual(service.returncode, 0)
            finally:
                if service.poll() is None:
                    service.kill()
                service.wait()

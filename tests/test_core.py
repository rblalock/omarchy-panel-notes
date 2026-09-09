import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from core.storage import Store, digest
from core.registry import Registry
from core.backend import Backend, PROJECT


class Storage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.store = Store(self.base / 'notes', self.base / 'recovery')
        self.scope = {'key':'file:/tmp/example.md', 'kind':'file', 'title':'Example'}
        self.note = self.store.for_scope(self.scope)

    def test_restart_and_exact_markdown(self):
        text = '# Title\n\n- [ ] Task\n\n```js\nconst x = 1;\n```\n'
        self.store.save(self.note['meta']['id'], text, self.note['revision'])
        other = Store(self.store.root, self.store.recovery)
        loaded = other.for_scope({**self.scope, 'title':'New title'})
        self.assertEqual(loaded['meta']['id'], self.note['meta']['id'])
        self.assertEqual(loaded['text'], text)
        self.assertEqual(other.recoveries(), [])

    def test_external_conflict_preserves_both(self):
        Path(self.note['path']).write_text('external edit')
        result = self.store.save(self.note['meta']['id'], 'my draft', self.note['revision'])
        self.assertTrue(result['conflict'])
        self.assertEqual(Path(self.note['path']).read_text(), 'external edit')
        self.assertEqual(self.store.recoveries()[0]['text'], 'my draft')

    def test_failed_write_keeps_recovery(self):
        from core import storage
        real = storage.atomic
        def fail(path, data):
            if str(path) == self.note['path']: raise OSError('Disk full')
            return real(path, data)
        with patch.object(storage, 'atomic', fail), self.assertRaises(OSError):
            self.store.save(self.note['meta']['id'], 'latest draft', self.note['revision'])
        self.assertEqual(self.store.recoveries()[0]['text'], 'latest draft')
        self.assertEqual(Path(self.note['path']).read_text(), '')

    def test_two_writers_never_silently_clobber(self):
        results = []
        def save(text): results.append(self.store.save(self.note['meta']['id'], text, self.note['revision']))
        workers = [threading.Thread(target=save, args=(value,)) for value in ('one', 'two')]
        for worker in workers: worker.start()
        for worker in workers: worker.join()
        self.assertEqual(sum(bool(x.get('conflict')) for x in results), 1)
        self.assertEqual(len(self.store.recoveries()), 1)

    def test_assets_and_migration(self):
        asset = self.store.import_asset(self.note['meta']['id'], b'\x89PNG\r\n\x1a\nfixture', 'png', {'app':'test'})
        self.store.save(self.note['meta']['id'], asset['markdown'], self.note['revision'])
        destination = self.store.migrate(self.base / 'moved')
        loaded = Store(destination).load(self.note['meta']['id'])
        self.assertEqual(loaded['text'], asset['markdown'])
        self.assertTrue((Path(loaded['path']).parent / asset['path']).exists())
        self.assertTrue(Path(self.note['path']).exists())

    def test_migration_recovery_remains_discoverable(self):
        Path(self.note['path']).write_text('other')
        self.store.save(self.note['meta']['id'], 'draft', self.note['revision'])
        moved = self.store.migrate(self.base / 'moved')
        self.assertEqual(Store(moved, self.store.recovery).recoveries()[0]['text'], 'draft')

    def test_malformed_neighbor_and_unknown_type(self):
        bad = self.store.root / 'notes/bad/note.json'; bad.parent.mkdir(); bad.write_text('{bad')
        wrong = self.store.root / 'notes/wrong/note.json'; wrong.parent.mkdir(); wrong.write_text('[]')
        unknown = self.store.for_scope({'key':'object:123', 'kind':'object', 'title':'Other'}, 'example.card')
        self.store.save(unknown['meta']['id'], '{"future":true}', unknown['revision'])
        self.assertEqual(len(self.store.search()['notes']), 2)
        self.assertEqual(len(self.store.search()['errors']), 2)
        self.assertEqual(self.store.load(unknown['meta']['id'])['meta']['type'], 'example.card')

    def test_unsafe_paths_rejected(self):
        with self.assertRaises(ValueError): self.store.load('../no')
        meta = self.note['meta']; meta['body'] = '../outside'
        (Path(self.note['path']).parent / 'note.json').write_text(json.dumps(meta))
        with self.assertRaises(ValueError): self.store.load(meta['id'])

    def test_unavailable_root_does_not_prevent_recovery_access(self):
        obstacle=self.base/'not-a-directory'; obstacle.write_text('file')
        unavailable=Store(obstacle/'collection',self.base/'independent-recovery')
        self.assertEqual(unavailable.recoveries(),[])
        with self.assertRaises(OSError): unavailable.for_scope(self.scope)


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = {'app':'test.app', 'title':'same title'}
        self.registry = Registry([PROJECT / 'providers', PROJECT / 'content'])

    def test_same_name_files_and_canonical_paths(self):
        first = self.base / 'a/note.md'; second = self.base / 'b/note.md'
        for path in (first, second): path.parent.mkdir(); path.write_text('')
        a = self.registry.resolve(self.source, {'file':str(first)})['scopes'][-1]
        b = self.registry.resolve(self.source, {'file':str(second)})['scopes'][-1]
        self.assertNotEqual(a['key'], b['key'])
        alias = self.base / 'alias.md'; alias.symlink_to(first)
        self.assertEqual(a['key'], self.registry.resolve(self.source, {'file':str(alias)})['scopes'][-1]['key'])
        first.unlink()
        self.assertEqual(len(self.registry.resolve(self.source, {'file':str(first)})['scopes']), 1)

    def test_page_query_fragment_and_profile_identity(self):
        def keys(url, partition='a'):
            return [s['key'] for s in self.registry.resolve(self.source, {'url':url, 'partition':partition})['scopes']]
        a = keys('https://example.org/path?q=1#view')
        b = keys('https://example.org/path?q=2#view')
        self.assertEqual(a[1], b[1]); self.assertNotEqual(a[2], b[2])
        self.assertNotEqual(a[2], keys('https://example.org/path?q=1#view', 'b')[2])
        self.assertEqual(len(keys('https://user:password@example.org/')), 1)

    def test_separate_provider_and_content_registration(self):
        p = self.base / 'custom'; p.mkdir()
        (p / 'extension.json').write_text(json.dumps({'apiVersion':1, 'id':'example.objects', 'kind':'context', 'entry':'provider.py'}))
        (p / 'provider.py').write_text("def resolve(source, context):\n return [{'key':'example:42','kind':'object','title':'Object 42'}]\n")
        c = self.base / 'card'; c.mkdir()
        (c / 'extension.json').write_text(json.dumps({'apiVersion':1, 'id':'example.card', 'kind':'content', 'type':'example.card', 'editor':'Editor.qml'}))
        (c / 'Editor.qml').write_text('import QtQuick\nItem {}\n')
        registry = Registry([PROJECT / 'providers', self.base])
        self.assertEqual(registry.resolve(self.source, {})['scopes'][-1]['key'], 'example:42')
        self.assertTrue(registry.content['example.card']['editorUrl'].endswith('Editor.qml'))

    def test_timeout_and_malformed_provider_preserve_app_fallback(self):
        p = self.base / 'slow'; p.mkdir()
        (p / 'extension.json').write_text(json.dumps({'apiVersion':1, 'id':'example.slow', 'kind':'context', 'entry':'provider.py'}))
        (p / 'provider.py').write_text('import time\ndef resolve(*args):\n time.sleep(10)\n')
        result = Registry([PROJECT / 'providers', self.base]).resolve(self.source, {})
        self.assertEqual(result['scopes'][0]['kind'], 'app'); self.assertEqual(len(result['errors']), 1)


class BackendContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'PANEL_NOTES_ROOT':str(self.base/'collection'),
                             'PANEL_NOTES_RECOVERY':str(self.base/'state/recovery'), 'XDG_CONFIG_HOME':str(self.base/'config')})
        self.env.start(); self.addCleanup(self.env.stop)
        self.backend = Backend(self.base/'runtime')
        self.source = {'session':'test-session','address':'0xabc','pid':123,'title':'one','app':'editor'}

    def test_ordered_writer_and_external_conflict(self):
        note = self.backend.dispatch({'op':'scope','scope':{'key':'test:1','kind':'object','title':'Object'}})
        common = {'op':'save','noteId':note['meta']['id'],'writerId':note['writerId'],'revision':note['revision']}
        self.backend.dispatch({**common,'sequence':1,'text':'first'})
        self.backend.dispatch({**common,'sequence':2,'text':'second'})
        with self.assertRaises(ValueError): self.backend.dispatch({**common,'sequence':1,'text':'late first'})
        self.assertEqual(Path(note['path']).read_text(),'second')
        Path(note['path']).write_text('external')
        conflict = self.backend.dispatch({**common,'sequence':3,'text':'local'})
        self.assertTrue(conflict['conflict'])
        recovered = self.backend.dispatch({'op':'recover','recoveryId':conflict['recoveryId']})
        self.assertEqual(recovered['text'],'local')
        self.assertEqual(Path(note['path']).read_text(),'external')

    def test_disabled_settings_fallback(self):
        self.backend.settings_path.parent.mkdir(parents=True)
        self.backend.settings_path.write_text(json.dumps({'plugins':[{'id':'io.github.rblalock.panel-notes','reducedMotion':True}]}))
        self.assertTrue(self.backend.settings()['reducedMotion'])
        self.backend.settings_path.write_text('{"plugins":[]}')
        restarted = Backend(self.base/'runtime')
        self.assertTrue(restarted.settings()['reducedMotion'])

    def test_custom_tabs_add_remove_persist_and_keep_notes(self):
        with patch('core.backend.snapshot', return_value=self.source):
            first = self.backend.dispatch({'op':'add-tab', 'value':'https://example.com/one'})
            scope = next(s for s in first['scopes'] if s.get('customTab'))
            note = self.backend.dispatch({'op':'scope', 'scope':scope})
            self.backend.dispatch({'op':'save', 'noteId':note['meta']['id'], 'writerId':note['writerId'],
                                   'revision':note['revision'], 'sequence':1, 'text':'Keep this thought'})
            second = self.backend.dispatch({'op':'add-tab', 'value':'https://example.com/two'})
            self.assertEqual(len([s for s in second['scopes'] if s.get('customTab')]), 2)
            duplicate = self.backend.dispatch({'op':'add-tab', 'value':'https://example.com/one'})
            self.assertEqual(len(duplicate['scopes']), 3)
            restarted = Backend(self.base/'runtime')
            reopened = restarted.dispatch({'op':'open', 'address':'0xabc'})
            self.assertEqual(len(reopened['scopes']), 3)
            removed = restarted.dispatch({'op':'remove-tab', 'key':scope['key']})
            self.assertNotIn(scope['key'], [s['key'] for s in removed['scopes']])
            self.assertEqual(restarted.store.load(note['meta']['id'])['text'], 'Keep this thought')
            again = restarted.dispatch({'op':'add-tab', 'value':'https://example.com/one'})
            restored = restarted.dispatch({'op':'scope', 'scope':next(s for s in again['scopes'] if s['key']==scope['key'])})
            self.assertEqual(restored['meta']['id'], note['meta']['id'])
        with patch('core.backend.snapshot', return_value={**self.source, 'app':'different'}):
            self.assertEqual(len(self.backend.dispatch({'op':'open', 'address':'0xabc'})['scopes']), 1)

    def test_custom_tab_validation_paths(self):
        file = self.base/'a file.md'; file.write_text('Source stays untouched')
        with patch('core.backend.snapshot', return_value=self.source):
            for value in ('nope', 'https://', 'https://user:password@example.com', '/missing-panel-notes-file'):
                with self.assertRaises(ValueError): self.backend.dispatch({'op':'add-tab', 'value':value})
            with self.assertRaises(ValueError):
                self.backend.dispatch({'op':'add-tab', 'value':str(file), 'expected':{'pid':999}})
            result = self.backend.dispatch({'op':'add-tab', 'value':str(file)})
            self.assertEqual(result['scopes'][-1]['kind'], 'file')
            folder = self.backend.dispatch({'op':'add-tab', 'value':str(self.base)})
            self.assertEqual(folder['scopes'][-1]['kind'], 'directory')
        self.assertEqual(file.read_text(), 'Source stays untouched')

    def test_app_note_identity_across_windows_and_restart(self):
        with patch('core.backend.snapshot', return_value=self.source):
            scopes = self.backend.dispatch({'op':'open', 'address':'0xabc'})['scopes']
            self.assertEqual([scope['kind'] for scope in scopes], ['app'])
            note = self.backend.dispatch({'op':'scope', 'scope':scopes[0]})
        other = {**self.source, 'address':'0xdef', 'pid':456, 'title':'Different tab'}
        with patch('core.backend.snapshot', return_value=other):
            restarted = Backend(self.base/'runtime')
            scopes = restarted.dispatch({'op':'open', 'address':'0xdef'})['scopes']
            self.assertEqual(restarted.dispatch({'op':'scope', 'scope':scopes[0]})['meta']['id'], note['meta']['id'])


if __name__ == '__main__': unittest.main()

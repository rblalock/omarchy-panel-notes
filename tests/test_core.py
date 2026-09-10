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

    def test_bundled_providers_do_not_launch_processes(self):
        with patch('core.registry.subprocess.run', side_effect=AssertionError('Unexpected process')):
            result = self.registry.resolve(self.source, {'name':'Ideas'})
        self.assertEqual([scope['kind'] for scope in result['scopes']], ['app','named'])
        self.assertEqual(result['errors'], [])

    def test_external_provider_cannot_claim_inline_execution_by_id(self):
        p = self.base / 'external'; p.mkdir()
        (p / 'extension.json').write_text(json.dumps({'apiVersion':1, 'id':'panel-notes.app', 'kind':'context', 'entry':'provider.py'}))
        (p / 'provider.py').write_text("def resolve(source, context):\n return [{'key':'external:1','kind':'object','title':'External'}]\n")
        registry = Registry([self.base])
        import subprocess
        with patch('core.registry.subprocess.run', wraps=subprocess.run) as run:
            result = registry.resolve(self.source, {})
        self.assertEqual(result['scopes'][0]['key'], 'external:1')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs['timeout'], .5)

    def test_named_identity_is_app_scoped_and_normalized(self):
        def named(app, name):
            return self.registry.resolve({'app':app}, {'name':name})['scopes'][-1]
        first = named('one.app', ' Ideas ')
        self.assertEqual(first['key'], named('one.app','ideas')['key'])
        self.assertNotEqual(first['key'], named('other.app','Ideas')['key'])
        self.assertEqual(named('one.app','Café')['key'], named('one.app','Cafe\u0301')['key'])
        self.assertNotIn('locator', first)

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
            first = self.backend.dispatch({'op':'add-tab', 'name':'Ideas'})
            scope = next(s for s in first['scopes'] if s.get('customTab'))
            note = self.backend.dispatch({'op':'scope', 'scope':scope})
            self.backend.dispatch({'op':'save', 'noteId':note['meta']['id'], 'writerId':note['writerId'],
                                   'revision':note['revision'], 'sequence':1, 'text':'Keep this thought'})
            second = self.backend.dispatch({'op':'add-tab', 'name':'Research'})
            self.assertEqual(len([s for s in second['scopes'] if s.get('customTab')]), 2)
            duplicate = self.backend.dispatch({'op':'add-tab', 'name':'Ideas'})
            self.assertEqual(len(duplicate['scopes']), 3)
            restarted = Backend(self.base/'runtime')
            reopened = restarted.dispatch({'op':'open', 'address':'0xabc'})
            self.assertEqual(len(reopened['scopes']), 3)
            removed = restarted.dispatch({'op':'remove-tab', 'key':scope['key']})
            self.assertNotIn(scope['key'], [s['key'] for s in removed['scopes']])
            self.assertEqual(restarted.store.load(note['meta']['id'])['text'], 'Keep this thought')
            again = restarted.dispatch({'op':'add-tab', 'name':'Ideas'})
            restored = restarted.dispatch({'op':'scope', 'scope':next(s for s in again['scopes'] if s['key']==scope['key'])})
            self.assertEqual(restored['meta']['id'], note['meta']['id'])
        with patch('core.backend.snapshot', return_value={**self.source, 'app':'different'}):
            self.assertEqual(len(self.backend.dispatch({'op':'open', 'address':'0xabc'})['scopes']), 1)

    def test_unreadable_existing_note_never_creates_empty_replacement(self):
        scope = {'key':'app:editor', 'kind':'app', 'title':'Editor'}
        note = self.backend.store.for_scope(scope)
        Path(note['path']).unlink()
        with self.assertRaises(OSError): self.backend.store.for_scope(scope)
        self.assertEqual(len(self.backend.store.directories()), 1)

    def test_rename_retains_identity_images_and_removed_note(self):
        with patch('core.backend.snapshot', return_value=self.source):
            scope = self.backend.dispatch({'op':'add-tab', 'name':'Ideas'})['scopes'][-1]
            note = self.backend.store.for_scope(scope)
            asset = self.backend.store.import_asset(note['meta']['id'], b'\x89PNG\r\n\x1a\nfixture', 'png')
            body = 'Keep this thought\n' + asset['markdown']
            self.backend.store.save(note['meta']['id'], body, note['revision'])
            renamed = self.backend.dispatch({'op':'rename-tab', 'key':scope['key'], 'name':'Plans'})
            self.assertEqual(renamed['selectedKey'], scope['key'])
            retained = self.backend.store.load(note['meta']['id'])
            self.assertEqual(retained['meta']['title'], 'Plans')
            self.assertEqual(retained['path'], note['path'])
            self.assertEqual(retained['text'], body)
            self.assertTrue((Path(note['path']).parent / asset['path']).exists())
            restarted = Backend(self.base/'runtime')
            restarted.dispatch({'op':'remove-tab', 'key':scope['key']})
            restored = restarted.dispatch({'op':'add-tab', 'name':' plans '})
            self.assertEqual(restored['selectedKey'], scope['key'])
            fresh = restarted.dispatch({'op':'add-tab', 'name':'Ideas'})
            self.assertNotEqual(fresh['selectedKey'], scope['key'])
            self.assertEqual(restarted.store.for_scope(fresh['scopes'][-1])['text'], '')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                restarted.dispatch({'op':'rename-tab', 'key':scope['key'], 'name':'Ideas'})
            restarted.dispatch({'op':'remove-tab', 'key':fresh['selectedKey']})
            with self.assertRaisesRegex(ValueError, 'already exists'):
                restarted.dispatch({'op':'rename-tab', 'key':scope['key'], 'name':'Ideas'})
            with self.assertRaises(ValueError):
                restarted.dispatch({'op':'rename-tab', 'key':'app:editor', 'name':'No'})

    def test_rename_metadata_failure_is_reconciled_on_reopen(self):
        with patch('core.backend.snapshot', return_value=self.source):
            scope = self.backend.dispatch({'op':'add-tab', 'name':'Ideas'})['scopes'][-1]
            note = self.backend.store.for_scope(scope)
            from core.storage import atomic
            def fail(path, data):
                if Path(path).name == 'note.json': raise OSError('Disk write failed')
                return atomic(path, data)
            with patch('core.storage.atomic', side_effect=fail), self.assertRaises(OSError):
                self.backend.dispatch({'op':'rename-tab', 'key':scope['key'], 'name':'Plans'})
            restarted = Backend(self.base/'runtime')
            reopened = restarted.dispatch({'op':'open', 'address':'0xabc'})
            self.assertEqual(reopened['scopes'][-1]['label'], 'Plans')
            self.assertEqual(restarted.store.load(note['meta']['id'])['meta']['title'], 'Plans')

    def test_named_tab_validation_and_literal_names(self):
        with patch('core.backend.snapshot', return_value=self.source):
            for invalid in ('', '   ', 'x'*121, 'line\nbreak', None):
                with self.assertRaises(ValueError): self.backend.dispatch({'op':'add-tab','name':invalid})
            with self.assertRaises(ValueError):
                self.backend.dispatch({'op':'add-tab','name':'Ideas','expected':{'pid':999}})
            for name in ('Project ideas', 'To-do', '/not/a/real/file', 'example.com'):
                result = self.backend.dispatch({'op':'add-tab','name':name})
                self.assertEqual(result['scopes'][-1]['kind'],'named')
                self.assertEqual(result['scopes'][-1]['label'],name)
                self.assertNotIn('locator',result['scopes'][-1])

    def test_resource_tabs_migrate_without_losing_notes_or_images(self):
        legacy = {'key':'url:https://example.com/', 'kind':'page', 'title':'https://example.com/', 'label':'example.com', 'locator':'https://example.com/'}
        note = self.backend.store.for_scope(legacy)
        asset = self.backend.store.import_asset(note['meta']['id'], b'\x89PNG\r\n\x1a\nfixture','png')
        body = 'Keep this thought\n' + asset['markdown']
        self.backend.store.save(note['meta']['id'],body,note['revision'])
        self.backend.tabs_path.write_text(json.dumps({'editor':[legacy],'browser':[legacy]}))
        tabs = self.backend.custom_tabs()
        first = self.backend.store.for_scope(tabs['editor'][0])
        second = self.backend.store.for_scope(tabs['browser'][0])
        self.assertEqual(first['meta']['id'],note['meta']['id'])
        self.assertNotEqual(first['meta']['id'],second['meta']['id'])
        for copied in (first,second):
            self.assertEqual(copied['text'],body)
            self.assertEqual(copied['meta']['scope']['kind'],'named')
            self.assertTrue((Path(copied['path']).parent/asset['path']).exists())
            self.assertNotIn('locator',copied['meta']['scope'])
        self.backend.store.save(first['meta']['id'],'Independent now',first['revision'])
        self.assertEqual(self.backend.store.load(second['meta']['id'])['text'],body)
        restarted = Backend(self.base/'runtime')
        self.assertEqual(restarted.custom_tabs(),tabs)
        self.assertEqual(len(restarted.store.directories()),2)

    def test_tab_migration_retries_after_interrupted_config_write(self):
        legacy = {'key':'file:/one/note.md','kind':'file','title':'note.md','label':'note.md'}
        other = {**legacy,'key':'file:/two/note.md'}
        for scope in (legacy,other):self.backend.store.for_scope(scope)
        original={'editor':[legacy,other]}
        self.backend.tabs_path.write_text(json.dumps(original))
        from core.backend import atomic
        def fail(path,data):
            if path==self.backend.tabs_path:raise OSError('Interrupted tab config write')
            return atomic(path,data)
        with patch('core.backend.atomic',side_effect=fail),self.assertRaises(OSError):self.backend.custom_tabs()
        self.assertEqual(json.loads(self.backend.tabs_path.read_text()),original)
        restarted=Backend(self.base/'runtime')
        tabs=restarted.custom_tabs()['editor']
        self.assertEqual([tab['label'] for tab in tabs],['note.md','note.md (2)'])
        self.assertEqual(len(restarted.store.directories()),2)

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

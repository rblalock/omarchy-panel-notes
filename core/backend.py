import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid
import unicodedata

from .registry import Registry
from .session import snapshot, changed, focus, environment, hypr
from .storage import Store, atomic

PLUGIN_ID = "io.github.rblalock.panel-notes"
PROJECT = Path(__file__).resolve().parent.parent


class Backend:
    def __init__(self, runtime):
        self.runtime = Path(runtime)
        self.settings_path = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "omarchy/shell.json"
        extensions = Path(os.environ.get("PANEL_NOTES_EXTENSIONS", str(Path.home() / ".local/share/panel-notes/extensions")))
        self.registry = Registry([PROJECT / "providers", PROJECT / "content", extensions])
        self.writers = {}
        self.lock = threading.RLock()
        self.recovery = Path(os.environ.get("PANEL_NOTES_RECOVERY", str(Path.home() / ".local/state/panel-notes/recovery")))
        self.settings_cache_path = self.recovery.parent / 'settings.json'
        self.preferences_path = self.recovery.parent / 'preferences.json'
        self.tabs_path = self.recovery.parent / 'custom-tabs.json'
        self.migrated_tabs = None
        try: self.preferences = json.loads(self.preferences_path.read_text())
        except (OSError, ValueError): self.preferences = {}
        self.store = Store(self.settings().get("notesRoot", str(Path.home() / "Documents/Panel Notes")), self.recovery)

    def settings(self):
        settings = {}
        try: settings = json.loads(self.settings_cache_path.read_text())
        except (OSError, ValueError): pass
        try:
            config = json.loads(self.settings_path.read_text())
            inline = next((x for x in config.get("plugins", []) if isinstance(x, dict) and x.get("id") == PLUGIN_ID), {}).copy()
            inline.pop('id', None)
            if inline:
                settings.update(inline)
                atomic(self.settings_cache_path, json.dumps(settings))
        except (OSError, ValueError):
            pass
        settings.pop("id", None)
        if os.environ.get("PANEL_NOTES_ROOT"):
            settings["notesRoot"] = os.environ["PANEL_NOTES_ROOT"]
        return settings

    @staticmethod
    def source_key(source):
        return (source["session"], source["address"], source["pid"])

    def custom_tabs(self):
        with self.lock:
            try: tabs = json.loads(self.tabs_path.read_text())
            except FileNotFoundError: return {}
            converted = {}
            for app, entries in tabs.items():
                converted[app] = []
                used = {tab['key'] for tab in entries if tab['kind'] == 'named'}
                for tab in entries:
                    if tab['kind'] == 'named':
                        converted[app].append(tab); continue
                    name = tab.get('label') or tab['title']
                    suffix = 1
                    while True:
                        label = name if suffix == 1 else name + ' (' + str(suffix) + ')'
                        scope = next(s for s in self.registry.resolve({'app':app}, {'name':label})['scopes'] if s['kind']=='named')
                        if scope['key'] not in used: break
                        suffix += 1
                    used.add(scope['key'])
                    converted[app].append({**scope, 'legacyKey':tab['key']})
            token = (str(self.store.root), json.dumps(converted, sort_keys=True))
            if token != self.migrated_tabs:
                self.store.adopt_named_tabs([tab for entries in converted.values() for tab in entries if tab.get('legacyKey')])
                if converted != tabs:
                    backup = self.tabs_path.with_name('custom-tabs.before-names.json')
                    if not backup.exists(): atomic(backup, json.dumps(tabs, indent=2))
                    atomic(self.tabs_path, json.dumps(converted, indent=2))
                self.migrated_tabs = token
            return converted

    def resolve_tabs(self, source):
        result = self.registry.resolve(source, {})
        self.store.sync_named_tabs(self.custom_tabs().get(source['app'], []))
        for tab in self.custom_tabs().get(source['app'], []):
            # Keep one entry per app-owned note identity.
            result['scopes'] = [scope for scope in result['scopes'] if scope['key'] != tab['key']]
            result['scopes'].append({**tab, 'customTab': True})
        return {'source': source, **result}

    def change_tab(self, request):
        source = snapshot(request.get('address'))
        if any(source.get(k) != v for k, v in request.get('expected', {}).items() if k in ('pid', 'session', 'app')):
            raise ValueError('The source window changed. Reopen notes and try again.')
        with self.lock:
            tabs = self.custom_tabs()
            current = tabs.get(source['app'], [])
            if request['op'] in ('add-tab', 'rename-tab'):
                name = request.get('name', '')
                if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in name):
                    raise ValueError('Enter a name between 1 and 120 characters.')
                name = unicodedata.normalize('NFC', name.strip())
                # Labels can change; note keys must survive renames and removal.
                self.store.sync_named_tabs(current)
                saved = self.store.named_scopes(source['app'])
                known = {tab['key']: tab for tab in [*saved, *current]}
                matching = next((tab for tab in known.values() if tab['title'].casefold() == name.casefold()), None)
                if request['op'] == 'rename-tab':
                    key = request.get('key')
                    tab = next((tab for tab in current if tab['key'] == key), None)
                    if tab is None: raise ValueError('This tab is no longer available.')
                    if matching and matching['key'] != key:
                        raise ValueError('A note with this name already exists in this app. Choose another name.')
                    current = [{**item, 'title':name, 'label':name} if item['key'] == key else item for item in current]
                    selected = key
                else:
                    tab = matching
                    if tab is None:
                        resolved = self.registry.resolve(source, {'name':name})
                        tab = next((scope for scope in resolved['scopes'] if scope['kind'] == 'named'), None)
                        if not tab: raise ValueError('Could not create this note tab.')
                        # An old deterministic key may belong to a renamed note.
                        if tab['key'] in known: tab = {**tab, 'key':'named:' + uuid.uuid4().hex}
                    if not any(item['key'] == tab['key'] for item in current): current = [*current, tab]
                    selected = tab['key']
            else:
                key = request.get('key')
                current = [tab for tab in current if tab['key'] != key]
                selected = None
            updated = {**tabs, source['app']: current}
            atomic(self.tabs_path, json.dumps(updated, indent=2))
        return {**self.resolve_tabs(source), 'selectedKey': selected}

    def dispatch(self, request):
        op = request.get("op")
        if op == "hello":
            return {"settings": {**self.settings(), 'scopeKeys':self.preferences}, "root": str(self.store.root),
                    "content": self.registry.content, "extensionErrors": self.registry.errors,
                    "recoveries": self.store.recoveries()}
        if op in ("add-tab", "rename-tab", "remove-tab"):
            return self.change_tab(request)
        if op == "open":
            try: source = snapshot(request.get("address"))
            except ValueError:
                if not request.get('library'): raise
                monitor = next((m for m in hypr('monitors') if m['focused']), hypr('monitors')[0])
                width, height = monitor['width'], monitor['height']
                if monitor['transform'] % 2: width, height = height, width
                width, height = width / monitor['scale'], height / monitor['scale']
                source = {'address':'', 'app':'Panel Notes', 'monitor':monitor,
                          'at':[monitor['x'] + max(0, (width-800)/2), monitor['y'] + max(0, (height-650)/2)],
                          'size':[min(800, width), min(650, height)]}
                return {'source':source, 'scopes':[], 'errors':[]}
            result = self.resolve_tabs(source)
            if not request.get('address') and self.source_key(snapshot()) != self.source_key(source):
                raise ValueError('Focus changed before notes opened. Invoke again on the intended window.')
            return result
        if op == "observe":
            return {"changed": changed(request["source"])}
        if op == "focus":
            focus(request["source"])
            return {}
        if op == 'preference':
            with self.lock:
                self.preferences[request['app']] = request['key']
                atomic(self.preferences_path, json.dumps(self.preferences))
            return {}
        if op == 'settings-cache':
            settings = request['settings']
            if not isinstance(settings, dict): raise ValueError('Invalid settings')
            atomic(self.settings_cache_path, json.dumps(settings))
            return {}
        if op == "scope":
            return self.writer(self.store.for_scope(request["scope"], request.get("type", "markdown")))
        if op == "load":
            return self.writer(self.store.load(request["noteId"]))
        if op == 'resume':
            result = self.store.save(request['noteId'], request['text'], request['revision'])
            return result if result.get('conflict') else {'note':self.writer(self.store.load(request['noteId']))}
        if op == "save":
            with self.lock:
                writer = self.writers.get(request.get("writerId"))
                if writer is None:
                    return self.store.save(request["noteId"], request["text"], request["revision"], request.get("recoveryId"))
                if writer["noteId"] != request["noteId"] or request["sequence"] != writer["sequence"] + 1:
                    raise ValueError("Out-of-order save refused. Reopen the note before continuing.")
                writer["sequence"] = request["sequence"]
                result = self.store.save(request["noteId"], request["text"], writer["revision"], request["writerId"])
                if not result.get("conflict"):
                    writer["revision"] = result["revision"]
                return result
        if op == "search":
            return self.store.search(request.get("query", ""))
        if op == "recoveries":
            return {"recoveries": self.store.recoveries()}
        if op == "recover":
            recovery = next((x for x in self.store.recoveries() if x["recoveryId"] == request["recoveryId"]), None)
            if recovery is None:
                raise ValueError("Recovery draft not found.")
            try: note = self.store.load(recovery["noteId"])
            except (OSError, ValueError): note = {'meta':{'title':'Recovered note', 'type':'markdown'}, 'path':None}
            scope = {"kind": "recovery", "key": "recovery:" + uuid.uuid4().hex, "title": note["meta"]["title"] + " — recovered draft"}
            recovered = self.store.for_scope(scope, note['meta'].get('type', 'markdown'))
            if note['path']:
                assets = Path(note['path']).parent / 'assets'
                if assets.exists():
                    shutil.copytree(assets, Path(recovered['path']).parent / 'assets')
                    recovered['meta']['assets'] = note['meta'].get('assets', [])
                    atomic(Path(recovered['path']).parent / 'note.json', json.dumps(recovered['meta'], indent=2))
            self.store.save(recovered["meta"]["id"], recovery["text"], recovered["revision"])
            (self.store.recovery / (request["recoveryId"] + ".json")).unlink()
            return self.writer(self.store.load(recovered["meta"]["id"]))
        if op == "external":
            note = self.store.load(request["noteId"])
            command = ["omawrite", note["path"]] if request.get("editor", True) else ["xdg-open", str(Path(note["path"]).parent)]
            subprocess.Popen(command, env=environment(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return {"path": note["path"]}
        if op == "clipboard-image":
            types = subprocess.run(["wl-paste", "--list-types"], env=environment(), capture_output=True, timeout=3, check=True).stdout.decode().splitlines()
            mime = next((x for x in ("image/png", "image/jpeg", "image/webp") if x in types), None)
            if not mime:
                return {"isImage": False}
            result = subprocess.run(["wl-paste", "--no-newline", "--type", mime], env=environment(), capture_output=True, timeout=5, check=True)
            return {"isImage": True, **self.store.import_asset(request["noteId"], result.stdout, {"image/png":"png","image/jpeg":"jpg","image/webp":"webp"}[mime])}
        if op == "prepare-capture":
            self.store.load(request["noteId"])
            return {"path": str(self.runtime / ("capture-" + uuid.uuid4().hex + ".png"))}
        if op == "import-capture":
            path = Path(request["path"])
            if path.parent != self.runtime or not path.name.startswith("capture-") or path.suffix != '.png' or path.is_symlink():
                raise ValueError("Invalid capture path.")
            try:
                if path.stat().st_size > 25 * 1024 * 1024:
                    raise ValueError("Window image exceeds 25 MB.")
                return self.store.import_asset(request["noteId"], path.read_bytes(), "png", request.get("source"))
            finally:
                path.unlink(missing_ok=True)
        if op == "collection":
            destination = request["path"]
            if not Path(destination).expanduser().is_absolute():
                raise ValueError("Choose an absolute folder path.")
            if request.get("move"):
                destination = self.store.migrate(destination)
            self.store = Store(destination, self.recovery)
            return {"root": str(self.store.root), "settings": {**self.settings(), "notesRoot": str(self.store.root)}}
        raise ValueError("Unknown operation: " + str(op))

    def writer(self, note):
        token = uuid.uuid4().hex
        self.writers[token] = {"noteId": note["meta"]["id"], "sequence": 0, "revision": note["revision"]}
        if len(self.writers) > 1024:
            self.writers.pop(next(iter(self.writers)))
        return {**note, "writerId": token}

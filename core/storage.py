import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data if isinstance(data, bytes) else data.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, root, recovery=None):
        self.root = Path(root).expanduser().resolve()
        self.recovery = Path(recovery) if recovery else self.root / "recovery"
        self.recovery.mkdir(parents=True, exist_ok=True, mode=0o700)

    @contextlib.contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / ".store.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def directories(self):
        return sorted((self.root / "notes").glob("*/note.json"))

    def directory(self, note_id):
        if not re.fullmatch(r"[a-f0-9]{32}", note_id):
            raise ValueError("Invalid note identity.")
        for path in self.directories():
            if path.parent.name.endswith("--" + note_id) and not path.parent.is_symlink():
                return path.parent
        raise ValueError("Note not found in this collection.")

    def load(self, note_id):
        directory = self.directory(note_id)
        meta = json.loads((directory / "note.json").read_text())
        if not isinstance(meta, dict) or not isinstance(meta.get('scope'), dict) or not isinstance(meta.get('title'), str) or not isinstance(meta.get('updatedAt'), (int, float)):
            raise ValueError('Malformed note metadata.')
        if meta.get('id') != note_id: raise ValueError('Note metadata identity does not match its folder.')
        body_name = meta.get("body", "notes.md")
        if Path(body_name).name != body_name or (directory / body_name).is_symlink():
            raise ValueError("Unsafe note body path.")
        if (directory / body_name).stat().st_size > 4 * 1024 * 1024:
            raise ValueError('This note exceeds the 4 MB editor limit.')
        body = (directory / body_name).read_text(encoding="utf-8")
        return {"meta": meta, "text": body, "revision": digest(body),
                "path": str(directory / body_name), "baseUrl": directory.as_uri() + "/"}

    def adopt_named_tabs(self, scopes):
        """Retain old note IDs; split formerly shared resources into app-owned notes.

        Each metadata update/clone is atomic and keyed by the destination scope,
        so an interrupted migration can retry without duplicating completed work.
        """
        if not scopes: return
        with self.lock():
            records = []
            for path in self.directories():
                try:
                    meta = json.loads(path.read_text())
                    if isinstance(meta, dict) and isinstance(meta.get('scope'), dict): records.append((path, meta))
                except (OSError, ValueError): continue
            for scope in scopes:
                if any(meta['scope'].get('key') == scope['key'] for _, meta in records): continue
                old = next(((path, meta) for path, meta in records if meta['scope'].get('key') == scope['legacyKey'] or meta.get('legacyScope', {}).get('key') == scope['legacyKey']), None)
                if old is None: continue  # A tab can exist before its note was created.
                path, meta = old
                self.load(meta['id'])  # Validate the source before moving its identity.
                updated = {**meta, 'scope':scope, 'title':scope['title'],
                           'legacyScope':meta.get('legacyScope', meta['scope']),
                           'legacyTitle':meta.get('legacyTitle', meta['title'])}
                if meta['scope'].get('key') == scope['legacyKey']:
                    atomic(path, json.dumps(updated, indent=2))
                    records[records.index(old)] = (path, updated)
                else:
                    # A second app previously shared this note. Give it an independent
                    # copy including relative images; publish only a complete folder.
                    note_id = uuid.uuid4().hex
                    updated['id'] = note_id
                    label = re.sub(r"[^\w-]+", "-", scope['title']).strip('-')[:60] or 'note'
                    destination = self.root / 'notes' / (label + '--' + note_id)
                    with tempfile.TemporaryDirectory(prefix='.named-tab-', dir=self.root/'notes') as temporary:
                        staged = Path(temporary) / 'copy'
                        shutil.copytree(path.parent, staged, symlinks=True)
                        atomic(staged/'note.json', json.dumps(updated, indent=2))
                        staged.rename(destination)
                    records.append((destination/'note.json', updated))

    def named_scopes(self, app):
        return [note['scope'] for note in self.search()['notes']
                if note['scope'].get('kind') == 'named' and note['scope'].get('app') == app]

    def sync_named_tabs(self, scopes):
        """Tab definitions own labels. Reconcile metadata after rename or restart.

        Save tab definitions first: if a metadata write fails, reopening retries it.
        Note IDs, body paths, revisions and assets never change during a rename.
        """
        by_key = {scope['key']: scope for scope in scopes}
        if not by_key: return
        with self.lock():
            for path in self.directories():
                try:
                    meta = json.loads(path.read_text())
                    scope = by_key.get(meta['scope']['key'])
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                if scope and (meta['title'] != scope['title'] or meta['scope'].get('label') != scope.get('label')):
                    self.load(meta['id'])
                    atomic(path, json.dumps({**meta, 'title':scope['title'], 'scope':scope}, indent=2))

    def for_scope(self, scope, content_type="markdown"):
        with self.lock():
            for path in self.directories():
                try:
                    meta = json.loads(path.read_text())
                    if not isinstance(meta, dict): raise ValueError('Malformed note metadata.')
                    matches = meta["scope"]["key"] == scope["key"] and meta.get("type") == content_type
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                # A matching note that cannot be read needs an error, not a new
                # empty note that silently hides the original from its app tab.
                if matches:
                    return self.load(meta["id"])
            note_id = uuid.uuid4().hex
            label = re.sub(r"[^\w-]+", "-", scope["title"]).strip("-")[:60] or "note"
            directory = self.root / "notes" / (label + "--" + note_id)
            meta = {"id": note_id, "version": 1, "type": content_type, "formatVersion": 1,
                    "body": "notes.md" if content_type == "markdown" else "content.txt",
                    "title": scope["title"], "scope": scope, "createdAt": time.time(),
                    "updatedAt": time.time(), "assets": []}
            atomic(directory / meta["body"], "")
            atomic(directory / "note.json", json.dumps(meta, indent=2))
            return self.load(note_id)

    def save(self, note_id, text, revision, recovery_id=None):
        if not isinstance(text, str) or len(text.encode()) > 4 * 1024 * 1024:
            raise ValueError("Notes must be text smaller than 4 MB.")
        recovery_id = recovery_id or uuid.uuid4().hex
        if not re.fullmatch(r"[a-f0-9]{32}", recovery_id):
            raise ValueError("Invalid recovery identity.")
        recovery_path = self.recovery / (recovery_id + ".json")
        atomic(recovery_path, json.dumps({"noteId": note_id, "root": str(self.root),
                                        "text": text, "revision": revision, "at": time.time()}))
        with self.lock():
            note = self.load(note_id)
            if note["revision"] != revision and note["text"] != text:
                return {"conflict": True, "disk": note, "recoveryId": recovery_id,
                        "message": "This note changed in another editor. Your draft is preserved."}
            atomic(note["path"], text)
            meta = note["meta"]
            meta["updatedAt"] = time.time()
            atomic(Path(note["path"]).parent / "note.json", json.dumps(meta, indent=2))
            recovery_path.unlink(missing_ok=True)
            return {"revision": digest(text), "savedAt": meta["updatedAt"]}

    def search(self, query=""):
        found, errors = [], []
        for path in self.directories():
            try:
                meta = json.loads(path.read_text())
                if not isinstance(meta, dict): raise ValueError('Malformed note metadata.')
                note = self.load(meta["id"])
                if query.casefold() in (meta["title"] + "\n" + note["text"]).casefold():
                    found.append({**meta, "excerpt": note["text"][:180]})
            except (OSError, ValueError, KeyError) as error:
                errors.append({"path": str(path), "error": str(error)})
        return {"notes": sorted(found, key=lambda n: n["updatedAt"], reverse=True), "errors": errors}

    def import_asset(self, note_id, data, extension, source=None):
        if extension not in ("png", "jpg", "webp") or len(data) > 25 * 1024 * 1024:
            raise ValueError("Use a PNG, JPEG or WebP image smaller than 25 MB.")
        valid = (extension == "png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or \
                (extension == "jpg" and data.startswith(b"\xff\xd8\xff")) or \
                (extension == "webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        if not valid:
            raise ValueError("The clipboard did not contain a supported image.")
        with self.lock():
            note = self.load(note_id)
            name = uuid.uuid4().hex + "." + extension
            relative = "assets/" + name
            if (Path(note['path']).parent / 'assets').is_symlink():
                raise ValueError('The note assets folder must not be a symbolic link.')
            atomic(Path(note["path"]).parent / relative, data)
            note["meta"].setdefault("assets", []).append({"path": relative, "at": time.time(), "source": source})
            atomic(Path(note["path"]).parent / "note.json", json.dumps(note["meta"], indent=2))
        return {"markdown": "![" + ("Source snapshot" if source else "Image") + "](" + relative + ")", "path": relative}

    def recoveries(self):
        out = []
        for path in self.recovery.glob("*.json"):
            try:
                draft = json.loads(path.read_text())
                if draft["root"] == str(self.root):
                    out.append({**draft, "recoveryId": path.stem})
            except (OSError, ValueError, KeyError):
                continue
        return out

    def migrate(self, destination):
        destination = Path(destination).expanduser().resolve()
        if destination == self.root or self.root in destination.parents or destination in self.root.parents:
            raise ValueError("Choose a separate folder outside the current notes folder.")
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("Choose an empty folder for moving the collection.")
        with self.lock():
            destination.mkdir(parents=True, exist_ok=True)
            for name in ("notes", "recovery"):
                source = self.root / name
                if source.exists():
                    if source.is_symlink() or any(p.is_symlink() for p in source.rglob('*')):
                        raise ValueError('Resolve symbolic links inside the collection before moving it.')
                    shutil.copytree(source, destination / name)
            for target in destination.rglob("*"):
                if target.is_file():
                    source = self.root / target.relative_to(destination)
                    if not source.is_file() or source.read_bytes() != target.read_bytes():
                        raise OSError("Collection verification failed; the original remains unchanged.")
            # Keep a recovery copy associated with the new collection, retaining originals.
            for draft in self.recoveries():
                new = {k:v for k,v in draft.items() if k != 'recoveryId'}
                new['root'] = str(destination)
                atomic(self.recovery / (uuid.uuid4().hex + '.json'), json.dumps(new))
        return str(destination)

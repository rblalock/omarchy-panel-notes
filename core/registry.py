import json
from pathlib import Path
import re
import subprocess
import sys


class Registry:
    """Explicit local extension packages. Executable providers are trusted code."""
    def __init__(self, roots):
        self.providers = []
        self.content = {}
        self.errors = []
        seen = set()
        for root in roots:
            for path in sorted(Path(root).glob("*/extension.json")):
                try:
                    manifest = json.loads(path.read_text())
                    identity = manifest["id"]
                    if manifest.get("apiVersion") != 1 or not re.fullmatch(r"[a-z0-9][a-z0-9.-]+", identity):
                        raise ValueError("Unsupported extension identity/version")
                    if identity in seen:
                        raise ValueError("Duplicate extension ID")
                    seen.add(identity)
                    if manifest["kind"] == "context":
                        entry = path.parent / manifest["entry"]
                        if not entry.resolve().is_relative_to(path.parent.resolve()) or not entry.is_file():
                            raise ValueError("Invalid provider entry")
                        self.providers.append((identity, entry.resolve()))
                    elif manifest["kind"] == "content":
                        content_type = manifest["type"]
                        if content_type in self.content:
                            raise ValueError("Duplicate content type")
                        entry = (path.parent / manifest["editor"]).resolve()
                        if not entry.is_relative_to(path.parent.resolve()) or not entry.is_file():
                            raise ValueError("Invalid editor entry")
                        self.content[content_type] = {**manifest, "editorUrl": entry.as_uri()}
                    else:
                        raise ValueError("Unknown extension kind")
                except Exception as error:
                    self.errors.append({"path": str(path), "error": str(error)})

    def resolve(self, source, context):
        scopes, errors = [], []
        for identity, entry in self.providers:
            try:
                run = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('provider_worker.py')), str(entry)],
                                     input=json.dumps({'source': source, 'context': context}), text=True,
                                     capture_output=True, timeout=.5, check=True)
                if len(run.stdout) > 131072: raise ValueError('Provider response exceeds 128 KB')
                result = json.loads(run.stdout)
                if not isinstance(result, list) or len(result) > 12:
                    raise ValueError("Provider must return at most 12 scopes")
                for scope in result:
                    if not all(isinstance(scope.get(k), str) and 0 < len(scope[k]) <= 8192 for k in ("key", "kind", "title")):
                        raise ValueError("Invalid scope")
                    if scope["key"] not in [s["key"] for s in scopes]:
                        scopes.append({**scope, "provider": identity})
            except Exception as error:
                errors.append({"provider": identity, "error": str(error)})
        return {"scopes": scopes, "errors": errors}

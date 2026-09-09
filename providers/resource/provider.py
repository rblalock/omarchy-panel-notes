from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def resolve(source, context):
    scopes = []
    if context.get("url"):
        url = urlsplit(context["url"])
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            return []
        host = url.netloc.lower()
        canonical = urlunsplit((url.scheme.lower(), host, url.path or "/", url.query, url.fragment))
        partition = context.get("partition", "")
        prefix = (partition + ":") if partition else ""
        scopes += [{"kind": "site", "key": "site:" + prefix + url.scheme + "://" + host,
                    "title": host, "locator": url.scheme + "://" + host},
                   {"kind": "page", "key": "url:" + prefix + canonical, "title": context.get("title") or canonical,
                    "label": "Current page", "locator": canonical}]
    if context.get("file"):
        path = Path(context["file"]).expanduser()
        if not path.is_absolute():
            return scopes
        path = path.resolve()
        if path.is_file():
            scopes.append({"kind": "file", "key": "file:" + str(path), "title": path.name,
                           "label": path.name, "locator": path.as_uri()})
    if context.get("cwd"):
        cwd = context["cwd"]
        host = context.get("host", "local")
        if cwd.startswith("/"):
            path = str(Path(cwd).resolve()) if host == "local" else cwd
            scopes.append({"kind": "directory", "key": "directory:" + host + ":" + path,
                           "title": path, "label": Path(path).name or "/", "host": host,
                           "locator": Path(path).as_uri() if host == "local" else ""})
    return scopes

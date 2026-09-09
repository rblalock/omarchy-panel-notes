# Panel Notes extension foundations (experimental)


Current product scope is App notes and named tabs under each app. No app-side
context bridge ships. The previous `bind`/`invalidate` protocol and shell, browser,
Obsidian and LibreOffice integrations have been removed. Future integration
contracts require a design review before implementation; the registry below is
an internal extension boundary, not a promise of automatic context support.

Panel Notes extensions are distinct from Omarchy plugins. Omarchy loads one
panel; the panel's registry discovers explicitly installed packages at
`~/.local/share/panel-notes/extensions/<package>/extension.json`, alongside
bundled `providers/` and `content/`. After changing packages, run `panel-notes shutdown`, then hide/reopen the panel
so its content registry reconnects to the restarted service. Executable
Python and QML extensions are trusted code, **not sandboxed**.

## Context provider

```json
{"apiVersion":1,"id":"your.project.objects","kind":"context","entry":"provider.py","capabilities":["object"]}
```

`provider.py` exports `resolve(source, context) -> list[scope]`. The request
contains the temporary source association (`session`, `address`, `pid`, app,
title, geometry) and an empty context on normal opening. Named tab creation passes the
explicitly entered name as context. It must return within 500 ms.
External providers run in a separate short-lived Python process; timed-out or
malformed providers report an error while other providers continue. The two
shipped App/named-tab resolvers are loaded once and run in-process, selected by
their exact bundled paths. External package IDs cannot opt into this fast path. Providers
must not use window addresses/PIDs/titles as durable resource keys.

```python
def resolve(source, context):
    object_id = context.get("objectId")
    if not object_id:
        return []  # unavailable or ambiguous; do not guess
    return [{"kind":"object", "key":"your.project:object:" + object_id,
             "title":"Object " + object_id, "label":"Current object",
             "locator":"https://example.org/objects/" + object_id}]
```

Return broad-to-specific scopes, at most 12 per provider. `kind`, `key`, and
`title` are required nonempty strings, at most 8192 characters each. Keys are
namespaced and globally deduplicated; same key/type opens the same note even in
another app. `label` is optional short UI text; `locator` is optional. The current UI creates app-owned named notes and has no resource-opening action.

The host resolves App notes on opening and adds persisted custom tabs. Generation
tokens discard late open replies. No app-side push, polling bridge, lease or
active-document tracking contract is implemented. See the integration roadmap
in [plan.md](plan.md#integration-roadmap--design-before-implementation).

## Content module

```json
{"apiVersion":1,"id":"your.project.plain","kind":"content","type":"your.project.plain","formatVersion":1,"editor":"Editor.qml","capabilities":{"preview":false,"images":false,"omawrite":false}}
```

`editor` must resolve inside the package. Types must be unique. The host gives
the QML editor these properties:

| Property | Meaning |
| --- | --- |
| `text: string` | Lossless serialized body, maximum 4 MB; it need not be Markdown |
| `baseUrl: string` | URL of this note directory for relative assets |
| `preview: bool` | Requested read/preview mode; module may render plain text |
| `readOnly: bool` | External editor owns this document until reload |

The required signal `edited(string)` sends the complete serialized body. Optional
`pasteRequested()` asks for clipboard import; `closeRequested()` dismisses notes.
The required method is `focusEditor()`. Modules requesting clipboard handling
provide `pasteText()`; modules advertising `images` also provide `insertAsset(asset)`
and choose their own serialization. Asset records include a relative `path` and
a Markdown convenience string. The host does not insert Markdown into other
content types. `preview`, `images`, and `omawrite` capabilities opt into the
corresponding controls; they are absent for the alternate plain-text fixture.

The host assigns note IDs, compares revisions, serializes saves, and reports
Saved only after durable writes. Metadata includes `type`, `formatVersion`,
`body`, `scope`, timestamps, and assets. Unknown fields survive saves. Markdown
uses `notes.md`; other serialized types use `content.txt`. Losing a content
extension displays an unavailable view and preserves its files. The host does
not convert unknown formats to Markdown. Open with `scope` RPC and a `type`
field; the first-release user interface only creates Markdown notes.

`examples/object-provider` and `examples/plain-content` are installable fixtures.
Registry tests load an external provider, and native checks open/edit/save the
alternate QML editor without modifying the panel's type routing.

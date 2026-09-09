# Panel Notes

Markdown notes organized under each app, with named tabs for your thoughts.
An Omarchy shell plugin with a window-sized frosted surface. Notes stay visible
when you use an adjacent app; moving or resizing their source hides the surface.

## Try it

```sh
cd ~/code/omarchy-panel-notes
./scripts/install
./scripts/bind-shortcut
```

Focus any application and press **Super+Alt+N**. Type a note; `Saved` means its
Markdown has reached disk. Press Escape to return to the source. The shortcut
toggles focused notes or opens notes for the newly focused application.

Commands are also available:

```sh
panel-notes toggle
panel-notes library
panel-notes hide
```

The installer refuses to replace an occupied shortcut. It stages and validates this checkout, then installs it
to `~/.config/omarchy/plugins/io.github.rblalock.panel-notes`, enables it in the
existing Omarchy shell, and links `~/.local/bin/panel-notes`. Repeat the install
command for local updates. Previous installed copies are retained under
`~/.local/state/panel-notes/plugin-backups`. This is local development delivery;
the checkout has no public marketplace release or remote update source.

## Everyday use

- **App** provides one note per app. They belong to the app, across restarts.
- With context available, tabs expose **Site / Current page**, **File / Vault**,
  or **Directory** notes. Most-specific context opens initially.
- The editor and preview use larger 20px type in a centered writing column,
  with a wider 960px maximum column and smaller margins on narrow windows.
  Preview selections, scrollbars, and subtle image outlines follow the current theme.
- **Preview** renders common Markdown, tables, task lists, fenced code, and
  imported images. Editing preserves your original source. Ctrl+B / Ctrl+I
  surround a selection; normal undo, selection, and keyboard editing remain native.
- **Ctrl+V** imports a clipboard image or pastes ordinary text. **Snapshot**
  (**Ctrl+Shift+S**) captures the source window as it looks now and inserts its
  image into the note. Preview fits images to the writing column.
- **Open in Omawrite** opens the same Markdown file and pauses panel editing.
  **Reload note** brings its external changes back. Conflicting drafts remain
  available under **All notes → Recover unsaved draft**. If the service disconnects,
  text stays in the editor; **Retry save** reconnects and checks for external conflicts.
- **All notes** searches saved titles and text even after their sources close.
- **Settings** chooses the notes folder. **Move collection**
  copies and verifies into an empty folder, retaining the original. **Use this
  folder** switches collections without deleting either one.

Notes default to `~/Documents/Panel Notes/notes/<name>--<id>/notes.md`, with
`note.json` and relative `assets/` beside them. Recovery lives independently in
`~/.local/state/panel-notes/recovery`, including when the selected disk fails.
Settings belong to this plugin's entry in `~/.config/omarchy/shell.json`. A
recovery copy at `~/.local/state/panel-notes/settings.json` retains the chosen
folder across Omarchy disable/re-enable; `preferences.json` remembers scope tabs.

## Keyboard shortcuts

Press **F1** in the panel for the full guide; hover an action to see its shortcut.
Shortcuts apply only while the notes panel has keyboard focus.

| Action | Shortcut |
|---|---|
| Open / toggle panel | Super+Alt+N |
| Close and return to source, from any view | Escape |
| Notes / focus editor | Ctrl+E |
| Search all notes | Ctrl+Shift+F |
| Settings / shortcut guide | Ctrl+, / F1 |
| Select scope | Alt+1…9 |
| Next / previous scope | Ctrl+Tab / Ctrl+Shift+Tab |
| Preview / edit | Ctrl+Shift+P |
| Add a named note tab | Ctrl+T |
| Remove selected custom tab (keep notes) | Ctrl+Shift+Delete |
| Snapshot current source window | Ctrl+Shift+S |
| Omawrite / reload external edits | Ctrl+O |
| Retry saving | Ctrl+S (also Ctrl+R when blocked) |
| Bold / italic / paste | Ctrl+B / Ctrl+I / Ctrl+V |
| Navigate controls / activate | Tab, Shift+Tab / Space, Enter |

Library: type to search; Down then arrow keys select a result, Enter opens it.
Alt+1…9 recovers the corresponding recovery draft.
Settings: Alt+M moves the collection; Alt+U switches folder. Normal edits autosave.

## Named tabs

Click **+** beside App (Ctrl+T), enter a name such as **Ideas** or **Research**, and
press Enter. Each tab contains one note under that app. Names are plain text,
not URLs or filesystem paths. Tabs persist across windows and restarts.

The same name in different apps creates separate notes. Adding the same name
again in one app selects its existing note (ignoring case and surrounding spaces).
Select a tab and click **Remove tab** (Ctrl+Shift+Delete) to remove it from the app;
its notes remain in **All notes**. Adding that name again restores them.

Tab associations live in `~/.local/state/panel-notes/custom-tabs.json`; the note
files stay in the configured collection. This is app-based organization in the
panel, not a new hierarchy of operating-system folders.

Old custom resource tabs are converted to named tabs with their content/images
preserved. Previously shared resource notes become independent copies per app.
A backup of the old tab configuration is kept as `custom-tabs.before-names.json`.

## Current scope and roadmap

Panel Notes currently provides one default note per app plus named note tabs. It does not detect active tabs, terminal directories, editor
files, browser pages or Slack channels. Changing the source app's internal tab
does not change your notes.

Shell hooks, Obsidian plugins, LibreOffice bridges and automatic file-binding
commands are not included. Future integrations must first have an agreed design,
then ship individually after native testing. The detailed review checklist is in
[the integration roadmap](docs/plan.md#integration-roadmap--design-before-implementation).
**Open in Omawrite** remains a normal action to edit the saved Markdown file.

## Extensions and limits

Providers and content modules share a versioned local registry, including the
bundled App/named-tab providers and Markdown editor. See [docs/extensions.md](docs/extensions.md)
and `examples/`. Future content can be added without making the host a Markdown
parser. This release does not embed browsers, drawing canvases, video, or agents.

The panel is a Wayland layer surface. Floating applications can pass underneath
it; it does not inherit their stacking order. A source move, resize, fullscreen,
workspace, close, or monitor change hides it, usually within the 180 ms geometry
check interval. No original windows are transformed or retiled to simulate a flip.
The notes service warms up when the plugin loads, and the built-in App/named-tab
lookups run without launching extra processes.
Opening and explicit dismissal use a 200 ms fade with 1% scale movement.
Dismissal releases keyboard and pointer input immediately while the exit finishes.
Source geometry/lifecycle changes still hide it immediately. Reduced motion uses
a short fade without scaling and an opaque background.

Notes are limited to 4 MB, imported PNG/JPEG/WebP images to 25 MB. Preview does
not automatically load remote images or execute HTML. Math, Mermaid, Obsidian
wikilink embeds, and syntax coloring are not supported. The packaged KDE
highlighter was evaluated as a possible optional dependency; the initial editor
keeps source editing dependency-free and delegates richer editing to Omawrite.
Unacknowledged keystrokes at process/power failure are not guaranteed; confirmed
saves and independently preserved recovery drafts are covered by the checks.

## Check and remove

Runtime dependencies: Omarchy 4 shell plugin APIs, Quickshell 0.3.1, Hyprland's
Lua dispatch API, Python 3, `wl-clipboard`, and optional Omawrite. This machine's
tested package versions and evidence are in [docs/verification.md](docs/verification.md).
Native checks temporarily use disposable workspaces and restore focus. They
need `wtype`, `grim`, and access to `/dev/uinput`. Core checks also use Node
for the Markdown formatter.

```sh
./scripts/check
./scripts/check-native
./scripts/check-tabs
./scripts/check-presentation
./scripts/check-motion
./scripts/check-opening
./scripts/check-installed-ui
./scripts/remove
```

Removal retains your notes, custom tab associations and recovery drafts.
The development plan and completion tracker are in [docs/plan.md](docs/plan.md).

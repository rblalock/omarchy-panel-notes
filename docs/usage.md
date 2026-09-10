# Using Panel Notes

## Tabs

Click **+** or press **Ctrl+T**, enter a name, and press Enter. Each named tab
contains one note under that app. The same name in two apps gives you separate notes.

Right-click a named tab, or select it and press **F2**, to rename it. The note,
images, and file location stay the same. Names must be unique within an app,
including notes retained after removing a tab. Matching ignores case and surrounding
spaces. The default App tab cannot be renamed or removed.

**Remove tab** hides the selected tab; its note remains searchable in **All notes**.
Add its current name again to bring it back.

## Keyboard shortcuts


Hover buttons for shortcuts; **F1** opens the full guide.

| Action | Shortcut |
|---|---|
| Open / toggle notes (optional binding) | Super+Alt+E |
| Close and return to source | Escape |
| Add / rename tab | Ctrl+T / F2 |
| Remove selected named tab, keep note | Ctrl+Shift+Delete |
| Select tab / next / previous | Alt+1…9 / Ctrl+Tab / Ctrl+Shift+Tab |
| Focus editor / search all notes | Ctrl+E / Ctrl+Shift+F |
| Preview / edit | Ctrl+Shift+P |
| Snapshot source window | Ctrl+Shift+S |
| Open in Omawrite / reload external edits | Ctrl+O |
| Settings / help | Ctrl+, / F1 |
| Bold / italic / paste text or image | Ctrl+B / Ctrl+I / Ctrl+V |
| Retry saving after an error | Ctrl+S |

In Add/Rename, Enter saves the name and Escape cancels. Normal note edits autosave.

## Storage and recovery


Default collection: **`~/Documents/Panel Notes`**. Choose another in Settings.
Each note has its own folder:

```text
notes/<original-name>--<id>/
  notes.md
  note.json
  assets/
```

Tabs organize notes under apps in the UI; the disk layout is a flat collection of
note folders. Renaming keeps folder paths stable. Back up the whole collection,
including metadata and images, plus `~/.local/state/panel-notes` to retain tab
organization and recovery drafts. Tab definitions are global across collections;
each collection contains its own note content.

**Saved** means the Markdown has reached disk. On external-edit conflicts, the
panel preserves a recovery draft instead of overwriting the other edit. When a
save fails, keep the panel open and use **Retry save** or **All notes** recovery.
**Open in Omawrite** pauses panel editing; **Reload note** reads the external edit.

Settings offers **Move collection** (copy and verify into an empty folder,
retaining the original) and **Use this folder** (switch without deleting files).
Recovery drafts and tab preferences live in `~/.local/state/panel-notes`.
Plugin settings use its entry in `~/.config/omarchy/shell.json`, with a recovery
copy in that state directory. Removal keeps all notes and state.

## Preview and window behavior

Preview supports common Markdown, quotes, code blocks, tables and imported images.
It does not fetch remote images or execute HTML. Math, Mermaid, syntax coloring,
and Obsidian embeds are not supported. Notes are limited to 4 MB; imported
PNG/JPEG/WebP images to 25 MB.

Moving, resizing, closing, or changing the workspace/monitor/fullscreen state of
the source hides the panel. Overlapping floating windows can pass underneath it.

## Troubleshooting

For a dependency and runtime report:

```sh
~/.config/omarchy/plugins/rblalock.panel-notes/panel-notes doctor
```

If installation reports `omarchy-shell is not responding`, wait a few seconds.
If the folder was added but enabling did not finish, run
`omarchy plugin enable rblalock.panel-notes`. If controls or commands remain
missing, run `omarchy restart shell`.

Report issues with the doctor output and steps to reproduce at
[GitHub Issues](https://github.com/rblalock/omarchy-panel-notes/issues).
For installations using an older plugin ID, see [upgrading](upgrading.md).

# Panel Notes: product and implementation plan

> Current scope (September 9, latest review): one note per app plus custom URL,
> file and folder tabs. All bundled automatic app integrations and setup/bridge
> commands have been removed. This supersedes the integration milestones and
> earlier setup instructions recorded below. Future integration work requires
> an agreed approach before implementation; see the roadmap at the end.


Status: first Markdown release implemented, verified, and installed locally.
Updated: 2026-09-09.
Working directory: `/home/rblalock/code/omarchy-panel-notes`.
Working plugin ID: `io.github.rblalock.panel-notes`.

Inspiration: [Flip](https://flip.pylondev.com/) and the supplied window-notes discussion.

This is the source of truth for the first working release. Check off work only
with evidence; record limitations alongside the relevant milestone. Future
content ideas below are extension requirements, not additional applications to
build in this release. A source check is not proof of a working desktop path.

## 1. Product

Leave thoughts alongside the thing they concern, without leaving the current
workspace. Invoke a shortcut over an application to reveal a native notes panel
over that window. Switch between app notes and the more specific contexts an
integration can identify. Notes survive the source window and remain searchable.

The first release provides Markdown notes, formatted preview, pasted images,
pasted images, local storage, and an Open in Omawrite handoff.
It is a standalone Omarchy plugin; it does not depend on Fluid.

### Agreed requirements

- The surface uses a subtle frost/scale/fade transition, not a card flip.
- The original application remains in its tile; the panel reserves no layout space.
- Clicking a neighboring application keeps notes visible and gives that app
  input immediately. Focus changes never rebind the note.
- Moving or resizing the source hides notes instead of tracking an animation.
- Source closure, loss of its visible workspace, fullscreen transitions and
  monitor changes hide the panel and retain writing.
- Notes are local ordinary files in a user-selectable global folder. The plugin
  manages note folders, metadata, attachments and recovery.
- App/site/page/file/directory are separate note scopes, expressed as tabs.
- Providers expose context and deep links; content modules provide editors and
  formats. Bundled implementations use the same contracts as installed extensions.
- Only Markdown content ships initially. Video, drawing canvases, interactive
  objects and agent features must fit later without changing context identity.

### Initial defaults

These are implementation defaults, not additional user requirements:

- One visible panel. Invoking on another source switches the panel to it.
- Escape closes only when notes have keyboard focus; unrelated apps keep Escape.
- Invoking while notes have focus closes them and returns to their source.
- Invoking on the same source/context toggles; invoking after that source has
  changed resource opens the new context. Capture the target before taking focus.
- Select the most specific known scope initially, then remember scope preference.
- Resource notes are shared across apps when they identify the same qualified
  resource. Browser profiles partition URL identity; App notes are app-specific.
- Default storage: `~/Documents/Panel Notes`. No remote sync service.
- The global shortcut is selected against existing bindings during setup; never
  overwrite a user's occupied binding silently.

## 2. Context and ownership

| Source | Available scopes | Acquisition approach |
| --- | --- | --- |
| Any ordinary app | App | Hyprland app identity; explicit manual association when useful |
| Browser | App; manual Site / Page | Automatic detection deferred; future third-party context plugin |
| File editor | App / File | App bridge or explicit file-aware launch/bind command |
| Obsidian | App / Vault / File | App plugin reports the current file and vault |
| LibreOffice | App / File | UNO bridge reports the focused document URL |
| Terminal | App / Directory; optional Project | Shell/terminal adapter reports host and current directory |

Unknown context is a normal result. Keep App notes usable when an adapter is
absent, unavailable, ambiguous or unsupported. Do not infer a document from its
title or a URL from clipboard manipulation. Show deeper tabs only with reliable
metadata. Manual attachment is a real fallback, clearly distinct from discovery.

A resource key is independent of a live Hyprland address or stableId. Both window
references and provider requests are session-scoped. Late replies must carry a
request generation/source identity and cannot overwrite a newer selection.

Site grouping uses meaningful host/domain boundaries, not a bare TLD. Preserve
subdomains and URL query/fragment semantics unless an explicit provider rule
knows they are irrelevant. Keep browser profile/tenant identity available where
needed to avoid mixing unrelated resources. A terminal directory includes host
identity; a local path and the same path over SSH are not equivalent.

File identity starts with a canonical absolute local path (or qualified remote
resource), with explicit handling for rename, Save As, symlinks and missing files.
Unsaved documents must not share a fake permanent path. Obsidian must distinguish
the active file view from a remembered file behind a non-file view.

While notes are open, the resource is latched. Browser navigation or app context
updates may mark the source as changed, but never silently switch the destination
of typed text. Switching scopes flushes the old draft before displaying another.

## 3. Panel behavior and appearance

| Event | Required behavior |
| --- | --- |
| Invoke over a source | Resolve/latch source; show its scope tabs; focus editor |
| Click/type in adjacent app | Keep panel visible and bound; release keyboard focus; deliver first click |
| Click back into notes | Resume editing the same note |
| Invoke over another source | Save old draft; switch to new source and context |
| Move/resize source | Hide promptly; preserve draft; do not restore focus unexpectedly |
| Source workspace becomes invisible, source closes, monitor layout changes | Hide; invalidate live association as appropriate; preserve content |
| Explicit close/Escape in notes | Save; hide; restore source focus only if still valid |
| Provider disconnect/context change | Preserve current note; report unavailable/changed context without rebinding |
| Save failure | Retain recovery draft, show actionable failure; never claim Saved |

Use a custom Quickshell `PanelWindow` with its input region restricted to the
visible panel and ordinary OnDemand keyboard behavior. Native testing proved that mapping the
surface grants opening focus without an exclusive grab. The stock `KeyboardPanel`/`PopupCard` outside-click dismissal is unsuitable.
Do not install fullscreen click-catching surfaces or an exclusive focus grab.
Do not use the stock navigation catcher over the editor: ordinary letters,
arrows, Space, Tab and Return must retain writing behavior.

Geometry change detection is a first milestone: IPC `movewindow` is a workspace
event, not continuous pixel movement. Compare source bounds with bounded polling
only while visible, combined with relevant lifecycle events. Hidden panels must
not keep capturing frames or polling at an animation frame rate. Fractional
scaling, negative monitor coordinates, rotation and fullscreen need real proof.

Layer surfaces do not inherit normal application stacking. Test overlapping
floating windows explicitly and document the behavior; do not claim a fully
compositor-owned second side. Keep the first implementation window-sized.

Motion target: roughly 180–220 ms, eased opacity and ~0.99 to 1.0 scale, with
theme-colored frost. Blur the background/source, not the writing. Respect reduced
motion and offer a simple fade. Use Omarchy `Color`/`Style` tokens and verify both
light and dark appearance. Capture failure must fall back to an opaque themed
surface without preventing writing.

Snapshot is an explicit user action: capture a fresh frame of the source window
at invocation, save it as a relative image asset, and insert it into the note.
Ctrl+Shift+S invokes the same action. Preview scales images to the writing column.
Temporary background frost images are separate and are never inserted implicitly.

## 4. Architecture and extension contracts

Keep these three responsibilities separate:

1. **Panel host:** Omarchy lifecycle, source targeting, visibility/focus, scope
   navigation, notes collection, settings and mediated storage/assets.
2. **Context providers:** identify supported sources; return available scopes,
   durable resource keys, human labels and optional declared open/reveal actions.
3. **Content types:** load/edit/preview a typed document and describe its format
   version and assets. The host never assumes every content body is Markdown.

Use a small versioned extension manifest and explicit registry. This registry is
owned by Panel Notes; it is not an invented addition to Omarchy's manifest schema.
Bundled providers and `markdown` register through the same mechanism as a user
extension. Document an example third-party provider and prove registration needs
no host source change. A test-only alternate content type should prove the host
can preserve/open an unfamiliar kind without Markdown-specific routing.

Context contract requirements:

- Namespaced provider ID and contract version; advertised capabilities.
- Request: source window/session identity and request generation.
- Response: supported/unavailable/ambiguous state and ordered scopes, each with
  kind, canonical resource key, title, optional locator and optional action.
- Explicit change/invalidation behavior and deadlines; malformed/stale results
  must not corrupt the active note or prevent fallback App notes.
- Optional deep-link actions are deliberate user actions. Provider payloads are
  structured data, not shell command fragments assembled from titles or URLs.
- App integrations may push context over a local bridge; the host validates
  source association instead of assuming a browser window ID is a Hyprland ID.

Content contract requirements:

- Namespaced type, format version, editor/preview entry and save/load interface.
- Host-assigned note ID/storage location and asset references.
- Dirty/saved/error state and external-change handling.
- Unsupported content remains on disk with an unavailable-type view; removing
  an extension never deletes its documents.

Installed executable extensions are trusted local code, as Omarchy plugins are.
Do not imply a sandbox. Keep external adapter messages bounded and validate
paths/IDs. Never fetch or execute code suggested by a note or provider payload.
An extensible foundation does not commit us to building a marketplace, an agent
runtime, a browser editor engine, or arbitrary window embedding in this release.

## 5. Storage and Markdown

Proposed on-disk shape:

```text
<selected root>/
  notes/<readable-name>--<stable-note-id>/
    note.json       # identity, scope, type/version, revision, attachment metadata
    notes.md        # Markdown-owned body
    assets/         # pasted images, referenced relatively
```

Recovery drafts live independently under `~/.local/state/panel-notes/recovery`,
so a failed selected volume does not take recovery with it.

Notes and identity metadata are authoritative; any search index is rebuildable.
Metadata must preserve unknown fields/content versions. Titles can change
without changing identity. Use atomic replacement and per-note revisions;
atomic writes alone do not resolve concurrent external edits.

Autosave must acknowledge successful durable writes, retain failures in recovery,
and order writes so a late older save cannot replace newer content. Ordinary
hide, panel teardown, plugin reload, disable/removal and process exit are separate
cases. `keepLoaded` and destruction callbacks are not a durability guarantee.
Track the difference between an unsaved in-flight keystroke and confirmed saved
content; do not promise zero-loss power-failure behavior without evidence.

Store settings on this plugin's inline `plugins[]` entry in Omarchy `shell.json`.
Keep note bodies out of shell configuration and outside the installed plugin
directory. Omarchy removes inline settings on disable: retain a recovery copy
of own settings in `~/.local/state/panel-notes/settings.json`. Remembered scope
choices use `preferences.json` there so choosing a tab does not trigger a shell
configuration reload. Verify a scoped settings read/write path; the current standalone
loader does not inject a `pluginSettings` object. Changing storage location must
either migrate and verify the existing collection or explicitly select another
collection. Never make old notes appear deleted because a path changed.

Markdown implementation:

- Native plain-text editing; preserve original Markdown source.
- Qt Markdown preview for common formatting, tables, task lists, code, links and
  local images. State actual supported syntax; math, Mermaid and Obsidian embeds
  are not promised.
- Evaluate the packaged KDE QML highlighter before maintaining custom parsing.
  Missing optional highlighting must not disable editing.
- Import clipboard images into `assets/` and insert relative references; ensure
  preview resolves against the note directory. Note rendering must not execute
  embedded HTML/scripts or automatically fetch remote images.
- Open in Omawrite flushes the latest draft, opens the exact file, and releases
  panel editing. Reload external changes on return. If both versions changed,
  retain both and offer resolution instead of overwriting either.
- Search/recent notes work after source windows close. Reveal/open source only
  when its provider offers a meaningful target; unavailable sources do not
  prevent reading or editing their notes.

## 6. Omarchy integration: verified contract and planned use

Reviewed the [development guide](https://plugins.omarchy.org/develop.html) and
its [shell reference](https://github.com/omacom/omarchy/blob/quattro/shell/README.md),
then inspected the installed shell. The guide's clock is a bar widget; our entry
is a standalone panel. It runs in the existing shell, not another resident
Quickshell process. Planned manifest fields:

```json
{
  "schemaVersion": 1,
  "id": "io.github.rblalock.panel-notes",
  "name": "Panel Notes",
  "version": "0.1.0",
  "author": "Rick Blalock",
  "license": "MIT",
  "description": "Notes attached to apps, pages, files and directories.",
  "kinds": ["panel"],
  "keepLoaded": true,
  "entryPoints": { "panel": "Panel.qml" }
}
```

The entry exposes `opened`, `open(payloadJson)` and idempotent `close()`; payloads
arrive as strings. Use the host's summon/hide routes. The context-aware shortcut
must distinguish a new source from a toggle; the generic shell toggle alone
cannot express that distinction. Do not recursively call host hide from close.

`keepLoaded` retains the panel on ordinary hide, but panel delegates are removed
on rescan/reload. Only retained services have different reload semantics.
`shell.updateEntryInline` is available for own settings and replaces the inline
entry settings; preserve unrelated own settings during updates.

The plugin folder must have a root manifest, matching relative entry points,
and a non-reserved namespaced ID; validation rejects symlinks. Develop in this
directory and copy/package into user configuration. Do not edit packaged
`/usr/share/omarchy` files. Shell/app adapters require explicit documented setup. Browser detection is deferred.

Local package baseline on 2026-09-09: Omarchy 4.0.3-1, Quickshell 0.3.1-1,
Hyprland 0.56.2-2, Qt 6.11.2, Omawrite 0.5.0-1. Recheck before release; these are
package observations, not an established compatibility range.

Planned source layout (keep small; add files when they earn their place):

```text
manifest.json / Panel.qml     Omarchy entry
qml/                         native surface, controls, Markdown editor
core/                        identity, storage, registry and local adapter bridge
providers/                   bundled context providers
content/markdown/            first content module
integrations/                optional shell and app-side bridges
scripts/                     check, install, remove and native verification
tests/                       storage, contracts and native interaction proofs
docs/plan.md                 this tracker
docs/extensions.md           versioned developer contract and example
README.md                    actual install/open/use/remove path
```

## 7. Milestones and tracked TODOs

Completed items are backed by [verification.md](verification.md), the automated
checks, and the native evidence folders linked there. Optional app permission
setup remains visible in the README; adapter source coverage is distinguished
from native application verification.

### M0 — Plan and native feasibility

- [x] M0.1 Record product requirements and latest interaction corrections here.
- [x] M0.2 Review official guide and installed manifest/lifecycle/settings code.
- [x] M0.3 Create the project skeleton and standalone panel; validate manifest/QML.
- [x] M0.4 Prove keyboard opening, first-click delivery to a neighbor, persistent
  visibility, re-entry and context-aware shortcut targeting on two native windows.
- [x] M0.5 Prove hide-on-geometry/lifecycle changes with fractional/rotated outputs;
  verify settings access and capture/fallback without changing original tiling.

Exit: viable shell surface with evidence for the non-popover focus behavior.

### M1 — Durable notes and real extension boundaries

- [x] M1.1 Implement versioned context/content registry and generic App provider.
- [x] M1.2 Implement resource keys, stale-response rejection and manual association.
- [x] M1.3 Implement note/asset store, revisions, atomic saves, recovery and search.
- [x] M1.4 Implement configurable root, settings persistence and collection move/select.
- [x] M1.5 Test restart recovery, failed writes, external conflicts and unavailable types.
- [x] M1.6 Prove a separately registered provider and alternate test content type
  work without modifying host routing; document the contracts.

Exit: persistent user content and genuinely replaceable providers/content modules.

### M2 — Complete Markdown workflow

- [x] M2.1 Implement scope tabs, Markdown typing/undo/shortcuts and formatted preview.
- [x] M2.2 Implement autosave feedback and draft retention across scope/source switches.
- [x] M2.3 Implement pasted-image import. Source snapshot attachments removed after user review.
- [x] M2.4 Implement same-file Omawrite handoff and external-change reconciliation.
- [x] M2.5 Implement collection search/recent/open and declared source reopening.
- [x] M2.6 Finish theme-aware frost, reduced motion and capture-failure fallback.
- [x] M2.7 Verify the complete two-window journey and saved-file read-back.

Exit: usable Markdown notes even for apps with no deeper integration.

### M3 — Context integrations

- [x] M3.1 Revised: remove bundled browser extension and transport; defer automatic
  browser context to a future third-party plugin. Manual URL scopes remain.
- [x] M3.2 File-aware launch/bind bridge for Omawrite and other file editors;
  exact paths, two same-named files, Save As/rename invalidation and deep links.
- [x] M3.3 Terminal/shell bridge: changing cwd, host identity, source association;
  explicitly handle or report unsupported tmux/SSH configurations.
- [x] M3.4 Obsidian adapter: vault/current-file scope, active-view validation,
  rename events and installation instructions.
- [x] M3.5 LibreOffice adapter: focused document URL via UNO and explicit setup;
  unsaved/closed documents never masquerade as stable file context.
- [x] M3.6 Run provider contract checks for all bundled adapters and real native
  file/terminal paths; state any app-specific runtime coverage gaps.

Exit: integrations are packaged, documented and tested at their actual supported
boundary. Missing optional app installations are reported, never described as
passed native tests. The app fallback remains useful without adapters.

### M4 — Installation and acceptance

- [x] M4.1 Provide local install/update/remove scripts and exact runnable README;
  retain notes during removal, validate configuration changes and document dependencies.
- [x] M4.2 Validate package contents, manifest and QML against installed imports.
- [x] M4.3 Verify installed plugin discovery, summon/hide, disable/re-enable and
  panel reload/restart recovery; use disposable test data for lifecycle tests.
- [x] M4.4 Complete the acceptance matrix below, record commands/results and
  unresolved limitations; fix failures before declaring the release complete.
- [x] M4.5 Update this tracker to the actual delivered state and provide the
  user with the working shortcut/command. Local delivery is distinct from a
  public repository, marketplace publication or remote installation qualification.

## 8. Acceptance and evidence

| Scenario | Evidence required |
| --- | --- |
| Two tiled apps, notes unfocused | Neighbor receives first click/typing, notes remain visible and unchanged; shortcut chooses correct target |
| Resize/move/fullscreen/workspace/monitor change | Prompt hide, no stale input surface, no stolen focus, latest saved draft recoverable |
| Source closes during editing | Note remains searchable and editable without a live window |
| Same titles, two files/tabs/profiles | Distinct resource notes; no title/PID-only matching or late reply rebinding |
| Navigation while notes are open | Current editor remains on its latched resource until explicit switch |
| Rapid edit/switch/hide/reload | Ordered persistence, honest save status and recovery of acknowledged writes |
| Read-only/full/missing storage, malformed metadata | Useful error, retained draft, healthy notes continue to work |
| External Omawrite edit | Same file, external updates seen, conflicts preserve both versions |
| Pasted images | Relative asset paths work after moving collection; capture failure leaves editing usable |
| Unknown/missing provider or content type | Generic context or unavailable-type view; existing files preserved |
| Themes, scaling, rotation, small windows | Legible editor, correctly bounded clicks and placement; no offscreen-only visual claims |
| Installation/removal | Shell discovers valid plugin; exact user opening path works; removal retains notes |

Planned checks, to run once their files exist:

```sh
./scripts/check-package
qmllint -I /usr/share/omarchy/shell /home/rblalock/code/omarchy-panel-notes/Panel.qml
./scripts/check
./scripts/check-native
# Removed: historical integration checks are no longer runnable.
./scripts/check-installed
omarchy plugin list --json
omarchy-shell shell summon io.github.rblalock.panel-notes '{}'
omarchy-shell shell hide io.github.rblalock.panel-notes
```

Evidence log: native window, Chromium, Omawrite, Ghostty/Bash and LibreOffice
checks have passed, together with storage/contract and installed lifecycle checks.
See [verification.md](verification.md) for durable report paths, exact results,
and coverage limits. Obsidian has adapter contract coverage; enabling it in a
real user vault is an explicit optional setup step.

## 9. References and implementation questions

- [Omarchy plugin development](https://plugins.omarchy.org/develop.html) and
  [shell contract](https://github.com/omacom/omarchy/blob/quattro/shell/README.md).
- Installed authoritative code: `/usr/share/omarchy/shell/shell.qml`,
  `services/PluginShellApi.qml`, `services/PluginRegistry.qml`,
  `Ui/KeyboardPanel.qml`, `Ui/PanelKeyCatcher.qml`, `Commons/Color.qml` and `Style.qml`.
- [Quickshell PanelWindow](https://quickshell.org/docs/v0.3.1/types/Quickshell/PanelWindow/),
  [ScreencopyView](https://quickshell.org/docs/v0.3.1/types/Quickshell.Wayland/ScreencopyView/),
  [FileView](https://quickshell.org/docs/v0.3.1/types/Quickshell.Io/FileView/),
  [Hyprland toplevel metadata](https://quickshell.org/docs/v0.3.1/types/Quickshell.Hyprland/HyprlandToplevel/).
- [Qt Markdown editing semantics](https://doc.qt.io/qt-6/qml-qtquick-textedit.html#textFormat-prop),
  [KDE QML syntax highlighting](https://api.kde.org/qml-org-kde-syntaxhighlighting-syntaxhighlighter.html),
  [Omawrite](https://github.com/omacom/omawrite).
- [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
  and [activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab):
  an arbitrary OS shortcut does not itself grant extension activeTab access.
- [Obsidian API](https://github.com/obsidianmd/obsidian-api/blob/master/obsidian.d.ts),
  [LibreOffice document URL](https://api.libreoffice.org/docs/idl/ref/interfacecom_1_1sun_1_1star_1_1frame_1_1XModel.html),
  [Ghostty OSC 7](https://ghostty.org/docs/vt/osc/7).

Resolved through implementation: OnDemand mapping provides opening focus; a
180 ms visible-only geometry check handles dismissal; own settings use the
scoped shell API with a recovery copy; acknowledged writes survive QML unload.
Python runs without bytecode writes inside the watched plugin folder, preventing
unwanted hot reloads. The helper communicates through a private local Unix socket.
Dismissal is immediate; the opening fade/scale supplies the subtle motion.

Release limits: a layer surface stays above overlapping floating windows; generic
manual file bindings cannot detect silent file switches in opaque apps; no automatic
SSH/tmux or Firefox adapter; Obsidian has contract rather than native vault coverage;
there is no guarantee for unacknowledged keystrokes at power loss. These are stated
product/support boundaries, not hidden claims of completed runtime verification.

## Review follow-up — September 9, 2026

- [x] Remove the manual Snapshot action and capture-import RPCs; retain pasted images.
- [x] Add panel-wide keyboard actions, scope navigation, search-result navigation,
  button shortcut hints, and an F1 guide.
- [x] Explain manual resource association and protect pending edits before rebinding.
- [x] Surface App-only context and per-app setup guidance.
- [x] Superseded: browser extension deleted at the user's request.
- [x] Provide a repeatable terminal-hook setup command.
- [x] Verify keyboard changes in native surfaces and install the updated plugin.
  Evidence: 23 native assertions, 6 installed-shell assertions, and a real new
  Ghostty using the user's Bash configuration (initial cwd and after cd).

## Corrective review — September 9, 2026

This section supersedes the earlier browser-extension milestones and shell setup delivery.
- [x] Delete the bundled browser extension, native host, browser RPCs and their tests.
  Keep generic URL scopes available to manual bindings and future context plugins.
- [x] Remove our Bash configuration entry. No automatic prompt integration.
- [x] Fix the optional Bash hook so its background helper is not an interactive job.
- [x] Add interface version, loaded source path and actual visible controls to inspection.
- [x] Make the installer reject stale running code and restart the shell if rescan cannot load the new version.
- [x] Visually verify the actual installed desktop has no Snapshot action and loads
  the shortcut-enabled interface. Current desktop capture: `.test-output/current-installed.png`.
  Native shortcut input was verified in the preceding isolated run; no further
  keyboard injection while the user is actively using their notes.

## Typography and Snapshot review — September 9, 2026

This review supersedes the earlier request to remove Snapshot.
- [x] Remove the inline Ctrl+, hint; keep button hover shortcut hints.
- [x] Use 20px note typography and center an 840px maximum writing column, with adaptive padding.
- [x] Restore Snapshot with Ctrl+Shift+S and capture a fresh source frame per invocation.
- [x] Fit preview images to the writing column while retaining full-resolution assets.
- [x] Verify wide/narrow layouts and source changes between consecutive snapshots in an isolated collection.
- [x] Install and verify the loaded interface revision (2026-09-09.4).

Reference: Omawrite's `src/Main.qml` uses 20px writing text and a centered column
around 65 characters. Panel Notes preserves the Omarchy theme font.

## Small preview polish — September 9, 2026

- [x] Retain the existing Markdown editor and preview rendering approach.
- [x] Widen the centered column from 840px to 960px; reduce maximum inner padding from 32px to 24px.
- [x] Use current-theme colors for preview selection, scrollbar, and subtle image outlines.
- [x] Check wide/narrow layouts and light/dark preview using a separate collection.
- [x] Install and confirm the loaded revision (2026-09-09.5).

## Markdown preview readability — September 9, 2026

- [x] Preserve ordinary entered line breaks in preview without rewriting saved Markdown.
- [x] Style top-level blockquotes with a current-theme accent rule and faint background.
- [x] Give top-level fenced code literal rendering, padding and a subtle background.
- [x] Separate headings from adjacent body text with consistent spacing.
- [x] Verify native line layout, literal code, unchanged persisted source, and light/dark appearance.
- [x] Install and confirm loaded interface 2026-09-09.6.

The preview still uses Qt Markdown for text, lists, tables and nested structures;
this is a small presentation layer, not a new Markdown editor or theme system.

## App tab and save-status cleanup — September 9, 2026

- [x] Hide the redundant app identifier below the App tab and remove the context-setup hint.
- [x] Align save status to the far bottom right, keeping actions on the left.
- [x] Visually check wide and narrow layouts in the native test shell.

## Custom resource tabs — September 9, 2026

Supersedes manual resource binding in Settings for the everyday user flow.

- [x] Add a + action beside the tabs, opening a focused URL/file/folder dialog (Ctrl+T).
- [x] Validate input inline; Enter adds and Escape cancels without closing notes.
- [x] Support multiple named custom tabs per app and persist them across restarts.
- [x] Keep resource note identities shared with context providers; duplicate additions select the existing tab.
- [x] Remove selected custom tabs (Ctrl+Shift+Delete), retaining notes and assets in All notes.
- [x] Keep adapter-supplied scopes separate from custom tabs and support clearing legacy manual bindings.
- [x] Remove the manual binding/setup copy and Reduce motion control from Settings.
- [x] Verify backend persistence, input validation, note retention and native keyboard/dialog behavior.

Custom tab associations live in `~/.local/state/panel-notes/custom-tabs.json`,
keyed by app ID; Markdown stays in the configured collection. Adding a tab does
not change the source app or claim to track its navigation.

## Integration removal — September 9, 2026

- [x] Remove Ghostty/terminal Bash and Zsh hooks and terminal setup script.
- [x] Remove the Obsidian plugin and LibreOffice UNO bridge.
- [x] Remove automatic file launch/bind commands, the legacy native-host entry,
  binding leases, process-ancestry tracking and context-change UI.
- [x] Remove obsolete adapter tests and setup guide; revise product/usage/API docs.
- [x] Preserve App note identities, custom tab associations, notes and assets.
- [x] Retain the small provider/content boundaries for future, reviewed extensions.
- [x] Check this machine for enabled project hooks and running bridges; none found.

## Integration roadmap — design before implementation

These are discovery items, not approved implementation tasks. Discuss the
approach with the user before writing an integration or changing any app setup.
Roll out one integration at a time after its design and native behavior are reviewed.

For each proposed integration, agree on:

1. The everyday journey and the resource identity that deserves its own notes.
2. How to obtain the active tab, pane or document reliably, including idle tab
   switches, multiple windows, process reuse and app restarts.
3. The available native API and required setup. Compare user effort and maintenance
   before choosing hooks, extensions, accessibility or bridges; none is assumed.
4. How context updates map to App/custom tabs, how uncertainty is displayed, and
   how to prevent stale context or switching a note while the user is typing.
5. Install, disable and remove behavior with no unexpected shell/app changes.
6. Native acceptance cases and a small experiment before shipping support.

- [ ] Ghostty: investigate focused tab/split identity and directory reporting;
  prompt-only reporting is insufficient. Treat tmux/SSH as separate decisions.
- [ ] Obsidian: investigate supported active-file interfaces; do not assume an
  Obsidian plugin is acceptable.
- [ ] LibreOffice: investigate active-document access and setup burden; the
  removed named-pipe bridge is not the approved approach.
- [ ] Omawrite/other editors: investigate file switches, Save As and shared processes;
  a launch-time association is not active-document detection.
- [ ] Browsers: investigate options and privacy/setup tradeoffs; no bundled
  extension is approved. Preserve explicit custom URL tabs as the current flow.
- [ ] Slack: investigate workspace/channel identity only after selecting a concrete
  workflow and agreeing on an integration method.

Until then, focus product work on reliable App notes, custom tabs, Markdown,
images, keyboard use and note storage/recovery.

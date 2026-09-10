# Panel Notes plan

Current target: **0.1.0 public repository for laptop testing**. Installation uses
`omarchy plugin add https://github.com/rblalock/omarchy-panel-notes.git --enable`.
Marketplace submission and release tagging follow laptop acceptance.

## Product requirements

- One default Markdown note per app, plus named tabs scoped to that app.
- Add with +/Ctrl+T; right-click/F2 renames; removal retains the note in All notes.
- Stable note identity across window changes, renames and restarts.
- Plain local Markdown, relative image assets, search, autosave and recovery.
- Source-window snapshots, pasted images, preview, optional Omawrite handoff.
- A theme-aware surface over the source window, with 200 ms subtle depth motion.
- Adjacent apps remain usable while notes stay visible. Source geometry/lifecycle
  changes hide notes; focus changes do not silently switch the note.
- Complete keyboard access and readable wide/narrow layouts.
- No automatic app integrations, browser extensions, shell hooks or office bridges.

## Architecture

Omarchy loads `Panel.qml` inside its existing shell. It owns presentation and
keyboard/pointer behavior. A local Python service owns storage and app/tab
resolution over a user-private Unix socket. Saved note IDs are independent of
live Hyprland window addresses. Tab names are labels and can change without
moving note files. Existing deterministic tab keys remain compatible.

`core/storage.py` owns atomic writes, revision conflicts, assets and collection
moves. `core/backend.py` owns operations and tab definitions. `core/server.py`
owns the service lifecycle. Bundled App/named providers and Markdown content
use the small experimental registry described in [extensions.md](extensions.md).

## Release preparation

- [x] Implement right-click/F2 rename with duplicate-name validation.
- [x] Preserve note identity, text, images, location and remove/re-add restoration.
- [x] Test retry after a partial rename metadata write.
- [x] Review standard Omarchy add/update/remove behavior against installed commands.
- [x] Make explicit shortcut setup repeatable, conflict-aware and reversible.
- [x] Add dependency/runtime diagnostics.
- [x] Recover explicit reconnect requests with fresh sockets; verify repeated draft recovery.
- [x] Refresh the backend after code updates; let unloaded idle services exit.
- [x] Replace stale README claims and separate historical plans from current scope.
- [x] Provide native IPC commands without required setup and document the public Git install path.
- [x] Add portable automated checks for future repository CI.
- [ ] User laptop acceptance: fresh installation, normal use, restart, removal/reinstall.
- [ ] Address laptop findings and record the actual tested environment.
- [x] Verify the public GitHub installation, loaded commands and Git update path.
- [ ] Prepare release notes after laptop feedback.
- [ ] Tag the accepted release and submit the marketplace listing.

The [laptop checklist](laptop-test.md) is the next gate. Public repository availability does not imply passing a second-machine test or
marketplace acceptance.

## Integration roadmap — design before implementation

These are discovery topics, not approved implementation work. Discuss each
approach before changing another app's setup:

- Ghostty: focused tab/split and directory identity, including tmux/SSH limits.
- Editors: active document changes, Save As, multiple windows and shared processes.
- Browsers: active page identity with acceptable setup and privacy tradeoffs.
- Slack: choose a concrete workspace/channel workflow before choosing an interface.
- Obsidian/LibreOffice: evaluate supported APIs; no plugin or bridge is assumed.

Each proposal must cover the everyday journey, reliable identity, required setup,
maintenance, behavior during typing, failure/disable/removal, and native evidence.
Roll out individually. Richer content, drawing canvases and agents are deferred.

## History

The superseded experiment plan is preserved in [archive/plan-history.md](archive/plan-history.md).
It records removed features and is not the current specification.

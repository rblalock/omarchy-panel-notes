# Candidate verification

Target: Panel Notes 0.1.0, interface `2026-09-09.17`. Public installation uses
the GitHub repository. Laptop acceptance and marketplace listing remain pending.

## Reviewed code and release preparation

- Renaming changes app-owned labels, preserving note keys, file paths, body and assets.
  Duplicate active/retained note names are refused; remove/re-add uses the current name.
- Tab definitions are authoritative for rename retries after a metadata write failure.
- Existing notes that cannot be read produce an error instead of an empty replacement.
- Setup checks dependencies/conflicts, backs up keybindings and restores them if reload fails.
  It uses shell IPC for the shortcut, without Bash/Zsh hooks or external app integration.
- Development installation cannot overwrite a Git-managed plugin or itself.
- The backend checks its code revision when starting after updates; only one service owns
  a runtime socket. An unloaded service exits after about 10 seconds without clients.
- The removal helper checks save completion and retains collection/state data.
- Current docs replace stale context claims; historical records live under `archive/`.

Reviewed the installed `/usr/bin/omarchy-plugin-add`, `omarchy-plugin-update`,
`omarchy-plugin-remove`, and `omarchy-git-url-check`. Add clones and validates Git
repositories; update fast-forwards origin HEAD; remove
unloads/deletes the plugin. These commands do not execute plugin setup/removal hooks.
The README therefore documents explicit setup, helper removal, and shell restart
following an update.

Official references: [publishing](https://plugins.omarchy.org/publish.html),
[development](https://plugins.omarchy.org/develop.html).

## Automated checks

- 28 Python tests: storage, conflicts, recovery, migration, app/tab identity,
  rename persistence/images/collisions/retry, provider isolation, service code
  reload/idle shutdown, and setup conflict/rollback/repetition.
- JavaScript cases for Markdown line breaks, quotes, code, lists, tables and images.
- QML lint and Omarchy manifest/package validation.
- Hosted CI passed on Python 3.12 and Node 22 for initial public commit `12b2cb7`:
  [GitHub Actions run](https://github.com/rblalock/omarchy-panel-notes/actions/runs/34432377340).
  Local Python is 3.14.7.

## Native evidence

Evidence directories are local `.test-output/` artifacts, excluded from packages.

| Check | Evidence | Result |
|---|---|---|
| Add/rename/remove/restore tabs, actual right-click and F2 | `tabs-1789008004` | 9 assertions passed |
| Markdown, image snapshots, source preservation, wide/narrow layout | `presentation-1789008008` | 9 assertions passed |
| Entrance/exit frames, focus release, resize and rapid reopening | `motion-1789008012` | 8 assertions passed |
| Complete desktop journey, external editing, three monitors and recovery | `native-1789008777` | 23 assertions passed |
| Opening, service restart, five consecutive draft reconnects | `opening-1789008789` | 7 assertions passed; 71 ms initial first frame, 61 ms warm median |
| Desktop journey including Ctrl+E from Settings/search fields | `native-1789010069` | 22 assertions passed; clipboard image case skipped because clipboard was not suitable for safe restoration |
| Actual Git-installed panel, public toggle, help, Settings, search, preview and Escape | `live-ui-1789010265` | 9 assertions passed |

Opening timings include the native fixture's IPC invocation through a submitted
frame; they exclude the global shortcut launcher and physical display scanout.
The 200 ms animation remains unchanged. Rename dialog screenshot was inspected. The full desktop check has one transient
image-path warning while switching notes with relative images; final image storage
and displayed preview were checked separately. Forced shutdown tests deliberately
emit PeerClosedError socket warnings.

A reconnect failure was reproduced during the broader journey. Quickshell 0.3.1's
[socket implementation](https://raw.githubusercontent.com/quickshell-mirror/quickshell/v0.3.1/src/io/socket.cpp)
can retain a failed connection object. Bootstrap now creates a fresh Socket and
bounds retries of explicit opening/save requests. The final runs above pass without
diagnostic logging. Earlier failed/interrupted runs are not counted as passing.
The native harness also now uses a valid PNG fixture, checks keyboard ownership,
and targets the source monitor before its workspace-change assertion.

## Public installation

Panel Notes follows the public Git installation pattern used by
[Grid wallpaper picker](https://github.com/rblalock/omarchy-grid-wallpaper-picker)
and [Omarchy Island](https://github.com/rblalock/omarchy-dynamic-island).
`omarchy-shell panel-notes toggle`, `library`, `hide` and `inspect` are available
when the plugin is enabled, without running setup. The shortcut and desktop
launcher are optional. Development copy installation remains separate.

The earlier transfer-bundle approach was rejected and removed. The acceptance
path is `omarchy plugin add https://github.com/rblalock/omarchy-panel-notes.git --enable`,
followed by the same commands documented in the README.

Commit `12b2cb7` was installed from that public HTTPS Git URL with stock Omarchy
commands. The previous development copy was backed up by stock removal. Its
cached interface required a shell restart. A second remove, shell restart while
absent, and public add verified loading without restarting after installation.
Enable briefly reported an IPC timeout; the new target became available after
startup settled. README troubleshooting covers this observed delay.

The installed UI check exposed Qt's text-field Ctrl+E handling in Settings.
Settings and search now explicitly return to Notes for that key. The disposable
native journey above verifies both fields. The installed check also now waits
for its source workspace animation and verifies panel focus before sending keys.
Its key chords allow 50 ms between virtual-keyboard modifier changes; sending
the entire chord without pauses intermittently missed shortcuts in the installed shell.

Stock `omarchy plugin update` fast-forwarded the public installation from
`12b2cb7` to `3c1dfb5`, followed by the documented shell restart. Installed HEAD
matched GitHub, interface `.17` loaded from the installed directory, and the nine
installed UI checks passed. Optional shortcut setup and `panel-notes doctor`
passed. All 32 pre-existing collection files retained their SHA-256 hashes across
removal, reinstallation and updating. [CI for the update](https://github.com/rblalock/omarchy-panel-notes/actions/runs/34432647189)
also passed.

## Remaining acceptance

The [laptop test](laptop-test.md) covers installation with standard Omarchy commands,
real machine defaults, reboot, scaling, optional Omawrite, and remove/reinstall.
Public Git installation/forward-update and hosted CI have passed on this desktop.
The separate laptop, reboot and physical display tests remain pending.

Current native environment: Omarchy 4.0.3-1, Quickshell 0.3.1-1,
Hyprland 0.56.2-2, Qt 6.11.2. Desktop outputs include scale 1, scale 1.6,
and a rotated scale-1.6 display. No physical monitor-unplug or power-loss test.

Earlier experiments, removed integrations and superseded test reports are retained
in [archive/verification-history.md](archive/verification-history.md).

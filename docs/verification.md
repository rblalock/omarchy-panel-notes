# Local delivery verification

> Current scope: App notes and named note tabs under each app. The historical app-adapter
> results below do not describe the installed product; all bundled integrations
> were removed in the latest September 9 review. Current evidence is appended.


Date: 2026-09-09. Evidence paths are relative to the development checkout. This records a local Omarchy installation, not marketplace
publication or qualification of other Linux/Hyprland versions.

## Environment

Omarchy 4.0.3-1; Quickshell 0.3.1-1; Hyprland 0.56.2-2 (Lua dispatch);
Qt 6.11.2; Python 3.14.7; Omawrite 0.5.0; Chromium 152.0.7977.82;
Ghostty 1.3.1; LibreOffice 26.8.0. Obsidian 1.13.7 is installed, but no user
vault was modified or enabled for testing.

Outputs exercised: DP-1 at scale 1; DP-3 at 1.6; HDMI-A-1 at 1.6 with transform
3 and a negative monitor origin. All test windows/data were disposable.

## Checks and evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Python storage/backend/provider checks | 19 passed | `.test-output/check-final.log`, `tests/test_core.py` |
| Obsidian adapter contract | Passed: active file, rename, non-file view, unfocused app | `tests/obsidian-contract.cjs` |
| Syntax and packaging | Python compile, JS/Bash checks, QML lint, staged Omarchy manifest validation passed | `scripts/check` |
| Native panel journey | 21 assertions passed | `.test-output/native-1788960595/results.json` |
| Native browser/file/terminal/office bridges | 7 assertions passed | `.test-output/integrations-1788959441/results.json` |
| Removal and reinstall | Passed: selected Markdown retained, plugin and shortcut restored | `.test-output/removal-1788960348/results.json` |
| Installed Omarchy lifecycle | 6 assertions passed | `.test-output/installed-1788960877/results.json` |

The native panel journey uses Linux virtual input for actual pointer delivery,
Wayland typing, compositor geometry, real source capture, and independent file
read-back. It proves opening focus, the first click into a neighboring app,
persistent notes while that app receives input, explicit re-entry, PNG clipboard
paste, resize/workspace/fullscreen/close dismissal, same-file
Omawrite edit/reload, missing-capture fallback, small-window layout, three outputs,
an independently registered alternate content editor, and recovery of editor text
after a live service disconnect with a fresh ordered writer on retry. Clipboard tests restore
the previous text clipboard and skip if richer formats cannot be restored.

Inspected screenshots: `notes.png`, `preview-light.png`, and `small.png` in the
native evidence folder. The light palette is applied to the disposable test
shell's reactive Omarchy Color tokens; the user's desktop theme is not changed.
The native log has no QML warnings/errors for the successful run.

The integration check launches a disposable Chromium profile, loads the real
extension/native host, and exercises URL, navigation, tab changes, and profile
identity. DevTools is used only by this test; it is not part of the product's
browser integration. It also launches a real Omawrite file, a real Ghostty/Bash
shell with a cwd change, and a separate LibreOffice profile with a named UNO pipe.

The installed check invokes **Super+Alt+N** through native Linux keyboard events,
types into the real Omarchy-hosted panel, then checks rescan, disable/re-enable,
service restart, and Escape focus return. It temporarily selects an isolated
collection and restores the original settings afterwards.

## Acceptance coverage

| Scenario | Observed result / boundary |
| --- | --- |
| Two tiled apps and unfocused notes | First click and subsequent typing reach neighbor; note/source retained |
| Resize, fullscreen, workspace, close, monitor move | Source changes dismiss the surface; confirmed Markdown survives |
| Same-name files, paths, browser profiles | Canonical path and URL/profile keys tested; no title-based identity |
| Late context reply | Rejected if the source no longer matches; editing remains latched |
| Ordered saves, restart, failed write, conflict | Writes ordered by writer sequence; stale writes refused; conflict/failure drafts preserved |
| Unavailable selected folder, malformed metadata | Service/recovery remains accessible; errors do not invalidate healthy records |
| External editing | Same file edited in Omawrite and reloaded; conflicting versions preserved by store tests |
| Images and collection move | Native PNG paste; relative files/metadata verified after migration |
| Unknown extension/type | Provider failure falls back; unknown records remain intact; alternate QML editor runs |
| Theme, scale, rotation, small window | Reactive light/dark palettes, 1/1.6 scaling, transform 3, 360×420 window inspected |
| Overlapping floating windows | Layer surface remains above normal windows by design; it does not inherit application stacking |

## Boundaries

- Obsidian has adapter contract coverage, not an enabled-vault native test.
  Its optional setup is documented; existing user vaults were left alone.
- The bundled browser extension and native host were deleted after review.
  Earlier browser evidence above is historical, not current functionality.
- Automatic tmux/SSH context is unavailable. Generic manual bindings require
  rebinding for silent resource switches that the app does not expose.
- No physical monitor unplug or power-loss experiment was performed. Monitor
  reassignment/scaling/rotation were exercised. Confirmed saves are verified;
  in-flight unacknowledged keystrokes have no zero-loss power-failure guarantee.
- Filesystem write errors are fault-injected; the user's disk was not filled.
  Binary content, drawing/video embedding, agents, math, Mermaid, and syntax
  coloring remain outside the first Markdown release.

## Important implementation findings

OnDemand layer-surface mapping grants opening focus; switching from Exclusive
back to OnDemand lost it. No exclusive grab is used. Re-entry deliberately
remaps the panel. Closing is immediate to remove its input surface.

Omarchy's registry rescan is asynchronous, and disable removes the inline entry.
Install waits for discovery; own settings have a separate recovery copy. Python
bytecode writes inside the plugin trigger the shell's recursive file watcher,
so all runtime Python entry paths disable bytecode writes. Runtime sockets,
captures, settings recovery, and note data live outside the installation.

The installer stages and validates a complete package outside the watched plugin
folder before renaming it into place. Installation waits for registry discovery
and allows a longer IPC timeout while the shell reloads its plugins.

## Review update: keyboard and context clarity

`./scripts/check` passes 19 Python checks and the Obsidian contract/syntax/package checks.
`.test-output/native-1788961749/results.json` records 23 passing native assertions,
including real keyboard preview/edit, settings, F1 help, searchable library and
result opening, Tab/Ctrl+E focus, Escape outside the editor, numbered/cyclic scope
selection, PNG paste, persisted assets, and service reconnect. The earlier native run skipped clipboard import
to preserve a complex user clipboard and caught an overstrict asset assertion in
the test; the test now accounts for that skip, and the final run exercised paste.

Manual source snapshots were removed after product review. Background screencopy
is still used only for transient frost; automatic thumbnail presentation is deferred.
The optional browser adapter is not installed into the user's normal browser.
Slack desktop has no channel/workspace adapter. Terminal setup is a guarded,
repeatable Bash/Zsh source entry; existing shells must source it once.

Installed update: `.test-output/installed-1788961871/results.json` records all six
lifecycle/input assertions passing with no cleanup errors.
`.test-output/terminal-setup-1788961851/results.json` verifies a fresh Ghostty using
the user's actual Bash configuration reports its initial cwd and follows `cd /tmp`.
The optional hook was enabled once in `~/.bashrc`, with a prior configuration
backup retained under `~/.local/state/panel-notes/config-backups`.

## Corrective review

The earlier installed checks were insufficient: they validated save/lifecycle
behavior but did not verify the running UI revision. The live shell still held
old QML, including Snapshot. The installer now checks interface version and
loaded path; it restarts Omarchy shell when rescan retains stale code.

The earlier automatic Bash setup was reverted by removing only the two owned
lines. The optional Bash helper now starts its job in a subshell; an interactive
PTY check confirms there are no job-start/completion notifications. Existing
shells retain function definitions until closed or explicitly cleared.

Browser integration/transport and browser-specific tests are deleted. Generic URL
providers and manual binding remain. Core checks now cover 17 Python tests plus
the Obsidian contract, syntax and package validation.

The lifecycle check that temporarily changes the global notes root must only be
run in an isolated desktop session. Use `scripts/check-installed-ui` on a live
user desktop: it changes neither storage settings nor note text. A failed live
lifecycle run during this review restored the configured notes root and preserved
a one-character draft in recovery; it was not counted as passing evidence.

Final live read-back: interface `2026-09-09.3` loaded from the installed Panel.qml;
status Saved, no failure. `.test-output/current-installed.png` was captured from
the user's currently visible notes panel and visually inspected: Preview and
Open in Omawrite are present; Snapshot is absent; keyboard help and shortcut
tooltips are present. No browser integration directory or native host registration
exists in the current source/installation. The configured notes root remains
`/home/rblalock/Documents/Panel Notes`; the Bash config contains no Panel Notes entry.

## Restored Snapshot and typography

The latest user review restores Snapshot as an explicit attachment action.
`scripts/check-presentation` uses a separate collection and changes only disposable
source windows. Evidence: `.test-output/presentation-1788964219/`. All five checks
pass: centered 840px column with 20px type, persisted snapshot asset, source-only
capture, a second fresh image after changing source content while notes remain
open, and narrow-window padding. Wide/edit/preview/narrow screenshots were
inspected. No QML warnings were emitted in this final native run. Preview uses
native Markdown text blocks and aspect-preserving image blocks for imported
standalone images; full-resolution files and Markdown source remain intact.

Reference: [Omawrite Main.qml](https://github.com/omacom/omawrite/blob/master/src/Main.qml)
uses 20px writing type with a centered column around 65 characters.
[Quickshell ScreencopyView](https://quickshell.org/docs/v0.3.1/types/Quickshell.Wayland/ScreencopyView/)
provides the fresh toplevel frame; a separate capture instance prevents reuse of
the cached background frost image.

Small preview polish evidence: `.test-output/presentation-1788965383/`.
Five native checks pass, including the updated 960px writing width and narrow
padding. Light/dark preview captures were produced with the test shell's local
Color object; the user's theme was not changed. No QML warnings were emitted.

## Markdown preview readability

Evidence: `.test-output/presentation-1788975727/`. Nine native checks pass,
including actual rendered line counts for ordinary text and quotes, exact literal
code and indentation, and byte-for-byte unchanged saved Markdown. Snapshot
freshness and wide/narrow layout checks still pass. Light/dark preview screenshots
were visually inspected; no QML warnings were emitted. The theme changes occur
only in the disposable test shell.

`scripts/check` passes all 17 backend tests, the Obsidian contract, new Markdown
presentation cases, syntax checks and package validation. Parser cases cover
quotes adjacent to images, fenced literal image/quote syntax, nested list
preservation, tables, CRLF, and existing external-image/HTML handling.

Installed runtime read-back confirms interface `2026-09-09.6` from the installed
Panel.qml. The installer restarted the shell after detecting cached older QML.

App tab/footer cleanup: `.test-output/presentation-1788975939/`. Wide and narrow
screenshots confirm no redundant text below App and right-aligned save status.
All nine existing native presentation checks pass; no QML warnings.

## Custom tab workflow

`scripts/check` passes 19 backend tests plus Markdown and Obsidian contracts,
QML syntax checks and package validation. New backend coverage includes multiple
URL tabs, deduplication, restart persistence, app isolation, file/folder paths,
invalid input, source identity checking, legacy binding removal, retained notes,
and restoration of the same note identity when re-added.

Native evidence: `.test-output/tabs-1788977862/`. The separate shell/collection
passes Ctrl+T dialog focus, Escape cancellation, inline invalid-path errors, Enter
submission, independent note content when switching, Alt+2 selection,
Ctrl+Shift+Delete removal, saved-note retention and restoration. Wide/narrow
dialog, tab row and Settings screenshots were inspected; no QML warnings.

The native fixture now edits through TextArea remove/insert instead of assigning
its text property, preserving the QML binding when switching notes.

## App notes and custom tabs only

The current package removes all bundled automatic context integrations, their
setup scripts and tests, the file-binding launcher, legacy native-host command,
and the bind/invalidate/lease/process-ancestry backend. No project hooks were
found in Bash/Zsh startup files, no installed Panel Notes adapter was found in
the registered Obsidian vaults, and no project context bridge was running. No
external Panel Notes extension directory exists on this machine.

`scripts/check` passes 18 backend tests and the Markdown formatter contract,
syntax and package checks. The app identity check proves the same app note is
reused across different windows/titles/PIDs and a backend restart. Custom tab
persistence, resource note restoration and file integrity checks remain passing.

Native checks pass in `.test-output/tabs-1788978390/` and
`.test-output/presentation-1788978393/`: add/remove/restore custom tabs, dialog
shortcuts, Markdown preview, note source preservation, fresh snapshots and
wide/narrow layouts. Neither native run emitted QML warnings.

## Subtle depth animation

`scripts/check-motion` passes eight native checks in
`.test-output/motion-1788978790/`. Frame samples show intermediate entrance and
exit progress. Exit retains a visible surface with an empty input mask and no
keyboard focus; typing immediately after dismissal reaches the source document
and leaves notes unchanged. Reopening interrupts exit safely. Explicit lifecycle
close and actual source resize bypass exit animation. The existing reduced-motion
preference remains compatible. The first test run needed a correction to focus
the disposable source TextArea; the final run passes with no QML warnings.

## Opening latency

Baseline: `.test-output/opening-1788979086/timings.json`. Initial opening first
frame 171 ms, repeat median 84 ms (eight repetitions); settled at 361/273.5 ms.
After warming the service and loading the two bundled resolvers in-process:
`.test-output/opening-1788979192/timings.json`: initial first frame 70 ms, repeat
median 58 ms; settled at 260/248 ms. The 200 ms animations are unchanged.

Measurement starts immediately before launching the native test's `qs ipc`
opening command and ends on the backing QQuickWindow's first `frameSwapped`
with nonzero opacity. It includes IPC invocation, window/resource resolution,
QML/rendering and the initial animation tick. It excludes the installed global
shortcut/Python launcher path and physical display scanout; these are local test
samples, not a guarantee for every workload.

The service reports ready before the first invocation in the optimized run. A
forced service shutdown/reopen restores the same saved note and identity; the
expected PeerClosedError warning corresponds to that intentional shutdown.
Custom-tab and motion checks pass in `.test-output/tabs-1788979197/` and
`.test-output/motion-1788979199/`. Twenty backend tests plus Markdown, syntax and
package checks pass. Tests prove bundled lookups spawn no workers while an
external provider claiming a bundled ID still runs under the 500 ms timeout.

## Bare website addresses

Twenty-one backend tests plus Markdown/syntax/package checks pass. New cases
cover bare domains, paths/query/fragments, localhost/ports, HTTPS deduplication
and invalid inputs. In `.test-output/tabs-1788979988/`, five native checks pass,
including bare-domain Enter submission, independent tabs, removal and restoring
the same note using the full HTTPS URL. The later, unrelated Settings screenshot
step stopped at its focus guard; it is not counted as a fully passing native run.

## Named tabs under apps

Twenty-one backend tests plus Markdown, QML syntax and package checks pass.
Coverage includes app-scoped/case-normalized/Unicode names, plain literal labels,
empty/oversized/control-character validation, preserved note IDs and assets during
legacy-tab migration, independent copies of formerly shared notes, collision
handling and retry after an interrupted configuration write.

`.test-output/tabs-1788980531/` passes seven native checks: Ctrl+T/Escape, empty
name handling, Enter adding an independent named note, remembering the selected
note on reopen, removal, restoration and simplified Settings. The Name dialog
and tab layout were inspected. No QML warnings were emitted.

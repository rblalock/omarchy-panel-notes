# Development

The working product scope is [docs/plan.md](docs/plan.md). Keep automatic app
integrations and new content types out of the initial release until discussed.

## Code map

- `Panel.qml`, `qml/`: native surface, tab dialogs, focus and animation.
- `content/markdown/`: plain source editor and light preview formatting.
- `core/backend.py`: note/tab operations and app associations.
- `core/storage.py`: durable notes, assets, revisions, recovery and collection moves.
- `core/server.py`: user-private socket, daemon startup/update/idle shutdown.
- `core/setup.py`: explicit shortcut setup/removal and diagnostics.
- `providers/`: bundled app and named-note resolution.
- `tests/`: storage/service/setup tests and disposable native fixtures.

## Checks

Portable checks (Python 3.12+ and Node 22):

```sh
python3 -B -m unittest discover -s tests -v
node tests/markdown-preview.cjs
```

On Omarchy, `./scripts/check` also checks QML and package validation. The service
lifecycle test takes about 11 seconds and uses isolated storage/runtime sockets.

Native checks use separate notes collections and disposable windows/workspaces,
restore focus, and require `grim`, `wtype` and access to `/dev/uinput`:

```sh
./scripts/check-tabs
./scripts/check-presentation
./scripts/check-motion
./scripts/check-opening
./scripts/check-native
```

Run these sequentially while not interacting with the test workspace. They are
not suitable for headless CI. `check-installed` and `check-removal` change global
plugin state and require `--isolated-session`; reserve them for a disposable desktop.
Do not run them on someone else's active notes session.

## Local development delivery

```sh
./scripts/install
python3 ~/.config/omarchy/plugins/rblalock.panel-notes/scripts/setup
```

The development installer stages and validates the current files, preserves the
previous installation in state backups, and verifies the loaded UI revision.
It restarts the shell if QML caching retained older code. It deliberately refuses
to replace a Git-managed installation: use the standard Git update path there.

Increment `Panel.qml`'s `interfaceVersion` and the expected version in
`scripts/check-installed-ui` when changing the running interface. Keep runtime
state, logs, sockets, Python bytecode, and notes outside the installed repository.

Public installation always uses the GitHub repository through `omarchy plugin add`.
The development installer is not part of the user installation path. Keep the
README commands and [laptop checklist](docs/laptop-test.md) aligned with that flow.

See [verification](docs/verification.md) for evidence and untested boundaries.

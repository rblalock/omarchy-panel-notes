# Laptop acceptance test

Install from the public GitHub repository with the same command as any other
user. Use an Omarchy 4 laptop with the Quattro shell and Lua Hyprland configuration.

## Install

```sh
omarchy plugin add https://github.com/rblalock/omarchy-panel-notes.git --enable
```

Focus an app and run `omarchy-shell panel-notes toggle`. It must work without a
developer checkout or setup helper. For quick access, add the optional binding
from the README, or run:

```sh
~/.config/omarchy/plugins/io.github.rblalock.panel-notes/scripts/setup
```

Then use **Super+Alt+N**. Diagnostics:

```sh
omarchy-shell panel-notes inspect
~/.config/omarchy/plugins/io.github.rblalock.panel-notes/panel-notes doctor
```

## Try the everyday path

- [ ] App note opens, typing autosaves, Escape returns to the source app.
- [ ] Add Ideas and Research. They have independent content.
- [ ] Right-click Ideas and rename it to Plans. Text and images stay intact.
- [ ] F2 opens rename; Escape cancels. An existing name is refused.
- [ ] Remove Plans, find it in All notes, then add Plans again to restore it.
- [ ] A second window of the same app shares its notes; another app has its own.
- [ ] Paste an image and take two snapshots after changing the source content.
- [ ] Preview displays quotes, line breaks, code and images in the current theme.
- [ ] Click/type in an adjacent app while notes stay visible.
- [ ] Resize/move/close the source: notes hide and saved text survives.
- [ ] Narrow windows and laptop display scaling remain usable.
- [ ] If installed, Omawrite opens the same file and Reload reads its edits.
- [ ] Log out/back in or reboot. Notes, names and selected tab return.

Use sample data. Notes default to `~/Documents/Panel Notes`.

## Disable and reinstall

Wait for Saved and close the panel. Disable/re-enable:

```sh
omarchy plugin disable io.github.rblalock.panel-notes
omarchy plugin enable io.github.rblalock.panel-notes
```

Confirm the notes still open. If you used the setup helper, remove with its companion:

```sh
python3 ~/.config/omarchy/plugins/io.github.rblalock.panel-notes/scripts/remove
```

If you did not use setup, use `omarchy plugin remove io.github.rblalock.panel-notes`
and remove your optional manual binding/desktop launcher.

Confirm the note collection remains and the setup-created shortcut/launcher are
gone. Repeat the original install/setup commands and check that text, tabs and
images return.

## Update and report

Wait for Saved, close notes, then use the standard Git update:

```sh
omarchy plugin update io.github.rblalock.panel-notes
omarchy restart shell
```

Check the installed revision and runtime:

```sh
git -C ~/.config/omarchy/plugins/io.github.rblalock.panel-notes rev-parse --short HEAD
omarchy-shell panel-notes inspect
```

Confirm saved notes and tab names survive. If nothing has changed upstream, the
update should report that the plugin is up to date. A later source commit should
fast-forward normally without replacing the installation or losing local state.

Report doctor output, the action that failed, expected/observed behavior, and a
screenshot using sample content. Laptop results are currently pending.

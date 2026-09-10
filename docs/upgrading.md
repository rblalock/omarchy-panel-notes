# Upgrading early installations

## Initial plugin ID

If you installed the initial `io.github.rblalock.panel-notes` version, wait for
**Saved**, then remove that installation before installing the renamed plugin.
Run this before updating the old checkout:

```sh
~/.config/omarchy/plugins/io.github.rblalock.panel-notes/scripts/remove
omarchy plugin add https://github.com/rblalock/omarchy-panel-notes.git --enable
omarchy restart shell
```

Your notes, tab names, and collection settings are retained. Run the optional
shortcut setup again if you used it. If you installed the old desktop launcher,
remove `~/.local/share/applications/io.github.rblalock.panel-notes.desktop` and
copy the renamed launcher using the [README instructions](../README.md#app-launcher).


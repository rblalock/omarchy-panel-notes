"""Explicit shortcut/launcher setup. Never modifies shell startup files."""
import json
import re
from pathlib import Path
import shutil
import subprocess
import time

from .backend import PLUGIN_ID
from .session import environment, hypr
from .storage import atomic

MARKER = '-- Panel Notes shortcut\n'
COMMAND = 'omarchy-shell panel-notes toggle'
BINDING = 'o.bind("SUPER + ALT + N", "Panel Notes", ' + json.dumps(COMMAND) + ')\n'
REQUIRED = ('python3', 'omarchy', 'omarchy-shell', 'qs', 'hyprctl', 'wl-paste')


def check_dependencies():
    missing = [command for command in REQUIRED if not shutil.which(command)]
    if missing:
        raise RuntimeError('Missing commands: ' + ', '.join(missing) + '. Panel Notes requires the Omarchy 4 shell, Quickshell and wl-clipboard.')


def without_shortcut(text):
    lines = text.splitlines(keepends=True)
    out = []
    index = 0
    while index < len(lines):
        if (lines[index] == MARKER and index + 1 < len(lines)
                and lines[index + 1].startswith('o.bind("SUPER + ALT + N", "Panel Notes", ')):
            index += 2
        else:
            out.append(lines[index])
            index += 1
    return ''.join(out)


def write_bindings(path, before, after, env):
    if before == after: return
    backup = Path.home() / '.local/state/panel-notes/config-backups' / ('bindings-' + str(time.time_ns()) + '.lua')
    atomic(backup, before)
    atomic(path, after)
    try:
        subprocess.run(['hyprctl', 'reload'], env=env, check=True, capture_output=True, text=True, timeout=5)
        result = subprocess.run(['hyprctl', 'configerrors'], env=env, check=True, capture_output=True, text=True, timeout=5)
        if result.stdout.strip() not in ('', 'ok'):
            raise RuntimeError('Hyprland reported configuration errors: ' + result.stdout.strip())
    except (RuntimeError, subprocess.SubprocessError, OSError):
        atomic(path, before)
        subprocess.run(['hyprctl', 'reload'], env=env, capture_output=True, timeout=5)
        raise


def setup():
    check_dependencies()
    target = Path.home() / '.config/omarchy/plugins' / PLUGIN_ID / 'panel-notes'
    if not target.is_file(): raise RuntimeError('Install Panel Notes with omarchy plugin add before running setup.')
    path = Path.home() / '.config/hypr/bindings.lua'
    if not path.is_file(): raise RuntimeError('Expected Omarchy 4 Lua configuration at ' + str(path))
    before = path.read_text()
    clean = without_shortcut(before)
    owned = before != clean
    conflicts = [bind for bind in hypr('binds') if bind.get('modmask') == 72 and bind.get('key', '').lower() == 'n'
                 and not (owned and bind.get('description') == 'Panel Notes')]
    if conflicts: raise RuntimeError('Super+Alt+N is already in use. No changes made. Choose a custom shortcut using the README instructions.')
    link = Path.home() / '.local/bin/panel-notes'
    if (link.exists() or link.is_symlink()) and not (link.is_symlink() and link.readlink() == target):
        raise RuntimeError(str(link) + ' already exists and is not our launcher. No changes made.')
    after = clean.rstrip() + '\n\n' + MARKER + BINDING
    write_bindings(path, before, after, environment())
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.is_symlink(): link.symlink_to(target)
    return 'Ready. Focus an app and press Super+Alt+N. Run panel-notes doctor for diagnostics.'


def remove_shortcut():
    path = Path.home() / '.config/hypr/bindings.lua'
    if path.is_file():
        before = path.read_text()
        write_bindings(path, before, without_shortcut(before), environment())
    target = Path.home() / '.config/omarchy/plugins' / PLUGIN_ID / 'panel-notes'
    link = Path.home() / '.local/bin/panel-notes'
    if link.is_symlink() and link.readlink() == target: link.unlink()


def doctor():
    check_dependencies()
    env = environment()
    print('Required commands: available')
    for label, args in [('Omarchy', ['omarchy', 'version']), ('Quickshell', ['qs', '--version']), ('Hyprland', ['hyprctl', 'version'])]:
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=5, check=True)
        print(label + ': ' + (result.stdout or result.stderr).strip().splitlines()[0])
    result = subprocess.run(['omarchy-shell', 'shell', 'call', PLUGIN_ID, 'inspect', ''], env=env, capture_output=True, text=True, timeout=10, check=True)
    try: state = json.loads(result.stdout)
    except ValueError: raise RuntimeError('The installed panel is not loaded. Enable it with: omarchy plugin enable ' + PLUGIN_ID)
    print('Loaded interface: ' + state['interfaceVersion'])
    print('Loaded from: ' + state['loadedPath'])
    expected = re.search(r'property string interfaceVersion: "([^"]+)"',
                         (Path(__file__).resolve().parent.parent / 'Panel.qml').read_text()).group(1)
    if state['interfaceVersion'] != expected:
        raise RuntimeError('An older interface is loaded. Run: omarchy restart shell')
    print('Notes service: ' + ('ready' if state['serviceReady'] else 'not ready'))
    print('Omawrite: ' + ('available' if shutil.which('omawrite') else 'optional; not installed'))
    if state.get('failure'): print('Panel error: ' + state['failure'])
    if not state['serviceReady']: raise RuntimeError('Notes service is not ready. Restart the shell, then run doctor again.')

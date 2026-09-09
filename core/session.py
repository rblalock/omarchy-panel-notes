import json
import os
import subprocess


def environment():
    env = os.environ.copy()
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    if not env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        result = subprocess.run(["hyprctl", "instances", "-j"], env=env,
                                capture_output=True, text=True, timeout=3)
        instances = json.loads(result.stdout or "[]")
        if len(instances) != 1:
            raise RuntimeError("Select a Hyprland session with HYPRLAND_INSTANCE_SIGNATURE.")
        env["HYPRLAND_INSTANCE_SIGNATURE"] = instances[0]["instance"]
        env.setdefault("WAYLAND_DISPLAY", instances[0]["wl_socket"])
    env.setdefault("QT_QPA_PLATFORM", "wayland")
    return env


def hypr(command, *args):
    result = subprocess.run(["hyprctl", "-j", command, *args], env=environment(),
                            capture_output=True, text=True, timeout=3)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def snapshot(address=None):
    clients = hypr("clients")
    window = next((w for w in clients if w["address"] == address), None) if address else hypr("activewindow")
    if not window or not window.get("address"):
        raise ValueError("Focus an application window, then open Panel Notes.")
    monitors = hypr("monitors")
    monitor = next((m for m in monitors if m["id"] == window["monitor"]), None)
    if not monitor:
        raise ValueError("The source monitor is unavailable.")
    return {
        "address": window["address"], "session": environment()["HYPRLAND_INSTANCE_SIGNATURE"],
        "pid": window["pid"], "app": window.get("initialClass") or window["class"],
        "title": window["title"], "at": window["at"], "size": window["size"],
        "workspace": window["workspace"]["id"], "fullscreen": window.get("fullscreen", 0),
        "monitor": {k: monitor[k] for k in ("id", "name", "x", "y", "scale", "transform", "width", "height")},
        "visible": window["workspace"]["id"] in (monitor["activeWorkspace"]["id"], monitor["specialWorkspace"]["id"]),
    }


def changed(source):
    try:
        now = snapshot(source["address"])
    except (ValueError, RuntimeError):
        return True
    return not now["visible"] or any(now[key] != source[key] for key in
        ("session", "pid", "at", "size", "workspace", "fullscreen", "monitor"))


def dispatch(method, **arguments):
    # JSON strings are valid Lua string literals for the ASCII selectors used here.
    def literal(value):
        if isinstance(value, bool): return "true" if value else "false"
        return json.dumps(value, ensure_ascii=False)
    fields = ", ".join(k + " = " + literal(v) for k, v in arguments.items())
    expression = "hl.dsp." + method + "({" + fields + "})"
    result = subprocess.run(["hyprctl", "dispatch", expression], env=environment(),
                            capture_output=True, text=True, timeout=3)
    if result.returncode: raise RuntimeError(result.stderr or result.stdout)


def focus(source):
    current = snapshot(source["address"])
    if current["session"] != source["session"] or current["pid"] != source["pid"]:
        raise ValueError("The original window is no longer available.")
    dispatch("focus", window="address:" + source["address"])

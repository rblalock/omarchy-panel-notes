import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import threading
import time

from .backend import Backend, PROJECT

MAX_MESSAGE = 32 * 1024 * 1024  # 4 MB text can expand sixfold when JSON-escaped.


def runtime():
    base = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    identity = str(PROJECT) + os.environ.get("PANEL_NOTES_ROOT", "")
    directory = base / ("panel-notes-" + hashlib.sha256(identity.encode()).hexdigest()[:12])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise ValueError("Panel Notes runtime directory is not owned by this user.")
    directory.chmod(0o700)
    return directory


def call(request, path=None):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(6)
        client.connect(str(path or runtime() / "bridge.sock"))
        client.sendall((json.dumps(request) + "\n").encode())
        response = json.loads(client.makefile("rb").readline(MAX_MESSAGE))
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "The notes service did not respond."))
        return response["result"]


def ensure():
    directory = runtime()
    with (directory / "start.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            call({"op": "ping"})
        except (OSError, ValueError, RuntimeError):
            log = (directory / "service.log").open("ab")
            subprocess.Popen([sys.executable, str(PROJECT / "panel-notes"), "serve"],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            log.close()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    call({"op": "ping"})
                    break
                except (OSError, ValueError, RuntimeError):
                    time.sleep(0.04)
            else:
                raise RuntimeError("Notes service failed to start; see " + str(directory / "service.log"))
    return str(directory / "bridge.sock")


def shutdown():
    directory = runtime()
    with (directory / 'start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try: call({'op':'shutdown'})
        except (OSError, ValueError, RuntimeError): return
        deadline = time.monotonic() + 3
        while (directory / 'bridge.sock').exists() and time.monotonic() < deadline:
            time.sleep(.02)
        if (directory / 'bridge.sock').exists(): raise RuntimeError('Notes service did not finish shutting down.')


def serve():
    directory = runtime()
    backend = Backend(directory)
    address = directory / "bridge.sock"
    address.unlink(missing_ok=True)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            # A retained panel can be idle for hours; blocking reads consume no CPU.
            self.request.settimeout(None)
            while True:
                try:
                    raw = self.rfile.readline(MAX_MESSAGE + 1)
                    if not raw:
                        break
                    if len(raw) > MAX_MESSAGE or not raw.endswith(b"\n"):
                        break
                    request = json.loads(raw)
                    op = request.get("op")
                    result = {"version": 1} if op in ("ping", "shutdown") else backend.dispatch(request)
                    response = {"id": request.get("id"), "ok": True, "result": result}
                except Exception as error:
                    response = {"id": locals().get("request", {}).get("id"), "ok": False, "error": str(error)}
                try:
                    self.wfile.write((json.dumps(response) + "\n").encode())
                    self.wfile.flush()
                except (BrokenPipeError, OSError):
                    break
                if locals().get("op") == "shutdown":
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    break

    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    with Server(str(address), Handler) as server:
        address.chmod(0o600)
        server.serve_forever(poll_interval=0.2)
    address.unlink(missing_ok=True)

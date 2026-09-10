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


def code_revision():
    """Identify the service code loaded in memory across Git-based updates."""
    digest = hashlib.sha256()
    paths = [PROJECT / 'panel-notes', *sorted((PROJECT / 'core').glob('*.py')),
             *sorted((PROJECT / 'providers').glob('*/*')),
             *sorted((PROJECT / 'content').glob('*/extension.json'))]
    for path in paths:
        if path.is_file():
            digest.update(str(path.relative_to(PROJECT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def stop_service(directory):
    try: call({'op':'shutdown'})
    except (FileNotFoundError, ConnectionRefusedError): return
    deadline = time.monotonic() + 3
    while (directory / 'bridge.sock').exists() and time.monotonic() < deadline:
        time.sleep(.02)
    if (directory / 'bridge.sock').exists(): raise RuntimeError('Notes service did not finish shutting down.')
    # Socket removal can precede process exit. Wait for ownership to be released
    # before a replacement process tries to claim this runtime.
    with (directory / 'service.lock').open('a') as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline: raise RuntimeError('Notes service is still exiting.')
                time.sleep(.02)


def ensure():
    directory = runtime()
    with (directory / "start.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            current = call({"op": "ping"})
        except (FileNotFoundError, ConnectionRefusedError):
            current = None
        if current is not None and current.get('codeRevision') != code_revision():
            stop_service(directory)
            current = None
        if current is None:
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
        stop_service(directory)


def serve():
    directory = runtime()
    service_lock = (directory / 'service.lock').open('a')
    try:
        fcntl.flock(service_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        service_lock.close()
        return
    backend = Backend(directory)
    revision = code_revision()
    address = directory / "bridge.sock"
    address.unlink(missing_ok=True)

    class Handler(socketserver.StreamRequestHandler):
        def setup(self):
            super().setup()
            with self.server.activity_lock:
                self.server.connections += 1

        def finish(self):
            try: super().finish()
            finally:
                with self.server.activity_lock:
                    self.server.connections -= 1
                    self.server.last_activity = time.monotonic()

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
                    result = {"version": 1, "codeRevision": revision} if op in ("ping", "shutdown") else backend.dispatch(request)
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

        def __init__(self, *args):
            self.activity_lock = threading.Lock()
            self.connections = 0
            self.last_activity = time.monotonic()
            self.idle_shutdown = False
            super().__init__(*args)

        def service_actions(self):
            # Disable/removal releases the QML socket. Avoid leaving a daemon
            # behind; a later opening can warm it again through ensure().
            with self.activity_lock:
                idle = not self.connections and time.monotonic() - self.last_activity > 10
                if idle and not self.idle_shutdown:
                    self.idle_shutdown = True
                    threading.Thread(target=self.shutdown, daemon=True).start()

    with Server(str(address), Handler) as server:
        address.chmod(0o600)
        server.serve_forever(poll_interval=0.2)
    address.unlink(missing_ok=True)
    service_lock.close()

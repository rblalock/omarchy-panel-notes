"""Bounded output and lifetime for short-lived Linux subprocesses."""
import os
import selectors
import signal
import subprocess
import time


def bounded_output(command, *, limit, timeout, env=None, input=None):
    """Read at most limit + 1 bytes, rejecting overflow before returning data.

    stderr is discarded, never buffered. A new process group lets cleanup stop
    descendants holding pipe ends as well as the direct child. This is lifecycle
    control, not a sandbox for executable extensions.
    """
    deadline = time.monotonic() + timeout
    output = bytearray()
    process = subprocess.Popen(command, env=env, start_new_session=True,
                               stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            pending = memoryview(input) if input is not None else None
            if pending:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE)
            elif process.stdin is not None:
                process.stdin.close()
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                for key, _ in selector.select(remaining):
                    if key.fileobj is process.stdin:
                        try:
                            written = os.write(key.fd, pending[:65536])
                            pending = pending[written:]
                        except BlockingIOError:
                            continue
                        except BrokenPipeError:
                            pending = None
                        if not pending:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                    else:
                        try:
                            chunk = os.read(key.fd, min(65536, limit + 1 - len(output)))
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                            continue
                        output.extend(chunk)
                        if len(output) > limit:
                            raise ValueError(f"Command output exceeds {limit} bytes: {command[0]}")
        # EOF is not proof of process exit: a producer can close stdout then hang.
        # Leave the leader waitable until group cleanup, so its PID cannot be
        # reused between observing exit and signalling descendants.
        while os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(min(.01, remaining))
    finally:
        # SIGKILL needs no grace period and works even when SIGTERM is ignored.
        # Do this even if the leader exited: descendants may still be running.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        finally:
            process.wait()
            process.stdout.close()
            if process.stdin is not None:
                process.stdin.close()
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, command)
    return bytes(output)

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import patch

from core.process import bounded_output


class BoundedProcess(unittest.TestCase):
    def run_code(self, code, **kwargs):
        return bounded_output([sys.executable, '-c', code], **kwargs)

    def test_exact_limit_empty_output_and_overflow(self):
        self.assertEqual(self.run_code('pass', limit=0, timeout=2), b'')
        self.assertEqual(self.run_code("print('abcd', end='')", limit=4, timeout=2), b'abcd')
        with self.assertRaisesRegex(ValueError, 'exceeds 4 bytes'):
            self.run_code("print('abcde', end='')", limit=4, timeout=2)

    def test_nonzero_exit_discards_partial_output(self):
        with self.assertRaises(subprocess.CalledProcessError) as error:
            self.run_code("import os; os.write(1, b'partial'); exit(7)", limit=64, timeout=2)
        self.assertEqual(error.exception.returncode, 7)
        self.assertIsNone(error.exception.output)

    def test_large_bidirectional_input_does_not_deadlock(self):
        data = b'hello' * 100000
        result = self.run_code("import sys; sys.stdout.buffer.write(b'x'*100000); "
                               "sys.stdout.buffer.flush(); sys.stdout.buffer.write(sys.stdin.buffer.read())",
                               input=data, limit=len(data) + 100000, timeout=3)
        self.assertEqual(result, b'x' * 100000 + data)

    def test_timeout_with_open_pipe_and_after_stdout_closes(self):
        for code in ('import time; time.sleep(10)',
                     'import os, time; os.close(1); time.sleep(10)'):
            with self.subTest(code=code), self.assertRaises(subprocess.TimeoutExpired):
                self.run_code(code, limit=64, timeout=.2)

    def test_stderr_is_discarded_without_blocking_or_buffering(self):
        self.assertEqual(self.run_code("import os; [os.write(2, b'x'*65536) for _ in range(1024)]; "
                                       "os.write(1, b'ok')", limit=2, timeout=3), b'ok')

    def test_endless_image_producer_has_bounded_memory(self):
        limit = 25 * 1024 * 1024
        tracemalloc.start()
        try:
            started = time.monotonic()
            with self.assertRaisesRegex(ValueError, 'exceeds'):
                self.run_code("import os\nwhile True: os.write(1, b'x'*65536)", limit=limit, timeout=3)
            _, peak = tracemalloc.get_traced_memory()
            self.assertLess(peak, limit * 1.2, f'Unbounded memory: {peak} bytes')
            self.assertLess(time.monotonic() - started, 3)
        finally:
            tracemalloc.stop()

    def test_group_cleanup_on_overflow_timeout_and_exited_leader(self):
        # The child ignores SIGTERM, holds stdout, and records its PID before
        # producing. Even an already-exited leader must not leave it running.
        for mode in ('overflow', 'timeout', 'exited-leader'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                pidfile = Path(directory) / 'pids'
                code = f'''
import os, signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
leader = os.getpid()
child = os.fork()
if child:
    if {mode!r} == 'exited-leader': os._exit(0)
    time.sleep(20)
else:
    with open({str(pidfile)!r}, 'w') as stream: stream.write(f'{{leader}} {{os.getpid()}}')
    if {mode!r} == 'overflow':
        while True: os.write(1, b'x'*65536)
    time.sleep(20)
'''
                processes = []
                popen = subprocess.Popen
                def record(*args, **kwargs):
                    child = popen(*args, **kwargs)
                    processes.append(child)
                    return child
                try:
                    expected = ValueError if mode == 'overflow' else subprocess.TimeoutExpired
                    with patch('core.process.subprocess.Popen', side_effect=record), self.assertRaises(expected):
                        self.run_code(code, limit=16384, timeout=.5)
                    leader, child = map(int, pidfile.read_text().split())
                    self.assertIsNotNone(processes[0].returncode)
                    with self.assertRaises(ChildProcessError):
                        os.waitpid(leader, os.WNOHANG)  # Direct child was reaped.
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        try: state = Path(f'/proc/{child}/stat').read_text().split()[2]
                        except (FileNotFoundError, ProcessLookupError): break
                        if state == 'Z': break  # Terminated; init owns reaping descendants.
                        time.sleep(.01)
                    else: self.fail('Producer descendant survived cleanup')
                finally:
                    for process in processes:
                        try: os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                        process.wait()

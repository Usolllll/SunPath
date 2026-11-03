"""Start the existing SunPath services. No install, build, seed, or configuration changes."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
FRONTEND_URL = 'http://127.0.0.1:5173'
BACKEND_URL = 'http://127.0.0.1:8000'


class WindowsJob:
    """Kill service process trees when the launcher window is closed on Windows."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ('PerProcessUserTimeLimit', ctypes.c_longlong),
                ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', wintypes.DWORD),
                ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t),
                ('PriorityClass', wintypes.DWORD),
                ('SchedulingClass', wintypes.DWORD),
            ]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount',
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ('BasicLimitInformation', BasicLimits),
                ('IoInfo', IOCounters),
                ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t),
                ('PeakJobMemoryUsed', ctypes.c_size_t),
            ]

        self.ctypes = ctypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def add(self, process):
        handle = self.kernel.OpenProcess(0x0100 | 0x0001, False, process.pid)
        if not handle:
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, handle):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
        finally:
            self.kernel.CloseHandle(handle)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        if connection.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError(f'Port {port} is already in use. Stop the existing service and try again.')


def check_files():
    python = ROOT / 'backend' / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    vite = ROOT / 'frontend' / 'node_modules' / 'vite' / 'bin' / 'vite.js'
    for path in (python, vite, ROOT / 'backend' / '.env'):
        if not path.is_file():
            raise RuntimeError(f'Missing {path.relative_to(ROOT)}. Complete first-time setup in README.md; this launcher does not install or initialize anything.')
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js is not available on PATH. Install Node.js or restart your terminal after installation.')
    for port in (8000, 5173):
        check_port(port)
    return python, node, vite


def wait_ready(processes, stop):
    pending = {BACKEND_URL + '/api/health', FRONTEND_URL}
    deadline = time.monotonic() + 45
    # Bypass OS HTTP proxies for local readiness checks.
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while pending and time.monotonic() < deadline:
        if stop.is_set():
            return False
        for name, process in processes:
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited with code {process.returncode}. See the service output above.')
        for url in tuple(pending):
            try:
                with client.open(url, timeout=1) as response:
                    if response.status == 200:
                        pending.remove(url)
            except (urllib.error.URLError, OSError):
                pass
        if pending:
            stop.wait(.25)
    if pending:
        raise RuntimeError('Startup timed out: ' + ', '.join(sorted(pending)) + '. Check the output above and backend/.env (including database availability).')
    return True


def stop_services(processes, job):
    if job:
        job.close()
    for _, process in reversed(processes):
        if process.poll() is None:
            if os.name == 'nt':
                # Also handles a process started just before job assignment failed.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true', help='Do not open the browser automatically.')
    args = parser.parse_args()
    processes = []
    job = None
    stop = threading.Event()

    def request_stop(signum, frame):
        stop.set()

    def read_enter():
        try:
            input()
        except (EOFError, OSError):
            return
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    if os.name == 'nt':
        signal.signal(signal.SIGBREAK, request_stop)
    try:
        python, node, vite = check_files()
        if os.name == 'nt':
            job = WindowsJob()
        print('\nSunPath - starting existing backend and frontend (no install/build/seed).', flush=True)
        commands = [
            ('Backend', [str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], ROOT / 'backend'),
            ('Frontend', [node, str(vite), '--host', '127.0.0.1', '--port', '5173', '--strictPort'], ROOT / 'frontend'),
        ]
        for name, command, cwd in commands:
            options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
            process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, **options)
            processes.append((name, process))
            if job:
                job.add(process)
        print('Waiting for both services... Press Ctrl+C to cancel.', flush=True)
        if not wait_ready(processes, stop):
            return 0
        print(f'\nFrontend: {FRONTEND_URL}\nBackend:  {BACKEND_URL}\nAPI docs: {BACKEND_URL}/docs\n\nPress Enter or Ctrl+C to stop BOTH services. Closing this window also stops them on Windows.\n', flush=True)
        if not args.no_browser:
            try:
                webbrowser.open(FRONTEND_URL)
            except webbrowser.Error:
                print('Could not open a browser. Open the frontend URL manually.', flush=True)
        threading.Thread(target=read_enter, daemon=True).start()
        while not stop.wait(.5):
            for name, process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f'{name} stopped unexpectedly (exit {process.returncode}).')
        return 0
    except (OSError, RuntimeError) as error:
        print(f'\n[SunPath] {error}', file=sys.stderr, flush=True)
        return 1
    finally:
        if processes:
            print('\nStopping SunPath services...', flush=True)
        stop_services(processes, job)


if __name__ == '__main__':
    sys.exit(main())

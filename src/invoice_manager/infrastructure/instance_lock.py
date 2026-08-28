from __future__ import annotations

import ctypes
import os
from pathlib import Path


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._acquired = False

    def acquire(self) -> None:
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(os.getpid()).encode("ascii"))
                except BaseException:
                    os.close(fd)
                    self.path.unlink(missing_ok=True)
                    raise
                os.close(fd)
                self._acquired = True
                return
            except FileExistsError as exc:
                owner_pid = self._owner_pid()
                if owner_pid is not None and self._process_is_alive(owner_pid):
                    raise RuntimeError("another Invoicer V2 instance is already running") from exc
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    continue

    def _owner_pid(self) -> int | None:
        try:
            return int(self.path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return None

    @staticmethod
    def _process_is_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == 259
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except (OSError, ProcessLookupError):
            return False
        return True

    def release(self) -> None:
        if self._acquired:
            self._acquired = False
            self.path.unlink(missing_ok=True)

    def __enter__(self) -> InstanceLock:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

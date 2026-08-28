"""Single-instance lock using a Windows named mutex."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


class InstanceLock:
    """A Windows-only named mutex that prevents multiple application instances."""

    MUTEX_NAME = "Local\\InvoiceReceiptManager_SingleInstance"

    def __init__(self) -> None:
        self._handle: wintypes.HANDLE | None = None

    def acquire(self) -> bool:
        """Try to acquire the single-instance lock.

        Returns True if this instance now owns the lock, False if another
        instance is already running.
        """
        kernel32 = ctypes.windll.kernel32
        self._handle = kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
        if not self._handle:
            return False
        return ctypes.GetLastError() != 183  # ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> InstanceLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self.release()

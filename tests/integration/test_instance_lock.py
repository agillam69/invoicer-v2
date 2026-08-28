"""Tests for the Windows single-instance lock."""

from __future__ import annotations

import sys
import uuid

import pytest

if sys.platform == "win32":
    from invoice_manager.infrastructure.instance_lock import InstanceLock


def _test_name() -> str:
    return f"Local\\InvoiceReceiptManager_Test_{uuid.uuid4()}"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_instance_lock_acquired_and_released():
    lock = InstanceLock(_test_name())
    assert lock.acquire() is True
    lock.release()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_second_instance_cannot_acquire():
    name = _test_name()
    first = InstanceLock(name)
    assert first.acquire() is True
    try:
        second = InstanceLock(name)
        assert second.acquire() is False
    finally:
        first.release()

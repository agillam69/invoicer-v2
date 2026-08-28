"""Tests for the Windows single-instance lock."""

from __future__ import annotations

import sys

import pytest

if sys.platform == "win32":
    from invoice_manager.infrastructure.instance_lock import InstanceLock


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_instance_lock_acquired_and_released():
    lock = InstanceLock()
    assert lock.acquire() is True
    lock.release()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_second_instance_cannot_acquire():
    first = InstanceLock()
    assert first.acquire() is True
    try:
        second = InstanceLock()
        assert second.acquire() is False
    finally:
        first.release()

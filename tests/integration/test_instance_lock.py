from pathlib import Path

import pytest

from invoice_manager.infrastructure.instance_lock import InstanceLock


def test_stale_lock_is_reclaimed(tmp_path: Path) -> None:
    path = tmp_path / "invoicer.lock"
    path.write_text("0", encoding="ascii")
    lock = InstanceLock(path)
    lock.acquire()
    assert path.read_text(encoding="ascii") != "0"
    lock.release()
    assert not path.exists()


def test_live_lock_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "invoicer.lock"
    first = InstanceLock(path)
    second = InstanceLock(path)
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="another Invoicer V2 instance"):
            second.acquire()
    finally:
        first.release()

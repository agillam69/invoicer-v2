"""Application bootstrap and entry point."""

from __future__ import annotations

import sys

from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.infrastructure.logging_setup import get_logger, setup_logging


def main() -> int:
    """Launch the Invoice & Receipt Manager."""
    config = AppConfig()
    setup_logging(config.logs_dir)
    log = get_logger("invoice_manager.app")

    lock = None
    if sys.platform == "win32":
        from invoice_manager.infrastructure.instance_lock import InstanceLock

        lock = InstanceLock()
        if not lock.acquire():
            log.warning("Another instance is already running")
            return 0

    try:
        from PySide6.QtWidgets import QApplication

        from invoice_manager.ui.login import run_login_flow
        from invoice_manager.ui.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("Invoice & Receipt Manager")
        app.setApplicationVersion("0.1.0")

        current_user = run_login_flow(config)
        if not current_user:
            log.info("Login cancelled")
            return 0

        window = MainWindow(config, current_user)
        window.show()
        return app.exec()
    except Exception as exc:  # noqa: BLE001
        log.exception("Fatal error during startup: %s", exc)
        return 1
    finally:
        if lock is not None:
            lock.release()


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from invoice_manager.application.auth import UserService
from invoice_manager.config import AppPaths
from invoice_manager.infrastructure.instance_lock import InstanceLock
from invoice_manager.infrastructure.logging_setup import configure_logging
from invoice_manager.persistence.database import (
    create_database,
    initialise_database,
    session_factory,
)
from invoice_manager.ui.login import LoginDialog
from invoice_manager.ui.main_window import MainWindow


def main() -> int:
    paths = AppPaths.resolve().ensure()
    logger = configure_logging(paths.logs)
    lock = InstanceLock(paths.data / "invoicer.lock")
    try:
        lock.acquire()
    except RuntimeError as exc:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Invoicer V2", str(exc))
        return 1
    try:
        engine = create_database(f"sqlite:///{paths.database.as_posix()}")
        initialise_database(engine)
        factory = session_factory(engine)
        service = UserService()
        app = QApplication.instance() or QApplication(sys.argv)
        if os.environ.get("INVOICER_SMOKE_EXIT") == "1":
            QTimer.singleShot(500, app.quit)
        with factory() as session:
            if service.first_run_required(session):
                logger.info("First run requires administrator creation")
                window = MainWindow("Administrator setup required")
                window.show()
                return app.exec()
            dialog = LoginDialog(service, session)
            logged_in: list[object] = []
            dialog.authenticated.connect(logged_in.append)
            if dialog.exec() != LoginDialog.DialogCode.Accepted:
                return 0
            user = logged_in[0] if logged_in else None
            shell = MainWindow(getattr(user, "display_name", ""))
            shell.show()
            return app.exec()
    finally:
        lock.release()

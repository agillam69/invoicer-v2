"""Application entry point: prepare storage, sign in, then show the shell."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog
from sqlalchemy.orm import Session

from invoice_manager.config import AppPaths
from invoice_manager.infrastructure.logging_setup import (
    configure_logging,
    install_exception_hook,
)
from invoice_manager.persistence.database import (
    create_engine_for_path,
    create_session_factory,
    seed_reference_data,
)
from invoice_manager.persistence.schema import upgrade_to_head
from invoice_manager.ui.login import LoginDialog
from invoice_manager.ui.main_window import MainWindow


def bootstrap_storage(paths: AppPaths) -> Session:
    """Ensure directories, schema and reference data exist; return a session."""
    paths.ensure_directories()
    upgrade_to_head(paths.database_url())
    engine = create_engine_for_path(paths.database_path)
    session_factory = create_session_factory(engine)
    session = session_factory()
    seed_reference_data(session)
    session.commit()
    return session


def main(argv: list[str] | None = None) -> int:
    paths = AppPaths.resolve()
    logger = configure_logging(paths.logs_dir)
    install_exception_hook(logger)
    logger.info("Starting Invoicer V2 with data root %s", paths.root)

    app = QApplication(argv if argv is not None else sys.argv)
    session = bootstrap_storage(paths)

    login = LoginDialog(session)
    if login.exec() != QDialog.DialogCode.Accepted or login.authenticated_user is None:
        logger.info("Sign-in cancelled; exiting")
        session.close()
        return 1

    window = MainWindow(login.authenticated_user, paths)
    window.show()
    exit_code = app.exec()
    session.close()
    logger.info("Invoicer V2 exited with code %s", exit_code)
    return exit_code

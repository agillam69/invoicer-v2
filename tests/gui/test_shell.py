"""GUI tests for the login dialog and application shell."""

from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from PySide6.QtWidgets import QLabel, QLineEdit, QMainWindow
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session

from invoice_manager.application.auth_service import AuthService
from invoice_manager.config import AppPaths
from invoice_manager.ui.login import LoginDialog
from invoice_manager.ui.main_window import MENU_ITEMS, NAV_SECTIONS, MainWindow

pytestmark = [pytest.mark.gui]

PASSWORD = "correct-horse-battery"


def _auth(session: Session, hasher: PasswordHasher) -> AuthService:
    return AuthService(session, hasher=hasher, failed_login_delay_seconds=0.0)


def _field(dialog: LoginDialog, name: str) -> QLineEdit:
    field = dialog.findChild(QLineEdit, name)
    assert isinstance(field, QLineEdit)
    return field


def _error_text(dialog: LoginDialog) -> str:
    label = dialog.findChild(QLabel, "errorMessage")
    assert isinstance(label, QLabel)
    return label.text()


def test_new_database_offers_first_run_setup(
    qtbot: QtBot, session: Session, hasher: PasswordHasher
) -> None:
    dialog = LoginDialog(session, auth=_auth(session, hasher))
    qtbot.addWidget(dialog)

    assert dialog.is_first_run is True
    assert dialog.windowTitle() == "Create Administrator"

    _field(dialog, "usernameField").setText("alex")
    _field(dialog, "displayNameField").setText("Alexander Gillam")
    _field(dialog, "passwordField").setText(PASSWORD)
    _field(dialog, "confirmPasswordField").setText(PASSWORD)
    dialog.submit()

    assert dialog.authenticated_user is not None
    assert dialog.authenticated_user.username == "alex"


def test_first_run_rejects_mismatched_confirmation(
    qtbot: QtBot, session: Session, hasher: PasswordHasher
) -> None:
    dialog = LoginDialog(session, auth=_auth(session, hasher))
    qtbot.addWidget(dialog)

    _field(dialog, "usernameField").setText("alex")
    _field(dialog, "passwordField").setText(PASSWORD)
    _field(dialog, "confirmPasswordField").setText("something-else")
    dialog.submit()

    assert dialog.authenticated_user is None
    assert "do not match" in _error_text(dialog)


def test_existing_user_signs_in(qtbot: QtBot, session: Session, hasher: PasswordHasher) -> None:
    auth = _auth(session, hasher)
    auth.create_first_admin("alex", PASSWORD)
    session.commit()

    dialog = LoginDialog(session, auth=auth)
    qtbot.addWidget(dialog)
    assert dialog.is_first_run is False
    assert dialog.windowTitle() == "Sign In"

    _field(dialog, "usernameField").setText("alex")
    _field(dialog, "passwordField").setText(PASSWORD)
    dialog.submit()

    assert dialog.authenticated_user is not None


def test_bad_password_shows_error_and_clears_field(
    qtbot: QtBot, session: Session, hasher: PasswordHasher
) -> None:
    auth = _auth(session, hasher)
    auth.create_first_admin("alex", PASSWORD)
    session.commit()

    dialog = LoginDialog(session, auth=auth)
    qtbot.addWidget(dialog)
    _field(dialog, "usernameField").setText("alex")
    _field(dialog, "passwordField").setText("a-wrong-password")
    dialog.submit()

    assert dialog.authenticated_user is None
    assert _error_text(dialog) != ""
    assert _field(dialog, "passwordField").text() == ""


def test_shell_shows_all_navigation_sections(
    qtbot: QtBot, session: Session, hasher: PasswordHasher, app_paths: AppPaths
) -> None:
    user = _auth(session, hasher).create_first_admin("alex", PASSWORD)

    window = MainWindow(user, app_paths)
    qtbot.addWidget(window)

    assert isinstance(window, QMainWindow)
    assert [section.title for section in NAV_SECTIONS] == [
        "Dashboard",
        "New Invoice",
        "Invoices",
        "Payments & Receipts",
        "Clients",
        "Products & Services",
        "Income & Expenses",
        "Reports",
    ]
    assert window.current_section_title() == "Dashboard"


def test_shell_navigation_switches_pages(
    qtbot: QtBot, session: Session, hasher: PasswordHasher, app_paths: AppPaths
) -> None:
    user = _auth(session, hasher).create_first_admin("alex", PASSWORD)
    window = MainWindow(user, app_paths)
    qtbot.addWidget(window)

    for index, section in enumerate(NAV_SECTIONS):
        window.select_section(index)
        assert window.current_section_title() == section.title


def test_shell_menus_cover_every_required_entry(
    qtbot: QtBot, session: Session, hasher: PasswordHasher, app_paths: AppPaths
) -> None:
    user = _auth(session, hasher).create_first_admin("alex", PASSWORD)
    window = MainWindow(user, app_paths)
    qtbot.addWidget(window)

    menu_bar = window.menuBar()
    menu_titles = [action.text() for action in menu_bar.actions()]
    assert menu_titles == list(MENU_ITEMS)

    entries = {
        action.text()
        for menu_action in menu_bar.actions()
        if menu_action.menu() is not None
        for action in menu_action.menu().actions()
    }
    assert entries == {entry for group in MENU_ITEMS.values() for entry in group}


def test_status_bar_shows_user_and_data_location(
    qtbot: QtBot, session: Session, hasher: PasswordHasher, app_paths: AppPaths
) -> None:
    user = _auth(session, hasher).create_first_admin("alex", PASSWORD)
    window = MainWindow(user, app_paths)
    qtbot.addWidget(window)

    labels = [label.text() for label in window.statusBar().findChildren(QLabel)]
    assert any("alex" in text for text in labels)
    assert any(str(app_paths.root) in text for text in labels)

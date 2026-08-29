"""Tests for application database configuration."""

from __future__ import annotations

import pytest
from sqlalchemy import URL

from invoice_manager.infrastructure.config import AppConfig


def test_database_url_defaults_to_local_sqlite(tmp_path):
    config = AppConfig(tmp_path)
    assert config.database_mode() == "sqlite"
    assert str(config.database_url()).startswith("sqlite:///")


def test_mysql_database_url_uses_environment_password(tmp_path, monkeypatch):
    config = AppConfig(tmp_path)
    config.configure_database(
        {
            "database_mode": "mysql",
            "mysql_host": "db.example.test",
            "mysql_port": 3307,
            "mysql_database": "invoices",
            "mysql_user": "invoice_user",
            "mysql_password_env": "TEST_INVOICE_DB_PASSWORD",
        }
    )
    monkeypatch.setenv("TEST_INVOICE_DB_PASSWORD", "secret:/value")

    url = config.database_url()
    assert isinstance(url, URL)
    assert url.drivername == "mysql+pymysql"
    assert url.host == "db.example.test"
    assert url.port == 3307
    assert url.database == "invoices"
    assert url.username == "invoice_user"
    assert url.password == "secret:/value"
    assert "secret:/value" not in config.config_path.read_text(encoding="utf-8")


def test_mysql_database_url_requires_password_environment_variable(tmp_path):
    config = AppConfig(tmp_path)
    config.configure_database(
        {
            "database_mode": "mysql",
            "mysql_password_env": "MISSING_INVOICE_DB_PASSWORD",
        }
    )
    with pytest.raises(RuntimeError, match="MISSING_INVOICE_DB_PASSWORD"):
        config.database_url()

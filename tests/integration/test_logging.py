from pathlib import Path

from invoice_manager.infrastructure.logging_setup import configure_logging


def test_rotating_log_is_created(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)
    logger.info("safe event")
    for handler in logger.handlers:
        handler.flush()
    assert (tmp_path / "app.log").exists()

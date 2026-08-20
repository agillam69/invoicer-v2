import pytest

from invoice_manager.ui.main_window import DESTINATIONS, MainWindow


@pytest.mark.gui
def test_shell_opens_with_all_eight_destinations(qtbot) -> None:
    window = MainWindow("Alexander Gillam")
    qtbot.addWidget(window)
    window.show()
    assert window.nav.count() == 8
    assert [window.nav.item(i).text() for i in range(8)] == list(DESTINATIONS)

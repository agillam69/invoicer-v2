import pytest

from invoice_manager.ui.main_window import DESTINATIONS, MainWindow


@pytest.mark.gui
def test_shell_opens_with_all_eight_destinations(qtbot) -> None:
    window = MainWindow("Alexander Gillam")
    qtbot.addWidget(window)
    window.show()
    assert window.nav.count() == 8
    assert [window.nav.item(i).text() for i in range(8)] == list(DESTINATIONS)
    actions = {action.text(): action for action in window.menuBar().actions()[0].menu().actions()}
    assert actions["About"].isEnabled()
    assert actions["App Log"].isEnabled()
    assert not actions["Settings"].isEnabled()

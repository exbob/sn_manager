from PySide6.QtWidgets import QApplication

from sn_manager.gui.fonts import apply_ui_font


def test_apply_ui_font_returns_str_or_none(qapp: QApplication) -> None:
    result = apply_ui_font(qapp)
    assert result is None or isinstance(result, str)
    if result is not None:
        assert qapp.font().family() == result

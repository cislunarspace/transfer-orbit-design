"""tests for src.view.ui_settings -- 界面设置持久化与全局样式表。"""

from __future__ import annotations

import pytest


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


def _make_qsettings(tmp_path, name: str = "ui.ini"):
    from PyQt6.QtCore import QSettings

    # 用独立 ini 文件隔离，不污染真实设置
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


class TestUISettingsPersistence:
    """QSettings 保存/加载往返。"""

    def test_roundtrip(self, qapp, tmp_path):
        from src.view.ui_settings import UISettings, load_ui_settings, save_ui_settings

        qs = _make_qsettings(tmp_path)
        settings = UISettings(font_size=14, theme="dark")
        save_ui_settings(qs, settings)
        assert load_ui_settings(qs) == settings

    def test_missing_keys_use_defaults(self, qapp, tmp_path):
        from src.view.ui_settings import UISettings, load_ui_settings

        assert load_ui_settings(_make_qsettings(tmp_path)) == UISettings()

    def test_bad_values_fall_back_to_defaults(self, qapp, tmp_path):
        from src.view.ui_settings import UISettings, load_ui_settings

        qs = _make_qsettings(tmp_path)
        qs.setValue("ui/font_size", "abc")
        qs.setValue("ui/theme", "blue")
        assert load_ui_settings(qs) == UISettings()

    def test_font_size_clamped_to_range(self, qapp, tmp_path):
        from src.view.ui_settings import (
            MAX_FONT_SIZE,
            MIN_FONT_SIZE,
            load_ui_settings,
        )

        qs = _make_qsettings(tmp_path, "big.ini")
        qs.setValue("ui/font_size", 99)
        assert load_ui_settings(qs).font_size == MAX_FONT_SIZE

        qs = _make_qsettings(tmp_path, "small.ini")
        qs.setValue("ui/font_size", 1)
        assert load_ui_settings(qs).font_size == MIN_FONT_SIZE


class TestStylesheet:
    """全局样式表：两主题都覆盖分隔条与运行/停止按钮，深色另加底色。"""

    def test_both_themes_cover_handles_and_buttons(self, qapp):
        from src.view.ui_settings import build_app_stylesheet

        for theme in ("light", "dark"):
            qss = build_app_stylesheet(theme)
            assert "QSplitter::handle" in qss
            assert "QPushButton#runButton" in qss
            assert "QPushButton#stopButton" in qss

    def test_dark_theme_sets_dark_background(self, qapp):
        from src.view.ui_settings import build_app_stylesheet

        assert "#2b2b2b" in build_app_stylesheet("dark")
        assert "#2b2b2b" not in build_app_stylesheet("light")

    def test_unknown_theme_treated_as_light(self, qapp):
        from src.view.ui_settings import build_app_stylesheet

        assert build_app_stylesheet("weird") == build_app_stylesheet("light")


class TestApplyUISettings:
    """应用到 QApplication：全局字号生效，主题 rcParams 切到 matplotlib。"""

    def test_font_size_applied_and_restored(self, qapp):
        from src.view.ui_settings import UISettings, apply_ui_settings

        original_size = qapp.font().pointSize()
        try:
            apply_ui_settings(qapp, UISettings(font_size=13, theme="light"))
            assert qapp.font().pointSize() == 13
        finally:
            apply_ui_settings(qapp, UISettings(font_size=original_size, theme="light"))

    def test_dark_theme_updates_mpl_rcparams(self, qapp):
        import matplotlib

        from src.view.ui_settings import UISettings, apply_ui_settings

        apply_ui_settings(qapp, UISettings(theme="dark"))
        assert matplotlib.rcParams["figure.facecolor"] == "#2b2b2b"
        apply_ui_settings(qapp, UISettings(theme="light"))
        assert matplotlib.rcParams["figure.facecolor"] == "white"

# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false
"""settings_schema — 设置 schema 结构的单元测试。"""


class TestSettingsSchema:
    def test_importable(self):
        from tod.gui.settings_schema import SETTINGS_SCHEMA
        assert isinstance(SETTINGS_SCHEMA, list)
        assert len(SETTINGS_SCHEMA) > 0

    def test_has_theme_item(self):
        from tod.gui.settings_schema import SETTINGS_SCHEMA
        keys = [item.key for item in SETTINGS_SCHEMA]
        assert "theme" in keys

    def test_has_plot_font_items(self):
        from tod.gui.settings_schema import SETTINGS_SCHEMA
        keys = [item.key for item in SETTINGS_SCHEMA]
        assert "plot_font_title" in keys
        assert "plot_font_label" in keys
        assert "plot_font_tick" in keys

    def test_theme_choices(self):
        from tod.gui.settings_schema import SETTINGS_SCHEMA
        theme_item = next(item for item in SETTINGS_SCHEMA if item.key == "theme")
        assert "light" in theme_item.choices
        assert "dark" in theme_item.choices
        assert "system" in theme_item.choices

    def test_all_items_have_key_and_label(self):
        from tod.gui.settings_schema import SETTINGS_SCHEMA
        for item in SETTINGS_SCHEMA:
            assert item.key, f"item missing key: {item}"
            assert item.label, f"item missing label: {item}"

import altair as alt
import pytest

from dysonsphere.theme import _load_style_overrides, create_config, theme


@pytest.fixture(autouse=True)
def reset_theme():
    theme()
    yield
    theme()


class TestThemeDefaults:
    def test_options_populated(self):
        opts = alt.theme.options
        assert "chartWidth" in opts
        assert "chartHeight" in opts
        assert "axisWidth" in opts
        assert "markSize" in opts
        assert "markStrokeWidth" in opts
        assert "closed" in opts
        assert "darkmode" in opts

    def test_mark_size_default(self):
        theme(chartWidth=200, chartHeight=100)
        assert alt.theme.options["markSize"] == pytest.approx(10.0)

    def test_mark_size_uses_min_dimension(self):
        theme(chartWidth=50, chartHeight=200)
        assert alt.theme.options["markSize"] == pytest.approx(5.0)

    def test_mark_stroke_width_defaults_to_axis_width(self):
        theme(axisWidth=0.5)
        assert alt.theme.options["markStrokeWidth"] == pytest.approx(0.5)

    def test_mark_stroke_width_explicit(self):
        theme(axisWidth=0.5, markStrokeWidth=1.0)
        assert alt.theme.options["markStrokeWidth"] == pytest.approx(1.0)

    def test_closed_defaults_false(self):
        theme()
        assert alt.theme.options["closed"] is False

    def test_view_fill_auto_closes(self):
        theme(viewFill="#eeeeee")
        assert alt.theme.options["closed"] is True

    def test_closed_explicit_overrides_view_fill(self):
        theme(viewFill="#eeeeee", closed=False)
        assert alt.theme.options["closed"] is False

    def test_chart_fill_defaults_white_light_mode(self):
        theme(darkmode=False)
        assert alt.theme.options["chartFill"] == "white"

    def test_chart_fill_none_in_dark_mode(self):
        theme(darkmode=True)
        assert alt.theme.options["chartFill"] is None

    def test_options_reset_on_each_call(self):
        theme(grid=True)
        assert alt.theme.options["grid"] is True
        theme()
        assert alt.theme.options["grid"] is False

    def test_palette_string_resolved_to_list(self):
        theme(palette="blues")
        from dysonsphere.palettes import colors
        assert alt.theme.options["palette"] == colors["blues"]

    def test_palette_unknown_string_passed_through(self):
        theme(palette="tableau10")
        assert alt.theme.options["palette"] == "tableau10"


class TestThemeRegistration:
    def test_theme_registered_as_dysonsphere(self):
        assert "dysonsphere" in alt.theme.names()

    def test_theme_is_active(self):
        theme()
        assert alt.theme.active == "dysonsphere"

    def test_unknown_kwarg_raises(self):
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            theme(notAParam=42)  # type: ignore[call-arg]


class TestStyleLoading:
    def test_default_block_applied(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[default]\nfontSize = 5\n", encoding="utf-8"
        )
        overrides = _load_style_overrides(None)
        assert overrides["fontSize"] == 5

    def test_named_style_applied(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[nih]\nfontSize = 6\naxisWidth = 0.5\n", encoding="utf-8"
        )
        overrides = _load_style_overrides("nih")
        assert overrides["fontSize"] == 6
        assert overrides["axisWidth"] == pytest.approx(0.5)

    def test_named_style_overrides_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[default]\nfontSize = 5\n[nih]\nfontSize = 6\n", encoding="utf-8"
        )
        overrides = _load_style_overrides("nih")
        assert overrides["fontSize"] == 6

    def test_explicit_kwarg_overrides_style(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[nih]\nfontSize = 6\n", encoding="utf-8"
        )
        theme(style="nih", fontSize=9)
        assert alt.theme.options["fontSize"] == 9

    def test_missing_style_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[nih]\nfontSize = 6\n", encoding="utf-8")
        with pytest.raises(ValueError, match="'missing'"):
            _load_style_overrides("missing")

    def test_unknown_toml_key_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[nih]\nnotAParam = 99\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Unknown theme parameter"):
            _load_style_overrides("nih")

    def test_no_config_file_no_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        overrides = _load_style_overrides(None)
        assert overrides == {}

    def test_builtin_style_no_config_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        overrides = _load_style_overrides("nih")
        assert overrides["fontSize"] == 6
        assert overrides["axisWidth"] == pytest.approx(0.5)

    def test_config_overrides_builtin_style(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[nih]\nfontSize = 9\n", encoding="utf-8"
        )
        overrides = _load_style_overrides("nih")
        assert overrides["fontSize"] == 9
        assert overrides["axisWidth"] == pytest.approx(0.5)  # from built-in preset


class TestCreateConfig:
    def test_creates_file(self, tmp_path):
        create_config(tmp_path)
        assert (tmp_path / "dysonsphere.toml").exists()

    def test_contains_builtin_style_names(self, tmp_path):
        create_config(tmp_path)
        content = (tmp_path / "dysonsphere.toml").read_text()
        assert "[nih]" in content
        assert "[notebook]" in content
        assert "[presentation]" in content
        assert "[my_style]" in content

    def test_does_not_overwrite(self, tmp_path):
        existing = tmp_path / "dysonsphere.toml"
        existing.write_text("sentinel", encoding="utf-8")
        create_config(tmp_path)
        assert existing.read_text() == "sentinel"

    def test_defaults_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        create_config()
        assert (tmp_path / "dysonsphere.toml").exists()

    def test_persist_flag_writes_to_xdg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        create_config(persist=True)
        assert (tmp_path / "dysonsphere" / "dysonsphere.toml").exists()


class TestCustomPalettes:
    def test_custom_palette_loaded(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            '[palettes]\nmy_pal = ["#ff0000", "#00ff00", "#0000ff"]\n', encoding="utf-8"
        )
        theme()
        from dysonsphere.palettes import colors
        assert "my_pal" in colors
        assert colors["my_pal"] == ["#ff0000", "#00ff00", "#0000ff"]

    def test_custom_palette_cleared_on_theme_reset(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            '[palettes]\nmy_pal = ["#ff0000"]\n', encoding="utf-8"
        )
        theme()
        from dysonsphere.palettes import colors
        assert "my_pal" in colors
        monkeypatch.chdir("/")
        theme()
        assert "my_pal" not in colors

    def test_empty_palette_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[palettes]\nbad = []\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="non-empty"):
            theme()

    def test_non_string_values_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[palettes]\nbad = [1, 2, 3]\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="strings"):
            theme()

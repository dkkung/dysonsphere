import altair as alt
import pytest

from dysonsphere.theme import (
    _dysonsphere_theme,
    _load_style_overrides,
    create_config,
    theme,
)


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

    def test_secondary_font_size_default(self):
        theme()  # fontSize=7
        assert alt.theme.options["secondaryFontSize"] == 6  # fontSize - 1

    def test_secondary_font_size_scales(self):
        theme(fontSize=12)
        assert alt.theme.options["secondaryFontSize"] == 11

    def test_secondary_font_size_explicit(self):
        theme(fontSize=12, secondaryFontSize=8)
        assert alt.theme.options["secondaryFontSize"] == 8

    def test_secondary_font_size_floored_at_smallest(self):
        theme(fontSize=5)  # fontSize - 1 = 4, but floored to smallestFontSize (5)
        assert alt.theme.options["secondaryFontSize"] == 5

    def test_secondary_font_size_escape_hatch_below_floor(self):
        theme(fontSize=3)  # fontSize < smallest → floor bypassed, tier follows the base
        assert alt.theme.options["secondaryFontSize"] == 2  # max(1, 3 - 1)

    def test_smallest_font_size_default(self):
        theme()
        assert alt.theme.options["smallestFontSize"] == 5  # fixed floor, not derived

    def test_sig_figs_default(self):
        theme()
        assert alt.theme.options["sigFigs"] == 3

    def test_sig_figs_override(self):
        theme(sigFigs=2)
        assert alt.theme.options["sigFigs"] == 2

    def test_smallest_font_size_custom_int(self):
        theme(smallestFontSize=4)
        assert alt.theme.options["smallestFontSize"] == 4
        assert alt.theme.options["fontSize"] == 7  # int does not minimize

    def test_smallest_font_size_true_minimizes_and_floors_secondary(self):
        theme(smallestFontSize=True)
        assert alt.theme.options["fontSize"] == 5  # base dropped to the floor
        assert alt.theme.options["secondaryFontSize"] == 5  # tier floored too, not 4
        assert alt.theme.options["smallestFontSize"] == 5

    def test_smallest_font_size_false_is_retrievable_int(self):
        theme(smallestFontSize=False)
        assert alt.theme.options["smallestFontSize"] == 5
        assert alt.theme.options["fontSize"] == 7  # no minimize

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


class TestRangePalettes:
    def _scheme(self, kind):
        return _dysonsphere_theme()["config"]["range"][kind]["scheme"]

    def test_defaults_unchanged(self):
        from dysonsphere.palettes import colors

        theme()
        assert self._scheme("category") == colors["blues"][::2]
        assert self._scheme("diverging") == colors["redsblues"]

    def test_per_type_override_by_name(self):
        from dysonsphere.palettes import colors

        theme(categoryPalette="reds")
        assert self._scheme("category") == colors["reds"]
        assert self._scheme("diverging") == colors["redsblues"]  # others untouched

    def test_per_type_override_raw_list(self):
        theme(rampPalette=["#ffffff", "#000000"])
        assert self._scheme("ramp") == ["#ffffff", "#000000"]

    def test_per_type_vega_scheme_passthrough(self):
        theme(heatmapPalette="viridis")
        assert self._scheme("heatmap") == "viridis"

    def test_global_palette_wins_over_per_type(self):
        from dysonsphere.palettes import colors

        theme(palette="greens", categoryPalette="reds")
        assert self._scheme("category") == colors["greens"]

    def test_global_palette_still_fills_all(self):
        from dysonsphere.palettes import colors

        theme(palette="greens")
        for kind in ("category", "diverging", "heatmap", "ordinal", "ramp"):
            assert self._scheme(kind) == colors["greens"]

    def test_per_type_from_custom_palette(self, tmp_path, monkeypatch):
        from dysonsphere.palettes import colors

        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text('[palettes]\nmine = ["#111111", "#222222"]\n', encoding="utf-8")
        theme(categoryPalette="mine")
        assert self._scheme("category") == ["#111111", "#222222"]
        theme()  # reset custom palette state
        assert self._scheme("category") == colors["blues"][::2]

    def test_per_type_via_toml(self, tmp_path, monkeypatch):
        from dysonsphere.palettes import colors

        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text('[default]\ndivergingPalette = "greensblues"\n', encoding="utf-8")
        theme()
        assert self._scheme("diverging") == colors["greensblues"]


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
        (tmp_path / "dysonsphere.toml").write_text("[default]\nfontSize = 5\n", encoding="utf-8")
        overrides = _load_style_overrides(None)
        assert overrides["fontSize"] == 5

    def test_named_style_applied(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[my_style]\nfontSize = 6\naxisWidth = 0.5\n", encoding="utf-8")
        overrides = _load_style_overrides("my_style")
        assert overrides["fontSize"] == 6
        assert overrides["axisWidth"] == pytest.approx(0.5)

    def test_named_style_overrides_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            "[default]\nfontSize = 5\n[my_style]\nfontSize = 6\n", encoding="utf-8"
        )
        overrides = _load_style_overrides("my_style")
        assert overrides["fontSize"] == 6

    def test_explicit_kwarg_overrides_style(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[my_style]\nfontSize = 6\n", encoding="utf-8")
        theme(style="my_style", fontSize=9)
        assert alt.theme.options["fontSize"] == 9

    def test_missing_style_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[my_style]\nfontSize = 6\n", encoding="utf-8")
        with pytest.raises(ValueError, match="'missing'"):
            _load_style_overrides("missing")

    def test_unknown_toml_key_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[my_style]\nnotAParam = 99\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Unknown theme parameter"):
            _load_style_overrides("my_style")

    def test_no_config_file_no_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        overrides = _load_style_overrides(None)
        assert overrides == {}

    def test_builtin_style_no_config_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        overrides = _load_style_overrides("notebook")
        assert overrides["fontSize"] == 18
        assert overrides["chartWidth"] == 900

    def test_config_overrides_builtin_style(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[notebook]\nfontSize = 9\n", encoding="utf-8")
        overrides = _load_style_overrides("notebook")
        assert overrides["fontSize"] == 9
        assert overrides["chartWidth"] == 900  # from built-in preset


class TestCreateConfig:
    def test_creates_file(self, tmp_path):
        create_config(tmp_path)
        assert (tmp_path / "dysonsphere.toml").exists()

    def test_contains_builtin_style_names(self, tmp_path):
        create_config(tmp_path)
        content = (tmp_path / "dysonsphere.toml").read_text()
        assert "[nih]" not in content
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
        (tmp_path / "dysonsphere.toml").write_text('[palettes]\nmy_pal = ["#ff0000"]\n', encoding="utf-8")
        theme()
        from dysonsphere.palettes import colors

        assert "my_pal" in colors
        monkeypatch.chdir("/")
        theme()
        assert "my_pal" not in colors

    def test_empty_palette_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[palettes]\nbad = []\n", encoding="utf-8")
        with pytest.raises(ValueError, match="non-empty"):
            theme()

    def test_non_string_values_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[palettes]\nbad = [1, 2, 3]\n", encoding="utf-8")
        with pytest.raises(ValueError, match="strings"):
            theme()


class TestCornerRadius:
    def test_false_default_omits_key_from_bar(self):
        theme()
        spec = _dysonsphere_theme()
        assert "cornerRadiusEnd" not in spec["config"]["bar"]

    def test_false_default_omits_key_from_rect(self):
        theme()
        spec = _dysonsphere_theme()
        assert "cornerRadius" not in spec["config"]["rect"]

    def test_true_resolves_to_min_dimension_over_100(self):
        theme(chartWidth=200, chartHeight=300, cornerRadius=True)
        assert alt.theme.options["cornerRadius"] == pytest.approx(2.0)

    def test_true_applies_corner_radius_end_to_bar(self):
        theme(chartWidth=100, chartHeight=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["bar"]["cornerRadiusEnd"] == pytest.approx(1.0)

    def test_true_applies_corner_radius_to_rect(self):
        theme(chartWidth=100, chartHeight=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["rect"]["cornerRadius"] == pytest.approx(1.0)

    def test_explicit_float_used_as_is(self):
        theme(cornerRadius=3.0)
        assert alt.theme.options["cornerRadius"] == pytest.approx(3.0)
        spec = _dysonsphere_theme()
        assert spec["config"]["bar"]["cornerRadiusEnd"] == pytest.approx(3.0)
        assert spec["config"]["rect"]["cornerRadius"] == pytest.approx(3.0)

    def test_true_applies_corner_radius_to_boxplot_box(self):
        theme(chartWidth=100, chartHeight=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["boxplot"]["box"]["cornerRadius"] == pytest.approx(1.0)

    def test_false_default_omits_key_from_boxplot_box(self):
        theme()
        spec = _dysonsphere_theme()
        assert "cornerRadius" not in spec["config"]["boxplot"]["box"]

    def test_true_applies_corner_radius_to_arc(self):
        theme(chartWidth=100, chartHeight=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["arc"]["cornerRadius"] == pytest.approx(1.0)

    def test_false_default_omits_key_from_arc(self):
        theme()
        spec = _dysonsphere_theme()
        assert "cornerRadius" not in spec["config"]["arc"]

    def test_arc_inner_radius_scales_with_chart_size(self):
        theme(chartWidth=100, chartHeight=100)
        spec = _dysonsphere_theme()
        assert spec["config"]["arc"]["innerRadius"] == pytest.approx(25.0)

    def test_arc_inner_radius_uses_smaller_dimension(self):
        theme(chartWidth=80, chartHeight=200)
        spec = _dysonsphere_theme()
        assert spec["config"]["arc"]["innerRadius"] == pytest.approx(20.0)

    def test_arc_pad_angle(self):
        theme()
        spec = _dysonsphere_theme()
        assert spec["config"]["arc"]["padAngle"] == pytest.approx(0.03)


class TestTitleConfig:
    def test_title_anchor_is_middle(self):
        theme()
        spec = _dysonsphere_theme()
        assert spec["config"]["title"]["anchor"] == "middle"

    def test_title_frame_is_group(self):
        theme()
        spec = _dysonsphere_theme()
        assert spec["config"]["title"]["frame"] == "group"

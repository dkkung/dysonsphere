import hashlib
import json
from typing import Any, cast

import altair as alt
import pytest

from dysonsphere.palettes import colors
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
        assert "width" in opts
        assert "height" in opts
        assert "axisWidth" in opts
        assert "markSize" in opts
        assert "markStrokeWidth" in opts
        assert "closed" in opts
        assert "dark" in opts

    def test_default_font_is_fallback_stack(self):
        # The default font must be a fallback stack, with the Helvetica Neue *family*
        # name first (so resvg resolves the italic face) and the PostScript name
        # "HelveticaNeue" plus generic fallbacks after it (so a macOS/vl-convert combo
        # that fails to match the spaced family name degrades to Helvetica Neue rather
        # than plain Helvetica). A regression here silently changes the font in exports.
        theme()
        font = alt.theme.options["font"]
        families = [f.strip() for f in font.split(",")]
        assert families[0] == "Helvetica Neue"
        assert "HelveticaNeue" in families
        assert families[-1] == "sans-serif"

    def test_default_font_size(self):
        theme()
        assert alt.theme.options["fontSize"] == 6

    def test_default_tick_size(self):
        theme()
        assert alt.theme.options["tickSize"] == pytest.approx(3.0)
        assert _dysonsphere_theme()["config"]["axis"]["tickSize"] == pytest.approx(3.0)

    def test_explicit_tick_size(self):
        theme(tickSize=2.25)
        assert alt.theme.options["tickSize"] == pytest.approx(2.25)
        assert _dysonsphere_theme()["config"]["axis"]["tickSize"] == pytest.approx(2.25)

    def test_mark_size_default(self):
        theme(width=200, height=100)
        assert alt.theme.options["markSize"] == pytest.approx(10.0)

    def test_mark_fill_default_follows_mode_live(self):
        from dysonsphere.theme import _opt

        theme(dark=False)
        assert alt.theme.options["markFill"] == "#DBDBDB"
        assert _opt("markFill") == "#DBDBDB"
        assert _dysonsphere_theme()["config"]["point"]["fill"] == "#DBDBDB"
        alt.theme.options["dark"] = True
        assert _opt("markFill") == "#9D9D9D"
        config = _dysonsphere_theme()["config"]
        assert config["point"]["fill"] == "#9D9D9D"
        assert config["bar"]["fill"] == "#9D9D9D"
        assert config["area"]["fill"] == "#9D9D9D"
        assert config["arc"]["fill"] == "#9D9D9D"
        assert config["circle"]["fill"] == "white"
        theme(dark=True)
        assert alt.theme.options["markFill"] == "#9D9D9D"

    @pytest.mark.parametrize("value", ["#DBDBDB", "#9D9D9D", "tomato"])
    def test_explicit_mark_fill_is_pinned_across_mode_toggle(self, value):
        from dysonsphere.theme import _opt

        theme(markFill=value)
        alt.theme.options["dark"] = True
        assert _opt("markFill") == value
        assert _dysonsphere_theme()["config"]["point"]["fill"] == value

    def test_configured_mark_fill_is_pinned(self, tmp_path, monkeypatch):
        from dysonsphere.theme import _opt

        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text('[default]\nmarkFill = "#DBDBDB"\n', encoding="utf-8")
        theme(dark=True)
        assert _opt("markFill") == "#DBDBDB"
        assert _dysonsphere_theme()["config"]["point"]["fill"] == "#DBDBDB"

    @pytest.mark.parametrize("stops", [["#123456"], ["#123456", "#654321"]])
    def test_automatic_mark_fill_ignores_custom_greys(self, stops, tmp_path, monkeypatch):
        from dysonsphere.theme import _opt

        monkeypatch.chdir(tmp_path)
        values = ", ".join(f'"{value}"' for value in stops)
        (tmp_path / "dysonsphere.toml").write_text(f"[palettes]\ngreys = [{values}]\n", encoding="utf-8")
        for darkmode, expected in ((False, "#DBDBDB"), (True, "#9D9D9D"), (False, "#DBDBDB")):
            theme(dark=darkmode)
            assert _opt("markFill") == expected
            assert _dysonsphere_theme()["config"]["point"]["fill"] == expected

    def test_all_grey_family_aliases_share_identity_across_modes(self):
        from dysonsphere.palettes import _PALETTE_ALIASES

        for darkmode in (False, True, False):
            theme(dark=darkmode)
            assert all(colors[alias] is colors[canonical] for alias, canonical in _PALETTE_ALIASES.items())

    def test_named_style_mark_fill_and_explicit_precedence_are_pinned(self, tmp_path, monkeypatch):
        from dysonsphere.theme import _opt

        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            '[default]\nmarkFill = "#123456"\n[paper]\nmarkFill = "#DBDBDB"\n', encoding="utf-8"
        )
        theme("paper", dark=True)
        assert _opt("markFill") == "#DBDBDB"
        theme("paper", dark=True, markFill="#9D9D9D")
        assert _opt("markFill") == "#9D9D9D"

    def test_callable_export_resolves_default_fill_and_accents_per_background(self, tmp_path):
        import dysonsphere as ds

        theme(dark=False)

        def chart():
            data = alt.Data(values=[{"x": 1, "y": 1}])
            default = alt.Chart(data).mark_point(filled=True, size=100).encode(x="x:Q", y="y:Q")
            accent = alt.Chart(data).mark_circle(color=ds.palettes.accents["blue"], size=25).encode(x="x:Q", y="y:Q")
            return default + accent

        ds.save(
            chart,
            tmp_path / "mode-fill",
            format="svg",
            background=["light", "dark"],
            transparent=False,
            saveMetadata=False,
        )
        light = (tmp_path / "mode-fill_light.svg").read_text()
        dark = (tmp_path / "mode-fill_dark.svg").read_text()
        assert "#DBDBDB" in light and "#28287D" in light
        assert "#9D9D9D" in dark and "#7783DB" in dark
        assert alt.theme.options["dark"] is False

    @pytest.mark.parametrize(
        ("overrides", "expected", "automatic"),
        [
            ({"markFill": "tomato"}, "tomato", False),
            ({"dark": True}, "#9D9D9D", True),
            ({"dark": True, "markFill": "#DBDBDB"}, "#DBDBDB", False),
        ],
    )
    def test_temporary_fill_overrides_and_mode_are_resolved_and_restored(self, overrides, expected, automatic):
        from dysonsphere.theme import _active_args, _opt, _temporary_theme

        theme()
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        with _temporary_theme(overrides):
            assert alt.theme.options["markFill"] == expected
            assert _opt("markFill") == expected
            assert alt.theme.options["_markFillAuto"] is automatic
            with _temporary_theme({"width": 240}):
                assert _opt("markFill") == expected
                assert alt.theme.options["_markFillAuto"] is automatic
        assert alt.theme.options == before_options
        assert _active_args() == before_args

    def test_mark_size_uses_min_dimension(self):
        theme(width=50, height=200)
        assert alt.theme.options["markSize"] == pytest.approx(5.0)

    def test_circle_size_default(self):
        theme(width=100, height=100)
        # config.circle.size is markSize / 8 (markSize = min(w, h) * 0.1 = 10 here).
        assert _dysonsphere_theme()["config"]["circle"]["size"] == pytest.approx(1.25)

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

    def test_chart_fill_auto_resolves_white_light_mode(self):
        # chartFill stays None ("auto") in the options; the config resolves it live from
        # darkmode so save()'s per-background toggle works without re-running theme()
        from dysonsphere.theme import _dysonsphere_theme

        theme(dark=False)
        assert alt.theme.options["chartFill"] is None
        assert _dysonsphere_theme()["background"] == "white"

    def test_chart_fill_auto_resolves_black_dark_mode(self):
        from dysonsphere.theme import _dysonsphere_theme

        theme(dark=True)
        assert _dysonsphere_theme()["background"] == "black"

    def test_chart_fill_explicit_used_as_is(self):
        from dysonsphere.theme import _dysonsphere_theme

        theme(chartFill="#eeeeee")
        assert _dysonsphere_theme()["background"] == "#eeeeee"

    def test_transparent_suppresses_background(self):
        from dysonsphere.theme import _dysonsphere_theme

        theme(transparent=True)
        assert _dysonsphere_theme()["background"] is None

    def test_sig_figs_default(self):
        theme()
        assert alt.theme.options["sigFigs"] == 3

    def test_sig_figs_override(self):
        theme(sigFigs=2)
        assert alt.theme.options["sigFigs"] == 2

    def test_save_defaults(self):
        theme()
        assert alt.theme.options["saveFormat"] == ["svg", "json"]
        assert alt.theme.options["saveBackground"] == "light"

    def test_save_defaults_override(self):
        theme(saveFormat="png", saveBackground=["light", "dark"])
        assert alt.theme.options["saveFormat"] == "png"  # stored as-is; save() normalizes
        assert alt.theme.options["saveBackground"] == ["light", "dark"]

    def test_font_size_accepts_positive_fraction(self):
        theme(fontSize=9.333)
        assert alt.theme.options["fontSize"] == pytest.approx(9.333)

    @pytest.mark.parametrize("removed", ["secondaryFontSize", "smallestFontSize"])
    def test_removed_font_options_are_rejected(self, removed):
        with pytest.raises(TypeError, match=removed):
            cast(Any, theme)(**{removed: 5})

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


class TestLegendPadding:
    """Entry spacing. Vega's own defaults are lopsided (10 across, 2 down); the theme evens it up."""

    @staticmethod
    def _legend():
        from dysonsphere.theme import _dysonsphere_theme

        return _dysonsphere_theme()["config"]["legend"]

    def test_defaults(self):
        theme()
        assert alt.theme.options["legendColumnPadding"] == 4
        assert alt.theme.options["legendRowPadding"] == 2
        assert self._legend()["columnPadding"] == 4
        assert self._legend()["rowPadding"] == 2

    def test_overrides(self):
        theme(legendColumnPadding=2, legendRowPadding=0)
        assert self._legend() == {**self._legend(), "columnPadding": 2, "rowPadding": 0}

    def test_row_padding_matches_vegas_default(self):
        """2 is what Vega already used, so existing vertical legends do not move."""
        theme()
        assert alt.theme.options["legendRowPadding"] == 2


class TestLegendGradientLength:
    def test_default_and_override(self):
        theme()
        assert alt.theme.options["legendGradientLength"] is None
        theme(legendGradientLength=0.75)
        assert alt.theme.options["legendGradientLength"] == 0.75

    def test_explicit_none_restores_orientation_aware_default(self):
        theme(legendGradientLength=None)
        assert alt.theme.options["legendGradientLength"] is None

    @pytest.mark.parametrize("value", [True, False, 0, -1, float("inf"), float("nan")])
    def test_requires_positive_finite_number(self, value):
        error = TypeError if isinstance(value, bool) else ValueError
        with pytest.raises(error, match="legendGradientLength"):
            theme(legendGradientLength=value)


class TestLegendGradientThickness:
    @staticmethod
    def _thickness():
        return _dysonsphere_theme()["config"]["legend"]["gradientThickness"]

    def test_default_and_override(self):
        theme()
        assert alt.theme.options["legendGradientThickness"] == 5
        assert self._thickness() == 5
        theme(legendGradientThickness=7.5)
        assert alt.theme.options["legendGradientThickness"] == 7.5
        assert self._thickness() == 7.5

    @pytest.mark.parametrize("value", [True, False, 0, -1, float("inf"), float("nan")])
    def test_requires_positive_finite_number(self, value):
        error = TypeError if isinstance(value, bool) else ValueError
        with pytest.raises(error, match="legendGradientThickness"):
            theme(legendGradientThickness=value)

    def test_independent_of_mark_and_chart_dimensions(self):
        theme(width=300, height=40, markSize=80)
        assert self._thickness() == 5


class TestRangePalettes:
    def _range(self, kind):
        # Raw range value: a bare array for `category` (positional), {"scheme": ...} otherwise.
        return _dysonsphere_theme()["config"]["range"][kind]

    def _scheme(self, kind):
        return self._range(kind)["scheme"]

    def test_defaults(self):
        from dysonsphere.palettes import categorical, colors

        theme()
        assert self._range("category") == categorical(1)  # bare array, positional
        assert self._scheme("ordinal") == colors["greys"]
        assert self._scheme("diverging") == colors["div1"]
        # continuous defaults: viridis - its mid-range stays separable when values are
        # scattered rather than smoothly graded (an RNA-seq matrix, not a density map)
        assert self._scheme("heatmap") == colors["viridis"]
        assert self._scheme("ramp") == colors["viridis"]

    @pytest.mark.parametrize("darkmode", [False, True])
    def test_complete_default_range_baseline(self, darkmode):
        theme(dark=darkmode)
        ranges = _dysonsphere_theme()["config"]["range"]
        digest = hashlib.sha256(json.dumps(ranges, separators=(",", ":")).encode()).hexdigest()
        assert digest == "92f22343bbe5ac3adeda22b515b3b58bcde2ffb287b6e2458b14674754fc56a7"

    def test_category_is_bare_array(self):
        # nominal scales map positionally, so category must NOT be {"scheme": ...}
        theme()
        assert isinstance(self._range("category"), list)

    def test_per_type_override_by_name(self):
        from dysonsphere.palettes import colors

        theme(categoryPalette="reds")
        assert self._range("category") == colors["reds"]
        assert self._scheme("diverging") == colors["div1"]  # others untouched

    def test_per_type_override_raw_list(self):
        theme(rampPalette=["#ffffff", "#000000"])
        assert self._scheme("ramp") == ["#ffffff", "#000000"]

    def test_per_type_vega_scheme_passthrough(self):
        theme(heatmapPalette="bluegreen")
        assert self._scheme("heatmap") == "bluegreen"

    def test_registered_name_takes_precedence_over_vega_scheme(self):
        theme(heatmapPalette="viridis")
        assert self._scheme("heatmap") == colors["viridis"]

    def test_category_vega_scheme_passthrough(self):
        # a Vega scheme *name* for category still needs the {"scheme": ...} wrapper
        theme(categoryPalette="tableau10")
        assert self._range("category") == {"scheme": "tableau10"}

    def test_global_palette_wins_over_per_type(self):
        from dysonsphere.palettes import colors

        theme(palette="greens", categoryPalette="reds")
        assert self._range("category") == colors["greens"]

    def test_global_palette_still_fills_all(self):
        from dysonsphere.palettes import colors

        theme(palette="greens")
        assert self._range("category") == colors["greens"]  # bare
        for kind in ("diverging", "heatmap", "ordinal", "ramp"):
            assert self._scheme(kind) == colors["greens"]

    def test_per_type_from_custom_palette(self, tmp_path, monkeypatch):
        from dysonsphere.palettes import categorical

        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text('[palettes]\nmine = ["#111111", "#222222"]\n', encoding="utf-8")
        theme(categoryPalette="mine")
        assert self._range("category") == ["#111111", "#222222"]
        theme()  # reset custom palette state
        assert self._range("category") == categorical(1)

    @pytest.mark.parametrize(
        ("canonical", "alias", "spelling"),
        [
            ("greys", "grays", "greys"),
            ("greys2", "grays2", "grays2"),
            ("warmgreys", "warmgrays", "warmgrays"),
            ("greysblues3", "graysblues3", "greysblues3"),
        ],
    )
    def test_custom_grey_family_spelling_synchronizes_alias(self, canonical, alias, spelling, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            f'[palettes]\n{spelling} = ["#111111", "#222222"]\n', encoding="utf-8"
        )
        theme(ordinalPalette=alias)
        assert colors[canonical] is colors[alias]
        assert colors[canonical] == ["#111111", "#222222"]
        (tmp_path / "dysonsphere.toml").unlink()
        theme()
        assert colors[canonical] is colors[alias]
        assert colors[canonical] != ["#111111", "#222222"]

    def test_equal_greys_spellings_allowed_and_conflict_is_atomic(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "dysonsphere.toml"
        config.write_text('[palettes]\ngreys = ["#111111"]\ngrays = ["#111111"]\n', encoding="utf-8")
        theme()
        before_options = dict(alt.theme.options)
        before_greys = colors["greys"]
        config.write_text('[palettes]\ngreys = ["#111111"]\ngrays = ["#222222"]\n', encoding="utf-8")
        with pytest.raises(ValueError, match="Conflicting palette definitions.*grays.*greys"):
            theme()
        assert alt.theme.options == before_options
        assert colors["greys"] is before_greys
        assert colors["grays"] is before_greys

    def test_custom_greys_does_not_regenerate_diverging_family(self, tmp_path, monkeypatch):
        built_in_diverging = list(colors["greysblues"])
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text('[palettes]\ngrays = ["#111111"]\n', encoding="utf-8")
        theme()
        assert colors["greys"] == ["#111111"]
        assert colors["greysblues"] == built_in_diverging
        assert colors["graysblues"] is colors["greysblues"]

    @pytest.mark.parametrize(
        ("user_name", "project_name"), [("greysblues", "graysblues"), ("graysblues", "greysblues")]
    )
    def test_project_spelling_override_wins_over_user(self, user_name, project_name, tmp_path, monkeypatch):
        user_dir = tmp_path / "user" / "dysonsphere"
        user_dir.mkdir(parents=True)
        (user_dir / "dysonsphere.toml").write_text(f'[palettes]\n{user_name} = ["#111111"]\n', encoding="utf-8")
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dysonsphere.toml").write_text(f'[palettes]\n{project_name} = ["#222222"]\n', encoding="utf-8")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user"))
        monkeypatch.chdir(project_dir)
        theme()
        assert colors["greysblues"] is colors["graysblues"]
        assert colors["greysblues"] == ["#222222"]

    def test_per_type_via_toml(self, tmp_path, monkeypatch):
        from dysonsphere.palettes import colors

        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text('[default]\ndivergingPalette = "greensblues"\n', encoding="utf-8")
        theme()
        assert self._scheme("diverging") == colors["greensblues"]


class TestInwardTicks:
    def test_off_by_default(self):
        theme()
        assert alt.theme.options["tickDirection"] == "out"
        assert alt.theme.options["closed"] is False  # no viewFill and outward ticks

    def test_defaults_closed(self):
        # inward ticks need a closed (non-offset) axis, so closed defaults True with them
        theme(tickDirection="in")
        assert alt.theme.options["closed"] is True

    def test_explicit_closed_false_wins(self):
        theme(tickDirection="in", closed=False)
        assert alt.theme.options["closed"] is False

    def test_tick_size_stays_positive(self):
        # inward is applied as an SVG post-process (not a negative config tickSize),
        # so the tick-position fixers still see the outward geometry they expect.
        theme(tickDirection="in")
        assert _dysonsphere_theme()["config"]["axis"]["tickSize"] == alt.theme.options["tickSize"]

    @pytest.mark.parametrize(("value", "error"), [("sideways", ValueError), (True, TypeError), (False, TypeError)])
    def test_invalid_direction_is_atomic(self, value, error):
        theme(width=123)
        before = dict(alt.theme.options)
        with pytest.raises(error, match="tickDirection"):
            cast(Any, theme)(tickDirection=value)
        assert alt.theme.options == before

    def test_removed_inward_ticks_keyword_is_rejected(self):
        with pytest.raises(TypeError, match="inwardTicks"):
            cast(Any, theme)(inwardTicks=True)

    def test_removed_inward_ticks_toml_key_is_rejected(self, tmp_path, monkeypatch):
        (tmp_path / "dysonsphere.toml").write_text("[default]\ninwardTicks = true\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="inwardTicks"):
            theme()


class TestThemeRegistration:
    def test_theme_registered_as_dysonsphere(self):
        assert "dysonsphere" in alt.theme.names()

    def test_theme_is_active(self):
        theme()
        assert alt.theme.active == "dysonsphere"

    def test_unknown_kwarg_raises(self):
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            cast(Any, theme)(notAParam=42)

    def test_all_options_have_explicit_keyword_only_parameters(self):
        import inspect

        from dysonsphere.theme import _BUILTIN_DEFAULTS

        params = inspect.signature(theme).parameters
        assert set(params) == {"style", *_BUILTIN_DEFAULTS}
        assert params["style"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert all(param.kind is inspect.Parameter.KEYWORD_ONLY for name, param in params.items() if name != "style")
        assert repr(params["fontSize"].default) == "<omitted>"

    def test_option_order_preserves_alphabetical_and_grouped_settings(self):
        import inspect

        from dysonsphere.theme import _BUILTIN_DEFAULTS

        keys = list(_BUILTIN_DEFAULTS)
        assert list(inspect.signature(theme).parameters) == ["style", *keys]
        padding = ["barPadding", "groupPadding", "outerPadding", "rectPadding", "subgroupPadding", "tickPadding"]
        palettes = ["palette", "categoryPalette", "divergingPalette", "heatmapPalette", "ordinalPalette", "rampPalette"]
        for group in (padding, palettes):
            start = keys.index(group[0])
            assert keys[start : start + len(group)] == group
        ungrouped = [key for key in keys if key not in padding + palettes]
        assert ungrouped == sorted(ungrouped, key=str.casefold)

    def test_style_remains_positional(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        theme("notebook")
        assert alt.theme.options["width"] == 900


class TestThemeValidation:
    @pytest.mark.parametrize("removed", ["chartWidth", "chartHeight"])
    def test_removed_dimension_kwargs_are_rejected(self, removed):
        with pytest.raises(TypeError, match=removed):
            cast(Any, theme)(**{removed: 120})

    @pytest.mark.parametrize(
        ("key", "value", "error"),
        [
            ("width", 0, ValueError),
            ("height", float("inf"), ValueError),
            ("fontSize", -1, ValueError),
            ("fontSize", True, TypeError),
            ("dark", 1, TypeError),
            ("markFillOpacity", 1.1, ValueError),
            ("markStrokeOpacity", float("nan"), ValueError),
            ("barPadding", 1.1, ValueError),
            ("outerPadding", -0.1, ValueError),
            ("markSize", -1, ValueError),
            ("strokeCap", "projecting", ValueError),
            ("fontStyle", "bold", ValueError),
            ("sigFigs", True, TypeError),
            ("saveFormat", [], ValueError),
            ("saveFormat", 1, TypeError),
            ("saveFormat", "pdf", ValueError),
            ("saveBackground", "sepia", ValueError),
            ("dashedWidth", [2, float("inf")], ValueError),
            ("dashedWidth", [True], TypeError),
            ("palette", [], TypeError),
            ("palette", "", ValueError),
            ("categoryPalette", "   ", ValueError),
            ("fontWeight", [], TypeError),
            ("fontWeight", {}, TypeError),
            ("fontWeight", 0.5, ValueError),
            ("fontWeight", 1000.1, ValueError),
        ],
    )
    def test_invalid_direct_values_are_atomic(self, key, value, error):
        from dysonsphere.palettes import colors
        from dysonsphere.theme import _active_args

        theme(width=123, palette="reds")
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        before_colors = dict(colors)
        with pytest.raises(error):
            cast(Any, theme)(**{key: value})
        assert alt.theme.options == before_options
        assert _active_args() == before_args
        assert dict(colors) == before_colors

    @pytest.mark.parametrize("dash", [[], [0], [2], [2, 1, 3]])
    def test_dash_sequences_allow_solid_and_odd_forms(self, dash):
        theme(dashedWidth=dash)
        assert alt.theme.options["dashedWidth"] == dash

    def test_signed_offsets_and_angles_and_explicit_zero(self):
        theme(axisOffset=-2, legendOffset=-3, xLabelAngle=-45, yLabelAngle=30, viewPadding=0)
        assert alt.theme.options["axisOffset"] == -2
        assert alt.theme.options["legendOffset"] == -3
        assert "continuousPadding" not in _dysonsphere_theme()["config"]["scale"]

    @pytest.mark.parametrize("offset", ["axisOffset", "legendOffset"])
    def test_derived_offset_overflow_is_atomic(self, offset):
        from dysonsphere.theme import _active_args

        theme(width=123)
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        kwargs = {"tickSize": 1.3e308, offset: True if offset == "axisOffset" else None}
        with pytest.raises(ValueError, match=f"{offset} must be finite"):
            cast(Any, theme)(**kwargs)
        assert alt.theme.options == before_options
        assert _active_args() == before_args

    @pytest.mark.parametrize("weight", [1, 347.5, 1000])
    def test_numeric_font_weights_supported_by_renderer(self, weight):
        import vl_convert as vlc

        theme(fontWeight=weight)
        chart = alt.Chart({"values": [{"x": 1}]}).mark_text(text="weight")
        svg = vlc.vegalite_to_svg(chart.to_dict())
        assert f'font-weight="{weight}"' in svg

    def test_invalid_toml_value_is_atomic(self, tmp_path, monkeypatch):
        from dysonsphere.palettes import colors
        from dysonsphere.theme import _active_args

        theme(width=123, palette="reds")
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        before_colors = dict(colors)
        (tmp_path / "dysonsphere.toml").write_text(
            '[default]\nfontSize = 0\n[palettes]\nlocal = ["red", "navy"]\n', encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="fontSize"):
            theme()
        assert alt.theme.options == before_options
        assert _active_args() == before_args
        assert dict(colors) == before_colors

    def test_explicit_none_overrides_toml_value(self, tmp_path, monkeypatch):
        (tmp_path / "dysonsphere.toml").write_text('[default]\nchartFill = "pink"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        theme(chartFill=None)
        assert alt.theme.options["chartFill"] is None

    @pytest.mark.parametrize("removed", ["secondaryFontSize", "smallestFontSize"])
    def test_removed_font_options_are_rejected_in_toml(self, removed, tmp_path, monkeypatch):
        (tmp_path / "dysonsphere.toml").write_text(f"[default]\n{removed} = 5\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match=removed):
            theme()

    @pytest.mark.parametrize("removed", ["chartWidth", "chartHeight"])
    def test_removed_dimension_options_are_rejected_in_toml(self, removed, tmp_path, monkeypatch):
        (tmp_path / "dysonsphere.toml").write_text(f"[default]\n{removed} = 120\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match=removed):
            theme()

    def test_named_css_colors_are_allowed_in_palette_lists(self):
        theme(categoryPalette=["navy", "rebeccapurple"])
        assert _dysonsphere_theme()["config"]["range"]["category"] == ["navy", "rebeccapurple"]


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
        assert overrides["width"] == 900

    def test_config_overrides_builtin_style(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text("[notebook]\nfontSize = 9\n", encoding="utf-8")
        overrides = _load_style_overrides("notebook")
        assert overrides["fontSize"] == 9
        assert overrides["width"] == 900  # from built-in preset


class TestCreateConfig:
    def test_creates_file(self, tmp_path):
        create_config(tmp_path)
        assert (tmp_path / "dysonsphere.toml").exists()

    def test_contains_builtin_style_names(self, tmp_path):
        create_config(tmp_path)
        content = (tmp_path / "dysonsphere.toml").read_text()
        assert "[nih]" not in content
        assert "[notebook]" in content
        assert "[presentation]" not in content  # removed as a built-in preset in v3.0
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
        theme(width=200, height=300, cornerRadius=True)
        assert alt.theme.options["cornerRadius"] == pytest.approx(2.0)

    def test_true_applies_corner_radius_end_to_bar(self):
        theme(width=100, height=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["bar"]["cornerRadiusEnd"] == pytest.approx(1.0)

    def test_true_applies_corner_radius_to_rect(self):
        theme(width=100, height=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["rect"]["cornerRadius"] == pytest.approx(1.0)

    def test_explicit_float_used_as_is(self):
        theme(cornerRadius=3.0)
        assert alt.theme.options["cornerRadius"] == pytest.approx(3.0)
        spec = _dysonsphere_theme()
        assert spec["config"]["bar"]["cornerRadiusEnd"] == pytest.approx(3.0)
        assert spec["config"]["rect"]["cornerRadius"] == pytest.approx(3.0)

    def test_true_applies_corner_radius_to_boxplot_box(self):
        theme(width=100, height=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["boxplot"]["box"]["cornerRadius"] == pytest.approx(1.0)

    def test_false_default_omits_key_from_boxplot_box(self):
        theme()
        spec = _dysonsphere_theme()
        assert "cornerRadius" not in spec["config"]["boxplot"]["box"]

    def test_true_applies_corner_radius_to_arc(self):
        theme(width=100, height=100, cornerRadius=True)
        spec = _dysonsphere_theme()
        assert spec["config"]["arc"]["cornerRadius"] == pytest.approx(1.0)

    def test_false_default_omits_key_from_arc(self):
        theme()
        spec = _dysonsphere_theme()
        assert "cornerRadius" not in spec["config"]["arc"]

    def test_arc_inner_radius_scales_with_chart_size(self):
        theme(width=100, height=100)
        spec = _dysonsphere_theme()
        assert spec["config"]["arc"]["innerRadius"] == pytest.approx(25.0)

    def test_arc_inner_radius_uses_smaller_dimension(self):
        theme(width=80, height=200)
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

    def test_subtitle_uses_numeric_font_size_in_render(self):
        import re

        import vl_convert as vlc

        theme(fontSize=9.333)
        chart = (
            alt.Chart({"values": [{"x": 1}]})
            .mark_point()
            .encode(x="x:Q")
            .properties(title={"text": "Main", "subtitle": "Sub"})
        )
        svg = vlc.vegalite_to_svg(chart.to_dict())
        subtitle = re.search(r'<text[^>]+font-size="([^"]+)"[^>]*>Sub</text>', svg)
        assert subtitle is not None
        assert float(subtitle.group(1).removesuffix("px")) == pytest.approx(9.333)


class TestErrorbandConfig:
    def test_border_stroke_properties_render_in_the_correct_fields(self):
        import re

        import vl_convert as vlc

        theme(markStrokeWidth=3, markStrokeOpacity=0.25)
        chart = (
            alt.Chart({"values": [{"x": 0, "y": 1}, {"x": 0, "y": 3}, {"x": 1, "y": 2}, {"x": 1, "y": 4}]})
            .mark_errorband(extent="ci")
            .encode(x="x:Q", y="y:Q")
        )
        svg = vlc.vegalite_to_svg(chart.to_dict())
        borders = re.findall(r'<path[^>]+opacity="0"[^>]*/>', svg)
        assert borders
        assert all('stroke-opacity="0.25"' in border and 'stroke-width="3"' in border for border in borders)


class TestTickConfig:
    # config.tick: crossbar-style defaults so a bare mark_tick at an aggregate composes
    # with mark_errorbar as one glyph (and mark_strip's mean tick inherits from it).

    def test_mirrors_errorbar_caps_and_median_span(self):
        theme()
        tick = _dysonsphere_theme()["config"]["tick"]
        eb_ticks = _dysonsphere_theme()["config"]["errorbar"]["ticks"]
        median = _dysonsphere_theme()["config"]["boxplot"]["median"]
        assert tick["color"] == eb_ticks["color"]
        assert tick["cornerRadius"] == eb_ticks["cornerRadius"]
        assert tick["thickness"] == eb_ticks["thickness"]
        assert tick["size"] == median["size"]  # markSize * 0.9

    def test_darkmode_flips_color(self):
        theme(dark=True)
        assert _dysonsphere_theme()["config"]["tick"]["color"] == "white"
        theme(dark=False)
        assert _dysonsphere_theme()["config"]["tick"]["color"] == "black"

    def test_scales_with_theme_params(self):
        theme(markSize=20, markStrokeWidth=1)
        tick = _dysonsphere_theme()["config"]["tick"]
        assert tick["size"] == pytest.approx(18.0)
        assert tick["thickness"] == 1
        assert tick["cornerRadius"] == pytest.approx(0.5)

    def test_boxplot_median_pins_square_corners(self):
        # The composite lowering lets config.tick leak into the boxplot's median tick
        # for any property the median config leaves unset - cornerRadius must stay
        # pinned to 0 so the median keeps square, box-flush ends.
        theme()
        assert _dysonsphere_theme()["config"]["boxplot"]["median"]["cornerRadius"] == 0


class TestTrailConfig:
    # config.trail: trail is a FILLED variable-width path (steel blue at Vega defaults);
    # color supplies the fill, and the unsized width matches config.line's strokeWidth.

    def test_matches_line_width_and_darkmode(self):
        theme()
        cfg = _dysonsphere_theme()["config"]
        assert cfg["trail"]["size"] == cfg["line"]["strokeWidth"]
        assert cfg["trail"]["color"] == "black"
        theme(dark=True)
        assert _dysonsphere_theme()["config"]["trail"]["color"] == "white"


class TestLineCap:
    # config.line pins strokeCap="butt" so a line's ink stops at its final data point.
    # theme(strokeCap=...) still caps axes/ticks/grid/rules.

    def test_line_is_butt_capped_regardless_of_theme_stroke_cap(self):
        theme()
        cfg = _dysonsphere_theme()["config"]
        assert cfg["line"]["strokeCap"] == "butt"
        assert cfg["rule"]["strokeCap"] == "round"
        assert cfg["axis"]["domainCap"] == "round"

        theme(strokeCap="square")
        cfg = _dysonsphere_theme()["config"]
        assert cfg["line"]["strokeCap"] == "butt"
        assert cfg["rule"]["strokeCap"] == "square"


class TestIdentityScalesPinPadding:
    """A scale whose domain equals its range maps data 1:1 to pixels, so `viewPadding` would
    compress it. Every such scale must pin `padding=0`."""

    @staticmethod
    def _identity_scales(spec: Any) -> list[dict[str, Any]]:
        found = []

        def walk(node):
            if isinstance(node, dict):
                enc = node.get("encoding")
                if isinstance(enc, dict):
                    for channel in ("x", "y"):
                        ch = enc.get(channel)
                        sc = ch.get("scale") if isinstance(ch, dict) else None
                        if (
                            isinstance(sc, dict)
                            and sc.get("domain") is not None
                            and sc.get("domain") == sc.get("range")
                        ):
                            found.append(sc)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(spec)
        return found

    @pytest.mark.parametrize("name", ["multilabel", "table"])
    def test_every_identity_scale_pins_padding(self, name):
        import numpy as np
        import polars as pl

        from dysonsphere.multilabel import add_multilabel
        from dysonsphere.table import mark_table

        theme()
        cats = ["a", "b", "c"]
        rng = np.random.default_rng(0)
        grp = pl.DataFrame({"g": np.repeat(cats, 12), "v": rng.normal(5, 1, 36)})
        builders = {
            "multilabel": lambda: add_multilabel(
                alt.Chart(grp).mark_point().encode(alt.X("g:N", title=None), alt.Y("v:Q", title="v")),
                {"r1": [True, False, True]},
                cats,
            ),
            "table": lambda: mark_table(pl.DataFrame({"gene": ["A", "B"], "fc": [1.5, -2.0]})),
        }
        scales = self._identity_scales(builders[name]().to_dict())
        assert scales, f"{name}: no identity scale found - update this test if the construction changed"
        assert all(s.get("padding") == 0 for s in scales), scales


class TestViewPadding:
    # theme(viewPadding=...) -> config.scale.continuousPadding on every plot.
    # float | bool like cornerRadius/boxplotOutliers: True (default) -> 5% of the smaller
    # chart dimension, False -> flush, a float -> that many pixels. Vega-Lite nice-rounds
    # the padded domain, so the request only lands exactly where the domain is explicit.

    def test_default_true_scales_with_chart_size_when_closed(self):
        theme(closed=True)
        assert _dysonsphere_theme()["config"]["scale"]["continuousPadding"] == 5.0  # 100 x 100

    def test_default_true_tracks_the_smaller_dimension(self):
        theme(closed=True, width=400, height=200)
        assert _dysonsphere_theme()["config"]["scale"]["continuousPadding"] == 10.0

    def test_resolved_value_is_readable_from_theme_options(self):
        # resolved in _compute_derived like markSize, so it is baked into exports
        theme(closed=True, width=200, height=200)
        assert alt.theme.options["viewPadding"] == 10.0

    def test_false_is_flush(self):
        theme(closed=True, viewPadding=False)
        assert "continuousPadding" not in _dysonsphere_theme()["config"]["scale"]

    def test_explicit_value_used_as_is(self):
        theme(closed=True, viewPadding=8)
        assert _dysonsphere_theme()["config"]["scale"]["continuousPadding"] == 8

    def test_axis_offset_none_is_rejected(self):
        from dysonsphere.palettes import colors
        from dysonsphere.theme import _active_args

        theme(palette="reds")
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        before_colors = dict(colors)
        with pytest.raises(ValueError, match="axisOffset=None"):
            cast(Any, theme)(axisOffset=None, palette="blues")
        assert alt.theme.options == before_options
        assert _active_args() == before_args
        assert dict(colors) == before_colors
        theme(axisOffset=True)
        assert alt.theme.options["axisOffset"] == pytest.approx(4.5)
        theme()
        assert alt.theme.options["axisOffset"] == 0

    def test_applies_on_open_plots(self):
        # the inset is the gap mechanism everywhere now - axes are flush by default
        theme()
        assert _dysonsphere_theme()["config"]["scale"]["continuousPadding"] == 5.0
        theme(viewPadding=8)
        assert _dysonsphere_theme()["config"]["scale"]["continuousPadding"] == 8

    def test_applies_under_inward_ticks(self):
        theme(tickDirection="in")  # implies closed
        assert _dysonsphere_theme()["config"]["scale"]["continuousPadding"] == 5.0

    def test_internal_scales_pinned_against_padding(self):
        # violin x:Q and labels' pinned scales carry padding=0 so viewPadding cannot
        # compress their pixel math
        import polars as pl

        from dysonsphere.annotations import labels
        from dysonsphere.marks import mark_violin

        theme(closed=True)
        df = pl.DataFrame({"g": ["a"] * 8 + ["b"] * 8, "v": [1.0, 2, 3, 4, 5, 6, 7, 8] * 2})
        violin = mark_violin(df, "g", "v", ["a", "b"]).to_dict()
        vx = next(lyr for lyr in violin["layer"] if lyr["encoding"]["x"].get("field") == "__x")
        assert vx["encoding"]["x"]["scale"]["padding"] == 0

        # labels deliberately does NOT pin padding: its geometry is pixel offsets from each
        # marker, so viewPadding insets marker and label together and alignment survives. Forcing
        # padding=0 here would override the user's viewPadding on the shared scale.
        pts = pl.DataFrame({"x": [1.0, 2, 3], "y": [1.0, 2, 3], "n": ["a", "b", "c"]})
        labels_spec = labels(pts, "x", "y", "n").to_dict()
        scales = [
            lyr["encoding"][ch]["scale"]
            for lyr in labels_spec["layer"]
            for ch in ("x", "y")
            if isinstance(lyr.get("encoding", {}).get(ch), dict) and "scale" in lyr["encoding"][ch]
            if isinstance(lyr["encoding"][ch]["scale"], dict) and "domain" in lyr["encoding"][ch]["scale"]
        ]
        assert scales and all("padding" not in sc for sc in scales)


class TestBandPaddingByMark:
    # Band padding is set per mark type. The global config.scale.bandPaddingInner is
    # deliberately NOT emitted: it overrides all three mark-specific keys at once, which
    # is what used to band mark_rect cells with the bar spacing.

    def test_emits_mark_specific_keys_not_the_global_inner(self):
        theme()
        scale = _dysonsphere_theme()["config"]["scale"]
        assert "bandPaddingInner" not in scale
        assert scale["barBandPaddingInner"] == 0.1
        assert scale["rectBandPaddingInner"] == 0
        assert scale["tickBandPaddingInner"] == 0.1
        assert scale["bandPaddingOuter"] == 0.1
        assert scale["bandWithNestedOffsetPaddingInner"] == 0.2
        assert scale["offsetBandPaddingInner"] == 0

    def test_each_key_is_independently_settable(self):
        theme(
            barPadding=0.3,
            rectPadding=0.05,
            tickPadding=0.4,
            outerPadding=0.2,
            groupPadding=0.5,
            subgroupPadding=0.1,
        )
        scale = _dysonsphere_theme()["config"]["scale"]
        assert scale["barBandPaddingInner"] == 0.3
        assert scale["rectBandPaddingInner"] == 0.05
        assert scale["tickBandPaddingInner"] == 0.4
        assert scale["bandPaddingOuter"] == 0.2
        assert scale["bandWithNestedOffsetPaddingOuter"] == 0.5
        assert scale["offsetBandPaddingOuter"] == 0.1

    def test_rect_cells_abut_in_rendered_output(self):
        # the regression this split exists to fix: heatmap cells must not be banded
        import re

        import polars as pl
        import vl_convert as vlc

        theme()
        rows = [{"x": x, "y": y, "v": float((x + y) % 3)} for y in range(3) for x in range(4)]
        chart = (
            alt.Chart(pl.DataFrame(rows))
            .mark_rect()
            .encode(x=alt.X("x:O"), y=alt.Y("y:O"), color=alt.Color("v:Q", legend=None))
        )
        svg = vlc.vegalite_to_svg(chart.to_dict())
        found = re.search(r'class="mark-rect role-mark[^"]*"[^>]*>(.*?)</g>', svg, re.S)
        assert found is not None
        marks = found.group(1)
        cells = re.findall(r'd="M([-\d.]+),[-\d.]+h([-\d.]+)v', marks)
        spans = sorted({(round(float(a), 4), round(float(w), 4)) for a, w in cells})
        xs = sorted({s for s, _ in spans})
        widths = {w for _, w in spans}
        assert len(widths) == 1  # every cell the same width
        cell = widths.pop()
        for left, right in zip(xs, xs[1:]):
            assert right - left == pytest.approx(cell, abs=1e-6)  # no gap between columns


class TestDeprecatedAliases:
    # bandPadding was split by mark type in v3.11 and is removed at v4.0.0.

    def test_kwarg_alias_is_rejected(self):
        with pytest.raises(TypeError, match="bandPadding"):
            cast(Any, theme)(bandPadding=0.25)

    def test_mark_median_stroke_is_rejected(self):
        with pytest.raises(TypeError, match="markMedianStroke"):
            cast(Any, theme)(markMedianStroke="black")

    def test_removed_aliases_do_not_change_theme_state(self):
        theme(width=123)
        before = dict(alt.theme.options)
        with pytest.raises(TypeError, match="bandPadding"):
            cast(Any, theme)(bandPadding=0.25)
        assert alt.theme.options == before

    def test_toml_alias_is_rejected(self, tmp_path, monkeypatch):
        (tmp_path / "dysonsphere.toml").write_text("[default]\nbandPadding = 0.3\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="bandPadding"):
            theme()

    def test_baked_theme_from_older_export_rejects_removed_alias(self):
        with pytest.raises(TypeError, match="bandPadding"):
            cast(Any, theme)(bandPadding=0.1, width=120)


class TestBoxplotOutliers:
    def test_false_default_hides_outliers(self):
        theme()
        assert _dysonsphere_theme()["config"]["boxplot"]["outliers"]["size"] == 0

    def test_true_resolves_to_mark_size_over_10(self):
        theme(markSize=12, boxplotOutliers=True)
        assert alt.theme.options["boxplotOutliers"] == pytest.approx(1.2)
        assert _dysonsphere_theme()["config"]["boxplot"]["outliers"]["size"] == pytest.approx(1.2)

    def test_explicit_size_used_as_is(self):
        theme(boxplotOutliers=5)
        assert _dysonsphere_theme()["config"]["boxplot"]["outliers"]["size"] == 5


# ── _opt() theme-option accessor ─────────────────────────────────────────────


class TestOptAccessor:
    def test_reads_active_theme(self):
        from dysonsphere.theme import _opt

        theme(barPadding=0.25)
        assert _opt("barPadding") == 0.25

    def test_falls_back_to_builtin_default(self):
        from dysonsphere.theme import _opt

        alt.theme.options = {}  # no theme() called
        try:
            assert _opt("barPadding") == 0.1
            assert _opt("width") == 100
        finally:
            theme()

    def test_fallback_resolves_derived_defaults(self):
        # the raw builtin for markSize/axisOffset is None (a derive-at-theme-time
        # sentinel); the fallback must expose the DERIVED value, not the sentinel
        from dysonsphere.theme import _opt

        alt.theme.options = {}
        try:
            assert _opt("markSize") == 10.0  # min(100, 100) * 0.1
            assert _opt("axisOffset") == 0  # flush by default; True derives from tickSize
            assert _opt("markStrokeWidth") == 0.25  # axisWidth
            assert _opt("closed") is False
        finally:
            theme()

    def test_unknown_key_raises(self):
        from dysonsphere.theme import _opt

        theme()
        with pytest.raises(KeyError):
            _opt("notAThing")

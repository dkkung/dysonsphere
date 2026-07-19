import altair as alt
import numpy as np
import polars as pl
import pytest

from dysonsphere.marks import mark_strip, mark_violin
from dysonsphere.theme import theme

CATEGORIES = ["A", "B", "C"]


@pytest.fixture(autouse=True)
def default_theme():
    theme(chartWidth=200, chartHeight=200)


@pytest.fixture
def group_df():
    rng = np.random.default_rng(0)
    n = 15
    return pl.DataFrame(
        {
            "group": CATEGORIES * n,
            "value": rng.normal(0, 1, len(CATEGORIES) * n),
        }
    )


class TestMarkViolin:
    def test_returns_layer_chart(self, group_df):
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        assert isinstance(result, alt.LayerChart)

    def test_custom_palette_list(self, group_df):
        result = mark_violin(
            group_df,
            xCol="group",
            yCol="value",
            categories=CATEGORIES,
            palette=["#FF0000", "#00FF00", "#0000FF"],
        )
        assert isinstance(result, alt.LayerChart)

    def test_y_title_default_is_col_name(self, group_df):
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        spec = result.to_dict()
        layer_specs = spec.get("layer", [])
        y_titles = [
            layer.get("encoding", {}).get("y", {}).get("title")
            for layer in layer_specs
            if layer.get("encoding", {}).get("y", {}).get("title") is not None
        ]
        assert any(t == "value" for t in y_titles)

    def test_y_title_none_suppresses(self, group_df):
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES, yTitle=None)
        spec = result.to_dict()
        for layer in spec.get("layer", []):
            y_enc = layer.get("encoding", {}).get("y", {})
            assert y_enc.get("title") is None or "title" not in y_enc

    def test_violin_x_uses_absolute_quantitative(self, group_df):
        # Violin line mark encodes x:Q with axis=None - absolute pixel coordinates,
        # not xOffset - so hconcat with mark_strip never squishes the violin.
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        spec = result.to_dict()
        violin_layer = next(
            lyr for lyr in spec["layer"] if isinstance(lyr.get("mark"), dict) and lyr["mark"].get("type") == "line"
        )
        x_enc = violin_layer["encoding"]["x"]
        assert x_enc["type"] == "quantitative"
        # axis=None serialises as null in to_dict()
        assert x_enc.get("axis") is None
        chart_width = alt.theme.options.get("chartWidth", 200)
        assert x_enc["scale"]["domain"] == [0, chart_width]

    def test_violin_no_xoffset_in_any_layer(self, group_df):
        # No layer uses xOffset - Vega-Lite won't merge xOffset scales across hconcat panels.
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        spec = result.to_dict()
        for layer in spec["layer"]:
            assert "xOffset" not in layer.get("encoding", {})

    def test_median_color_wired_to_spec(self, group_df):
        # Proves the medianColor param flows to the boxplot median fill. Uses an explicit
        # value (not the default) so it doesn't pin the cosmetic default, which may change.
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES, medianColor="red")
        box = next(
            lyr
            for lyr in result.to_dict()["layer"]
            if isinstance(lyr.get("mark"), dict) and lyr["mark"].get("type") == "boxplot"
        )
        assert box["mark"]["median"]["fill"] == "red"

    def test_x_title_defaults_to_col_name(self, group_df):
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        spec = result.to_dict()
        x_titles = [
            layer.get("encoding", {}).get("x", {}).get("title")
            for layer in spec["layer"]
            if layer.get("encoding", {}).get("x", {}).get("title") is not None
        ]
        assert any(t == "group" for t in x_titles)

    def test_x_title_none_suppresses(self, group_df):
        result = mark_violin(group_df, xCol="group", yCol="value", categories=CATEGORIES, xTitle=None)
        spec = result.to_dict()
        for layer in spec["layer"]:
            x_enc = layer.get("encoding", {}).get("x", {})
            assert x_enc.get("title") is None or "title" not in x_enc


class TestMarkStrip:
    def test_returns_layer_chart(self, group_df):
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        assert isinstance(result, alt.LayerChart)

    def test_x_title_defaults_to_col_name(self, group_df):
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        spec = result.to_dict()
        x_titles = [
            layer.get("encoding", {}).get("x", {}).get("title")
            for layer in spec["layer"]
            if layer.get("encoding", {}).get("x", {}).get("title") is not None
        ]
        assert any(t == "group" for t in x_titles)

    def test_x_title_none_suppresses(self, group_df):
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES, xTitle=None)
        spec = result.to_dict()
        for layer in spec["layer"]:
            x_enc = layer.get("encoding", {}).get("x", {})
            assert x_enc.get("title") is None or "title" not in x_enc

    def test_mark_size_param(self, group_df):
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES, markSize=20)
        spec = result.to_dict()
        circle_layer = next(lyr for lyr in spec["layer"] if lyr.get("mark", {}).get("type") == "circle")
        assert circle_layer["mark"]["size"] == 20

    def test_mark_opacity_param(self, group_df):
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES, markOpacity=0.5)
        spec = result.to_dict()
        circle_layer = next(lyr for lyr in spec["layer"] if lyr.get("mark", {}).get("type") == "circle")
        assert circle_layer["mark"]["opacity"] == 0.5

    def test_errorbars_disabled(self, group_df):
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES, errorbars=False)
        assert isinstance(result, alt.LayerChart)

    def test_errorbars_center_tick_is_mean(self, group_df):
        # The centre tick must draw the MEAN (the errorbar statistic), not the median -
        # a median tick sits off-centre between the caps on skewed data.
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES)
        spec = result.to_dict()
        tick_layer = next(lyr for lyr in spec["layer"] if lyr.get("mark", {}).get("type") == "tick")
        errorbar_layer = next(lyr for lyr in spec["layer"] if lyr.get("mark", {}).get("type") == "errorbar")
        assert tick_layer["encoding"]["y"]["field"] == "__mean"
        assert tick_layer["encoding"]["y"]["field"] == errorbar_layer["encoding"]["y"]["field"]
        # and no hidden boxplot (the old median source) remains in the errorbar mode
        assert not any(lyr.get("mark", {}).get("type") == "boxplot" for lyr in spec["layer"])

    def test_errorbars_disabled_keeps_median_boxplot(self, group_df):
        # Without error bars the centre statistic stays the median (via the hidden boxplot).
        result = mark_strip(group_df, xCol="group", yCol="value", categories=CATEGORIES, errorbars=False)
        spec = result.to_dict()
        assert any(lyr.get("mark", {}).get("type") == "boxplot" for lyr in spec["layer"])

    def test_beeswarm_scatter(self, group_df):
        result = mark_strip(
            group_df,
            xCol="group",
            yCol="value",
            categories=CATEGORIES,
            scatter="beeswarm",
        )
        assert isinstance(result, alt.LayerChart)

    def test_invalid_scatter_raises(self, group_df):
        with pytest.raises(ValueError, match="scatter"):
            mark_strip(
                group_df,
                xCol="group",
                yCol="value",
                categories=CATEGORIES,
                scatter="invalid",
            )


class TestLabelMap:
    def test_strip_x_axis_gets_label_expr(self, group_df):
        chart = mark_strip(group_df, "group", "value", CATEGORIES, labelMap={"A": "Alpha"})
        spec = chart.to_dict()
        expr = spec["layer"][0]["encoding"]["x"]["axis"]["labelExpr"]
        assert "datum.value == 'A' ? 'Alpha'" in expr and expr.endswith("datum.value")

    def test_violin_boxplot_axis_gets_label_expr(self, group_df):
        chart = mark_violin(group_df, "group", "value", CATEGORIES, labelMap={"A": ["Alpha", "(n=5)"]})
        spec = chart.to_dict()
        expr = spec["layer"][1]["encoding"]["x"]["axis"]["labelExpr"]
        assert "? ['Alpha', '(n=5)']" in expr  # multi-line label

    def test_label_map_combines_with_angle(self, group_df):
        chart = mark_strip(group_df, "group", "value", CATEGORIES, labelMap={"A": "Alpha"}, xLabelAngle=-45)
        axis = chart.to_dict()["layer"][0]["encoding"]["x"]["axis"]
        assert axis["labelAngle"] == 315 and "labelExpr" in axis

    def test_no_label_map_no_label_expr(self, group_df):
        chart = mark_strip(group_df, "group", "value", CATEGORIES)
        axis = chart.to_dict()["layer"][0]["encoding"]["x"].get("axis", {})
        assert "labelExpr" not in (axis or {})

    def test_strip_spec_is_deterministic(self, group_df):
        # group_by(maintain_order=True) in the errorbar summary: identical inputs must
        # produce identical specs (stable inlined datasets -> stable vegaliteChecksum)
        import json

        a = json.dumps(mark_strip(group_df, "group", "value", CATEGORIES).to_dict(), sort_keys=True)
        b = json.dumps(mark_strip(group_df, "group", "value", CATEGORIES).to_dict(), sort_keys=True)
        assert a == b


class TestCategoryOrderPreserved:
    """The scaffold pins the DOMAIN (not just sort=) on x and colour so the category order
    survives Vega-Lite's shared-scale union when marks are layered/concatenated - otherwise the
    order gets re-sorted alphabetically through the merge and colours stop matching their bars.
    """

    def _domains(self, chart, names=("x", "color")):
        import vl_convert as vlc

        vg = vlc.vegalite_to_vega(chart.to_dict())
        out: dict[str, list[list[str]]] = {}

        def walk(o):
            if isinstance(o, dict):
                for s in o.get("scales", []) or []:
                    if s.get("name") in names and isinstance(s.get("domain"), list):
                        out.setdefault(s["name"], []).append(s["domain"])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(vg)
        return out

    @pytest.fixture
    def unsorted_df(self):
        rng = np.random.default_rng(0)
        cats = ["C", "A", "B"]  # deliberately NOT alphabetical
        return pl.DataFrame({"group": [c for c in cats for _ in range(20)], "value": rng.normal(size=60)})

    def test_strip_x_and_color_follow_categories(self, unsorted_df):
        cats = ["C", "A", "B"]
        d = self._domains(mark_strip(unsorted_df, "group", "value", cats))
        assert d.get("x"), "no literal x domain (order not pinned)"
        assert d.get("color"), "no literal colour domain (order not pinned)"
        for dom in d["x"] + d["color"]:
            assert dom == cats, f"{dom} did not preserve categories order {cats}"

    def test_violin_color_follows_categories(self, unsorted_df):
        cats = ["C", "A", "B"]
        d = self._domains(mark_violin(unsorted_df, "group", "value", cats), names=("color",))
        assert d.get("color")
        for dom in d["color"]:
            assert dom == cats

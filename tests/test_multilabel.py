import altair as alt
import numpy as np
import polars as pl
import pytest

from dysonsphere.marks import mark_strip
from dysonsphere.multilabel import _multilabel_layer, add_multilabel
from dysonsphere.theme import theme


@pytest.fixture(autouse=True)
def default_theme():
    theme(dashedWidth=[2, 2])


CATS = ["A", "B", "C", "D"]
GROUPS = {"Row": [True, False, True, False]}

ML_CATS = ["A", "B", "C"]
ML_GROUPS = {"Row 1": [True, False, True]}


class TestSpans:
    def test_line_style_height_larger_than_no_spans(self):
        theme(chartWidth=100)
        base = _multilabel_layer(GROUPS, CATS)
        with_spans = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        assert with_spans._kwds["height"] > base._kwds["height"]

    def test_bracket_style_height_larger_than_line(self):
        theme(chartWidth=100)
        line = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        bracket = _multilabel_layer(
            GROUPS,
            CATS,
            span={"": ["A", "B"]},
            spanBracketStyle="bracket",
            spanBracketReverse=False,
        )
        assert bracket._kwds["height"] > line._kwds["height"]

    def test_label_increases_height(self):
        theme(chartWidth=100)
        no_lbl = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        with_lbl = _multilabel_layer(GROUPS, CATS, span={"Group 1": ["A", "B"]})
        assert with_lbl._kwds["height"] > no_lbl._kwds["height"]

    def test_implicit_span_matches_explicit(self):
        theme(chartWidth=100)
        explicit = _multilabel_layer(GROUPS, CATS, span={"G": ["A", "B", "C"]})
        implicit = _multilabel_layer(GROUPS, CATS, span={"G": ["A", "C"]})
        assert explicit._kwds["height"] == pytest.approx(implicit._kwds["height"])

    def test_span_label_position_top(self):
        theme(chartWidth=100)
        ann = _multilabel_layer(GROUPS, CATS, span={"G1": ["A", "B"]}, spanLabelPosition="top")
        assert isinstance(ann, alt.LayerChart)

    def test_span_reverse(self):
        theme(chartWidth=100)
        rev = _multilabel_layer(
            GROUPS,
            CATS,
            span={"": ["A", "B"]},
            spanBracketStyle="bracket",
            spanBracketReverse=True,
        )
        line = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        assert rev._kwds["height"] == pytest.approx(line._kwds["height"])

    def test_multiple_spans(self):
        theme(chartWidth=100)
        ann = _multilabel_layer(
            GROUPS,
            CATS,
            span={"Group 1": ["A", "B"], "Group 2": ["C", "D"]},
        )
        assert isinstance(ann, alt.LayerChart)

    def test_list_of_dicts_multiple_unlabeled(self):
        theme(chartWidth=100)
        ann = _multilabel_layer(
            GROUPS,
            CATS,
            span=[{None: ["A", "B"]}, {None: ["C", "D"]}],
        )
        assert isinstance(ann, alt.LayerChart)

    def test_invalid_cat_raises(self):
        theme(chartWidth=100)
        with pytest.raises(ValueError, match="not in categories"):
            _multilabel_layer(GROUPS, CATS, span={"G": ["A", "Z"]})

    def test_empty_span_raises(self):
        theme(chartWidth=100)
        with pytest.raises(ValueError, match="must not be empty"):
            _multilabel_layer(GROUPS, CATS, span={"G": []})

    def test_invalid_bracket_style_raises(self):
        theme(chartWidth=100)
        with pytest.raises(ValueError, match="spanBracketStyle"):
            _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]}, spanBracketStyle="arrow")

    def test_invalid_label_position_raises(self):
        theme(chartWidth=100)
        with pytest.raises(ValueError, match="spanLabelPosition"):
            _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]}, spanLabelPosition="left")

    def test_explicit_span_gap_changes_height(self):
        theme(chartWidth=100)
        default_gap = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        large_gap = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]}, spanGap=20)
        assert large_gap._kwds["height"] > default_gap._kwds["height"]

    def test_defer_cat_label_below_spans(self):
        theme(chartWidth=100)
        no_span = _multilabel_layer(GROUPS, CATS, categoryLabel=True, categoryLabelPosition="bottom")
        with_span = _multilabel_layer(
            GROUPS,
            CATS,
            categoryLabel=True,
            categoryLabelPosition="bottom",
            span={"G": ["A", "B"]},
        )
        assert with_span._kwds["height"] > no_span._kwds["height"]


class TestAddMultilabel:
    def test_accepts_plain_chart(self):
        theme(chartWidth=100)
        df = pl.DataFrame({"g": ML_CATS * 5, "v": range(15)})
        base = alt.Chart(df).mark_boxplot().encode(x=alt.X("g:N", sort=ML_CATS), y=alt.Y("v:Q"))
        result = add_multilabel(base, ML_GROUPS, categories=ML_CATS)
        assert isinstance(result, alt.VConcatChart)

    def test_accepts_layer_chart(self):
        theme(chartWidth=100)
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ML_CATS * 20, "v": rng.normal(0, 1, 60).tolist()})
        strip = mark_strip(df, "g", "v", ML_CATS)
        assert isinstance(strip, alt.LayerChart)
        result = add_multilabel(strip, ML_GROUPS, categories=ML_CATS)
        assert isinstance(result, alt.VConcatChart)

    def test_accepts_concat_chart(self):
        # A vconcat stack (e.g. western_blot's image strips): _strip_x_labels recurses into the
        # panels, so the table lands below the whole stack. The param annotation includes the
        # concat types, so this is a first-class call (no type-ignore needed).
        theme(chartWidth=100)
        df = pl.DataFrame({"g": ML_CATS * 5, "v": range(15)})
        panel = alt.Chart(df).mark_boxplot().encode(x=alt.X("g:N", sort=ML_CATS), y="v:Q")
        stack = alt.vconcat(panel, panel)
        assert isinstance(stack, alt.VConcatChart)
        result = add_multilabel(stack, ML_GROUPS, categories=ML_CATS)
        assert isinstance(result, alt.VConcatChart)
        result.to_dict()  # would raise if the composition were malformed


class TestMultilabelLabelMap:
    def test_category_label_row_uses_display_names(self):
        import json

        chart = _multilabel_layer(
            {"C1": [True, False]},
            ["metadata_a", "metadata_b"],
            categoryLabel=True,
            labelMap={"metadata_a": "A!", "metadata_b": ["B", "two lines"]},
        )
        blob = json.dumps(chart.to_dict())
        assert "A!" in blob
        assert "B two lines" in blob  # list labels space-joined in the text row
        # raw values still present (they are the band-scale positions)
        assert "metadata_a" in blob


class TestMultilabelXOrder:
    def _x_domains(self, vg) -> list[list[str]]:
        found: list[list[str]] = []

        def walk(o):
            if isinstance(o, dict):
                for s in o.get("scales", []) or []:
                    if s.get("name") == "x" and isinstance(s.get("domain"), list):
                        found.append(s["domain"])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(vg)
        return found

    def test_shared_x_domain_follows_categories_not_alphabetical(self):
        # Regression: add_multilabel shares the x scale; without pinning the annotation's x
        # domain, resolve_scale(x="shared") re-sorted it alphabetically, so the strip's bars
        # rendered in a different order than the (unshared) colour scale - category colours
        # stopped matching their bars. Use a NON-alphabetical order to catch it.
        import vl_convert as vlc

        cats = ["USA", "Europe", "Japan"]  # not alphabetical
        df = pl.DataFrame({"g": [c for c in cats for _ in range(5)], "y": [float(i) for i in range(15)]})
        strip = mark_strip(df, "g", "y", cats)
        chart = add_multilabel(strip, categories=cats, showSampleSize=True, df=df, xCol="g")
        vg = vlc.vegalite_to_vega(chart.to_dict())
        domains = self._x_domains(vg)
        assert domains, "no resolved x domain found"
        for dom in domains:
            assert dom == cats, f"x domain {dom} did not preserve categories order {cats}"

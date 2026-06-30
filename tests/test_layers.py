import altair as alt
import pytest

from dysonsphere.layers import _rule_mark_kwargs, add_rule
from dysonsphere.multilabel import _multilabel_layer
from dysonsphere.theme import theme


@pytest.fixture(autouse=True)
def default_theme():
    theme(dashedWidth=[2, 2])


class TestRuleMarkKwargs:
    def test_opacity_always_present(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=0.5)
        assert kwargs["opacity"] == pytest.approx(0.5)

    def test_color_none_omitted(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=1.0)
        assert "color" not in kwargs

    def test_color_set(self):
        kwargs = _rule_mark_kwargs(color="red", strokeWidth=None, strokeDash=None, opacity=1.0)
        assert kwargs["color"] == "red"

    def test_stroke_width_none_omitted(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=1.0)
        assert "strokeWidth" not in kwargs

    def test_stroke_width_set(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=2.0, strokeDash=None, opacity=1.0)
        assert kwargs["strokeWidth"] == pytest.approx(2.0)

    def test_stroke_dash_none_omitted(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=1.0)
        assert "strokeDash" not in kwargs

    def test_stroke_dash_false_forces_solid(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=False, opacity=1.0)
        assert kwargs["strokeDash"] == [0, 0]

    def test_stroke_dash_true_reads_theme(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=True, opacity=1.0)
        assert kwargs["strokeDash"] == [2, 2]

    def test_stroke_dash_list_passthrough(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=[4, 2], opacity=1.0)
        assert kwargs["strokeDash"] == [4, 2]


class TestAddRule:
    def test_no_label_returns_chart(self):
        result = add_rule(0.5)
        assert isinstance(result, alt.Chart)

    def test_with_label_returns_layer_chart(self):
        result = add_rule(0.5, label="threshold")
        assert isinstance(result, alt.LayerChart)

    def test_multiple_values_returns_chart(self):
        result = add_rule([0.25, 0.5, 0.75])
        assert isinstance(result, alt.Chart)

    def test_multiple_values_with_labels_returns_layer(self):
        result = add_rule([0.25, 0.75], label=["low", "high"])
        assert isinstance(result, alt.LayerChart)

    def test_vertical_rule(self):
        result = add_rule(5.0, axis="x")
        assert isinstance(result, alt.Chart)

    def test_invalid_axis_raises(self):
        with pytest.raises(ValueError, match="axis"):
            add_rule(0.5, axis="z")


CATS = ["A", "B", "C", "D"]
GROUPS = {"Row": [True, False, True, False]}


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
            GROUPS, CATS, span={"": ["A", "B"]},
            spanBracketStyle="bracket", spanBracketReverse=False,
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
            GROUPS, CATS, span={"": ["A", "B"]}, spanBracketStyle="bracket", spanBracketReverse=True
        )
        line = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        assert rev._kwds["height"] == pytest.approx(line._kwds["height"])

    def test_multiple_spans(self):
        theme(chartWidth=100)
        ann = _multilabel_layer(
            GROUPS, CATS,
            span={"Group 1": ["A", "B"], "Group 2": ["C", "D"]},
        )
        assert isinstance(ann, alt.LayerChart)

    def test_list_of_dicts_multiple_unlabeled(self):
        theme(chartWidth=100)
        ann = _multilabel_layer(
            GROUPS, CATS,
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
            GROUPS, CATS,
            categoryLabel=True,
            categoryLabelPosition="bottom",
            span={"G": ["A", "B"]},
        )
        assert with_span._kwds["height"] > no_span._kwds["height"]

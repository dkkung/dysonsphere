import math
from typing import Any, cast

import altair as alt
import numpy as np
import polars as pl
import pytest

from dysonsphere.marks import mark_violin
from dysonsphere.stats import (
    _BRACKET_TICK_PX,
    _bracket_offsets,
    _correlation_label,
    _drop_tick_lengths,
    _format_asterisks,
    _format_pvalue,
    _resolve_y_spacing,
    _stack_levels,
    comparisons,
    correlation,
)
from dysonsphere.theme import _opt, theme
from dysonsphere.utils import _band_geometry, _nested_band_centers

CATEGORIES = ["A", "B"]


@pytest.fixture(autouse=True)
def default_theme():
    theme(chartWidth=200, chartHeight=200)


@pytest.fixture
def group_df():
    rng = np.random.default_rng(0)
    return pl.DataFrame(
        {
            "group": CATEGORIES * 15,
            "value": rng.normal(0, 1, 30),
        }
    )


class TestFormatPvalue:
    def test_below_threshold(self):
        assert _format_pvalue(0.0005) == "P < 0.001"

    def test_exactly_threshold(self):
        assert _format_pvalue(0.001) == "P = 0.001"

    def test_above_threshold(self):
        assert _format_pvalue(0.0234) == "P = 0.0234"  # 3 sig figs, not floored/rounded to decimals

    def test_custom_sigfigs(self):
        assert _format_pvalue(0.4789, 2) == "P = 0.48"

    def test_p_one_strips_trailing_zeros(self):
        assert _format_pvalue(1.0) == "P = 1"

    def test_p_zero(self):
        assert _format_pvalue(0.0) == "P < 0.001"

    def test_no_trailing_zeros(self):
        assert _format_pvalue(0.6) == "P = 0.6"

    def test_floor_is_fixed_at_0001(self):
        # the floor is a fixed convention, independent of sigFigs
        assert _format_pvalue(0.005) == "P = 0.005"  # above the floor → shown
        assert _format_pvalue(0.0009) == "P < 0.001"  # below → floored
        assert _format_pvalue(0.0009, 5) == "P < 0.001"  # sigFigs doesn't move the floor

    def test_symbol_false_drops_p_and_equals(self):
        # labelStyle="value": no "P", no redundant "= ", but keep a meaningful operator.
        assert _format_pvalue(0.041, symbol=False) == "0.041"  # bare value
        assert _format_pvalue(4e-7, symbol=False) == "< 0.001"  # floored → keep "<"
        assert _format_pvalue(1.23e-5, notation="scientific", symbol=False) == "1.23×10⁻⁵"
        assert _format_pvalue(1.23e-5, notation="e", symbol=False) == "1.23e-05"
        assert _format_pvalue(1e-5, notation="power", symbol=False) == "≈ 10⁻⁵"  # power keeps "≈"


class TestFormatPvalueNotation:
    def test_scientific(self):
        assert _format_pvalue(0.023, 2, "scientific") == "P = 2.3×10⁻²"

    def test_scientific_small(self):
        assert _format_pvalue(1.5e-5, 2, "scientific") == "P = 1.5×10⁻⁵"

    def test_scientific_default_sigfigs(self):
        assert _format_pvalue(0.0234, notation="scientific") == "P = 2.34×10⁻²"  # sigFigs=3

    def test_e_notation(self):
        assert _format_pvalue(0.023, 2, "e") == "P = 2.3e-02"

    def test_e_notation_small(self):
        assert _format_pvalue(1.5e-5, 2, "e") == "P = 1.5e-05"

    def test_e_notation_strips_trailing_zeros(self):
        assert _format_pvalue(4.0e-14, 3, "e") == "P = 4e-14"

    def test_power_rounds_to_nearest(self):
        # log10(0.04) ≈ -1.397 → rounds to -1 → 10⁻¹
        assert _format_pvalue(0.04, notation="power") == "P ≈ 10⁻¹"

    def test_power_exact(self):
        assert _format_pvalue(1e-5, notation="power") == "P ≈ 10⁻⁵"

    def test_power_rounding_far_from_threshold(self):
        # log10(0.006) ≈ -2.22 → rounds to -2 → 10⁻²
        assert _format_pvalue(0.006, notation="power") == "P ≈ 10⁻²"

    def test_invalid_notation_si(self):
        with pytest.raises(ValueError, match="notation must be"):
            _format_pvalue(0.05, notation="si")

    def test_invalid_notation_bogus(self):
        with pytest.raises(ValueError, match="notation must be"):
            _format_pvalue(0.05, notation="bogus")


class TestFormatAsterisks:
    def test_three_stars(self):
        assert _format_asterisks(0.0005) == "***"

    def test_exactly_0001(self):
        assert _format_asterisks(0.001) == "**"

    def test_two_stars(self):
        assert _format_asterisks(0.005) == "**"

    def test_exactly_001(self):
        assert _format_asterisks(0.01) == "*"

    def test_one_star(self):
        assert _format_asterisks(0.025) == "*"

    def test_exactly_005(self):
        assert _format_asterisks(0.05) == "ns"

    def test_ns(self):
        assert _format_asterisks(0.1) == "ns"

    def test_p_one(self):
        assert _format_asterisks(1.0) == "ns"


class TestAddComparisons:
    def test_returns_layer_chart_with_explicit_pvalue(self, group_df):
        result = comparisons(group_df, "group", "value", [("A", "B")], pvalues=[0.01])
        assert isinstance(result, alt.LayerChart)

    def test_returns_layer_chart_running_test(self, group_df):
        result = comparisons(group_df, "group", "value", [("A", "B")])
        assert isinstance(result, alt.LayerChart)

    def test_multiple_pairs(self, group_df):
        df = pl.DataFrame(
            {
                "group": ["A"] * 10 + ["B"] * 10 + ["C"] * 10,
                "value": np.random.default_rng(1).normal(0, 1, 30),
            }
        )
        result = comparisons(
            df,
            "group",
            "value",
            [("A", "B"), ("B", "C")],
            pvalues=[0.01, 0.05],
        )
        assert isinstance(result, alt.LayerChart)

    def test_auto_ystep_is_1_75x_ypad(self):
        # Two overlapping pairs stack; the auto level gap is 1.75 * yPad - enough that a
        # bracket's label clears the bracket above it without the airy spacing 2x gave.
        df = pl.DataFrame(
            {
                "group": ["A"] * 4 + ["B"] * 4 + ["C"] * 4,
                "value": [1.0, 2.0, 3.0, 4.0] * 3,
            }
        )
        result = comparisons(
            df,
            "group",
            "value",
            [("A", "C"), ("B", "C")],  # overlapping spans -> two stacking levels
            pvalues=[0.01, 0.02],
            yPad=5.0,
        )
        spec = result.to_dict()
        # Each pair's first sub-layer is the horizontal bar ({x, x2, y}); collect the two ys.
        bar_ys = [pair_layer["layer"][0]["data"]["values"][0]["y"] for pair_layer in spec["layer"]]
        assert abs(abs(bar_ys[1] - bar_ys[0]) - 1.75 * 5.0) < 1e-9

    def test_auto_brackets_anchor_on_their_own_pair(self):
        # Each bracket anchors at ITS OWN pair's data maximum, not the tallest annotated group,
        # so a bracket over two low groups stays with them. An un-annotated group ("Z") that
        # dominates the domain must not move anything: placement is pixel offsets off the
        # anchors, evaluated against the real scale, so the domain never enters the arithmetic.
        df = pl.DataFrame(
            {
                "group": ["A"] * 4 + ["B"] * 4 + ["C"] * 4 + ["Z"] * 4,
                "value": [0.0, 0.1, 0.05, 0.08]
                + [0.2, 0.25, 0.22, 0.28]
                + [0.4, 0.45, 0.42, 0.48]
                + [0.0, 100.0, 50.0, 25.0],  # un-annotated, dominates the domain
            }
        )
        result = comparisons(df, "group", "value", [("A", "B"), ("A", "C")], pvalues=[0.01, 0.02])
        spec = result.to_dict()
        bar_ys = [pair_layer["layer"][0]["data"]["values"][0]["y"] for pair_layer in spec["layer"]]
        # These two overlap, so they share one ladder anchored at C's max (0.48) - the tallest
        # category any of them spans. Crucially it is NOT Z's 100: an un-annotated group never
        # drags a bracket up. Disjoint brackets keep separate anchors (see the disjoint test).
        assert bar_ys == pytest.approx([0.48, 0.48])

    def test_auto_bracket_clears_a_taller_group_it_spans(self):
        # A bracket from A to C passes over B, so its anchor is the maximum over every category
        # it SPANS - not just its two endpoints. Anchoring on the endpoints alone puts the bracket
        # below a taller middle group, and on a bar chart it would cross straight through that bar.
        df = pl.DataFrame(
            {
                "group": ["A"] * 4 + ["B"] * 4 + ["C"] * 4,
                "value": [4.0, 4.1, 3.9, 4.05] + [14.0, 14.2, 13.8, 14.1] + [5.0, 5.1, 4.9, 5.05],
            }
        )
        spec = comparisons(df, "group", "value", [("A", "C")], pvalues=[0.01], categories=["A", "B", "C"]).to_dict()
        anchor = spec["layer"][0]["layer"][0]["data"]["values"][0]["y"]
        assert anchor == pytest.approx(14.2), "anchor should be B's maximum, the tallest spanned group"

    def test_auto_brackets_lift_by_a_constant_pixel_offset(self):
        # The lift is a plain number, not a `scale('y', …)` expression. An expression would be
        # exact under a custom domain but resolves against nothing inside a facet/concat (Vega
        # renames the scale there), which silently wrecks `add_multilabel` compositions.
        df = pl.DataFrame({"group": ["A"] * 4 + ["B"] * 4, "value": [1.0, 2, 3, 4] + [5.0, 6, 7, 8]})
        spec = comparisons(df, "group", "value", [("A", "B")], pvalues=[0.01]).to_dict()
        y_offset = spec["layer"][0]["layer"][0]["mark"]["yOffset"]
        assert isinstance(y_offset, (int, float)), f"expected a constant offset, got {y_offset!r}"
        assert y_offset == pytest.approx(-6.0)

    def test_overlapping_brackets_form_an_even_ladder(self):
        # Brackets that overlap sit on evenly spaced rungs, as low as every bracket's own data
        # allows - so a short comparison rises to join the rhythm instead of being stranded
        # well below the others (the Europe-Japan case on the pairwise guide page).
        df = pl.DataFrame(
            {
                "group": ["A"] * 6 + ["B"] * 6 + ["C"] * 6,
                "value": [80.0, 90, 100, 110, 120, 130] * 2 + [150.0, 170, 190, 210, 220, 230],
            }
        )
        theme(chartHeight=100, fontSize=7)
        spec = comparisons(
            df,
            "group",
            "value",
            [("A", "B"), ("A", "C"), ("B", "C")],
            pvalues=[0.5, 0.001, 0.001],
            categories=["A", "B", "C"],
        ).to_dict()
        # All rungs of a ladder hang off ONE anchor, so their spacing is a difference of pixel
        # offsets - no data-to-pixel map involved, which is what makes it exact on a log axis.
        anchors = {pair["layer"][0]["data"]["values"][0]["y"] for pair in spec["layer"]}
        assert len(anchors) == 1, f"one ladder should share one anchor, got {anchors}"
        # offsets are signed - a bracket below the shared anchor gets a positive (downward) one
        rungs = sorted(pair["layer"][0]["mark"]["yOffset"] for pair in spec["layer"])
        gaps = [round(rungs[i + 1] - rungs[i], 6) for i in range(len(rungs) - 1)]
        assert len(set(gaps)) == 1, f"rungs should be evenly spaced, got {gaps}"

    def test_reverse_brackets_anchor_below_their_data(self):
        # A `reverse` bracket hangs BELOW its groups, so it anchors on their MINIMUM and its ladder
        # descends. Anchoring on the maximum (the upward rule) and then hanging downward from it
        # drops the bracket and its label straight onto the data.
        df = pl.DataFrame({"group": ["A"] * 4 + ["B"] * 4, "value": [5.0, 5.4, 4.6, 5.2] + [8.0, 8.4, 7.6, 8.2]})
        spec = comparisons(df, "group", "value", [("A", "B")], pvalues=[0.01], reverse=[("A", "B")]).to_dict()
        pair = spec["layer"][0]
        assert pair["layer"][0]["data"]["values"][0]["y"] == pytest.approx(4.6)
        # positive offset = further down the screen
        assert pair["layer"][0]["mark"]["yOffset"] > 0

    def test_mixed_directions_do_not_share_a_ladder(self):
        # Brackets above and below sit on opposite sides of the data, so neither pushes the other.
        df = pl.DataFrame(
            {
                "group": ["A"] * 4 + ["B"] * 4 + ["C"] * 4,
                "value": [5.0, 5.4, 4.6, 5.2] + [7.0, 7.4, 6.6, 7.2] + [9.0, 9.4, 8.6, 9.2],
            }
        )
        spec = comparisons(
            df,
            "group",
            "value",
            [("A", "B"), ("A", "C")],
            pvalues=[0.01, 0.02],
            categories=["A", "B", "C"],
            reverse=[("A", "B")],
        ).to_dict()
        offs = [pair["layer"][0]["mark"]["yOffset"] for pair in spec["layer"]]
        assert offs[0] > 0 and offs[1] < 0, f"one each way, got {offs}"
        # each sits the plain gap off its own data - neither was bumped by the other
        assert abs(offs[0]) == pytest.approx(6.0) and abs(offs[1]) == pytest.approx(6.0)

    def test_disjoint_brackets_are_not_tied_to_one_ladder(self):
        # Brackets sharing no category are independent: each hugs its own groups rather than the
        # shorter one floating up to meet a taller comparison elsewhere in the chart.
        df = pl.DataFrame(
            {
                "group": ["A"] * 4 + ["B"] * 4 + ["C"] * 4 + ["D"] * 4,
                "value": [1.0, 1.1, 0.9, 1.05] * 2 + [50.0, 51, 49, 50.5] * 2,
            }
        )
        spec = comparisons(
            df,
            "group",
            "value",
            [("A", "B"), ("C", "D")],
            pvalues=[0.01, 0.02],
            categories=["A", "B", "C", "D"],
        ).to_dict()
        offsets = [abs(pair["layer"][0]["mark"]["yOffset"]) for pair in spec["layer"]]
        assert offsets == [pytest.approx(6.0), pytest.approx(6.0)]

    def test_auto_bracket_stack_clears_its_labels(self):
        # Overlapping spans are pushed apart by at least a label's worth of pixels. Too small a
        # step puts the lower bracket's label through the bar above it (the collision that a
        # flat 10 px minimum produced).
        # B and C top out at the same value, so both brackets want the same height and one has to
        # be bumped. Separation comes from the offsets only when the anchors coincide like this;
        # otherwise the anchors themselves already hold them apart.
        df = pl.DataFrame(
            {
                "group": ["A"] * 4 + ["B"] * 4 + ["C"] * 4,
                "value": [1.0, 1.1, 1.05, 1.08] + [2.0, 2.1, 2.05, 2.08] + [2.0, 2.1, 2.05, 2.08],
            }
        )
        theme(chartHeight=200, fontSize=7)
        spec = comparisons(df, "group", "value", [("A", "B"), ("A", "C")], pvalues=[0.01, 0.02]).to_dict()
        anchors = [pair["layer"][0]["data"]["values"][0]["y"] for pair in spec["layer"]]
        assert anchors[0] == anchors[1], "this case is only meaningful when the anchors coincide"
        offsets = sorted(abs(pair["layer"][0]["mark"]["yOffset"]) for pair in spec["layer"])
        assert offsets[1] - offsets[0] >= 7 + 6 - 1e-6

    def test_top_preset_test_label_raises_only_the_domain_top(self):
        # A top-preset test label sits flush with the plot edge, which is where the brackets now
        # are. The bracket layer raises only the TOP of the shared y scale so the stack fits
        # under it - the lower bound, `zero` and nice-rounding must be left alone.
        df = pl.DataFrame(
            {
                "group": ["A"] * 5 + ["B"] * 5 + ["C"] * 5,
                "value": [1.0, 1.2, 0.9, 1.1, 1.05] + [3.0, 3.2, 2.9, 3.1, 3.05] + [6.0, 6.2, 5.9, 6.1, 6.05],
            }
        )
        spec = comparisons(
            df, "group", "value", [("A", "B"), ("A", "C")], test="anova", categories=["A", "B", "C"]
        ).to_dict()
        scales = [
            sub["encoding"]["y"]["scale"]
            for pair in spec["layer"]
            for sub in pair.get("layer", [])
            if isinstance(sub.get("encoding", {}).get("y"), dict) and "scale" in sub["encoding"]["y"]
        ]
        assert len(scales) == 1, "exactly one layer should carry the bound"
        assert "domainMax" in scales[0] and set(scales[0]) == {"domainMax"}
        assert scales[0]["domainMax"] > df["value"].cast(pl.Float64).max()

    def test_closed_plot_raises_the_domain_for_its_brackets(self):
        # A closed plot draws a border around the plot area, so a bracket in the margin above it
        # is outside the box - with its label further out still. Raise the top so the stack sits
        # inside the frame, the same lift a top-preset test label gets.
        df = pl.DataFrame(
            {
                "group": ["A"] * 4 + ["B"] * 4 + ["C"] * 4,
                "value": [1.0, 1.2, 0.9, 1.1] + [3.0, 3.2, 2.9, 3.1] + [6.0, 6.2, 5.9, 6.1],
            }
        )
        theme(closed=True)
        spec = comparisons(
            df, "group", "value", [("A", "B"), ("A", "C")], pvalues=[0.01, 0.02], categories=["A", "B", "C"]
        ).to_dict()
        bounds = [
            sub["encoding"]["y"]["scale"]
            for pair in spec["layer"]
            for sub in pair.get("layer", [])
            if "scale" in sub.get("encoding", {}).get("y", {})
        ]
        assert len(bounds) == 1 and set(bounds[0]) == {"domainMax"}
        assert bounds[0]["domainMax"] > df["value"].cast(pl.Float64).max()

    def test_no_domain_bound_without_a_top_label(self):
        # Nothing to clear: a pairwise call draws no test label by default, so the axis is
        # left exactly as the user's data defines it.
        df = pl.DataFrame({"group": ["A"] * 4 + ["B"] * 4, "value": [1.0, 2, 3, 4] + [5.0, 6, 7, 8]})
        spec = comparisons(df, "group", "value", [("A", "B")], pvalues=[0.01]).to_dict()
        assert not [
            sub
            for pair in spec["layer"]
            for sub in pair.get("layer", [])
            if "scale" in sub.get("encoding", {}).get("y", {})
        ]

    def test_explicit_spacing_args_opt_out_of_pixel_mode(self):
        # yStep / yPad / yStart / yPositions are the user's own numbers on their own scale, so
        # passing any of them keeps data-unit placement rather than being silently ignored.
        df = pl.DataFrame({"group": ["A"] * 4 + ["B"] * 4, "value": [1.0, 2, 3, 4] + [5.0, 6, 7, 8]})
        args = [("A", "B")]

        def _no_expr(chart, why):
            spec = chart.to_dict()
            marks = [sub["mark"] for sub in spec["layer"][0]["layer"] if isinstance(sub.get("mark"), dict)]
            assert marks, "expected bracket sub-layers"
            assert not any("expr" in str(m.get("yOffset", "")) for m in marks), why

        _no_expr(comparisons(df, "group", "value", args, pvalues=[0.01], yStep=2.0), "yStep")
        _no_expr(comparisons(df, "group", "value", args, pvalues=[0.01], yPad=1.5), "yPad")
        _no_expr(comparisons(df, "group", "value", args, pvalues=[0.01], yStart=12.0), "yStart")

    def test_asterisk_label_style(self, group_df):
        result = comparisons(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[0.001],
            labelStyle="asterisks",
        )
        assert isinstance(result, alt.LayerChart)

    def test_unknown_test_raises(self, group_df):
        with pytest.raises(ValueError, match="Unknown test"):
            comparisons(group_df, "group", "value", [("A", "B")], test="bogus")

    def test_incomplete_categories_raises(self):
        # an explicit `categories` that omits an x-value in the data mis-sizes the band geometry and
        # would silently shift the brackets - raise instead (naming the missing value).
        df = pl.DataFrame({"group": ["A"] * 5 + ["B"] * 5 + ["C"] * 5, "value": list(range(15))})
        with pytest.raises(ValueError, match="categories is missing"):
            comparisons(df, "group", "value", [("A", "B")], categories=["A", "B"])

    @pytest.mark.parametrize("categories", [["A", "B", "D"], ["A", "B", "B"]])
    def test_categories_reject_extra_or_duplicate_values(self, categories):
        df = pl.DataFrame({"group": ["A"] * 5 + ["B"] * 5, "value": list(range(10))})
        with pytest.raises(ValueError, match="categories"):
            comparisons(df, "group", "value", [("A", "B")], pvalues=[0.1], categories=categories)

    def test_notation_scientific(self, group_df):
        result = comparisons(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[1.5e-5],
            notation="scientific",
            sigFigs=2,
        )
        assert isinstance(result, alt.LayerChart)
        spec = result.to_dict()
        label = spec["layer"][0]["layer"][-1]["data"]["values"][0]["label"]
        assert label == "P = 1.5×10⁻⁵"

    def test_notation_e(self, group_df):
        result = comparisons(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[1.5e-5],
            notation="e",
            sigFigs=2,
        )
        assert isinstance(result, alt.LayerChart)

    def test_notation_power(self, group_df):
        result = comparisons(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[1e-5],
            notation="power",
        )
        assert isinstance(result, alt.LayerChart)
        spec = result.to_dict()
        label = spec["layer"][0]["layer"][-1]["data"]["values"][0]["label"]
        assert label == "P ≈ 10⁻⁵"

    def test_notation_default_unchanged(self, group_df):
        result = comparisons(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[0.023],
        )
        spec = result.to_dict()
        label = spec["layer"][0]["layer"][-1]["data"]["values"][0]["label"]
        assert label == "P = 0.023"

    def test_label_uses_primary_font_size(self, group_df):
        theme(chartWidth=200, chartHeight=200, fontSize=10)  # statistics labels use fontSize
        spec = comparisons(group_df, "group", "value", [("A", "B")], pvalues=[0.01]).to_dict()
        assert spec["layer"][0]["layer"][-1]["mark"]["fontSize"] == 10


def _text_labels(layer):
    """Pull rendered text-mark strings from a chart spec.

    text (test label, correlation readout) encodes its string via ``alt.value`` (an
    ``encoding.text.value`` literal), not a dataset field - walk the layer tree for those.
    """
    found: list[Any] = []

    def walk(node):
        if isinstance(node, dict):
            text_enc = node.get("encoding", {}).get("text")
            if isinstance(text_enc, dict) and "value" in text_enc:
                found.append(text_enc["value"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(layer.to_dict())
    return found


class TestTestLabel:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def test_pairwise_no_label_by_default(self, tri_df):
        layer = comparisons(tri_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=MULTI)
        assert _text_labels(layer) == []  # auto → hidden for pairwise

    def test_pairwise_label_opt_in(self, tri_df):
        layer = comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, testLabelPosition="topRight")
        assert _text_labels(layer) == ["Mann-Whitney U"]

    def test_pairwise_label_wilcoxon_name(self, tri_df):
        layer = comparisons(
            tri_df, "g", "v", [("A", "B")], categories=MULTI, test="wilcoxon", testLabelPosition="topRight"
        )
        assert _text_labels(layer) == ["Wilcoxon signed-rank"]

    def test_omnibus_label_shown_by_default(self, tri_df):
        layer = comparisons(tri_df, "g", "v", categories=MULTI, test="anova")
        assert _text_labels(layer)[0].startswith("ANOVA P")  # auto → topLeft for omnibus

    def test_omnibus_label_hidden(self, tri_df):
        layer = comparisons(tri_df, "g", "v", categories=MULTI, test="anova", testLabelPosition=None)
        assert _text_labels(layer) == []

    def test_omnibus_posthoc_shows_omnibus_not_posthoc(self, tri_df):
        layer = comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, test="anova")
        labels = _text_labels(layer)
        assert any(t.startswith("ANOVA P") for t in labels) and "Tukey HSD" not in labels

    def test_test_label_override(self, tri_df):
        layer = comparisons(
            tri_df, "g", "v", categories=MULTI, test="anova", testLabel="my label", testLabelPosition="topLeft"
        )
        assert _text_labels(layer) == ["my label"]

    def test_manual_coords_draw_label(self, tri_df):
        layer = comparisons(
            tri_df, "g", "v", categories=MULTI, test="anova", testLabelPosition=None, testLabelX=1.0, testLabelY=2.0
        )
        assert _text_labels(layer)[0].startswith("ANOVA P")

    def test_omnibus_label_never_asterisks(self, tri_df):
        # labelStyle="asterisks" affects only the brackets, not the omnibus result label
        layer = comparisons(tri_df, "g", "v", categories=MULTI, test="kruskal", labelStyle="asterisks")
        label = _text_labels(layer)[0]
        assert " P " in label and "*" not in label


class TestTickHeight:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def test_tick_height_is_a_fixed_pixel_length(self, tri_df):
        # The end legs are a fixed pixel length off the bracket bar, not a data-unit conversion,
        # so they are the same length whatever the y range. Both ends sit at the same anchor and
        # the leg length rides in y2Offset.
        theme(chartWidth=200, chartHeight=200, tickSize=3)
        layer = comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, bracketStyle="bracket")
        spec = layer.to_dict()
        legs = [
            sub["mark"]
            for sub in spec["layer"][0]["layer"]
            if isinstance(sub.get("mark"), dict) and "y2Offset" in sub.get("mark", {})
        ]
        assert legs, "expected end-leg layers carrying a y2Offset"
        # the leg spans _BRACKET_TICK_PX from the bar, whatever the y range - and does NOT
        # follow tickSize, which is set to a different value here on purpose
        assert all(abs(m["y2Offset"] - m["yOffset"]) == pytest.approx(_BRACKET_TICK_PX) for m in legs)

    def test_auto_tick_height_is_pixels_even_with_explicit_positions(self, tri_df):
        # The legs are a pixel length by definition. Deriving them in data units assumes a linear
        # axis, and on a log axis they collapse to a fraction of a pixel - so an auto tickHeight
        # rides in y2Offset whichever placement mode is in use.
        theme(chartWidth=200, chartHeight=200, tickSize=3)
        spec = comparisons(
            tri_df, "g", "v", [("A", "B")], categories=MULTI, bracketStyle="bracket", yPositions=[99.0]
        ).to_dict()
        legs = [
            sub["mark"]
            for sub in spec["layer"][0]["layer"]
            if isinstance(sub.get("mark"), dict) and "y2Offset" in sub.get("mark", {})
        ]
        assert legs, "explicit positions should still get pixel end legs"
        assert all(abs(m["y2Offset"] - m.get("yOffset", 0)) == pytest.approx(_BRACKET_TICK_PX) for m in legs)

    def test_tick_height_explicit_stays_data_units(self, tri_df):
        # An explicit tickHeight is a data-unit number on the user's scale, unchanged.
        theme(chartWidth=200, chartHeight=200, tickSize=3)
        layer = comparisons(
            tri_df, "g", "v", [("A", "B")], categories=MULTI, bracketStyle="bracket", yStart=10.0, tickHeight=0.5
        )
        spec = layer.to_dict()
        gaps = [
            abs(v["y"] - v["y2"])
            for sub in spec["layer"][0]["layer"]
            for v in sub.get("data", {}).get("values", [])
            if "y" in v and "y2" in v
        ]
        assert any(abs(g - 0.5) < 1e-9 for g in gaps)


class TestLabelBaseline:
    @pytest.fixture
    def two_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12, "v": rng.normal(0, 1, 24)})

    def _text_mark(self, layer):
        def walk(node):
            if isinstance(node, dict):
                m = node.get("mark")
                if isinstance(m, dict) and m.get("type") == "text":
                    return m
                for sub in node.get("layer", []):
                    found = walk(sub)
                    if found:
                        return found
            return None

        m = walk(layer.to_dict())
        assert m is not None, "no text mark found"
        return m

    def test_non_reverse_keeps_inherited_baseline(self, two_df):
        m = self._text_mark(comparisons(two_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=CATEGORIES))
        assert "baseline" not in m  # reverse=False must not set an explicit baseline

    def test_reverse_sets_top_baseline(self, two_df):
        layer = comparisons(two_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=CATEGORIES, reverse=[("A", "B")])
        assert self._text_mark(layer)["baseline"] == "top"


class TestBracketStyleDict:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def _rule_counts(self, layer):
        """Map each bracket (bar x/x2) to its number of rule marks: 1 = line, 3 = bracket."""
        counts = {}
        for sub in layer.to_dict()["layer"]:
            rules = [s for s in sub.get("layer", []) if isinstance(s.get("mark"), dict) and s["mark"]["type"] == "rule"]
            if rules:
                bar = rules[0]["data"]["values"][0]
                counts[(bar["x"], bar["x2"])] = len(rules)
        return counts

    def _run(self, tri_df, style):
        return comparisons(
            tri_df, "g", "v", [("A", "B"), ("A", "C")], pvalues=[0.01, 0.02], categories=MULTI, bracketStyle=style
        )

    def test_uniform_line(self, tri_df):
        assert set(self._rule_counts(self._run(tri_df, "line")).values()) == {1}

    def test_uniform_bracket(self, tri_df):
        assert set(self._rule_counts(self._run(tri_df, "bracket")).values()) == {3}

    def test_dict_per_pair(self, tri_df):
        counts = self._rule_counts(self._run(tri_df, {("A", "B"): "line", ("A", "C"): "bracket"}))
        assert counts[("A", "B")] == 1 and counts[("A", "C")] == 3

    def test_dict_order_insensitive_and_fallback(self, tri_df):
        # reversed key still matches A-B; A-C is absent → falls back to "bracket"
        counts = self._rule_counts(self._run(tri_df, {("B", "A"): "line"}))
        assert counts[("A", "B")] == 1 and counts[("A", "C")] == 3

    def test_dict_invalid_value_raises(self, tri_df):
        with pytest.raises(ValueError, match="bracketStyle dict values"):
            self._run(tri_df, {("A", "B"): "squiggle"})

    def test_invalid_string_raises(self, tri_df):
        with pytest.raises(ValueError, match="bracketStyle must be"):
            self._run(tri_df, "squiggle")


class TestSigFigs:
    @pytest.fixture
    def group_df(self):
        return pl.DataFrame({"g": ["A"] * 10 + ["B"] * 10, "v": [float(i) for i in range(20)]})

    def _label(self, layer):
        return layer.to_dict()["layer"][0]["layer"][-1]["data"]["values"][0]["label"]

    def test_theme_sigfigs_drives_label(self, group_df):
        theme(chartWidth=200, chartHeight=200, sigFigs=2)
        assert self._label(comparisons(group_df, "g", "v", [("A", "B")], pvalues=[0.4789])) == "P = 0.48"

    def test_per_call_overrides_theme(self, group_df):
        theme(chartWidth=200, chartHeight=200, sigFigs=2)
        lbl = self._label(comparisons(group_df, "g", "v", [("A", "B")], pvalues=[0.4789], sigFigs=4))
        assert lbl == "P = 0.4789"

    def test_report_independent_of_theme_sigfigs(self):
        # theme sigFigs=2, but the report stays at its fixed 3 sig figs
        theme(chartWidth=200, chartHeight=200, sigFigs=2)
        assert st._fmt_p(0.47891234) == "= 0.479"
        assert st._fmt(0.47891234) == "0.479"


class TestNotationDict:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def _bracket_labels(self, layer):
        """Map bracket bar (x, x2) → its label text (inline-data brackets)."""
        labels = {}
        for sub in layer.to_dict()["layer"]:
            bar_x = None
            texts = []
            for s in sub.get("layer", []):
                for v in (s.get("data") or {}).get("values", []) if isinstance(s.get("data"), dict) else []:
                    if "x2" in v:
                        bar_x = (v["x"], v["x2"])
                    if "label" in v:
                        texts.append(v["label"])
            if bar_x and texts:
                labels[bar_x] = texts[0]
        return labels

    def _test_label(self, layer):
        vals = _text_labels(layer)
        return vals[0] if vals else None

    def test_scalar_applies_to_all(self, tri_df):
        labels = self._bracket_labels(
            comparisons(
                tri_df,
                "g",
                "v",
                [("A", "B"), ("A", "C")],
                pvalues=[1e-5, 1e-8],
                categories=MULTI,
                notation="scientific",
            )
        )
        assert all("×10" in v for v in labels.values())

    def test_dict_per_pair(self, tri_df):
        labels = self._bracket_labels(
            comparisons(
                tri_df,
                "g",
                "v",
                [("A", "B"), ("A", "C")],
                pvalues=[1e-5, 1e-8],
                categories=MULTI,
                notation={("A", "B"): "scientific", ("A", "C"): "power"},
            )
        )
        assert "×10" in labels[("A", "B")] and "≈ 10" in labels[("A", "C")]

    def test_dict_unlisted_pair_is_plain(self, tri_df):
        labels = self._bracket_labels(
            comparisons(
                tri_df,
                "g",
                "v",
                [("A", "B"), ("A", "C")],
                pvalues=[0.012, 1e-8],
                categories=MULTI,
                notation={("A", "C"): "scientific"},
            )
        )
        assert labels[("A", "B")] == "P = 0.012" and "×10" in labels[("A", "C")]

    def test_test_key_sets_omnibus_notation(self, tri_df):
        layer = comparisons(tri_df, "g", "v", categories=MULTI, test="anova", notation={"test": "e"})
        assert "e-" in self._test_label(layer) or "e+" in self._test_label(layer)

    def test_dict_without_test_key_omnibus_plain(self, tri_df):
        layer = comparisons(tri_df, "g", "v", categories=MULTI, test="anova", notation={("A", "B"): "scientific"})
        assert self._test_label(layer).startswith("ANOVA P = 0.")

    def test_invalid_value_raises(self, tri_df):
        with pytest.raises(ValueError, match="notation dict values"):
            comparisons(tri_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=MULTI, notation={("A", "B"): "si"})

    def test_invalid_string_key_raises(self, tri_df):
        with pytest.raises(ValueError, match="notation dict string keys must be 'test'"):
            comparisons(tri_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=MULTI, notation={"omnibus": "e"})


class TestCorrectionMetadata:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def test_correction_recorded(self, tri_df):
        from dysonsphere import _statistics as _st

        _st._REPORTS.clear()
        comparisons(tri_df, "g", "v", [("A", "B"), ("A", "C")], categories=MULTI, correction="holm")
        rec = next(iter(_st._REPORTS.values()))
        assert rec["comparisons"]["correction"] == "holm"

    def test_tukey_correction_stored_none(self, tri_df):
        from dysonsphere import _statistics as _st

        _st._REPORTS.clear()
        comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, test="anova", correction="bonferroni")
        rec = next(iter(_st._REPORTS.values()))
        assert rec["comparisons"]["correction"] is None  # tukey carries its own correction

    def test_fdr_correction_recorded(self, tri_df):
        from dysonsphere import _statistics as _st

        _st._REPORTS.clear()
        comparisons(tri_df, "g", "v", [("A", "B"), ("A", "C")], categories=MULTI, correction="fdr_bh")
        rec = next(iter(_st._REPORTS.values()))
        assert rec["comparisons"]["correction"] == "fdr_bh"


# ── Pure statistics module (dysonsphere._statistics) ─────────────────────────
from dysonsphere import _statistics as st  # noqa: E402

MULTI = ["A", "B", "C"]
_A = np.array([1.0, 2, 3, 4, 5])
_B = np.array([3.0, 4, 5, 6, 7])
_C = np.array([6.0, 7, 8, 9, 10])
_GROUPS = [_A, _B, _C]


class TestPostHocReference:
    """Golden values validated against scikit-posthocs (Dunn, Nemenyi) and pingouin (Games-Howell)."""

    def test_dunn(self):
        assert float(st._dunn_matrix(_GROUPS)[0, 2]) == pytest.approx(0.002003, abs=1e-6)

    def test_games_howell(self):
        assert float(st._games_howell_matrix(_GROUPS)[0, 2]) == pytest.approx(0.002669, abs=1e-6)

    def test_nemenyi(self):
        assert float(st._nemenyi_matrix(_GROUPS)[0, 2]) == pytest.approx(0.004464, abs=1e-6)

    @pytest.mark.parametrize("fn", [st._dunn_matrix, st._games_howell_matrix, st._nemenyi_matrix])
    def test_matrix_invariants(self, fn):
        m = fn(_GROUPS)
        assert m.shape == (3, 3)
        assert np.allclose(np.diag(m), 1.0)
        assert np.allclose(m, m.T)  # symmetric
        off = m[~np.eye(3, dtype=bool)]
        assert np.all((off >= 0) & (off <= 1))

    def test_nemenyi_requires_balanced(self):
        with pytest.raises(ValueError, match="balanced"):
            st._nemenyi_matrix([_A, _B, np.array([1.0, 2, 3])])


class TestOmnibusRunners:
    def test_anova(self):
        r = st._run_omnibus("anova", _GROUPS, MULTI)
        assert r.statSymbol == "F" and r.df == (2, 12)
        assert r.stat == pytest.approx(12.666667, abs=1e-5)
        assert r.pvalue == pytest.approx(0.001103, abs=1e-5)
        assert r.effectName == "η²" and r.effectSize == pytest.approx(0.678571, abs=1e-5)

    def test_kruskal(self):
        r = st._run_omnibus("kruskal", _GROUPS, MULTI)
        assert r.statSymbol == "H" and r.df == (2,)
        assert r.effectName == "ε²" and r.effectSize == pytest.approx(0.688649, abs=1e-5)

    def test_friedman(self):
        r = st._run_omnibus("friedman", _GROUPS, MULTI)
        assert r.statSymbol == "χ²" and r.effectName == "W"
        assert 0 <= r.effectSize <= 1

    def test_alexandergovern(self):
        r = st._run_omnibus("alexandergovern", _GROUPS, MULTI)
        assert r.statSymbol == "A" and r.effectName == "η²"

    def test_unknown(self):
        with pytest.raises(ValueError, match="Unknown omnibus"):
            st._run_omnibus("nope", _GROUPS, MULTI)

    def test_friedman_requires_balanced(self):
        with pytest.raises(ValueError, match="balanced"):
            st._run_omnibus("friedman", [_A, _B, np.array([1.0, 2, 3])], MULTI)


class TestAdjust:
    def test_none(self):
        assert st._adjust([0.01, 0.02], None, 3) == [0.01, 0.02]

    def test_bonferroni(self):
        assert st._adjust([0.01, 0.5], "bonferroni", 3) == pytest.approx([0.03, 1.0])

    def test_holm_monotone_and_capped(self):
        out = st._adjust([0.01, 0.02, 0.03], "holm", 3)
        assert out == sorted(out)  # non-decreasing in p order
        assert all(p <= 1.0 for p in out)

    def test_fdr_bh_matches_scipy(self):
        # scipy's false_discovery_control is the reference (m == len case).
        from scipy.stats import false_discovery_control as fdc

        pvals = [0.01, 0.02, 0.03, 0.005, 0.5]
        expected = fdc(pvals, method="bh").tolist()
        assert st._adjust(pvals, "fdr_bh", len(pvals)) == pytest.approx(expected)

    def test_fdr_by_matches_scipy(self):
        from scipy.stats import false_discovery_control as fdc

        pvals = [0.01, 0.02, 0.03, 0.005, 0.5]
        expected = fdc(pvals, method="by").tolist()
        assert st._adjust(pvals, "fdr_by", len(pvals)) == pytest.approx(expected)

    def test_fdr_bh_monotone_in_p_order_and_capped(self):
        pvals = [0.04, 0.01, 0.2, 0.005, 0.03]
        out = st._adjust(pvals, "fdr_bh", len(pvals))
        # Adjusted p-values are non-decreasing when sorted by the raw p-value.
        by_rank = [out[i] for i in sorted(range(len(pvals)), key=lambda i: pvals[i])]
        assert by_rank == sorted(by_rank)
        assert all(0.0 <= p <= 1.0 for p in out)

    def test_fdr_by_more_conservative_than_bh(self):
        pvals = [0.01, 0.02, 0.03, 0.005, 0.5]
        bh = st._adjust(pvals, "fdr_bh", len(pvals))
        by = st._adjust(pvals, "fdr_by", len(pvals))
        assert all(b >= h for b, h in zip(by, bh))

    def test_fdr_bh_honors_larger_family_size(self):
        # m (total family) may exceed len(pvals) via nComparisons; the denominator
        # and BY factor both use m, so a larger family inflates the adjusted values.
        pvals = [0.01, 0.02]
        small = st._adjust(pvals, "fdr_bh", 2)
        large = st._adjust(pvals, "fdr_bh", 10)
        assert all(g >= s for g, s in zip(large, small))
        # p(i) * m / i, then running min from the top: [0.01*10/1, 0.02*10/2] = [0.1, 0.1].
        assert large == pytest.approx([0.1, 0.1])

    def test_unknown(self):
        with pytest.raises(ValueError, match="correction"):
            st._adjust([0.1], "bogus", 1)


class TestReportRegistry:
    def test_describe(self):
        d = st._describe("X", np.array([1.0, 2, 3, 4]))
        assert d["n"] == 4 and d["mean"] == pytest.approx(2.5) and d["median"] == pytest.approx(2.5)

    def test_register_dedups_and_marks(self):
        st._REPORTS.clear()
        same = {"kind": "pairwise", "test": "x"}
        other = {"kind": "omnibus", "test": "y"}
        m1 = st._register_report(dict(same))
        m2 = st._register_report(dict(same))  # identical content
        m3 = st._register_report(dict(other))
        # identical content collapses to one entry (keyed by hash); distinct content is separate
        assert len(st._REPORTS) == 2
        # marker names are unique (nonce) even for identical content, so a spec never has dup names
        assert m1 != m2
        h1, h2, h3 = st._marker_hash(m1), st._marker_hash(m2), st._marker_hash(m3)
        assert h1 is not None and h2 is not None and h3 is not None
        assert h1 == h2  # same content → same hash
        assert h1 != h3
        assert st._live_report(h1) == same
        assert st._live_report(h3) == other
        assert st._live_report("missing") is None

    def test_make_record_structure(self):
        r = st._run_omnibus("anova", _GROUPS, MULTI)
        rec = st._make_record(
            test="anova",
            is_omnibus=True,
            omnibus=r,
            descriptives=st._describe_all(_GROUPS, MULTI),
            comparisons=[{"g1": "A", "g2": "C", "pvalue": 0.001, "effectName": "d", "effect": -2.5}],
            comparison_test="tukey_hsd",
            correction=None,
            pvalues_provided=False,
        )
        assert rec["kind"] == "omnibus" and rec["test"] == "anova"
        assert rec["omnibus"]["statistic"]["symbol"] == "F"
        assert rec["omnibus"]["effect"]["name"] == "eta_squared"
        assert rec["comparisons"]["test"] == "tukey_hsd"
        assert rec["comparisons"]["pairs"][0]["group1"] == "A"
        assert rec["comparisons"]["pairs"][0]["effect"]["name"] == "cohens_d"

    def test_make_record_is_json_serializable(self):
        import json

        rec = st._make_record(
            test="mannwhitneyu",
            is_omnibus=False,
            omnibus=None,
            descriptives=st._describe_all([_A, np.array([1.0])], ["A", "B"]),  # B has n=1 → sd None
            comparisons=[{"g1": "A", "g2": "B", "pvalue": 0.02, "effectName": "r", "effect": 0.3}],
            comparison_test="mannwhitneyu",
            correction=None,
            pvalues_provided=False,
        )
        json.dumps(rec)  # must not raise (sd is None, not NaN)
        assert rec["groups"][1]["sd"] is None

    def test_render_report_from_record(self):
        r = st._run_omnibus("anova", _GROUPS, MULTI)
        rec = st._make_record(
            test="anova",
            is_omnibus=True,
            omnibus=r,
            descriptives=st._describe_all(_GROUPS, MULTI),
            comparisons=[{"g1": "A", "g2": "C", "pvalue": 0.001, "effectName": "d", "effect": -2.5}],
            comparison_test="tukey_hsd",
            correction=None,
            pvalues_provided=False,
        )
        text = st._render_report(rec)
        lines = text.splitlines()
        title = "Statistics | Omnibus | ANOVA"
        assert lines[0] == title
        assert lines[1] == "─" * len(title)  # box-drawing underline matches title width
        assert "Group descriptives:" in text
        assert "Post-hoc (tukey_hsd):" in text and "A vs C" in text


class TestReportPValues:
    def test_fmt_p_readable_decimal(self):
        assert st._fmt_p(0.032) == "= 0.032"

    def test_fmt_p_scientific_for_tiny(self):
        assert st._fmt_p(1.2179613642216176e-11) == "= 1.22e-11"  # 3 sig figs, e-notation

    def test_fmt_p_never_floors(self):
        # a value that the old code would have shown as "< 0.001"
        assert st._fmt_p(2.2e-16) == "= 2.2e-16"

    def test_clamp_leaves_normal_untouched(self):
        assert st._clamp_p(0.05) == 0.05

    def test_clamp_zero_to_smallest_float(self):
        import sys

        assert st._clamp_p(0.0) == sys.float_info.min

    def test_fmt_p_clamp_uses_less_than(self):
        import sys

        assert st._fmt_p(sys.float_info.min) == "< 2.23e-308"

    def test_make_record_clamps_zero_pvalues(self):
        import sys

        rec = st._make_record(
            test="mannwhitneyu",
            is_omnibus=False,
            omnibus=None,
            descriptives=st._describe_all(_GROUPS, MULTI),
            comparisons=[{"g1": "A", "g2": "B", "pvalue": 0.0, "effectName": "r", "effect": 0.5}],
            comparison_test="mannwhitneyu",
            correction=None,
            pvalues_provided=False,
        )
        assert rec["comparisons"]["pairs"][0]["pvalue"] == sys.float_info.min  # never 0.0

    def test_full_pipeline_zero_pvalue(self):
        import sys

        import polars as pl

        from dysonsphere.stats import comparisons
        from dysonsphere.theme import theme

        theme(chartWidth=200, chartHeight=200)
        df = pl.DataFrame({"g": ["A"] * 5 + ["B"] * 5, "v": [float(i) for i in range(10)]})
        st._REPORTS.clear()
        comparisons(df, "g", "v", [("A", "B")], categories=["A", "B"], pvalues=[0.0])
        rec = next(iter(st._REPORTS.values()))
        assert rec["comparisons"]["pairs"][0]["pvalue"] == sys.float_info.min
        assert "< 2.23e-308" in st._render_report(rec)


# comparisons omnibus integration
@pytest.fixture
def multi_df():
    rng = np.random.default_rng(3)
    return pl.DataFrame(
        {
            "group": [c for c in MULTI for _ in range(20)],
            "value": np.concatenate([rng.normal(m, 1, 20) for m in (1.0, 2.0, 3.5)]),
        }
    )


class TestAddComparisonsOmnibus:
    def _texts(self, layer):
        spec = layer.to_dict()
        return [v for sub in spec.get("layer", []) for v in str(sub).split("'") if v]

    def test_omnibus_corner_label_present(self, multi_df):
        layer = comparisons(multi_df, "group", "value", test="anova", categories=MULTI)
        assert "ANOVA" in str(layer.to_dict())

    def test_verbose_label(self, multi_df):
        layer = comparisons(multi_df, "group", "value", test="anova", categories=MULTI, omnibusVerbose=True)
        s = str(layer.to_dict())
        assert "F(2, 57)" in s and "η²" in s

    def test_omnibus_position_none_no_label(self, multi_df):
        layer = comparisons(multi_df, "group", "value", test="kruskal", categories=MULTI, testLabelPosition=None)
        assert "Kruskal" not in str(layer.to_dict())

    def test_omnibus_with_posthoc_brackets(self, multi_df):
        layer = comparisons(multi_df, "group", "value", pairs=[("A", "C")], test="anova", categories=MULTI)
        # corner label + one bracket layer
        assert "ANOVA" in str(layer.to_dict())

    def test_report_includes_all_comparisons_not_just_bracketed(self, multi_df):
        # only A-C is bracketed, but the omnibus report should list all 3 pairs
        st._REPORTS.clear()
        comparisons(multi_df, "group", "value", pairs=[("A", "C")], test="anova", categories=MULTI)
        pairs = next(iter(st._REPORTS.values()))["comparisons"]["pairs"]
        listed = {(p["group1"], p["group2"]) for p in pairs}
        assert listed == {("A", "B"), ("A", "C"), ("B", "C")}

    def test_report_all_comparisons_omnibus_only(self, multi_df):
        # no brackets at all, but the report still lists every pairwise post-hoc
        st._REPORTS.clear()
        comparisons(multi_df, "group", "value", test="kruskal", categories=MULTI)
        rec = next(iter(st._REPORTS.values()))
        assert rec["comparisons"]["test"] == "dunn"
        assert len(rec["comparisons"]["pairs"]) == 3

    def test_report_queued_as_record(self, multi_df):
        st._REPORTS.clear()
        comparisons(multi_df, "group", "value", test="anova", categories=MULTI)
        assert len(st._REPORTS) == 1
        rec = next(iter(st._REPORTS.values()))
        assert rec["kind"] == "omnibus" and rec["omnibus"]["name"] == "ANOVA"
        assert "ANOVA" in st._render_report(rec)

    def test_report_prints(self, multi_df, capsys):
        comparisons(multi_df, "group", "value", test="anova", categories=MULTI, report=True)
        assert "Group descriptives:" in capsys.readouterr().out

    @pytest.mark.parametrize("as_path", [False, True])
    def test_save_writes_file(self, multi_df, tmp_path, as_path):
        outdir = tmp_path / "reports"
        target = outdir if as_path else str(outdir)
        comparisons(multi_df, "group", "value", test="anova", categories=MULTI, saveReport=target)
        files = list(outdir.glob("dysonsphere_report_*.txt"))
        assert len(files) == 1 and "ANOVA" in files[0].read_text()

    def test_save_true_uses_cwd_and_false_writes_nothing(self, multi_df, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        comparisons(multi_df, "group", "value", test="anova", categories=MULTI, saveReport=True)
        assert len(list(tmp_path.glob("dysonsphere_report_*.txt"))) == 1

        clean = tmp_path / "no_report"
        clean.mkdir()
        monkeypatch.chdir(clean)
        comparisons(multi_df, "group", "value", test="anova", categories=MULTI, saveReport=False)
        assert list(clean.iterdir()) == []

    def test_pairwise_requires_pairs(self, multi_df):
        with pytest.raises(ValueError, match="pairs is required"):
            comparisons(multi_df, "group", "value", test="mannwhitneyu", categories=MULTI)

    def test_empty_pairs_rejected(self, multi_df):
        with pytest.raises(ValueError, match="must not be empty"):
            comparisons(multi_df, "group", "value", pairs=[], test="anova", categories=MULTI)

    def test_default_posthoc_per_omnibus(self, multi_df):
        # kruskal default post-hoc is dunn; just ensure it runs and brackets build
        layer = comparisons(multi_df, "group", "value", pairs=[("A", "C")], test="kruskal", categories=MULTI)
        assert isinstance(layer, alt.LayerChart)


# Correlation (dysonsphere._statistics + correlation)
_CX = np.array([1.0, 2, 3, 4, 5, 6, 7, 8])
_CY = np.array([2.1, 3.9, 6.2, 7.8, 10.1, 12.2, 13.8, 16.3])  # strong positive linear


class TestCorrelationStats:
    def test_pearson_matches_scipy(self):
        from scipy import stats as sp

        r = st._run_correlation("pearson", _CX, _CY)
        assert r["coefficient"] == pytest.approx(float(sp.pearsonr(_CX, _CY).statistic), abs=1e-9)
        assert r["rSquared"] == pytest.approx(r["coefficient"] ** 2)
        assert r["slope"] is not None and r["intercept"] is not None

    def test_spearman_no_line(self):
        r = st._run_correlation("spearman", _CX, _CY)
        assert r["symbol"] == "ρ" and r["rSquared"] is None and r["slope"] is None

    def test_kendall(self):
        r = st._run_correlation("kendall", _CX, _CY)
        assert r["symbol"] == "τ" and r["rSquared"] is None

    def test_unknown_method(self):
        with pytest.raises(ValueError, match="method must be"):
            st._run_correlation("nope", _CX, _CY)

    def test_record_shape_and_clamp(self):
        rec = st._make_correlation_record(st._run_correlation("pearson", _CX, _CY), "h", "w")
        assert rec["kind"] == "correlation" and rec["method"] == "pearson"
        assert rec["coefficient"]["symbol"] == "r" and rec["coefficient"]["name"] == "pearson_r"
        assert rec["fit"]["slope"] is not None
        import json

        json.dumps(rec)  # JSON-safe

    def test_render_pearson_report(self):
        rec = st._make_correlation_record(st._run_correlation("pearson", _CX, _CY), "h", "w")
        text = st._render_report(rec)
        assert text.startswith("Statistics | Correlation | Pearson")
        assert "r² = " in text and "Fit: y = " in text and "(h vs w)" in text

    def test_render_negative_intercept_sign(self):
        # y = 2x - 5  -> intercept negative, must render "- 5.000" not "+ -5.000"
        x = np.array([1.0, 2, 3, 4])
        y = 2 * x - 5
        text = st._render_report(st._make_correlation_record(st._run_correlation("pearson", x, y), "x", "y"))
        assert "x - " in text and "+ -" not in text


class TestOlsBand:
    def test_confidence_half_width_at_xbar_matches_closed_form(self):
        # At x = mean(x) the CI half-width collapses to t * s * sqrt(1/n).
        from scipy import stats as sp

        x, y = _CX, _CY
        n = x.size
        s = np.sqrt(np.sum((y - (sp.linregress(x, y).slope * x + sp.linregress(x, y).intercept)) ** 2) / (n - 2))
        expected = sp.t.ppf(0.975, n - 2) * s * np.sqrt(1 / n)
        lo, hi = st._ols_band(x, y, np.array([x.mean()]), level=0.95, kind="confidence")
        assert (hi[0] - lo[0]) / 2 == pytest.approx(expected)

    def test_prediction_wider_than_confidence_everywhere(self):
        loc, hic = st._ols_band(_CX, _CY, _CX, kind="confidence")
        lop, hip = st._ols_band(_CX, _CY, _CX, kind="prediction")
        assert np.all((hip - lop) > (hic - loc))

    def test_band_is_narrowest_at_xbar(self):
        xs = np.linspace(_CX.min(), _CX.max(), 51)
        lo, hi = st._ols_band(_CX, _CY, xs, kind="confidence")
        width = hi - lo
        # xbar sits at the midpoint of this symmetric, evenly-spaced grid (index 25).
        assert int(np.argmin(width)) == 25

    def test_higher_level_is_wider(self):
        lo90, hi90 = st._ols_band(_CX, _CY, _CX, level=0.90)
        lo99, hi99 = st._ols_band(_CX, _CY, _CX, level=0.99)
        assert np.all((hi99 - lo99) > (hi90 - lo90))

    def test_invalid_kind_raises(self):
        with pytest.raises(ValueError, match="kind must be"):
            st._ols_band(_CX, _CY, _CX, kind="bogus")

    def test_requires_min_n(self):
        with pytest.raises(ValueError, match="n >= 3"):
            st._ols_band(np.array([1.0, 2.0]), np.array([1.0, 2.0]), np.array([1.5]))


class TestCorrelationLabel:
    def _pearson(self):
        return st._run_correlation("pearson", _CX, _CY)

    def _label(self, res, **kw):
        kw.setdefault("coefficient", "r")
        kw.setdefault("includePvalue", False)
        kw.setdefault("includeEquation", False)
        return _correlation_label(res, sigFigs=3, notation=None, **kw)

    def test_default_is_coefficient_only(self):
        assert self._label(self._pearson()) == f"r = {self._pearson()['coefficient']:.3g}"

    def test_coefficient_r2_only(self):
        assert self._label(self._pearson(), coefficient="r2").startswith("r² = ")
        assert "r = " not in self._label(self._pearson(), coefficient="r2")

    def test_coefficient_both(self):
        lbl = self._label(self._pearson(), coefficient="both")
        assert lbl.startswith("r = ") and "r² = " in lbl

    def test_include_pvalue(self):
        assert "P " in self._label(self._pearson(), includePvalue=True)

    def test_include_equation(self):
        assert ", y = " in self._label(self._pearson(), coefficient="both", includeEquation=True)

    def test_rank_ignores_coefficient_and_equation(self):
        rho = st._run_correlation("spearman", _CX, _CY)
        lbl = self._label(rho, coefficient="both", includeEquation=True, includePvalue=True)
        assert lbl.startswith("ρ = ") and "r² = " not in lbl and ", y = " not in lbl

    def test_verbose_shortcut(self):
        # verbose=True == coefficient="both", includePvalue=True, includeEquation=True
        chart = correlation(pl.DataFrame({"x": _CX, "y": _CY}), "x", "y", verbose=True)
        readout = _text_labels(chart)[0]
        assert "r = " in readout and "r² = " in readout and "P " in readout and ", y = " in readout

    def test_invalid_coefficient_raises(self):
        with pytest.raises(ValueError, match="coefficient must be"):
            correlation(pl.DataFrame({"x": _CX, "y": _CY}), "x", "y", coefficient="nope")


class TestAddCorrelation:
    @pytest.fixture
    def scatter_df(self):
        rng = np.random.default_rng(0)
        x = rng.uniform(0, 10, 60)
        return pl.DataFrame({"x": x, "y": 0.9 * x + rng.normal(0, 1, 60)})

    def test_pearson_has_line_and_label(self, scatter_df):
        layer = correlation(scatter_df, "x", "y")
        assert isinstance(layer, alt.LayerChart)
        assert len(layer.to_dict()["layer"]) == 2  # line + readout

    def test_fit_line_fields_match_the_columns(self):
        # The fit line's sidecar must carry the REAL column names: Vega-Lite merges a shared
        # axis title by joining the layers' DISTINCT derived titles, so private names ("_x")
        # rendered as "height, _x" on the base chart's axes. Matching names dedupe to one.
        rng = np.random.default_rng(1)
        x = rng.uniform(0, 10, 40)
        df = pl.DataFrame({"height": x, "weight": 2.0 * x + rng.normal(0, 1, 40)})
        spec = correlation(df, "height", "weight").to_dict()
        line = spec["layer"][0]
        assert line["mark"]["type"] == "line"
        assert line["encoding"]["x"]["field"] == "height"
        assert line["encoding"]["y"]["field"] == "weight"
        # No title/axis overrides: an explicit title on the BASE chart must keep winning.
        assert "title" not in line["encoding"]["x"]
        assert "title" not in line["encoding"]["y"]

    def test_fit_line_survives_special_column_names(self):
        # field=/type= (not shorthand) so a ':' in a column name is not parsed as a type tag.
        rng = np.random.default_rng(2)
        x = rng.uniform(0, 10, 40)
        df = pl.DataFrame({"hp:max": x, "mpg.city": 1.5 * x + rng.normal(0, 1, 40)})
        spec = correlation(df, "hp:max", "mpg.city").to_dict()
        line = spec["layer"][0]
        assert line["encoding"]["x"]["field"] == "hp:max"
        assert line["encoding"]["y"]["field"] == "mpg.city"

    def test_spearman_no_line(self, scatter_df):
        layer = correlation(scatter_df, "x", "y", method="spearman")
        assert len(layer.to_dict()["layer"]) == 1  # readout only, no line

    def test_line_false_suppresses_line(self, scatter_df):
        layer = correlation(scatter_df, "x", "y", line=False)
        assert len(layer.to_dict()["layer"]) == 1

    def test_position_none_no_label(self, scatter_df):
        layer = correlation(scatter_df, "x", "y", position=None)
        assert len(layer.to_dict()["layer"]) == 1  # line only

    def test_linestyle_overrides_curated(self, scatter_df):
        spec = correlation(scatter_df, "x", "y", color="red", lineStyle={"color": "blue"}).to_dict()
        marks = [lyr["mark"] for lyr in spec["layer"] if isinstance(lyr.get("mark"), dict)]
        line_mark = next(m for m in marks if m.get("type") == "line")
        assert line_mark["color"] == "blue"  # lineStyle wins

    def _area_layer(self, spec):
        return next(
            (lyr for lyr in spec["layer"] if isinstance(lyr.get("mark"), dict) and lyr["mark"].get("type") == "area"),
            None,
        )

    def test_ci_adds_band_under_line(self, scatter_df):
        spec = correlation(scatter_df, "x", "y", ci=True).to_dict()
        assert len(spec["layer"]) == 3  # band + line + readout
        # The band is the FIRST layer, so it renders beneath the fit line.
        assert spec["layer"][0]["mark"]["type"] == "area"
        band = self._area_layer(spec)
        # Fill pinned (black default), stroke off so config.area's grey/stroke can't leak.
        assert band["mark"]["fill"] == "black"
        assert band["mark"]["fillOpacity"] == pytest.approx(0.15)
        assert band["mark"]["stroke"] is None
        # Lower bound rides on the y field (title dedupe); upper bound in y2.
        assert band["encoding"]["y"]["field"] == "y"
        assert band["encoding"]["y2"]["field"] == "__ci_hi"

    def test_no_band_by_default(self, scatter_df):
        assert self._area_layer(correlation(scatter_df, "x", "y").to_dict()) is None

    def test_ci_opacity_and_color_overrides(self, scatter_df):
        band = self._area_layer(correlation(scatter_df, "x", "y", ci=0.99, ciColor="#c0392b", ciOpacity=0.3).to_dict())
        assert band["mark"]["fill"] == "#c0392b" and band["mark"]["fillOpacity"] == pytest.approx(0.3)

    def test_prediction_band_wider_than_confidence(self, scatter_df):
        def _spread(spec):
            band = self._area_layer(spec)
            # The sidecar frame is hoisted to top-level `datasets` and referenced by name.
            vals = band["data"].get("values") or spec["datasets"][band["data"]["name"]]
            return max(v["__ci_hi"] - v["y"] for v in vals)

        ci_spec = correlation(scatter_df, "x", "y", ci=True, interval="confidence").to_dict()
        pi_spec = correlation(scatter_df, "x", "y", ci=True, interval="prediction").to_dict()
        assert _spread(pi_spec) > _spread(ci_spec)

    def test_no_band_for_rank_method(self, scatter_df):
        # Rank methods have no OLS line, so ci is a silent no-op (like line=).
        assert self._area_layer(correlation(scatter_df, "x", "y", method="spearman", ci=True).to_dict()) is None

    def test_invalid_ci_level_raises(self, scatter_df):
        with pytest.raises(ValueError, match="ci must be"):
            correlation(scatter_df, "x", "y", ci=1.5)

    def test_invalid_interval_raises(self, scatter_df):
        with pytest.raises(ValueError, match="interval must be"):
            correlation(scatter_df, "x", "y", ci=True, interval="bogus")

    def test_record_queued(self, scatter_df):
        st._REPORTS.clear()
        correlation(scatter_df, "x", "y")
        assert len(st._REPORTS) == 1 and next(iter(st._REPORTS.values()))["kind"] == "correlation"

    def test_report_prints(self, scatter_df, capsys):
        correlation(scatter_df, "x", "y", report=True)
        assert "Correlation | Pearson" in capsys.readouterr().out

    @pytest.mark.parametrize("as_path", [False, True])
    def test_save_writes_file(self, scatter_df, tmp_path, as_path):
        outdir = tmp_path / "reports"
        target = outdir if as_path else str(outdir)
        correlation(scatter_df, "x", "y", saveReport=target)
        files = list(outdir.glob("dysonsphere_report_*.txt"))
        assert len(files) == 1 and "Correlation" in files[0].read_text()


class TestGroupedComparisons:
    """comparisons(xOffset=...) - compare xOffset subgroups within each x-category."""

    @pytest.fixture
    def qpcr_df(self):
        # Deterministic so the control is a TRUE null (identical conditions -> p == 1, never a
        # random dip below 0.05): G1 strongly induced by the treatment, G2 (housekeeping) unchanged.
        base = [1.0, 1.1, 0.9, 1.05, 0.95, 1.0]
        induced = [10.0, 10.5, 9.5, 10.2, 9.8, 10.1]
        rows = []
        for gene, veh, trt in [("G1", base, induced), ("G2", base, base)]:
            for cond, vals in [("Veh", veh), ("Trt", trt)]:
                rows += [{"gene": gene, "cond": cond, "expr": v} for v in vals]
        return pl.DataFrame(rows)

    def test_returns_layerchart_two_levels_default_pairs(self, qpcr_df):
        # exactly two levels -> pairs defaults to comparing them
        r = comparisons(qpcr_df, "gene", "expr", xOffset="cond", categories=["G1", "G2"], xOffsetSort=["Veh", "Trt"])
        assert isinstance(r, alt.LayerChart)

    def test_real_per_category_pvalues(self, qpcr_df):
        # the whole point: stats are computed per category from the data, not hardcoded.
        st._REPORTS.clear()
        comparisons(
            qpcr_df,
            "gene",
            "expr",
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=["Veh", "Trt"],
            test="ttest_ind",
        )
        rec = next(iter(st._REPORTS.values()))
        pairs = rec["comparisons"]["pairs"]
        g1 = next(p for p in pairs if p["group1"].startswith("G1"))
        g2 = next(p for p in pairs if p["group1"].startswith("G2"))
        assert g1["pvalue"] < 0.001  # induced gene: significant
        assert g2["pvalue"] > 0.05  # unchanged control: not significant
        # comparison labels encode the category so multi-gene records stay legible
        assert g1["group1"] == "G1 (Veh)" and g1["group2"] == "G1 (Trt)"

    def test_bracket_sort_matches_bars(self, qpcr_df):
        # every bracket layer carries the level sort so the shared xOffset scale keeps bar order.
        r = comparisons(qpcr_df, "gene", "expr", xOffset="cond", categories=["G2", "G1"], xOffsetSort=["Trt", "Veh"])
        sorts: list[Any] = []

        def walk(node):
            if isinstance(node, dict):
                enc = node.get("encoding", {})
                if "xOffset" in enc and isinstance(enc["xOffset"], dict) and "sort" in enc["xOffset"]:
                    sorts.append(enc["xOffset"]["sort"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(r.to_dict())
        assert sorts and all(s == ["Trt", "Veh"] for s in sorts)

    def test_per_category_placement(self, qpcr_df):
        # each bracket sits above its OWN category's bars -> the induced gene's bracket is higher.
        r = comparisons(qpcr_df, "gene", "expr", xOffset="cond", categories=["G1", "G2"], xOffsetSort=["Veh", "Trt"])
        ys = {}
        for bracket in r.to_dict()["layer"]:
            top_row = bracket["layer"][0]["data"]["values"][0]  # top line's first point
            ys[top_row["gene"]] = top_row["__y"]
        assert ys["G1"] > ys["G2"]

    def test_three_levels_requires_pairs(self):
        df = pl.DataFrame({"g": ["A"] * 9, "c": ["x", "y", "z"] * 3, "v": [1.0, 2.0, 3.0] * 3})
        with pytest.raises(ValueError, match="pairs is required"):
            comparisons(df, "g", "v", xOffset="c", categories=["A"], xOffsetSort=["x", "y", "z"])

    def test_nonadjacent_pair(self):
        rng = np.random.default_rng(1)
        df = pl.DataFrame(
            {"g": ["A"] * 30, "c": (["x"] * 10 + ["y"] * 10 + ["z"] * 10), "v": list(rng.normal(0, 1, 30))}
        )
        r = comparisons(df, "g", "v", xOffset="c", pairs=[("x", "z")], categories=["A"], xOffsetSort=["x", "y", "z"])
        assert isinstance(r, alt.LayerChart)

    def test_unknown_level_raises(self, qpcr_df):
        with pytest.raises(ValueError, match="not in xOffset"):
            comparisons(
                qpcr_df,
                "gene",
                "expr",
                xOffset="cond",
                pairs=[("Veh", "NOPE")],
                categories=["G1", "G2"],
                xOffsetSort=["Veh", "Trt"],
            )

    def test_omnibus_test_rejected(self, qpcr_df):
        with pytest.raises(ValueError, match="grouped comparisons"):
            comparisons(
                qpcr_df,
                "gene",
                "expr",
                xOffset="cond",
                test="anova",
                categories=["G1", "G2"],
                xOffsetSort=["Veh", "Trt"],
            )

    def test_incomplete_categories_raises(self, qpcr_df):
        # an explicit `categories` that omits a gene in the data would misalign the shared x scale
        with pytest.raises(ValueError, match="categories is missing"):
            comparisons(qpcr_df, "gene", "expr", xOffset="cond", categories=["G1"], xOffsetSort=["Veh", "Trt"])

    def test_incomplete_xoffsetsort_raises(self, qpcr_df):
        # an explicit `xOffsetSort` that omits a level in the data would misalign the xOffset scale
        with pytest.raises(ValueError, match="xOffsetSort is missing"):
            comparisons(qpcr_df, "gene", "expr", xOffset="cond", categories=["G1", "G2"], xOffsetSort=["Veh"])

    @pytest.mark.parametrize("sort", [["Veh", "Other"], ["Veh", "Veh"]])
    def test_xoffsetsort_rejects_extra_or_duplicate_values(self, qpcr_df, sort):
        with pytest.raises(ValueError, match="xOffsetSort"):
            comparisons(qpcr_df, "gene", "expr", xOffset="cond", categories=["G1", "G2"], xOffsetSort=sort)


class TestGroupedCorrelation:
    """correlation(groupBy=...) - a fit + coefficient per series."""

    @pytest.fixture
    def grouped_df(self):
        rng = np.random.default_rng(3)
        rows = []
        for g, (slope, inter) in [("A", (1.0, 2.0)), ("B", (0.4, 6.0)), ("C", (-0.5, 10.0))]:
            x = rng.uniform(0, 10, 40)
            y = slope * x + inter + rng.normal(0, 1.0, 40)
            rows += [{"x": float(a), "y": float(b), "line": g} for a, b in zip(x, y)]
        return pl.DataFrame(rows)

    @staticmethod
    def _layers(spec):
        return [leaf for group in spec["layer"] for leaf in group.get("layer", [group])]

    def test_returns_layerchart(self, grouped_df):
        assert isinstance(correlation(grouped_df, "x", "y", groupBy="line"), alt.LayerChart)

    def test_one_record_per_group_with_labels(self, grouped_df):
        st._REPORTS.clear()
        correlation(grouped_df, "x", "y", groupBy="line")
        recs = list(st._REPORTS.values())
        assert len(recs) == 3
        by_group = {r["group"]: r for r in recs}
        assert set(by_group) == {"A", "B", "C"}
        # real per-group coefficients: A strongly positive, C negative
        assert by_group["A"]["coefficient"]["value"] > 0.7
        assert by_group["C"]["coefficient"]["value"] < -0.3
        assert all(r["kind"] == "correlation" for r in recs)

    def test_fit_lines_colored_by_group(self, grouped_df):
        # every fit line encodes color by the group column (so it merges with the scatter's scale)
        spec = correlation(grouped_df, "x", "y", groupBy="line").to_dict()
        line_colors = [
            lyr["encoding"]["color"]["field"]
            for lyr in self._layers(spec)
            if lyr["mark"].get("type") == "line" and "color" in lyr.get("encoding", {})
        ]
        assert line_colors and all(f == "line" for f in line_colors)

    def test_one_fit_line_and_readout_per_group(self, grouped_df):
        spec = correlation(grouped_df, "x", "y", groupBy="line").to_dict()
        n_lines = sum(1 for lyr in self._layers(spec) if lyr["mark"].get("type") == "line")
        n_text = sum(1 for lyr in self._layers(spec) if lyr["mark"].get("type") == "text")
        assert n_lines == 3 and n_text == 3

    def test_readout_text_neutral_with_colored_swatch(self, grouped_df):
        # the colour link is a per-group SWATCH (a filled point, legend-symbol sized); the readout
        # text stays neutral (no color encoding) so it's legible even for pale palette colours.
        spec = correlation(grouped_df, "x", "y", groupBy="line").to_dict()
        texts = [lyr for lyr in self._layers(spec) if lyr["mark"].get("type") == "text"]
        swatches = [lyr for lyr in self._layers(spec) if lyr["mark"].get("type") == "point"]
        assert len(texts) == 3 and len(swatches) == 3
        assert all("color" not in lyr.get("encoding", {}) for lyr in texts)  # neutral ink
        assert all(lyr["encoding"]["color"]["field"] == "line" for lyr in swatches)  # coloured swatch
        # the swatch scales with the font (symbolSize = fontSize*6 at the default fontSize 6)
        assert all(lyr["mark"]["size"] == pytest.approx(36.0) for lyr in swatches)

    def test_rank_method_no_lines(self, grouped_df):
        # spearman reports the coefficient (readouts) but draws no fit line
        spec = correlation(grouped_df, "x", "y", groupBy="line", method="spearman").to_dict()
        assert not [lyr for lyr in self._layers(spec) if lyr["mark"].get("type") == "line"]
        assert sum(1 for lyr in self._layers(spec) if lyr["mark"].get("type") == "text") == 3

    def test_position_none_no_readouts(self, grouped_df):
        spec = correlation(grouped_df, "x", "y", groupBy="line", position=None).to_dict()
        assert not [lyr for lyr in self._layers(spec) if lyr["mark"].get("type") == "text"]

    def test_ci_band_per_group(self, grouped_df):
        spec = correlation(grouped_df, "x", "y", groupBy="line", ci=True).to_dict()
        assert sum(1 for lyr in self._layers(spec) if lyr["mark"].get("type") == "area") == 3

    @pytest.mark.parametrize("as_path", [False, True])
    def test_grouped_save_report_uses_shared_dispatch(self, grouped_df, tmp_path, as_path):
        outdir = tmp_path / "reports"
        target = outdir if as_path else str(outdir)
        correlation(grouped_df, "x", "y", groupBy="line", saveReport=target)
        assert len(list(outdir.glob("dysonsphere_report_*.txt"))) == 3


class TestStackLevels:
    """Direct tests for the shared bracket-stacking helper (greedy interval scheduling)."""

    def test_empty(self):
        assert _stack_levels([]) == []

    def test_disjoint_spans_share_level_zero(self):
        # (0,1) and (2,3) don't overlap → both on level 0.
        assert _stack_levels([(0, 1), (2, 3)]) == [0, 0]

    def test_overlap_bumps_to_next_level(self):
        # (0,2) and (1,3) overlap → the second must climb a level.
        assert _stack_levels([(0, 2), (1, 3)]) == [0, 1]

    def test_ties_on_left_endpoint_break_by_right(self):
        # Same left endpoint → the narrower span is placed first and takes level 0,
        # regardless of input order.
        assert _stack_levels([(0, 3), (0, 1)]) == [1, 0]

    def test_orientation_agnostic(self):
        # (lo, hi) may arrive reversed; the helper normalises with min/max.
        assert _stack_levels([(3, 0), (0, 1)]) == [1, 0]

    def test_nested_span_overlaps(self):
        # A span fully containing another still counts as overlapping → separate levels.
        # The outer span leads on left endpoint, so it takes level 0.
        assert _stack_levels([(0, 4), (1, 2)]) == [0, 1]

    def test_lexicographic_groups_comparisons_by_left_group(self):
        # Every comparison against group 1 forms one nested staircase before group 2 starts,
        # rather than interleaving anchors. Disjoint pairs still share a level (1v2 + 3v4).
        spans = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]  # 1v2 1v3 1v4 2v3 2v4 3v4
        assert _stack_levels(spans) == [0, 1, 2, 3, 4, 0]

    def test_level_count_is_minimal(self):
        # The overlap graph of intervals is perfect, so greedy coloring in left-endpoint order
        # uses exactly the maximum clique - the fewest levels any layout could use.
        def max_clique(spans):
            points = {c for s in spans for c in s}
            return max(sum(1 for s in spans if min(s) <= p <= max(s)) for p in points)

        cases = [
            [(0, 1), (0, 2), (2, 4), (3, 4)],  # span-length order needs 3 here; 2 suffice
            [(0, 1), (1, 2), (2, 3), (0, 2), (1, 3)],
            [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
        ]
        for spans in cases:
            assert max(_stack_levels(spans)) + 1 == max_clique(spans)


class TestResolveYSpacing:
    """Direct tests for the shared y-spacing resolver."""

    def test_none_args_resolved_from_extent(self):
        # bracket gap = 10 px * y_range / chartHeight; y_step = 1.75 * y_pad.
        y_pad, tick, y_step = _resolve_y_spacing(True, 20.0, 100.0, None, None, None)
        assert y_pad == pytest.approx(10.0 * 20.0 / 100.0)
        assert y_step == pytest.approx(y_pad * 1.75)
        assert tick > 0

    def test_line_uses_smaller_gap(self):
        bracket_pad = _resolve_y_spacing(True, 20.0, 100.0, None, None, None)[0]
        line_pad = _resolve_y_spacing(False, 20.0, 100.0, None, None, None)[0]
        assert line_pad == pytest.approx(bracket_pad * 0.8)

    def test_explicit_values_pass_through(self):
        assert _resolve_y_spacing(True, 20.0, 100.0, 5.0, 0.3, 9.0) == (5.0, 0.3, 9.0)

    def test_zero_chart_height_guarded(self):
        # No division by zero; auto pad/tick collapse to 0, y_step follows.
        assert _resolve_y_spacing(True, 20.0, 0.0, None, None, None) == (0.0, 0.0, 0.0)


def _ref_labels(layer):
    """Pull the rendered p-value strings from reference-mode label layers (each rides a tiny
    inline dataset with a ``label`` field, unlike text's ``value``-encoded labels)."""
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for row in node.get("data", {}).get("values", []) if isinstance(node.get("data"), dict) else []:
                if isinstance(row, dict):
                    if "label" in row:
                        found.append(row["label"])
                    elif "__label" in row:
                        found.append(row["__label"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(layer.to_dict())
    return found


class TestReferenceMode:
    """comparisons(reference=...) - compare every group against one, bare label per mark."""

    @pytest.fixture
    def dose_df(self):
        rng = np.random.default_rng(7)
        cats = ["Ctrl", "Low", "Mid", "High"]
        return pl.DataFrame(
            {
                "group": [c for c in cats for _ in range(10)],
                "value": np.concatenate([rng.normal(m, 0.6, 10) for m in (5.0, 5.4, 6.2, 7.2)]),
            }
        )

    def test_one_label_per_non_reference_group(self, dose_df):
        cats = ["Ctrl", "Low", "Mid", "High"]
        layer = comparisons(dose_df, "group", "value", reference="Ctrl", categories=cats, test="ttest_ind")
        # one label per non-reference category, none for the reference
        assert len(_ref_labels(layer)) == len(cats) - 1

    def test_record_has_only_reference_pairs(self, dose_df):
        from dysonsphere import _statistics as _st

        _st._REPORTS.clear()
        comparisons(dose_df, "group", "value", reference="Ctrl", categories=["Ctrl", "Low", "Mid", "High"])
        rec = next(iter(_st._REPORTS.values()))
        pairs = [(p["group1"], p["group2"]) for p in rec["comparisons"]["pairs"]]
        assert pairs == [("Ctrl", "Low"), ("Ctrl", "Mid"), ("Ctrl", "High")]

    def test_correction_applies_over_family(self, dose_df):
        from dysonsphere import _statistics as _st

        _st._REPORTS.clear()
        comparisons(
            dose_df, "group", "value", reference="Ctrl", categories=["Ctrl", "Low", "Mid", "High"], correction="holm"
        )
        rec = next(iter(_st._REPORTS.values()))
        assert rec["comparisons"]["correction"] == "holm"

    def test_rejects_omnibus(self, dose_df):
        with pytest.raises(ValueError, match="omnibus"):
            comparisons(dose_df, "group", "value", reference="Ctrl", test="anova")

    def test_rejects_pairs_with_reference(self, dose_df):
        with pytest.raises(ValueError, match="derives its own"):
            comparisons(dose_df, "group", "value", reference="Ctrl", pairs=[("Ctrl", "Low")])

    def test_rejects_unknown_reference(self, dose_df):
        with pytest.raises(ValueError, match="not a category"):
            comparisons(dose_df, "group", "value", reference="Nope", categories=["Ctrl", "Low", "Mid", "High"])

    def _label_ys(self, layer):
        """Single-factor reference labels carry a ``y`` field (unlike grouped's ``__y``)."""
        ys: list[float] = []

        def walk(node):
            if isinstance(node, dict):
                for row in node.get("data", {}).get("values", []) if isinstance(node.get("data"), dict) else []:
                    if isinstance(row, dict) and "y" in row and "label" in row:
                        ys.append(round(row["y"], 3))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(layer.to_dict())
        return ys

    def test_pvalues_dict_used_and_uncorrected(self, dose_df):
        from dysonsphere import _statistics as _st

        cats = ["Ctrl", "Low", "Mid", "High"]
        _st._REPORTS.clear()
        comparisons(
            dose_df,
            "group",
            "value",
            reference="Ctrl",
            categories=cats,
            correction="holm",
            pvalues={"Low": 0.5, "Mid": 0.01, "High": 1e-6},
        )
        rec = next(iter(_st._REPORTS.values()))
        assert [round(p["pvalue"], 4) for p in rec["comparisons"]["pairs"]] == [0.5, 0.01, 0.0]
        assert rec["comparisons"]["correction"] is None  # user p-values are not corrected

    def test_pvalues_missing_and_extra_and_list_raise(self, dose_df):
        cats = ["Ctrl", "Low", "Mid", "High"]
        with pytest.raises(ValueError, match="missing an entry"):
            comparisons(dose_df, "group", "value", reference="Ctrl", categories=cats, pvalues={"Low": 0.1})
        with pytest.raises(ValueError, match="not matching any group"):
            comparisons(
                dose_df,
                "group",
                "value",
                reference="Ctrl",
                categories=cats,
                pvalues={"Low": 0.1, "Mid": 0.1, "High": 0.1, "Z": 0.1},
            )
        with pytest.raises(ValueError, match="must be a dict keyed by group"):
            comparisons(dose_df, "group", "value", reference="Ctrl", categories=cats, pvalues=[0.1, 0.2, 0.3])

    def test_ypositions_scalar_is_flat_row(self, dose_df):
        cats = ["Ctrl", "Low", "Mid", "High"]
        layer = comparisons(dose_df, "group", "value", reference="Ctrl", categories=cats, yPositions=9.0)
        ys = self._label_ys(layer)
        assert ys == [9.0, 9.0, 9.0]

    def test_ypositions_dict_partial(self, dose_df):
        cats = ["Ctrl", "Low", "Mid", "High"]
        layer = comparisons(dose_df, "group", "value", reference="Ctrl", categories=cats, yPositions={"Mid": 9.0})
        ys = self._label_ys(layer)
        assert 9.0 in ys and len(ys) == 3 and len(set(ys)) == 3  # one pinned, two auto (distinct)

    def test_ypositions_unknown_key_and_list_raise(self, dose_df):
        cats = ["Ctrl", "Low", "Mid", "High"]
        with pytest.raises(ValueError, match="not matching any group"):
            comparisons(dose_df, "group", "value", reference="Ctrl", categories=cats, yPositions={"Z": 9.0})
        with pytest.raises(ValueError, match="single number .* or a dict"):
            comparisons(dose_df, "group", "value", reference="Ctrl", categories=cats, yPositions=[1.0, 2.0, 3.0])

    def test_ystart_raises(self, dose_df):
        with pytest.raises(ValueError, match="does not apply in reference mode"):
            comparisons(
                dose_df, "group", "value", reference="Ctrl", categories=["Ctrl", "Low", "Mid", "High"], yStart=9.0
            )

    def test_labelstyle_value_renders_bare_numbers(self, dose_df):
        # labelStyle="value" drops "P =" but keeps "<" on floored values.
        cats = ["Ctrl", "Low", "Mid", "High"]
        layer = comparisons(
            dose_df,
            "group",
            "value",
            reference="Ctrl",
            categories=cats,
            pvalues={"Low": 0.041, "Mid": 0.0023, "High": 7e-6},
            labelStyle="value",
        )
        labels = _ref_labels(layer)
        assert "0.041" in labels and "0.0023" in labels and "< 0.001" in labels
        assert not any(lbl.startswith("P") for lbl in labels)

    def test_rejects_reference_with_xoffsetcol_omnibus_only(self, dose_df):
        # reference + xOffset is now grouped-reference (not an error); a bad reference level errors.
        rng = np.random.default_rng(3)
        genes = ["A", "B"]
        lvls = ["Veh", "Low", "High"]
        df = pl.DataFrame(
            {
                "gene": [g for g in genes for _ in lvls for _ in range(6)],
                "cond": [lv for _ in genes for lv in lvls for _ in range(6)],
                "expr": rng.normal(1.0, 0.2, len(genes) * len(lvls) * 6),
            }
        )
        # valid grouped reference: 2 genes x 2 non-ref levels = 4 labels
        layer = comparisons(
            df, "gene", "expr", xOffset="cond", reference="Veh", categories=genes, xOffsetSort=lvls, test="ttest_ind"
        )
        assert len(_ref_labels(layer)) == len(genes) * (len(lvls) - 1)
        # bad reference level raises
        with pytest.raises(ValueError, match="not a level"):
            comparisons(df, "gene", "expr", xOffset="cond", reference="Nope", categories=genes, xOffsetSort=lvls)

    def test_grouped_record_labels_subgroups(self, dose_df):
        from dysonsphere import _statistics as _st

        rng = np.random.default_rng(4)
        genes = ["A", "B"]
        lvls = ["Veh", "Drug"]
        df = pl.DataFrame(
            {
                "gene": [g for g in genes for _ in lvls for _ in range(6)],
                "cond": [lv for _ in genes for lv in lvls for _ in range(6)],
                "expr": rng.normal(1.0, 0.2, len(genes) * len(lvls) * 6),
            }
        )
        _st._REPORTS.clear()
        comparisons(df, "gene", "expr", xOffset="cond", reference="Veh", categories=genes, xOffsetSort=lvls)
        rec = next(iter(_st._REPORTS.values()))
        pairs = [(p["group1"], p["group2"]) for p in rec["comparisons"]["pairs"]]
        assert pairs == [("A (Veh)", "A (Drug)"), ("B (Veh)", "B (Drug)")]


def _y_positions(layer):
    """Rendered annotation y-coordinates (grouped label/bracket layers carry ``__y``)."""
    ys: list[float] = []

    def walk(node):
        if isinstance(node, dict):
            for row in node.get("data", {}).get("values", []) if isinstance(node.get("data"), dict) else []:
                if isinstance(row, dict) and "__y" in row:
                    ys.append(round(row["__y"], 3))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(layer.to_dict())
    return ys


class TestGroupedManualOverrides:
    """comparisons grouped mode: explicit pvalues / yStart / yPositions (dict-keyed)."""

    @pytest.fixture
    def gdf(self):
        rng = np.random.default_rng(2)
        genes = ["A", "B"]
        lvls = ["Veh", "Low", "High"]
        rows = [
            {"gene": g, "cond": lv, "expr": rng.normal(b * m, 0.2)}
            for g, b in zip(genes, (1.0, 2.0))
            for lv, m in zip(lvls, (1.0, 1.4, 2.2))
            for _ in range(8)
        ]
        return pl.DataFrame(rows), genes, lvls

    def _call(self, gdf, **kw):
        df, genes, lvls = gdf
        return comparisons(df, "gene", "expr", xOffset="cond", categories=genes, xOffsetSort=lvls, **kw)

    def test_reference_pvalues_dict_used_and_uncorrected(self, gdf):
        from dysonsphere import _statistics as _st

        _st._REPORTS.clear()
        self._call(
            gdf,
            reference="Veh",
            correction="holm",
            pvalues={("A", "Low"): 0.5, ("A", "High"): 0.001, ("B", "Low"): 0.02, ("B", "High"): 1e-6},
        )
        rec = next(iter(_st._REPORTS.values()))
        assert [round(p["pvalue"], 4) for p in rec["comparisons"]["pairs"]] == [0.5, 0.001, 0.02, 0.0]
        assert rec["comparisons"]["correction"] is None  # provided p-values are not corrected

    def test_bracket_pvalues_dict_order_insensitive(self, gdf):
        from dysonsphere import _statistics as _st

        _st._REPORTS.clear()
        self._call(gdf, pairs=[("Low", "High")], pvalues={("A", ("Low", "High")): 0.03, ("B", ("High", "Low")): 0.004})
        rec = next(iter(_st._REPORTS.values()))
        assert [round(p["pvalue"], 4) for p in rec["comparisons"]["pairs"]] == [0.03, 0.004]

    def test_reference_ystart_raises(self, gdf):
        # yStart has no meaning in reference mode (no stack); it raises rather than silently no-op.
        with pytest.raises(ValueError, match="does not apply in reference mode"):
            self._call(gdf, reference="Veh", yStart=9.0)

    def test_bracket_ystart_scalar_is_exact_base(self, gdf):
        # Brackets: an explicit scalar yStart is the exact stack base (not floor+yPad); the lowest
        # bracket in every category sits exactly at yStart.
        ys = _y_positions(self._call(gdf, pairs=[("Low", "High")], yStart=9.0))
        assert min(ys) == 9.0  # single pair per category -> all at the base, exactly

    def test_bracket_ystart_dict_per_category(self, gdf):
        ys = sorted(set(_y_positions(self._call(gdf, pairs=[("Low", "High")], yStart={"A": 3.0, "B": 7.0}))))
        assert ys == [3.0, 7.0]

    def test_bracket_ystart_unknown_category_raises(self, gdf):
        with pytest.raises(ValueError, match="not in the data"):
            self._call(gdf, pairs=[("Low", "High")], yStart={"Z": 3.0})

    def test_reference_ypositions_partial_fallback(self, gdf):
        ys = _y_positions(self._call(gdf, reference="Veh", yPositions={("A", "Low"): 8.0}))
        assert 8.0 in ys and len(ys) == 4  # one overridden, three auto

    def test_reference_ypositions_scalar_is_flat_row(self, gdf):
        # A single number flattens every grouped-reference label to one height.
        ys = _y_positions(self._call(gdf, reference="Veh", yPositions=10.0))
        assert ys and all(y == 10.0 for y in ys)

    def test_reference_ypositions_category_keyed_flat_row_per_category(self, gdf):
        # A dict keyed by category → one flat row per category (each level in that category shares it).
        ys = sorted(set(_y_positions(self._call(gdf, reference="Veh", yPositions={"A": 5.0, "B": 9.0}))))
        assert ys == [5.0, 9.0]

    def test_reference_ypositions_category_keyed_partial(self, gdf):
        # Unlisted categories fall back to auto placement.
        ys = _y_positions(self._call(gdf, reference="Veh", yPositions={"A": 5.0}))
        assert ys.count(5.0) == 2 and any(y != 5.0 for y in ys)  # A's two labels pinned, B's auto

    def test_ypositions_category_keyed_unknown_raises(self, gdf):
        with pytest.raises(ValueError, match="not in the data"):
            self._call(gdf, reference="Veh", yPositions={"Z": 5.0})

    def test_ypositions_mixed_keys_raise(self, gdf):
        with pytest.raises(ValueError, match="keys must be uniform"):
            self._call(gdf, reference="Veh", yPositions={"A": 5.0, ("B", "Low"): 6.0})

    def test_missing_pvalue_raises(self, gdf):
        with pytest.raises(ValueError, match="missing an entry"):
            self._call(gdf, reference="Veh", pvalues={("A", "Low"): 0.5})

    def test_unknown_pvalue_key_raises(self, gdf):
        with pytest.raises(ValueError, match="not matching any comparison"):
            self._call(
                gdf,
                reference="Veh",
                pvalues={("A", "Low"): 0.1, ("A", "High"): 0.1, ("B", "Low"): 0.1, ("B", "High"): 0.1, ("Z", "x"): 0.1},
            )

    def test_unknown_yposition_key_raises(self, gdf):
        with pytest.raises(ValueError, match="not matching any comparison"):
            self._call(gdf, reference="Veh", yPositions={("Z", "x"): 5.0})

    def test_list_pvalues_rejected_in_grouped(self, gdf):
        with pytest.raises(ValueError, match="must be a dict"):
            self._call(gdf, reference="Veh", pvalues=[0.1, 0.2, 0.3, 0.4])

    def test_dict_pvalues_rejected_in_single_factor(self):
        df = pl.DataFrame({"g": ["A"] * 8 + ["B"] * 8, "v": np.random.default_rng(0).normal(0, 1, 16)})
        with pytest.raises(ValueError, match="for grouped mode"):
            comparisons(df, "g", "v", pairs=[("A", "B")], categories=["A", "B"], pvalues={("A", "B"): 0.1})


class TestBracketOrder:
    """_bracket_offsets picks the rung order per component: a readable fan when it is free,
    a tight ladder against the data when it is not."""

    STEP = 13.0
    GAP = 6.0

    def _levels(self, anchors, spans, hi=6.0):
        """Rung index per bracket, recovered from the returned (anchor, offset) pairs."""

        def to_px(v, _hi=hi):
            return 100.0 * (1.0 - v / _hi)

        placed = _bracket_offsets(anchors, spans, self.GAP, self.STEP, to_px)
        # offsets are constant pixel lifts off one shared anchor, so rung = offset / step
        offs = [off for _, off in placed]
        lowest = min(offs)
        return [round((o - lowest) / self.STEP) for o in offs]

    ALL4 = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]  # 1v2 1v3 1v4 2v3 2v4 3v4

    def test_ordered_groups_get_the_lexicographic_fan(self):
        # A dose response: the fan costs nothing, so comparisons against group 1 run
        # consecutively (rungs 0,1,2) before group 2 starts (rungs 3,4).
        means = [1.2, 2.2, 3.4, 4.6]
        anchors = [max(means[a : b + 1]) for a, b in self.ALL4]
        assert self._levels(anchors, self.ALL4) == [0, 1, 2, 3, 4, 0]

    def test_unordered_groups_keep_the_tight_ladder(self):
        # Group 1 is the tallest, so the fan would strand 2v3/2v4 far above their own data.
        # Demand order wins instead, and 2v3 - lowest data - takes rung 0.
        means = [4.6, 1.2, 3.4, 2.2]
        anchors = [max(means[a : b + 1]) for a, b in self.ALL4]
        levels = self._levels(anchors, self.ALL4)
        assert levels != [0, 1, 2, 3, 4, 0]
        assert levels[3] == 0  # 2v3 on the first rung

    def test_tie_is_broken_by_order_not_float_noise(self):
        # The two candidate orders often tie mathematically and differ only by ~1e-14 px of
        # summation error. Unrounded, that noise picks the layout and the fan never appears.
        # These are the exact values a rendered 4-group dose response produces (data max 5.2,
        # nice-rounded to a [0, 5.5] domain) - the tie does not arise at other domains.
        means = [1.6, 2.7, 3.9, 5.2]
        anchors = [max(means[a : b + 1]) for a, b in self.ALL4]
        assert self._levels(anchors, self.ALL4, hi=5.5) == [0, 1, 2, 3, 4, 0]

    def test_disjoint_components_are_decided_independently(self):
        # Two clusters that share no groups each get their own ladder from rung 0.
        spans = [(0, 1), (1, 2), (3, 4), (4, 5)]
        means = [1.2, 2.0, 1.6, 4.6, 5.2, 4.9]
        anchors = [max(means[a : b + 1]) for a, b in spans]
        levels = self._levels(anchors, spans)
        assert {levels[0], levels[1]} == {0, 1}
        assert {levels[2], levels[3]} == {0, 1}

    def test_never_uses_more_rungs_than_the_tight_ladder(self):
        # Whatever order wins, it is scored on rung count first - so the fan can never cost height.
        for means in ([1.2, 2.2, 3.4, 4.6], [4.6, 1.2, 3.4, 2.2], [1.5, 5.5, 2.0, 1.8]):
            anchors = [max(means[a : b + 1]) for a, b in self.ALL4]
            assert max(self._levels(anchors, self.ALL4)) + 1 <= len(self.ALL4)


class TestDropTicks:
    """bracketStyle='drop' - end ticks reach toward each group's own data."""

    PAD = 4.0

    def test_reaches_toward_its_own_group_data(self):
        # One bracket, nothing in the way: both ends stop PAD short of their own group's data.
        lens = _drop_tick_lengths([0.0], [(0, 1)], [50.0, 30.0], ["drop"], [10.0, 20.0], [(0.0, 0.0, 0.0)])
        assert lens == [(50.0 - self.PAD, 30.0 - self.PAD)]

    def test_stops_above_a_lower_bracket_in_that_column(self):
        # Bracket 0 sits above bracket 1, which spans column 1 - so bracket 0's right end
        # stops above bracket 1's bar rather than continuing to the data.
        lens = _drop_tick_lengths(
            [0.0, 20.0],
            [(0, 2), (1, 2)],
            [90.0, 90.0, 90.0],
            ["drop", "drop"],
            [10.0, 20.0, 30.0],
            [(0.0, 0.0, -99.0), (0.0, 0.0, -99.0)],
        )
        assert lens[0][1] == 20.0 - self.PAD

    def test_stops_above_a_lower_bracket_label(self):
        # The label of a lower bracket sits ABOVE its bar, so a tick crossing that column has to
        # clear the label, not the bar - this is what a bar-only test misses.
        lens = _drop_tick_lengths(
            [0.0, 40.0],
            [(0, 2), (1, 2)],
            [90.0, 90.0, 90.0],
            ["drop", "drop"],
            [10.0, 20.0, 30.0],
            [(0.0, 0.0, -99.0), (15.0, 35.0, 25.0)],
        )
        assert lens[0][1] == 25.0 - self.PAD  # label top at 25, not the bar at 40

    def test_falls_back_to_a_fixed_cap_when_there_is_no_room(self):
        # A label directly beneath leaves no room to drop. The tick must still be drawn - an
        # earlier version deleted it, which read as a broken bracket.
        lens = _drop_tick_lengths(
            [0.0, 10.0],
            [(0, 1), (0, 1)],
            [90.0, 90.0],
            ["drop", "drop"],
            [10.0, 20.0],
            [(0.0, 0.0, -99.0), (5.0, 25.0, 2.0)],
        )
        assert lens[0][0] == _BRACKET_TICK_PX
        assert lens[0][1] == _BRACKET_TICK_PX

    def test_never_pushes_through_the_obstacle_it_cleared(self):
        # When even a fixed cap would touch, the tick shrinks below it rather than overshooting.
        lens = _drop_tick_lengths(
            [0.0, 1.0],
            [(0, 1), (0, 1)],
            [90.0, 90.0],
            ["drop", "drop"],
            [10.0, 20.0],
            [(0.0, 0.0, -99.0), (5.0, 25.0, 1.0)],
        )
        assert lens[0][0] <= 1.0

    def test_non_drop_styles_keep_the_fixed_length(self):
        lens = _drop_tick_lengths([0.0], [(0, 1)], [50.0, 50.0], ["bracket"], [10.0, 20.0], [(0.0, 0.0, 0.0)])
        assert lens == [(_BRACKET_TICK_PX, _BRACKET_TICK_PX)]

    def test_renders_per_end_lengths(self):
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 10 + ["B"] * 10 + ["C"] * 10, "v": rng.normal(0, 1, 30)})
        spec = comparisons(df, "g", "v", [("A", "B"), ("A", "C")], categories=MULTI, bracketStyle="drop").to_dict()
        ends = self._leg_ends(spec)
        assert ends, "drop brackets should still emit end legs"
        assert len(set(ends)) > 1, "drop ticks should differ in length, not all be the fixed cap"

    def test_reverse_ticks_travel_up_to_the_group_minimum(self):
        # A reverse bracket hangs below the data with ticks pointing up, so it approaches each
        # group's MINIMUM. Bar at 100, minima at 60/80 -> lengths 40-PAD and 20-PAD.
        lens = _drop_tick_lengths(
            [100.0],
            [(0, 1)],
            [10.0, 10.0],
            ["drop"],
            [10.0, 20.0],
            [(0.0, 0.0, 999.0)],
            [True],
            [60.0, 80.0],
        )
        assert lens == [(40.0 - self.PAD, 20.0 - self.PAD)]

    def test_reverse_is_blocked_by_what_lies_above_it(self):
        # Bracket 0 hangs lowest; bracket 1 sits between it and the data, so bracket 0's tick
        # stops below bracket 1's bar instead of reaching the minimum.
        lens = _drop_tick_lengths(
            [100.0, 70.0],
            [(0, 1), (0, 1)],
            [10.0, 10.0],
            ["drop", "drop"],
            [10.0, 20.0],
            [(0.0, 0.0, 999.0), (0.0, 0.0, 999.0)],
            [True, True],
            [30.0, 30.0],
        )
        assert lens[0][0] == 30.0 - self.PAD  # 100 -> 70 is 30 px of travel

    def test_mixed_directions_do_not_block_each_other(self):
        # Up and down brackets sit on opposite sides of the data, so neither is an obstacle for
        # the other - each still reaches its own side.
        lens = _drop_tick_lengths(
            [0.0, 100.0],
            [(0, 1), (0, 1)],
            [40.0, 40.0],
            ["drop", "drop"],
            [10.0, 20.0],
            [(0.0, 0.0, -99.0), (0.0, 0.0, 999.0)],
            [False, True],
            [60.0, 60.0],
        )
        assert lens[0][0] == 40.0 - self.PAD  # down to the maximum
        assert lens[1][0] == 40.0 - self.PAD  # up to the minimum

    def test_grouped_mode_emits_per_end_lengths(self):
        rows = []
        for gene, scale in [("G1", 1.0), ("G2", 1.8)]:
            for cond, m in {"Veh": 1.0, "Low": 2.2, "High": 3.6}.items():
                rows += [
                    {"gene": gene, "cond": cond, "expr": (m + o) * scale} for o in (0.0, 0.25, -0.15, 0.1, 0.3, -0.05)
                ]
        df = pl.DataFrame(rows)
        spec = comparisons(
            df,
            "gene",
            "expr",
            pairs=[("Veh", "Low"), ("Veh", "High")],
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=["Veh", "Low", "High"],
            bracketStyle="drop",
        ).to_dict()
        ends = self._grouped_leg_ends(spec)
        assert ends, "grouped drop brackets should emit end legs"
        assert len(set(ends)) > 1, "grouped drop ticks should differ per end"

    def test_single_factor_drop_ends_above_its_group_whatever_the_pair_order(self):
        # Two defects met here. The tick length was a pixel distance measured against a y domain
        # guessed from the data, so a chart pinning a wider one overshot; and the solved lengths
        # come back in COLUMN order, so a pair written against the category order handed each end
        # the other group's length - the long drop landing on the tall group.
        rng = np.random.default_rng(0)
        cats = ["Ctrl", "A", "B"]
        means = {"Ctrl": 1.0, "A": 20.0, "B": 12.0}
        df = pl.DataFrame(
            {
                "g": [c for c in cats for _ in range(6)],
                "v": [float(means[c] + rng.normal(0, 0.3)) for c in cats for _ in range(6)],
            }
        )
        tops = {c: cast(float, df.filter(pl.col("g") == c)["v"].max()) for c in cats}
        lo, hi = 0.0, 40.0
        height = float(_opt("chartHeight"))

        for pair in (("Ctrl", "A"), ("A", "Ctrl")):
            base = (
                alt.Chart(df)
                .mark_point()
                .encode(x=alt.X("g:N", sort=cats), y=alt.Y("v:Q", scale=alt.Scale(domain=[lo, hi])))
            )
            spec = (
                base + comparisons(df, "g", "v", pairs=[pair], categories=cats, test="ttest_ind", bracketStyle="drop")
            ).to_dict()
            found: dict[str, float] = {}

            def collect(node: Any) -> None:
                if isinstance(node, dict):
                    mark = node.get("mark")
                    if isinstance(mark, dict):
                        for row in node.get("data", {}).get("values") or []:
                            if "y2" in row and "x2" not in row and "x" in row:
                                # where the tick actually ends, in data units, as Vega draws it
                                px = height * (1.0 - (row["y2"] - lo) / (hi - lo)) + (mark.get("y2Offset") or 0.0)
                                found[row["x"]] = lo + (1.0 - px / height) * (hi - lo)
                    for value in node.values():
                        collect(value)
                elif isinstance(node, list):
                    for value in node:
                        collect(value)

            collect(spec)
            assert set(found) == set(pair), f"{pair}: expected a leg per group, got {found}"
            for group, end in found.items():
                assert end >= tops[group] - 1e-6, f"{pair}: {group} drop ran through its own data ({end:.2f})"

    def test_drop_ends_above_its_group_on_a_log_scale(self):
        # The old pixel conversion assumed a LINEAR scale, so on a log axis the tick landed far
        # below its group. A data-space endpoint is scale-type independent.
        rng = np.random.default_rng(3)
        cats = ["Ctrl", "Lo", "Hi"]
        mult = {"Ctrl": 1.0, "Lo": 30.0, "Hi": 900.0}
        df = pl.DataFrame(
            {
                "g": [c for c in cats for _ in range(6)],
                "v": [float(mult[c] * (1 + rng.normal(0, 0.05))) for c in cats for _ in range(6)],
            }
        )
        tops = {c: cast(float, df.filter(pl.col("g") == c)["v"].max()) for c in cats}
        base = (
            alt.Chart(df)
            .mark_point()
            .encode(x=alt.X("g:N", sort=cats), y=alt.Y("v:Q", scale=alt.Scale(type="log", domain=[0.5, 2000])))
        )
        spec = (
            base
            + comparisons(df, "g", "v", pairs=[("Ctrl", "Hi")], categories=cats, test="ttest_ind", bracketStyle="drop")
        ).to_dict()
        ends: dict[str, tuple[float, float]] = {}
        height = float(_opt("chartHeight"))

        def collect(node: Any) -> None:
            if isinstance(node, dict):
                mark = node.get("mark")
                if isinstance(mark, dict):
                    for row in node.get("data", {}).get("values") or []:
                        if "y2" in row and "x2" not in row and "x" in row:
                            ends[row["x"]] = (row["y2"], mark.get("y2Offset") or 0.0)
                for value in node.values():
                    collect(value)
            elif isinstance(node, list):
                for value in node:
                    collect(value)

        collect(spec)
        assert set(ends) == {"Ctrl", "Hi"}
        for group, (y2, y2_offset) in ends.items():
            # Resolve where the tick really ends, in data units, on the log scale it is drawn on.
            # A pixel offset converted as if the scale were linear lands far below its group.
            frac = (math.log10(y2) - math.log10(0.5)) / (math.log10(2000) - math.log10(0.5))
            px = height * (1.0 - frac) + y2_offset
            end = 10 ** (math.log10(0.5) + (1.0 - px / height) * (math.log10(2000) - math.log10(0.5)))
            assert end >= tops[group] - 1e-6, f"{group} drop ran through its own data on a log scale"

    def test_grouped_drop_ends_above_its_group_under_a_pinned_domain(self):
        # Regression: the tick length used to be a pixel distance measured against a y domain
        # the library guessed from the data. A chart that pins its own wider domain made every
        # drop overshoot - through the bar it should stop above, and off the bottom of the plot.
        rows = []
        for gene, lps in [("G1", 1.0), ("G2", 21.0)]:
            for cond, m in {"Veh": 1.0, "LPS": lps}.items():
                rows += [{"gene": gene, "cond": cond, "expr": m + o} for o in (0.0, 0.1, -0.1)]
        df = pl.DataFrame(rows)
        spec = comparisons(
            df,
            "gene",
            "expr",
            pairs=[("Veh", "LPS")],
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=["Veh", "LPS"],
            bracketStyle="drop",
        ).to_dict()
        tops: dict[tuple[str, str], float] = {}
        for r in rows:
            key = (r["gene"], r["cond"])
            tops[key] = max(tops.get(key, float("-inf")), r["expr"])
        ends = [
            (row["gene"], row["cond"], row["__y2"])
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            for row in (sub.get("data", {}).get("values") or [])
            if "__y2" in row and row["__y2"] != row.get("__y")
        ]
        assert ends, "grouped drop brackets should emit end legs"
        for gene, cond, end in ends:
            # The endpoint is in data units, so it must land at or above that group's own top -
            # never below it, and never below the axis floor.
            assert end >= tops[(gene, cond)] - 1e-9, f"{gene}/{cond} drop ran through its own data"
            assert end > 0, f"{gene}/{cond} drop ran past the axis"

    def test_grouped_mode_rejects_unknown_style(self):
        rows = []
        for gene in ("G1", "G2"):
            for cond in ("Veh", "Low"):
                rows += [{"gene": gene, "cond": cond, "expr": float(i)} for i in range(6)]
        with pytest.raises(ValueError, match="'bracket', 'line', or 'drop'"):
            comparisons(
                pl.DataFrame(rows),
                "gene",
                "expr",
                pairs=[("Veh", "Low")],
                xOffset="cond",
                categories=["G1", "G2"],
                xOffsetSort=["Veh", "Low"],
                bracketStyle="nope",
            )

    def _leg_offsets(self, spec):
        return [
            m["y2Offset"]
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            if isinstance((m := sub.get("mark")), dict) and "y2Offset" in m
        ]

    def _leg_ends(self, spec):
        """Single-factor drop ticks end at a DATA position (y2), not a pixel y2Offset."""
        return [
            row["y2"]
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            for row in (sub.get("data", {}).get("values") or [])
            if "y2" in row and row["y2"] != row.get("y")
        ]

    def _grouped_leg_ends(self, spec):
        """Grouped drop ticks end at a DATA position (__y2), not a pixel y2Offset."""
        return [
            row["__y2"]
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            for row in (sub.get("data", {}).get("values") or [])
            if "__y2" in row and row["__y2"] != row.get("__y")
        ]

    def test_explicit_ystart_still_gets_drop_ticks(self):
        # Explicit y spacing opts out of pixel placement; drop must work there too, not fall
        # back to fixed caps.
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 10 + ["B"] * 10 + ["C"] * 10, "v": rng.normal(0, 1, 30)})
        spec = comparisons(
            df,
            "g",
            "v",
            [("A", "B"), ("B", "C")],
            categories=MULTI,
            bracketStyle="drop",
            yStart=5.0,
            yStep=1.0,
        ).to_dict()
        ends = self._leg_ends(spec)
        assert ends, "explicit placement should still emit end legs"
        assert len(set(ends)) > 1, "drop ticks should vary, not all be the fixed cap"

    def test_pinned_positions_are_included_in_the_domain(self):
        # A bracket pinned far above the data stretches the rendered domain. Estimating from the
        # data alone would send its ticks straight through the marks.
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 10 + ["B"] * 10 + ["C"] * 10, "v": rng.normal(0, 1, 30)})
        spec = comparisons(
            df,
            "g",
            "v",
            [("A", "B"), ("B", "C")],
            categories=MULTI,
            bracketStyle="drop",
            yPositions=[40.0, 60.0],
        ).to_dict()
        ends = self._leg_ends(spec)
        assert ends
        # every leg ends inside the data range - a data-only domain overshoots it wildly
        assert all(-10.0 <= e <= 60.0 for e in ends), "a data-only domain overshoots the plot wildly"

    def test_grouped_explicit_placement_still_gets_drop_ticks(self):
        # Grouped drop was solved only under automatic placement; an explicit yStart left it
        # falling back to fixed caps.
        rows = []
        for gene, sc in [("G1", 1.0), ("G2", 1.8)]:
            for cond, m in {"Veh": 1.0, "Low": 2.2, "High": 3.6}.items():
                rows += [{"gene": gene, "cond": cond, "expr": (m + o) * sc} for o in (0.0, 0.25, -0.15, 0.1)]
        spec = comparisons(
            pl.DataFrame(rows),
            "gene",
            "expr",
            pairs=[("Veh", "Low"), ("Veh", "High")],
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=["Veh", "Low", "High"],
            bracketStyle="drop",
            yStart=9.0,
            yStep=1.5,
        ).to_dict()
        ends = self._grouped_leg_ends(spec)
        assert ends
        assert len(set(ends)) > 1, "explicit grouped placement should still vary tick lengths"

    def test_drop_counts_as_a_ticked_bracket_for_spacing(self):
        # yPad/gap targets branch on whether any bracket carries ticks; "drop" does, so an
        # all-drop chart must be spaced like "bracket", not like the bar-only "line".
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 10 + ["B"] * 10 + ["C"] * 10, "v": rng.normal(0, 1, 30)})
        bars = {}
        for style in ("bracket", "drop", "line"):
            spec = comparisons(df, "g", "v", [("A", "B")], categories=MULTI, bracketStyle=style).to_dict()
            bars[style] = [
                s["mark"]["yOffset"]
                for layer in spec["layer"]
                for s in layer.get("layer", [])
                if isinstance(s.get("mark"), dict) and "yOffset" in s.get("mark", {})
            ]
        assert bars["drop"] == bars["bracket"]
        assert bars["drop"] != bars["line"]

    def test_explicit_tick_height_with_drop_raises(self):
        # tickHeight fixes a length, drop computes one per end - accepting both would silently
        # ignore whichever lost.
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 10 + ["B"] * 10 + ["C"] * 10, "v": rng.normal(0, 1, 30)})
        with pytest.raises(ValueError, match="Pass one or the other"):
            comparisons(df, "g", "v", [("A", "B")], categories=MULTI, bracketStyle="drop", tickHeight=0.5)

    def test_explicit_tick_height_with_drop_raises_in_grouped(self):
        rows = []
        for gene in ("G1", "G2"):
            for cond in ("Veh", "Low"):
                rows += [{"gene": gene, "cond": cond, "expr": float(i)} for i in range(6)]
        with pytest.raises(ValueError, match="Pass one or the other"):
            comparisons(
                pl.DataFrame(rows),
                "gene",
                "expr",
                pairs=[("Veh", "Low")],
                xOffset="cond",
                categories=["G1", "G2"],
                xOffsetSort=["Veh", "Low"],
                bracketStyle="drop",
                tickHeight=0.5,
            )

    def test_tick_height_still_works_with_other_styles(self):
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 10 + ["B"] * 10 + ["C"] * 10, "v": rng.normal(0, 1, 30)})
        for style in ("bracket", "line"):
            assert (
                comparisons(df, "g", "v", [("A", "B")], categories=MULTI, bracketStyle=style, tickHeight=0.5)
                is not None
            )


class TestGroupedLabelCentering:
    """A grouped p-value label centres on its own bracket, not on the band."""

    @staticmethod
    def _frame(levels):
        rows = []
        for gene, sc in [("G1", 1.0), ("G2", 1.7)]:
            for i, lv in enumerate(levels):
                rows += [{"gene": gene, "cond": lv, "expr": (1.0 + 1.1 * i + o) * sc} for o in (0.0, 0.25, -0.15, 0.1)]
        return pl.DataFrame(rows)

    @staticmethod
    def _label_xs(spec):
        return [
            sub["encoding"]["x"]["value"]
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            if isinstance(sub.get("mark"), dict)
            and sub["mark"].get("type") == "text"
            and "value" in sub.get("encoding", {}).get("x", {})
        ]

    def test_asymmetric_pair_sits_on_its_bracket_not_the_band(self):
        levels = ["Veh", "Low", "High"]
        theme(chartWidth=100)
        spec = comparisons(
            self._frame(levels),
            "gene",
            "expr",
            pairs=[("Veh", "Low")],
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=levels,
        ).to_dict()
        subs = _nested_band_centers(2, 3, 100.0)
        expected = [(row[0] + row[1]) / 2 for row in subs]
        bands = list(_band_geometry(2, 100.0, scale="band", bandPadding=0.2).centers)
        assert self._label_xs(spec) == pytest.approx(expected)
        # and is genuinely off the band centre, which is what it used to use
        assert all(abs(a - b) > 1.0 for a, b in zip(expected, bands))

    def test_symmetric_pair_still_lands_on_the_band_centre(self):
        # A pair spanning the whole group has its midpoint AT the band centre - the old
        # behaviour was correct here, which is why two-level charts never showed the bug.
        levels = ["Veh", "Low", "High"]
        theme(chartWidth=100)
        spec = comparisons(
            self._frame(levels),
            "gene",
            "expr",
            pairs=[("Veh", "High")],
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=levels,
        ).to_dict()
        bands = list(_band_geometry(2, 100.0, scale="band", bandPadding=0.2).centers)
        assert self._label_xs(spec) == pytest.approx(bands)

    def test_label_tracks_the_pair_not_the_category(self):
        # Two different pairs in the same category must get different label positions.
        levels = ["Veh", "D1", "D2", "D3", "D4"]
        theme(chartWidth=100)
        spec = comparisons(
            self._frame(levels),
            "gene",
            "expr",
            pairs=[("Veh", "D1"), ("D3", "D4")],
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=levels,
        ).to_dict()
        xs = self._label_xs(spec)
        assert len(set(xs)) == 4, "each (category, pair) should get its own label position"


class TestGroupedReverse:
    """reverse= in grouped mode: brackets hang below their sub-bars, ticks pointing up."""

    LV = ["Veh", "Low", "High"]
    PAIRS = [("Veh", "Low"), ("Low", "High")]

    @staticmethod
    def _frame():
        rows = []
        for gene, sc in [("G1", 1.0), ("G2", 1.6)]:
            for i, lv in enumerate(["Veh", "Low", "High"]):
                rows += [{"gene": gene, "cond": lv, "expr": (3.0 + 1.1 * i + o) * sc} for o in (0.0, 0.25, -0.15, 0.1)]
        return pl.DataFrame(rows)

    def _spec(self, **kw):
        return comparisons(
            self._frame(),
            "gene",
            "expr",
            pairs=self.PAIRS,
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=self.LV,
            labelStyle="asterisks",
            **kw,
        ).to_dict()

    @staticmethod
    def _bracket_ys(spec, category):
        return [
            v["__y"]
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            for v in sub.get("data", {}).get("values", [])
            if "__y" in v and v.get("gene") == category
        ]

    @staticmethod
    def _marks(spec, mtype):
        return [
            sub["mark"]
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            if isinstance(sub.get("mark"), dict) and sub["mark"].get("type") == mtype
        ]

    def test_reverse_hangs_the_bracket_below_its_groups(self):
        # Per CATEGORY: a normal bracket sits at or above that category's data, a reverse one at
        # or below it. (Bracket offsets ride a shared anchor and are legitimately either sign, so
        # the offset alone says nothing about direction.)
        df = self._frame()
        for cat in ("G1", "G2"):
            lo = float(df.filter(pl.col("gene") == cat)["expr"].min())
            hi = float(df.filter(pl.col("gene") == cat)["expr"].max())
            up = self._bracket_ys(self._spec(), cat)
            down = self._bracket_ys(self._spec(reverse=self.PAIRS), cat)
            assert up and down
            assert min(up) >= hi - 1e-9, f"{cat}: normal brackets should sit above the data"
            assert max(down) <= lo + 1e-9, f"{cat}: reverse brackets should sit below the data"

    def test_reverse_hangs_the_label_below(self):
        normal = self._marks(self._spec(), "text")
        rev = self._marks(self._spec(reverse=self.PAIRS), "text")
        assert normal and rev
        assert all(m.get("baseline") is None for m in normal)
        assert all(m.get("baseline") == "top" for m in rev)

    def test_mixed_directions_in_one_chart(self):
        # Only the named pair reverses; the other keeps pointing up.
        texts = self._marks(self._spec(reverse=[("Veh", "Low")]), "text")
        assert any(m["dy"] > 0 for m in texts) and any(m["dy"] < 0 for m in texts)

    def test_reverse_works_with_drop_ticks(self):
        spec = self._spec(reverse=self.PAIRS, bracketStyle="drop")
        # Grouped drop ticks end at a DATA position (__y2), not a pixel y2Offset.
        ends = [
            row["__y2"]
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            for row in (sub.get("data", {}).get("values") or [])
            if "__y2" in row and row["__y2"] != row.get("__y")
        ]
        assert ends
        assert len(set(ends)) > 1, "drop ticks should vary per end"

    def test_non_adjacent_span_clears_the_groups_it_passes_over(self):
        # A Veh-D3 bracket passes over D1 and D2 without touching them. It must anchor on every
        # level it SPANS, not just its endpoints - otherwise a dipping middle group sits on the
        # wrong side of a reverse bracket.
        means = {"Veh": 5.0, "D1": 6.2, "D2": 3.0, "D3": 6.8}  # D2 dips below both endpoints
        levels = ["Veh", "D1", "D2", "D3"]
        rows = [
            {"gene": g, "cond": lv, "expr": (means[lv] + o) * sc}
            for g, sc in [("G1", 1.0), ("G2", 1.5)]
            for lv in levels
            for o in (0.0, 0.25, -0.15, 0.1)
        ]
        df = pl.DataFrame(rows)
        spec = comparisons(
            df,
            "gene",
            "expr",
            pairs=[("Veh", "D3")],
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=levels,
            labelStyle="asterisks",
            reverse=[("Veh", "D3")],
        ).to_dict()
        for cat in ("G1", "G2"):
            sub = df.filter(pl.col("gene") == cat)
            spanned_min = cast(float, sub["expr"].min())
            endpoints_min = cast(float, sub.filter(pl.col("cond").is_in(["Veh", "D3"]))["expr"].min())
            assert spanned_min < endpoints_min, "fixture must have a dipping middle group"
            ys = self._bracket_ys(spec, cat)
            assert ys and max(ys) <= spanned_min + 1e-9


class TestPairsAll:
    """pairs="all" - expand to every unique pair, so `correction` covers the real family."""

    @pytest.fixture
    def four_df(self):
        # Four cleanly separated groups: every pairwise test is significant, so a missing
        # comparison shows up as a missing bracket rather than a borderline p-value.
        rng = np.random.default_rng(0)
        rows = []
        for i, g in enumerate(["A", "B", "C", "D"]):
            rows += [{"g": g, "v": float(i * 10 + x)} for x in rng.normal(0, 1, 8)]
        return pl.DataFrame(rows)

    @pytest.fixture
    def three_df(self, four_df):
        return four_df.filter(pl.col("g") != "D")

    def _record(self):
        return next(iter(st._REPORTS.values()))

    def test_expands_to_every_unique_pair(self, four_df):
        comparisons(four_df, "g", "v", pairs="all", categories=["A", "B", "C", "D"])
        pairs = [(p["group1"], p["group2"]) for p in self._record()["comparisons"]["pairs"]]
        assert pairs == [
            ("A", "B"),
            ("A", "C"),
            ("A", "D"),
            ("B", "C"),
            ("B", "D"),
            ("C", "D"),
        ]

    def test_follows_categories_order_not_alphabetical(self, four_df):
        comparisons(four_df, "g", "v", pairs="all", categories=["D", "B", "A", "C"])
        pairs = [(p["group1"], p["group2"]) for p in self._record()["comparisons"]["pairs"]]
        assert pairs[0] == ("D", "B")
        assert pairs[-1] == ("A", "C")

    def test_correction_family_is_every_pair(self, four_df):
        # The whole point: m defaults to len(pairs), so "all" corrects over 6, not a subset.
        comparisons(four_df, "g", "v", pairs="all", correction="bonferroni", categories=["A", "B", "C", "D"])
        corrected = [p["pvalue"] for p in self._record()["comparisons"]["pairs"]]
        st._REPORTS.clear()
        comparisons(four_df, "g", "v", pairs="all", categories=["A", "B", "C", "D"])
        raw = [p["pvalue"] for p in self._record()["comparisons"]["pairs"]]
        assert len(raw) == 6
        for r, c in zip(raw, corrected):
            assert c == pytest.approx(min(1.0, r * 6))

    def test_equivalent_to_listing_pairs_by_hand(self, three_df):
        cats = ["A", "B", "C"]
        by_hand = [("A", "B"), ("A", "C"), ("B", "C")]
        comparisons(three_df, "g", "v", pairs=by_hand, categories=cats, correction="holm")
        expected = self._record()
        st._REPORTS.clear()
        comparisons(three_df, "g", "v", pairs="all", categories=cats, correction="holm")
        assert self._record() == expected

    def test_draws_a_bracket_per_pair(self, three_df):
        r = comparisons(three_df, "g", "v", pairs="all", categories=["A", "B", "C"])
        assert isinstance(r, alt.LayerChart)
        # One nested layer per pair (bar + two end ticks + label), so exactly one p-value
        # label per pair - every comparison is drawn, not just the ones that fit.
        spec = r.to_dict()
        assert len(spec["layer"]) == 3

        def _texts(layers):
            return sum(
                (1 if layer.get("mark", {}).get("type") == "text" else 0) + _texts(layer.get("layer", []))
                for layer in layers
            )

        assert _texts(spec["layer"]) == 3

    def test_works_with_omnibus_post_hoc(self, three_df):
        comparisons(three_df, "g", "v", pairs="all", test="kruskal", categories=["A", "B", "C"])
        rec = self._record()
        assert rec["kind"] == "omnibus"
        assert rec["comparisons"]["test"] == "dunn"
        assert len(rec["comparisons"]["pairs"]) == 3

    def test_grouped_expands_over_levels(self):
        rows = []
        for gene in ["G1", "G2"]:
            for i, cond in enumerate(["Veh", "Low", "High"]):
                noise = (0.0, 0.3, -0.2, 0.1, 0.2, -0.1)
                rows += [{"gene": gene, "cond": cond, "expr": float(i * 5 + x)} for x in noise]
        df = pl.DataFrame(rows)
        comparisons(
            df,
            "gene",
            "expr",
            pairs="all",
            xOffset="cond",
            categories=["G1", "G2"],
            xOffsetSort=["Veh", "Low", "High"],
        )
        pairs = [(p["group1"], p["group2"]) for p in self._record()["comparisons"]["pairs"]]
        # every level pair, within every category
        assert len(pairs) == 6
        assert ("G1 (Veh)", "G1 (Low)") in pairs
        assert ("G2 (Veh)", "G2 (High)") in pairs

    def test_rejects_other_strings(self, four_df):
        two = four_df.filter(pl.col("g").is_in(["A", "B"]))
        with pytest.raises(ValueError, match="pairs must be a list of tuples, 'all', or None"):
            comparisons(two, "g", "v", pairs="ALL", categories=["A", "B"])

    def test_rejects_with_reference(self, three_df):
        with pytest.raises(ValueError, match="reference derives its own comparisons"):
            comparisons(three_df, "g", "v", pairs="all", reference="A", categories=["A", "B", "C"])

    def test_rejects_single_category(self, four_df):
        one = four_df.filter(pl.col("g") == "A")
        with pytest.raises(ValueError, match="at least two"):
            comparisons(one, "g", "v", pairs="all", categories=["A"])


class TestBracketNoPhantomAxis:
    """A bracket must not contribute an x scale - it cannot merge with a base that resolves x
    independently (mark_violin does), and would draw its own axis titled from internal fields."""

    @staticmethod
    def _x_encodings(spec, out=None):
        out = [] if out is None else out
        if isinstance(spec, dict):
            enc = spec.get("encoding", {})
            for ch in ("x", "x2"):
                if ch in enc:
                    out.append(enc[ch])
            for v in spec.values():
                TestBracketNoPhantomAxis._x_encodings(v, out)
        elif isinstance(spec, list):
            for v in spec:
                TestBracketNoPhantomAxis._x_encodings(v, out)
        return out

    def _bracket_spec(self, **kw):
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})
        return comparisons(df, "g", "v", [("A", "B")], categories=MULTI, **kw).to_dict()

    def test_bracket_positions_in_pixels_not_a_nominal_field(self):
        encs = self._x_encodings(self._bracket_spec())
        assert encs, "bracket should encode x"
        assert all("value" in e for e in encs), f"bracket x must be pixel values, got {encs}"
        assert not any("field" in e for e in encs), "a field on x contributes a scale that can strand"

    def test_holds_for_every_bracket_style(self):
        for style in ("bracket", "line", "drop"):
            encs = self._x_encodings(self._bracket_spec(bracketStyle=style))
            assert all("value" in e for e in encs), f"{style}: {encs}"

    def test_pair_identity_is_still_recorded_in_the_data(self):
        # Position moved to pixels, but the spec must still say which groups each bracket spans.
        spec = self._bracket_spec()
        vals = [
            v
            for layer in spec["layer"]
            for sub in layer.get("layer", [])
            for v in sub.get("data", {}).get("values", [])
        ]
        assert any(v.get("x") == "A" and v.get("x2") == "B" for v in vals)

    def test_violin_base_draws_no_extra_category_labels(self):
        # The regression: mark_violin resolves x independently, so an encoded bracket drew its own
        # axis - three real category labels became five.
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})
        spec = (mark_violin(df, "g", "v", MULTI) + comparisons(df, "g", "v", [("A", "B")], categories=MULTI)).to_dict()
        fields = [e["field"] for e in self._x_encodings(spec) if "field" in e]
        assert "x" not in fields and "x2" not in fields, f"bracket fields leaked onto x: {fields}"

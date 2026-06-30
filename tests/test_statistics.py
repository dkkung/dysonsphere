import altair as alt
import numpy as np
import polars as pl
import pytest

from dysonsphere.statistics import _format_asterisks, _format_pvalue, add_pvalue
from dysonsphere.theme import theme

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
        assert _format_pvalue(0.0234) == "P = 0.023"

    def test_custom_decimals(self):
        assert _format_pvalue(0.1, decimals=2) == "P = 0.10"

    def test_p_one(self):
        assert _format_pvalue(1.0) == "P = 1.000"

    def test_p_zero(self):
        assert _format_pvalue(0.0) == "P < 0.001"

    def test_decimals_affects_threshold(self):
        # decimals=2 → threshold=0.01; p=0.005 is below it
        assert _format_pvalue(0.005, decimals=2) == "P < 0.01"

    def test_decimals_threshold_exact(self):
        # p=0.01 is not below threshold=0.01
        assert _format_pvalue(0.01, decimals=2) == "P = 0.01"


class TestFormatPvalueNotation:
    def test_scientific(self):
        result = _format_pvalue(0.023, notation="scientific", decimals=2)
        assert result == "P = 2.30×10⁻²"

    def test_scientific_small(self):
        result = _format_pvalue(1.5e-5, notation="scientific", decimals=2)
        assert result == "P = 1.50×10⁻⁵"

    def test_scientific_default_decimals(self):
        # decimals=3 by default
        result = _format_pvalue(0.023, notation="scientific")
        assert result == "P = 2.300×10⁻²"

    def test_e_notation(self):
        result = _format_pvalue(0.023, notation="e", decimals=2)
        assert result == "P = 2.30e-02"

    def test_e_notation_small(self):
        result = _format_pvalue(1.5e-5, notation="e", decimals=2)
        assert result == "P = 1.50e-05"

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


class TestAddPvalue:
    def test_returns_layer_chart_with_explicit_pvalue(self, group_df):
        result = add_pvalue(group_df, "group", "value", [("A", "B")], pvalues=[0.01])
        assert isinstance(result, alt.LayerChart)

    def test_returns_layer_chart_running_test(self, group_df):
        result = add_pvalue(group_df, "group", "value", [("A", "B")])
        assert isinstance(result, alt.LayerChart)

    def test_multiple_pairs(self, group_df):
        df = pl.DataFrame(
            {
                "group": ["A"] * 10 + ["B"] * 10 + ["C"] * 10,
                "value": np.random.default_rng(1).normal(0, 1, 30),
            }
        )
        result = add_pvalue(
            df,
            "group",
            "value",
            [("A", "B"), ("B", "C")],
            pvalues=[0.01, 0.05],
        )
        assert isinstance(result, alt.LayerChart)

    def test_asterisk_label_style(self, group_df):
        result = add_pvalue(
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
            add_pvalue(group_df, "group", "value", [("A", "B")], test="bogus")

    def test_notation_scientific(self, group_df):
        result = add_pvalue(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[1.5e-5],
            notation="scientific",
            decimals=2,
        )
        assert isinstance(result, alt.LayerChart)
        spec = result.to_dict()
        label = spec["layer"][0]["layer"][-1]["data"]["values"][0]["label"]
        assert label == "P = 1.50×10⁻⁵"

    def test_notation_e(self, group_df):
        result = add_pvalue(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[1.5e-5],
            notation="e",
            decimals=2,
        )
        assert isinstance(result, alt.LayerChart)

    def test_notation_power(self, group_df):
        result = add_pvalue(
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
        result = add_pvalue(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[0.023],
        )
        spec = result.to_dict()
        label = spec["layer"][0]["layer"][-1]["data"]["values"][0]["label"]
        assert label == "P = 0.023"

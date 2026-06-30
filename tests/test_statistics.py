import altair as alt
import numpy as np
import polars as pl
import pytest

from dysonsphere.layers import _format_asterisks, _format_pvalue, add_statistics
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


class TestDeprecatedAlias:
    def test_add_pvalue_warns_and_works(self, group_df):
        from dysonsphere.layers import add_pvalue

        with pytest.warns(DeprecationWarning, match="add_statistics"):
            result = add_pvalue(group_df, "group", "value", [("A", "B")], pvalues=[0.01])
        assert isinstance(result, alt.LayerChart)

    def test_add_pvalue_exposed_on_namespace(self):
        import dysonsphere as ds

        assert hasattr(ds, "add_pvalue") and hasattr(ds, "add_statistics")


class TestAddStatistics:
    def test_returns_layer_chart_with_explicit_pvalue(self, group_df):
        result = add_statistics(group_df, "group", "value", [("A", "B")], pvalues=[0.01])
        assert isinstance(result, alt.LayerChart)

    def test_returns_layer_chart_running_test(self, group_df):
        result = add_statistics(group_df, "group", "value", [("A", "B")])
        assert isinstance(result, alt.LayerChart)

    def test_multiple_pairs(self, group_df):
        df = pl.DataFrame(
            {
                "group": ["A"] * 10 + ["B"] * 10 + ["C"] * 10,
                "value": np.random.default_rng(1).normal(0, 1, 30),
            }
        )
        result = add_statistics(
            df,
            "group",
            "value",
            [("A", "B"), ("B", "C")],
            pvalues=[0.01, 0.05],
        )
        assert isinstance(result, alt.LayerChart)

    def test_asterisk_label_style(self, group_df):
        result = add_statistics(
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
            add_statistics(group_df, "group", "value", [("A", "B")], test="bogus")

    def test_notation_scientific(self, group_df):
        result = add_statistics(
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
        result = add_statistics(
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
        result = add_statistics(
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
        result = add_statistics(
            group_df,
            "group",
            "value",
            [("A", "B")],
            pvalues=[0.023],
        )
        spec = result.to_dict()
        label = spec["layer"][0]["layer"][-1]["data"]["values"][0]["label"]
        assert label == "P = 0.023"


# ── Pure statistics module (dysonsphere.statistics) ─────────────────────────
from dysonsphere import statistics as st  # noqa: E402

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

    def test_unknown(self):
        with pytest.raises(ValueError, match="correction"):
            st._adjust([0.1], "bogus", 1)


class TestReportRegistry:
    def test_describe(self):
        d = st._describe("X", np.array([1.0, 2, 3, 4]))
        assert d["n"] == 4 and d["mean"] == pytest.approx(2.5) and d["median"] == pytest.approx(2.5)

    def test_drain_dedups_and_clears(self):
        st._REPORTS.clear()
        same = {"kind": "pairwise", "test": "x"}
        other = {"kind": "omnibus", "test": "y"}
        st._push_report(dict(same))
        st._push_report(dict(same))
        st._push_report(dict(other))
        assert st._drain_reports() == [same, other]
        assert st._drain_reports() == []

    def test_make_record_structure(self):
        r = st._run_omnibus("anova", _GROUPS, MULTI)
        rec = st._make_record(
            test="anova",
            is_omnibus=True,
            omnibus=r,
            descriptives=st._describe_all(_GROUPS, MULTI),
            comparisons=[{"g1": "A", "g2": "C", "pvalue": 0.001, "effectName": "d", "effect": -2.5}],
            comparison_test="tukey_hsd",
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
            pvalues_provided=False,
        )
        text = st._render_report(rec)
        lines = text.splitlines()
        title = "Statistics | Omnibus | ANOVA"
        assert lines[0] == title
        assert lines[1] == "─" * len(title)  # box-drawing underline matches title width
        assert "Group descriptives:" in text
        assert "Post-hoc (tukey_hsd):" in text and "A vs C" in text


# ── add_statistics omnibus integration ──────────────────────────────────────────
@pytest.fixture
def multi_df():
    rng = np.random.default_rng(3)
    return pl.DataFrame(
        {
            "group": [c for c in MULTI for _ in range(20)],
            "value": np.concatenate([rng.normal(m, 1, 20) for m in (1.0, 2.0, 3.5)]),
        }
    )


class TestAddStatisticsOmnibus:
    def _texts(self, layer):
        spec = layer.to_dict()
        return [v for sub in spec.get("layer", []) for v in str(sub).split("'") if v]

    def test_omnibus_corner_label_present(self, multi_df):
        layer = add_statistics(multi_df, "group", "value", test="anova", categories=MULTI)
        assert "ANOVA" in str(layer.to_dict())

    def test_verbose_label(self, multi_df):
        layer = add_statistics(multi_df, "group", "value", test="anova", categories=MULTI, omnibusVerbose=True)
        s = str(layer.to_dict())
        assert "F(2, 57)" in s and "η²" in s

    def test_omnibus_position_none_no_label(self, multi_df):
        layer = add_statistics(multi_df, "group", "value", test="kruskal", categories=MULTI, omnibusPosition=None)
        assert "Kruskal" not in str(layer.to_dict())

    def test_omnibus_with_posthoc_brackets(self, multi_df):
        layer = add_statistics(multi_df, "group", "value", pairs=[("A", "C")], test="anova", categories=MULTI)
        # corner label + one bracket layer
        assert "ANOVA" in str(layer.to_dict())

    def test_report_includes_all_comparisons_not_just_bracketed(self, multi_df):
        # only A-C is bracketed, but the omnibus report should list all 3 pairs
        st._REPORTS.clear()
        add_statistics(multi_df, "group", "value", pairs=[("A", "C")], test="anova", categories=MULTI)
        pairs = st._REPORTS[0]["comparisons"]["pairs"]
        listed = {(p["group1"], p["group2"]) for p in pairs}
        assert listed == {("A", "B"), ("A", "C"), ("B", "C")}

    def test_report_all_comparisons_omnibus_only(self, multi_df):
        # no brackets at all, but the report still lists every pairwise post-hoc
        st._REPORTS.clear()
        add_statistics(multi_df, "group", "value", test="kruskal", categories=MULTI)
        rec = st._REPORTS[0]
        assert rec["comparisons"]["test"] == "dunn"
        assert len(rec["comparisons"]["pairs"]) == 3

    def test_report_queued_as_record(self, multi_df):
        st._REPORTS.clear()
        add_statistics(multi_df, "group", "value", test="anova", categories=MULTI)
        assert len(st._REPORTS) == 1
        rec = st._REPORTS[0]
        assert rec["kind"] == "omnibus" and rec["omnibus"]["name"] == "ANOVA"
        assert "ANOVA" in st._render_report(rec)

    def test_report_prints(self, multi_df, capsys):
        add_statistics(multi_df, "group", "value", test="anova", categories=MULTI, report=True)
        assert "Group descriptives:" in capsys.readouterr().out

    def test_save_writes_file(self, multi_df, tmp_path):
        add_statistics(multi_df, "group", "value", test="anova", categories=MULTI, save=str(tmp_path))
        files = list(tmp_path.glob("dysonsphere_report_*.txt"))
        assert len(files) == 1 and "ANOVA" in files[0].read_text()

    def test_pairwise_requires_pairs(self, multi_df):
        with pytest.raises(ValueError, match="pairs is required"):
            add_statistics(multi_df, "group", "value", test="mannwhitneyu", categories=MULTI)

    def test_empty_pairs_rejected(self, multi_df):
        with pytest.raises(ValueError, match="must not be empty"):
            add_statistics(multi_df, "group", "value", pairs=[], test="anova", categories=MULTI)

    def test_default_posthoc_per_omnibus(self, multi_df):
        # kruskal default post-hoc is dunn; just ensure it runs and brackets build
        layer = add_statistics(multi_df, "group", "value", pairs=[("A", "C")], test="kruskal", categories=MULTI)
        assert isinstance(layer, alt.LayerChart)

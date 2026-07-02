import altair as alt
import numpy as np
import polars as pl
import pytest

from dysonsphere.layers import (
    _correlation_label,
    _format_asterisks,
    _format_pvalue,
    add_comparisons,
    add_correlation,
)
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
        result = add_comparisons(group_df, "group", "value", [("A", "B")], pvalues=[0.01])
        assert isinstance(result, alt.LayerChart)

    def test_returns_layer_chart_running_test(self, group_df):
        result = add_comparisons(group_df, "group", "value", [("A", "B")])
        assert isinstance(result, alt.LayerChart)

    def test_multiple_pairs(self, group_df):
        df = pl.DataFrame(
            {
                "group": ["A"] * 10 + ["B"] * 10 + ["C"] * 10,
                "value": np.random.default_rng(1).normal(0, 1, 30),
            }
        )
        result = add_comparisons(
            df,
            "group",
            "value",
            [("A", "B"), ("B", "C")],
            pvalues=[0.01, 0.05],
        )
        assert isinstance(result, alt.LayerChart)

    def test_asterisk_label_style(self, group_df):
        result = add_comparisons(
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
            add_comparisons(group_df, "group", "value", [("A", "B")], test="bogus")

    def test_notation_scientific(self, group_df):
        result = add_comparisons(
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
        result = add_comparisons(
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
        result = add_comparisons(
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
        result = add_comparisons(
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
        spec = add_comparisons(group_df, "group", "value", [("A", "B")], pvalues=[0.01]).to_dict()
        assert spec["layer"][0]["layer"][-1]["mark"]["fontSize"] == 10


def _text_labels(layer):
    """Pull rendered text-mark strings out of a chart's named datasets."""
    datasets = layer.to_dict().get("datasets", {})
    return [rows[0]["__text"] for rows in datasets.values() if rows and "__text" in rows[0]]


class TestTestLabel:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def test_pairwise_no_label_by_default(self, tri_df):
        layer = add_comparisons(tri_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=MULTI)
        assert _text_labels(layer) == []  # auto → hidden for pairwise

    def test_pairwise_label_opt_in(self, tri_df):
        layer = add_comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, testLabelPosition="topRight")
        assert _text_labels(layer) == ["Mann-Whitney U"]

    def test_pairwise_label_wilcoxon_name(self, tri_df):
        layer = add_comparisons(
            tri_df, "g", "v", [("A", "B")], categories=MULTI, test="wilcoxon", testLabelPosition="topRight"
        )
        assert _text_labels(layer) == ["Wilcoxon signed-rank"]

    def test_omnibus_label_shown_by_default(self, tri_df):
        layer = add_comparisons(tri_df, "g", "v", categories=MULTI, test="anova")
        assert _text_labels(layer)[0].startswith("ANOVA P")  # auto → topLeft for omnibus

    def test_omnibus_label_hidden(self, tri_df):
        layer = add_comparisons(tri_df, "g", "v", categories=MULTI, test="anova", testLabelPosition=None)
        assert _text_labels(layer) == []

    def test_omnibus_posthoc_shows_omnibus_not_posthoc(self, tri_df):
        layer = add_comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, test="anova")
        labels = _text_labels(layer)
        assert any(t.startswith("ANOVA P") for t in labels) and "Tukey HSD" not in labels

    def test_test_label_override(self, tri_df):
        layer = add_comparisons(
            tri_df, "g", "v", categories=MULTI, test="anova", testLabel="my label", testLabelPosition="topLeft"
        )
        assert _text_labels(layer) == ["my label"]

    def test_manual_coords_draw_label(self, tri_df):
        layer = add_comparisons(
            tri_df, "g", "v", categories=MULTI, test="anova", testLabelPosition=None, testLabelX=1.0, testLabelY=2.0
        )
        assert _text_labels(layer)[0].startswith("ANOVA P")

    def test_omnibus_label_never_asterisks(self, tri_df):
        # labelStyle="asterisks" affects only the brackets, not the omnibus result label
        layer = add_comparisons(tri_df, "g", "v", categories=MULTI, test="kruskal", labelStyle="asterisks")
        label = _text_labels(layer)[0]
        assert " P " in label and "*" not in label


class TestTickHeight:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def test_tick_height_defaults_to_tick_size(self, tri_df):
        # bracket end-tick height (data units) = tickSize(px) * y_range / chartHeight
        theme(chartWidth=200, chartHeight=200, tickSize=3)
        sub = tri_df.filter(pl.col("g").is_in(["A", "B"]))
        y_range = float(sub["v"].max() - sub["v"].min())
        expected = 3 * y_range / 200
        layer = add_comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, bracketStyle="bracket")
        # the end-tick sub-layers carry y/y2 whose gap equals tickHeight
        spec = layer.to_dict()
        gaps = [
            abs(v["y"] - v["y2"])
            for sub in spec["layer"][0]["layer"]
            for v in sub.get("data", {}).get("values", [])
            if "y" in v and "y2" in v
        ]
        assert any(abs(g - expected) < 1e-9 for g in gaps)


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
        m = self._text_mark(add_comparisons(two_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=CATEGORIES))
        assert "baseline" not in m  # reverse=False must not set an explicit baseline

    def test_reverse_sets_top_baseline(self, two_df):
        layer = add_comparisons(
            two_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=CATEGORIES, reverse=[("A", "B")]
        )
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
        return add_comparisons(
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
        assert self._label(add_comparisons(group_df, "g", "v", [("A", "B")], pvalues=[0.4789])) == "P = 0.48"

    def test_per_call_overrides_theme(self, group_df):
        theme(chartWidth=200, chartHeight=200, sigFigs=2)
        lbl = self._label(add_comparisons(group_df, "g", "v", [("A", "B")], pvalues=[0.4789], sigFigs=4))
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
        d = layer.to_dict().get("datasets", {})
        vals = [v[0].get("__text") for v in d.values() if v and "__text" in v[0]]
        return vals[0] if vals else None

    def test_scalar_applies_to_all(self, tri_df):
        labels = self._bracket_labels(
            add_comparisons(
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
            add_comparisons(
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
            add_comparisons(
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
        layer = add_comparisons(tri_df, "g", "v", categories=MULTI, test="anova", notation={"test": "e"})
        assert "e-" in self._test_label(layer) or "e+" in self._test_label(layer)

    def test_dict_without_test_key_omnibus_plain(self, tri_df):
        layer = add_comparisons(tri_df, "g", "v", categories=MULTI, test="anova", notation={("A", "B"): "scientific"})
        assert self._test_label(layer).startswith("ANOVA P = 0.")

    def test_invalid_value_raises(self, tri_df):
        with pytest.raises(ValueError, match="notation dict values"):
            add_comparisons(
                tri_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=MULTI, notation={("A", "B"): "si"}
            )

    def test_invalid_string_key_raises(self, tri_df):
        with pytest.raises(ValueError, match="notation dict string keys must be 'test'"):
            add_comparisons(tri_df, "g", "v", [("A", "B")], pvalues=[0.01], categories=MULTI, notation={"omnibus": "e"})


class TestCorrectionMetadata:
    @pytest.fixture
    def tri_df(self):
        rng = np.random.default_rng(0)
        return pl.DataFrame({"g": ["A"] * 12 + ["B"] * 12 + ["C"] * 12, "v": rng.normal(0, 1, 36)})

    def test_correction_recorded(self, tri_df):
        from dysonsphere import statistics as _st

        _st._REPORTS.clear()
        add_comparisons(tri_df, "g", "v", [("A", "B"), ("A", "C")], categories=MULTI, correction="holm")
        rec = next(iter(_st._REPORTS.values()))
        assert rec["comparisons"]["correction"] == "holm"

    def test_tukey_correction_stored_none(self, tri_df):
        from dysonsphere import statistics as _st

        _st._REPORTS.clear()
        add_comparisons(tri_df, "g", "v", [("A", "B")], categories=MULTI, test="anova", correction="bonferroni")
        rec = next(iter(_st._REPORTS.values()))
        assert rec["comparisons"]["correction"] is None  # tukey carries its own correction


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
        assert st._marker_hash(m1) == st._marker_hash(m2)  # same content → same hash
        assert st._marker_hash(m1) != st._marker_hash(m3)
        # select returns the records for the requested hashes, in registration order
        got = st._select_reports([st._marker_hash(m1), st._marker_hash(m3)])
        assert got == [same, other]

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

        from dysonsphere.layers import add_comparisons
        from dysonsphere.theme import theme

        theme(chartWidth=200, chartHeight=200)
        df = pl.DataFrame({"g": ["A"] * 5 + ["B"] * 5, "v": [float(i) for i in range(10)]})
        st._REPORTS.clear()
        add_comparisons(df, "g", "v", [("A", "B")], categories=["A", "B"], pvalues=[0.0])
        rec = next(iter(st._REPORTS.values()))
        assert rec["comparisons"]["pairs"][0]["pvalue"] == sys.float_info.min
        assert "< 2.23e-308" in st._render_report(rec)


# ── add_comparisons omnibus integration ──────────────────────────────────────────
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
        layer = add_comparisons(multi_df, "group", "value", test="anova", categories=MULTI)
        assert "ANOVA" in str(layer.to_dict())

    def test_verbose_label(self, multi_df):
        layer = add_comparisons(multi_df, "group", "value", test="anova", categories=MULTI, omnibusVerbose=True)
        s = str(layer.to_dict())
        assert "F(2, 57)" in s and "η²" in s

    def test_omnibus_position_none_no_label(self, multi_df):
        layer = add_comparisons(multi_df, "group", "value", test="kruskal", categories=MULTI, testLabelPosition=None)
        assert "Kruskal" not in str(layer.to_dict())

    def test_omnibus_with_posthoc_brackets(self, multi_df):
        layer = add_comparisons(multi_df, "group", "value", pairs=[("A", "C")], test="anova", categories=MULTI)
        # corner label + one bracket layer
        assert "ANOVA" in str(layer.to_dict())

    def test_report_includes_all_comparisons_not_just_bracketed(self, multi_df):
        # only A-C is bracketed, but the omnibus report should list all 3 pairs
        st._REPORTS.clear()
        add_comparisons(multi_df, "group", "value", pairs=[("A", "C")], test="anova", categories=MULTI)
        pairs = next(iter(st._REPORTS.values()))["comparisons"]["pairs"]
        listed = {(p["group1"], p["group2"]) for p in pairs}
        assert listed == {("A", "B"), ("A", "C"), ("B", "C")}

    def test_report_all_comparisons_omnibus_only(self, multi_df):
        # no brackets at all, but the report still lists every pairwise post-hoc
        st._REPORTS.clear()
        add_comparisons(multi_df, "group", "value", test="kruskal", categories=MULTI)
        rec = next(iter(st._REPORTS.values()))
        assert rec["comparisons"]["test"] == "dunn"
        assert len(rec["comparisons"]["pairs"]) == 3

    def test_report_queued_as_record(self, multi_df):
        st._REPORTS.clear()
        add_comparisons(multi_df, "group", "value", test="anova", categories=MULTI)
        assert len(st._REPORTS) == 1
        rec = next(iter(st._REPORTS.values()))
        assert rec["kind"] == "omnibus" and rec["omnibus"]["name"] == "ANOVA"
        assert "ANOVA" in st._render_report(rec)

    def test_report_prints(self, multi_df, capsys):
        add_comparisons(multi_df, "group", "value", test="anova", categories=MULTI, report=True)
        assert "Group descriptives:" in capsys.readouterr().out

    def test_save_writes_file(self, multi_df, tmp_path):
        add_comparisons(multi_df, "group", "value", test="anova", categories=MULTI, save=str(tmp_path))
        files = list(tmp_path.glob("dysonsphere_report_*.txt"))
        assert len(files) == 1 and "ANOVA" in files[0].read_text()

    def test_pairwise_requires_pairs(self, multi_df):
        with pytest.raises(ValueError, match="pairs is required"):
            add_comparisons(multi_df, "group", "value", test="mannwhitneyu", categories=MULTI)

    def test_empty_pairs_rejected(self, multi_df):
        with pytest.raises(ValueError, match="must not be empty"):
            add_comparisons(multi_df, "group", "value", pairs=[], test="anova", categories=MULTI)

    def test_default_posthoc_per_omnibus(self, multi_df):
        # kruskal default post-hoc is dunn; just ensure it runs and brackets build
        layer = add_comparisons(multi_df, "group", "value", pairs=[("A", "C")], test="kruskal", categories=MULTI)
        assert isinstance(layer, alt.LayerChart)


# ── Correlation (dysonsphere.statistics + add_correlation) ───────────────────
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
        spec = add_correlation(pl.DataFrame({"x": _CX, "y": _CY}), "x", "y", verbose=True).to_dict()
        name = next(
            lyr["data"]["name"]
            for lyr in spec["layer"]
            if lyr.get("encoding", {}).get("text", {}).get("field") == "__text"
        )
        readout = spec["datasets"][name][0]["__text"]
        assert "r = " in readout and "r² = " in readout and "P " in readout and ", y = " in readout

    def test_invalid_coefficient_raises(self):
        with pytest.raises(ValueError, match="coefficient must be"):
            add_correlation(pl.DataFrame({"x": _CX, "y": _CY}), "x", "y", coefficient="nope")


class TestAddCorrelation:
    @pytest.fixture
    def scatter_df(self):
        rng = np.random.default_rng(0)
        x = rng.uniform(0, 10, 60)
        return pl.DataFrame({"x": x, "y": 0.9 * x + rng.normal(0, 1, 60)})

    def test_pearson_has_line_and_label(self, scatter_df):
        layer = add_correlation(scatter_df, "x", "y")
        assert isinstance(layer, alt.LayerChart)
        assert len(layer.to_dict()["layer"]) == 2  # line + readout

    def test_spearman_no_line(self, scatter_df):
        layer = add_correlation(scatter_df, "x", "y", method="spearman")
        assert len(layer.to_dict()["layer"]) == 1  # readout only, no line

    def test_line_false_suppresses_line(self, scatter_df):
        layer = add_correlation(scatter_df, "x", "y", line=False)
        assert len(layer.to_dict()["layer"]) == 1

    def test_position_none_no_label(self, scatter_df):
        layer = add_correlation(scatter_df, "x", "y", position=None)
        assert len(layer.to_dict()["layer"]) == 1  # line only

    def test_linestyle_overrides_curated(self, scatter_df):
        spec = add_correlation(scatter_df, "x", "y", color="red", lineStyle={"color": "blue"}).to_dict()
        marks = [lyr["mark"] for lyr in spec["layer"] if isinstance(lyr.get("mark"), dict)]
        line_mark = next(m for m in marks if m.get("type") == "line")
        assert line_mark["color"] == "blue"  # lineStyle wins

    def test_record_queued(self, scatter_df):
        st._REPORTS.clear()
        add_correlation(scatter_df, "x", "y")
        assert len(st._REPORTS) == 1 and next(iter(st._REPORTS.values()))["kind"] == "correlation"

    def test_report_prints(self, scatter_df, capsys):
        add_correlation(scatter_df, "x", "y", report=True)
        assert "Correlation | Pearson" in capsys.readouterr().out

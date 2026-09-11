import sys
from typing import Any, cast

import altair as alt
import numpy as np
import polars as pl
import pytest
from scipy import stats as scipy_stats

from dysonsphere import _statistics as st
from dysonsphere.export import save
from dysonsphere.stats import _format_pvalue, comparisons, correlation
from dysonsphere.theme import theme


@pytest.fixture(autouse=True)
def _stats_theme():
    theme(width=200, height=200)


def _df():
    return pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4 + ["C"] * 4, "v": list(range(12)), "unused": [None] * 12})


def test_statistical_validation_ignores_unrelated_missing_columns():
    with pytest.raises(ValueError, match="column 'v'.*missing"):
        comparisons(_df().with_columns(pl.lit(None).alias("v")), "g", "v", [("A", "B")])


def test_missing_group_id_has_grouping_context():
    with pytest.raises(ValueError, match="grouping column 'g'.*missing grouping ID"):
        comparisons(
            _df().with_columns(pl.when(pl.arange(0, 12) == 0).then(None).otherwise(pl.col("g")).alias("g")),
            "g",
            "v",
            [("A", "B")],
        )


@pytest.mark.parametrize("value", [True, "0.1", -0.1, 1.1, float("nan"), float("inf")])
def test_supplied_pvalues_are_finite_non_bool_probabilities(value):
    with pytest.raises(ValueError, match=r"finite numeric value in \[0, 1\]"):
        comparisons(_df(), "g", "v", [("A", "B")], pvalues=[value])


def test_zero_pvalue_has_an_underflow_bound_in_every_notation():
    assert "<" in _format_pvalue(0.0, notation="scientific")
    assert "<" in _format_pvalue(0.0, notation="e")
    assert "<" in _format_pvalue(0.0, notation="power")
    assert "0e" not in _format_pvalue(0.0, notation="e")


def test_zero_pvalue_bound_survives_svg_rendering(tmp_path):
    data = _df().filter(pl.col("g").is_in(["A", "B"]))
    chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + comparisons(
        data, "g", "v", [("A", "B")], pvalues=[0.0], notation="e"
    )
    save(chart, str(tmp_path / "underflow"), format="svg", background=["light"])
    svg = (tmp_path / "underflow.svg").read_text()
    assert "P &lt; 2.23e-308" in svg
    assert "P = 0" not in svg


@pytest.mark.parametrize("pvalue", [0.0, np.nextafter(0.0, 1.0)])
@pytest.mark.parametrize("notation", [None, "scientific", "e", "power"])
@pytest.mark.parametrize("label_style", ["p", "value", "asterisks"])
def test_underflow_and_subnormal_values_work_with_every_label_style(pvalue, notation, label_style):
    data = _df().filter(pl.col("g").is_in(["A", "B"]))
    layer = comparisons(
        data,
        "g",
        "v",
        [("A", "B")],
        pvalues=[pvalue],
        notation=notation,
        labelStyle=label_style,
    )
    assert layer.to_dict()
    if notation == "e" and label_style != "asterisks":
        expected = "2.23e-308" if pvalue == 0.0 else "4.94e-324"
        assert expected in str(layer.to_dict())


@pytest.mark.parametrize("correction", ["bonferroni", "holm", "fdr_bh", "fdr_by"])
@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_invalid_n_comparisons_are_rejected_for_every_correction(correction, value):
    with pytest.raises(ValueError):
        comparisons(_df(), "g", "v", [("A", "B")], correction=correction, nComparisons=value)


@pytest.mark.parametrize("test", ["tukey_hsd", "dunn", "nemenyi", "games_howell"])
def test_direct_matrix_test_identifiers_are_accepted(test):
    comparisons(_df(), "g", "v", [("A", "B")], test=test, pvalues=[0.2])


def test_grouped_post_hoc_is_rejected_instead_of_ignored():
    data = pl.DataFrame({"category": ["A", "A", "B", "B"], "level": ["x", "y"] * 2, "value": [1.0, 2.0, 3.0, 4.0]})
    with pytest.raises(ValueError, match="grouped comparisons do not support postHoc"):
        comparisons(data, "category", "value", xOffset="level", postHoc="dunn")


def test_undefined_pvalues_do_not_enter_correction():
    with pytest.raises(ValueError, match="finite numeric value"):
        st._adjust([float("nan"), 0.05], "holm", 2)
    assert st._adjust([0.0, 1.0], "holm", 2) == [0.0, 1.0]


@pytest.mark.parametrize("correction", ["bonferroni", "holm", "fdr_bh", "fdr_by"])
def test_n_comparisons_widens_computed_families(correction):
    recs_before = len(st._REPORTS)
    comparisons(_df(), "g", "v", [("A", "B"), ("A", "C")], correction=correction, nComparisons=5)
    assert len(st._REPORTS) == recs_before + 1
    raw = [scipy_stats.mannwhitneyu(np.arange(4), np.arange(start, start + 4)).pvalue for start in (4, 8)]
    record = next(iter(st._REPORTS.values()))
    assert [pair["pvalue"] for pair in record["comparisons"]["pairs"]] == pytest.approx(
        _reference_adjust(raw, correction, 5)
    )
    with pytest.raises(ValueError, match="at least the computed family size"):
        comparisons(_df(), "g", "v", [("A", "B"), ("A", "C")], correction=correction, nComparisons=1)


def test_tukey_does_not_require_an_external_family_size():
    comparisons(_df(), "g", "v", [("A", "B")], test="anova", correction="holm", nComparisons=1)


def test_supplied_omnibus_comparisons_are_final_and_requested_only():
    comparisons(_df(), "g", "v", [("A", "C")], test="anova", pvalues=[0.0])
    rec = next(iter(st._REPORTS.values()))
    assert rec["test"] == "anova"
    assert rec["omnibus"]["name"] == "ANOVA"
    assert [(p["group1"], p["group2"]) for p in rec["comparisons"]["pairs"]] == [("A", "C")]
    assert rec["comparisons"]["test"] is None
    assert rec["comparisons"]["correction"] is None
    assert rec["comparisons"]["pairs"][0]["effect"] is None
    assert rec["comparisons"]["pairs"][0]["pvalue"] == sys.float_info.min


def test_supplied_omnibus_still_runs_omnibus_but_skips_post_hoc(monkeypatch):
    calls = []
    original = st._run_omnibus

    def wrapped(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    def unexpected(*args, **kwargs):
        raise AssertionError("supplied comparisons must not calculate post-hoc tests or effects")

    import dysonsphere.stats as annotations

    monkeypatch.setattr(st, "_run_omnibus", wrapped)
    monkeypatch.setattr(st, "_post_hoc_matrix", unexpected)
    monkeypatch.setattr(st, "_pair_effect", unexpected)
    monkeypatch.setattr(annotations, "_bracket_pvalues", unexpected)
    comparisons(_df(), "g", "v", [("A", "C")], test="anova", pvalues=[0.0])
    rec = next(iter(st._REPORTS.values()))
    assert calls == ["anova"]
    assert rec["omnibus"]["name"] == "ANOVA"
    assert [(p["group1"], p["group2"]) for p in rec["comparisons"]["pairs"]] == [("A", "C")]


def test_grouped_supplied_values_skip_pair_effects(monkeypatch):
    df = pl.DataFrame(
        {
            "gene": ["A"] * 6 + ["B"] * 6,
            "cond": ["Veh", "Drug"] * 3 + ["Veh", "Drug"] * 3,
            "v": [1.0, 2.0] * 3 + [3.0, 4.0] * 3,
        }
    )

    def fail(*args, **kwargs):
        raise AssertionError("supplied p-values must not calculate effects")

    monkeypatch.setattr(st, "_pair_effect", fail)
    comparisons(
        df,
        "gene",
        "v",
        xOffset="cond",
        categories=["A", "B"],
        xOffsetSort=["Veh", "Drug"],
        pvalues={("A", ("Veh", "Drug")): 0.0, ("B", ("Veh", "Drug")): 1.0},
    )
    rec = next(iter(st._REPORTS.values()))
    assert rec["comparisons"]["test"] is None
    assert all(pair["effect"] is None for pair in rec["comparisons"]["pairs"])


def test_grouped_options_are_not_dropped():
    df = pl.DataFrame(
        {
            "gene": ["A"] * 6 + ["B"] * 6,
            "cond": ["Veh", "Drug"] * 6,
            "x": np.tile([1.0, 2.0, 3.0], 4),
            "v": np.arange(12),
        }
    )
    layer = comparisons(
        df,
        "gene",
        "v",
        xOffset="cond",
        categories=["A", "B"],
        xOffsetSort=["Veh", "Drug"],
        testLabelPosition="topRight",
        testLabel="group test",
        pvalues={("A", ("Veh", "Drug")): 0.2, ("B", ("Veh", "Drug")): 0.3},
    )
    assert "group test" in str(layer.to_dict())
    corr = correlation(
        df,
        "x",
        "v",
        groupBy="gene",
        label="custom",
        ci=True,
        ciColor="red",
        lineStyle={"color": "blue"},
    )
    spec = corr.to_dict()
    assert any("custom" in str(layer) for layer in spec["layer"])
    leaves = [leaf for group in spec["layer"] for leaf in group.get("layer", [group])]
    assert any(layer.get("mark", {}).get("fill") == "red" for layer in leaves)
    assert any(layer.get("mark", {}).get("color") == "blue" for layer in leaves)


def test_grouped_ci_uses_group_color_when_no_override():
    import vl_convert as vlc

    df = pl.DataFrame(
        {
            "x": [1.0, 2.0, 3.0] * 2,
            "v": [2.0, 4.0, 6.0, 3.0, 5.0, 7.0],
            "g": ["A"] * 3 + ["B"] * 3,
        }
    )
    spec = correlation(df, "x", "v", groupBy="g", ci=True, position=None).to_dict()
    compiled = vlc.vegalite_to_vega(spec)
    fills = []

    def collect(node):
        if isinstance(node, dict):
            update = node.get("encode", {}).get("update", {})
            if isinstance(update, dict) and isinstance(update.get("fill"), dict):
                fills.append(update["fill"])
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(compiled)
    assert any(isinstance(fill, dict) and fill.get("field") == "g" for fill in fills)
    assert {fill.get("value") for fill in fills if isinstance(fill, dict) and "value" in fill} != {None}


@pytest.mark.parametrize("ci", [float("nan"), float("inf"), -0.1, 1.0, "0.95"])
def test_correlation_rejects_invalid_ci_before_single_or_group_dispatch(ci):
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 4.0, 6.0], "g": ["A", "A", "A"]})
    with pytest.raises(ValueError, match="confidence level"):
        correlation(df, "x", "y", ci=ci)
    with pytest.raises(ValueError, match="confidence level"):
        correlation(df, "x", "y", groupBy="g", ci=ci)


def test_correlation_rejects_non_mapping_line_style():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 4.0, 6.0]})
    with pytest.raises(ValueError, match="lineStyle must be a dict"):
        correlation(df, "x", "y", lineStyle=cast(Any, [("color", "red")]))


def test_grouped_unsupported_mapping_and_list_forms_raise():
    df = pl.DataFrame({"g": ["A"] * 4, "c": ["x", "y"] * 2, "v": [1.0, 2.0, 3.0, 4.0]})
    with pytest.raises(ValueError, match="notation mappings"):
        comparisons(df, "g", "v", xOffset="c", notation={("x", "y"): "e"})
    with pytest.raises(ValueError, match="yPositions accepts"):
        comparisons(df, "g", "v", xOffset="c", yPositions=[1.0])


def test_grouped_correlation_validation_has_no_partial_records():
    df = pl.DataFrame(
        {"x": [1.0, 2.0, 3.0, 1.0, 1.0, 1.0], "y": [1.0, 2.0, 3.0, 2.0, 2.0, 2.0], "g": ["ok"] * 3 + ["bad"] * 3}
    )
    with pytest.raises(ValueError):
        correlation(df, "x", "y", groupBy="g")
    assert not st._REPORTS


def test_boolean_numeric_columns_are_valid_correlation_observations():
    df = pl.DataFrame({"x": [False, True, False, True], "y": [False, False, True, True]})
    correlation(df, "x", "y", method="pearson")
    grouped = pl.concat([df, df]).with_columns(pl.Series("g", ["A"] * 4 + ["B"] * 4))
    correlation(grouped, "x", "y", groupBy="g", method="spearman")


def test_grouped_correlation_error_identifies_failing_group():
    df = pl.DataFrame(
        {"x": [1.0, 2.0, 3.0, 1.0, 1.0, 1.0], "y": [1.0, 2.0, 3.0, 2.0, 2.0, 2.0], "g": ["ok"] * 3 + ["bad"] * 3}
    )
    with pytest.raises(ValueError, match="correlation group 'bad'"):
        correlation(df, "x", "y", groupBy="g")


def test_all_hidden_grouped_correlation_records_are_exported(tmp_path):
    df = pl.DataFrame(
        {
            "x": [1.0, 2.0, 3.0] * 2,
            "v": [2.0, 4.0, 6.0, 3.0, 5.0, 7.0],
            "g": ["A"] * 3 + ["B"] * 3,
        }
    )
    base = alt.Chart(df).mark_point().encode(x="x:Q", y="v:Q")
    chart = base + correlation(df, "x", "v", groupBy="g", line=False, position=None)
    save(chart, str(tmp_path / "hidden"), format="json", background=["light"])
    import json

    metadata = json.loads((tmp_path / "hidden.json").read_text())["usermeta"]["dysonsphere"]
    assert len(metadata["statistics"]) == 2


def test_rank_correlation_keeps_line_default_inactive():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 1.0, 3.0]})
    correlation(df, "x", "y", method="spearman", line=True)


@pytest.mark.parametrize("column", ["x", "y"])
@pytest.mark.parametrize("grouped", [False, True])
def test_correlation_validates_both_coordinate_columns(column, grouped):
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 1.0, 3.0], "g": ["a"] * 3})
    df = df.with_columns(pl.col(column).cast(pl.String))
    with pytest.raises(ValueError, match=f"column '{column}'.*non-numeric"):
        correlation(df, "x", "y", groupBy="g" if grouped else None)
    assert not st._REPORTS


def test_empty_statistical_data_rejected_before_dispatch():
    df = pl.DataFrame(schema={"g": pl.String, "x": pl.Float64, "y": pl.Float64})
    for grouped in (False, True):
        with pytest.raises(ValueError, match="no observations"):
            correlation(df, "x", "y", groupBy="g" if grouped else None)
    with pytest.raises(ValueError, match="no observations"):
        comparisons(df, "g", "y", [("a", "b")])
    assert not st._REPORTS


def test_single_correlation_band_follows_effective_line_color():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 1.0, 3.0, 5.0]})
    layer = correlation(df, "x", "y", ci=True, color="red", lineStyle={"color": "blue"})
    spec = layer.to_dict()
    band = next(part for part in spec["layer"] if part["mark"]["type"] == "area")
    assert band["mark"]["fill"] == "blue"


def _reference_adjust(values, correction, family_size):
    if correction == "bonferroni":
        return [min(value * family_size, 1.0) for value in values]
    if correction == "holm":
        order = np.argsort(values)
        candidates = [min(values[index] * (family_size - rank), 1.0) for rank, index in enumerate(order)]
        result = np.empty(len(values))
        result[order] = np.maximum.accumulate(candidates)
        return result.tolist()
    extended = [*values, *([1.0] * (family_size - len(values)))]
    return scipy_stats.false_discovery_control(extended, method=correction.removeprefix("fdr_"))[: len(values)]


@pytest.mark.parametrize("correction", ["bonferroni", "holm", "fdr_bh", "fdr_by"])
def test_matrix_family_covers_unplotted_pairs(correction):
    raw_matrix = st._dunn_matrix([np.arange(start, start + 4) for start in (0, 4, 8)])
    raw = [raw_matrix[0, 1], raw_matrix[0, 2], raw_matrix[1, 2]]
    comparisons(_df(), "g", "v", [("A", "C")], test="kruskal", correction=correction, nComparisons=5)
    record = next(iter(st._REPORTS.values()))
    pairs = record["comparisons"]["pairs"]
    assert len(pairs) == 3
    assert [pair["pvalue"] for pair in pairs] == pytest.approx(_reference_adjust(raw, correction, 5))
    with pytest.raises(ValueError, match="computed family size"):
        comparisons(_df(), "g", "v", [("A", "C")], test="kruskal", correction=correction, nComparisons=2)


@pytest.mark.parametrize("test", ["dunn", "games_howell"])
def test_undefined_post_hoc_errors_are_public_value_errors(test):
    data = _df().with_columns(pl.lit(1.0).alias("v"))
    with pytest.raises(ValueError, match=test):
        comparisons(data, "g", "v", [("A", "B")], test=test)
    assert not st._REPORTS

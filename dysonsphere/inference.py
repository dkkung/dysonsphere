"""Statistical inference annotations - significance brackets, omnibus labels, correlation readouts.

The annotation wrappers for what ``statistics.py`` computes: ``add_comparisons`` (pairwise
brackets and omnibus test labels) and ``add_correlation`` (coefficient readout + OLS fit line).
Pure computation stays in ``statistics.py`` (no Altair there); this module builds the Vega-Lite
layers that present it. Statistical results are registered in the ``statistics._REPORTS``
registry and embedded into exports by ``save()`` via layer-name markers.
"""

import math
from typing import Any, cast

import altair as alt
import polars as pl

from .annotations import add_text
from .theme import _opt
from .utils import _empty_layer, _internal_data, _resolve_dash, band_geometry

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["add_comparisons", "add_correlation"]

# P-value annotations

_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def _superscript(n: int) -> str:
    sign = "⁻" if n < 0 else ""
    return sign + "".join(_SUP[int(d)] for d in str(abs(n)))


def _format_pvalue(p: float, sigFigs: int = 3, notation: str | None = None) -> str:
    # `sigFigs` sets the significant-figure precision; `%g` gives that and strips trailing
    # zeros. Plain notation floors at a fixed 0.001 convention (`P < 0.001`); scientific/e/
    # power never floor (they represent any magnitude at `sigFigs` figures).
    if notation is None:
        if p < 0.001:
            return "P < 0.001"
        return f"P = {p:.{sigFigs}g}"
    if notation == "power":
        exp = round(math.log10(p))
        return f"P ≈ 10{_superscript(exp)}"
    # scientific / e share the mantissa (at `sigFigs` sig figs) and exponent.
    exp = math.floor(math.log10(p))
    mantissa = f"{p / 10**exp:.{sigFigs}g}"
    if notation == "scientific":
        return f"P = {mantissa}×10{_superscript(exp)}"
    if notation == "e":
        return f"P = {mantissa}e{exp:+03d}"
    raise ValueError(f"notation must be 'power', 'scientific', or 'e', got {notation!r}")


def _format_asterisks(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


# --- shared resolvers for add_comparisons / _add_grouped_comparisons ---------------------------
# Extracted so the single-factor and grouped paths share one implementation (they had drifted -
# see the y-spacing chart_height guard). Pure functions; error messages are load-bearing (pinned
# by `match=` tests in test_statistics.py) - keep them verbatim.


def _resolve_method(test: str, post_hoc: str | None, pvalues: list[float] | None, is_omnibus: bool) -> str | None:
    """The comparison method: a post-hoc for omnibus, the test itself for pairwise, None for
    user-supplied p-values. Also the record's ``comparison_test`` (a pure alias)."""
    from .statistics import _POSTHOC_DEFAULTS

    if pvalues is not None:
        return None
    if is_omnibus:
        return post_hoc if post_hoc is not None else _POSTHOC_DEFAULTS[test]
    return test


def _resolve_notation(
    notation: str | dict[Any, Any] | None, pairs: list[tuple[str, str]] | None
) -> tuple[str | None, list[str | None]]:
    """Return ``(test_notation, pair_notations)``. A scalar applies everywhere; a dict is per-pair
    (order-insensitive keys, unlisted → plain None) plus an optional ``"test"`` key for the
    omnibus/test label."""
    if isinstance(notation, dict):
        valid = {None, "scientific", "e", "power"}
        bad_vals = [v for v in notation.values() if v not in valid]
        if bad_vals:
            raise ValueError(f"notation dict values must be None/'scientific'/'e'/'power', got {bad_vals}")
        bad_keys = [k for k in notation if isinstance(k, str) and k != "test"]
        if bad_keys:
            raise ValueError(f"notation dict string keys must be 'test', got {sorted(bad_keys)}")
        pair_map = {frozenset(k): v for k, v in notation.items() if not isinstance(k, str)}
        return notation.get("test"), [pair_map.get(frozenset(p)) for p in (pairs or [])]
    return notation, [notation] * len(pairs or [])


def _resolve_bracket_styles(bracket_style: str | dict[Any, Any], pairs: list[tuple[str, str]]) -> list[str]:
    """Per-pair bracket style: a string applies to all; a dict maps a pair (order-insensitive) to
    its style, with ``"bracket"`` as the fallback for unlisted pairs."""
    valid = {"line", "bracket"}
    if isinstance(bracket_style, dict):
        bad = set(bracket_style.values()) - valid
        if bad:
            raise ValueError(f"bracketStyle dict values must be 'line' or 'bracket', got {sorted(bad)}")
        style_map = {frozenset(k): v for k, v in bracket_style.items()}
        return [style_map.get(frozenset(p), "bracket") for p in pairs]
    if bracket_style not in valid:
        raise ValueError(f"bracketStyle must be 'line', 'bracket', or a dict, got {bracket_style!r}")
    return [bracket_style] * len(pairs)


def _check_coverage(
    df: pl.DataFrame, col: str, values: list[Any] | None, param_name: str, noun: str, tail: str
) -> None:
    """Raise if an explicit ordering ``values`` for ``param_name`` omits any value present in
    ``df[col]`` - a guaranteed mis-position of the band geometry / shared-scale reorder. No-op
    when ``values`` is None (the caller supplies its own default order). ``noun``/``tail`` carry
    the exact per-param message wording."""
    if values is None:
        return
    missing = set(df[col].unique().to_list()) - set(values)
    if missing:
        raise ValueError(f"{param_name} is missing {col!r} {noun} present in the data: {sorted(missing)}. {tail}")


def _stack_levels(spans: list[tuple[int, int]]) -> list[int]:
    """Assign a stacking level to each ``(lo, hi)`` index span via greedy interval scheduling:
    shorter spans first (so narrow brackets sit lower), each placed on the lowest level whose
    occupants it doesn't overlap. Returns the level per span, in input order."""
    order = sorted(range(len(spans)), key=lambda i: abs(spans[i][1] - spans[i][0]))
    levels: list[list[tuple[int, int]]] = []
    result = [0] * len(spans)
    for i in order:
        lo, hi = min(spans[i]), max(spans[i])
        for level_idx, occupied in enumerate(levels):
            if not any(not (hi < occ_lo or lo > occ_hi) for occ_lo, occ_hi in occupied):
                occupied.append((lo, hi))
                result[i] = level_idx
                break
        else:
            levels.append([(lo, hi)])
            result[i] = len(levels) - 1
    return result


def _resolve_y_spacing(
    any_bracket: bool,
    y_range: float,
    chart_height: float,
    y_pad: float | None,
    tick_height: float | None,
    y_step: float | None,
) -> tuple[float, float, float]:
    """Resolve the auto ``(y_pad, tick_height, y_step)`` for bracket stacking, each only when
    None. The gap targets ~10 px for brackets / ~8 px for lines and the tick height matches the
    theme ``tickSize``, both converted from px to data units via ``chart_height``; ``y_step`` is
    ``1.75 * y_pad``. All three guard ``chart_height == 0``."""
    if y_pad is None:
        y_pad = (10.0 if any_bracket else 8.0) * y_range / chart_height if chart_height else 0.0
    if tick_height is None:
        tick_height = _opt("tickSize") * y_range / chart_height if chart_height else 0.0
    if y_step is None:
        y_step = y_pad * 1.75
    return y_pad, tick_height, y_step


def _emit_report(record: dict[str, Any], report: bool, save: bool | str) -> str:
    """Register ``record`` for the export metadata and, if requested, print the rendered report
    and/or write it to a timestamped ``.txt``. Returns the marker name tagged onto the layer."""
    from datetime import datetime
    from pathlib import Path

    from .statistics import _register_report, _render_report

    marker = _register_report(record)
    if report or save:
        report_text = _render_report(record)
        if report:
            print(report_text)
        if save:
            directory = Path(save) if isinstance(save, str) else Path.cwd()
            directory.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            (directory / f"dysonsphere_report_{ts}.txt").write_text(report_text + "\n", encoding="utf-8")
    return marker


def _pvalue_layer(
    df: pl.DataFrame | None = None,
    x_col: str | None = None,
    y_col: str | None = None,
    group1: str | None = None,
    group2: str | None = None,
    *,
    test: str = "mannwhitneyu",
    pvalue: float | None = None,
    correction: str | None = None,
    n_comparisons: int = 1,
    y: float | None = None,
    y_pad: float = 5,
    tick_height: float = 0.5,
    bracket_style: str = "bracket",
    label_style: str = "p",
    categories: list[Any] | None = None,
    chartWidth: int | None = None,
    strokeWidth: float | None = None,
    fontSize: int | None = None,
    reverse: bool = False,
    sigFigs: int = 3,
    notation: str | None = None,
) -> alt.LayerChart:
    from scipy import stats as _stats

    # --- p-value ---
    if pvalue is None:
        if df is None or x_col is None or y_col is None:
            raise ValueError("df, x_col, and y_col are required when pvalue is not provided.")

        if test == "tukey_hsd":
            _cats = categories if categories is not None else sorted(df[x_col].unique().to_list())
            all_groups = [df.filter(pl.col(x_col) == cat)[y_col].to_numpy() for cat in _cats]
            result = _stats.tukey_hsd(*all_groups)
            pvalue = float(result.pvalue[_cats.index(group1)][_cats.index(group2)])
        else:
            a = df.filter(pl.col(x_col) == group1)[y_col].to_numpy()
            b = df.filter(pl.col(x_col) == group2)[y_col].to_numpy()
            _tests = {
                "mannwhitneyu": lambda: _stats.mannwhitneyu(a, b, alternative="two-sided").pvalue,
                "ttest_ind": lambda: _stats.ttest_ind(a, b).pvalue,
                "ttest_rel": lambda: _stats.ttest_rel(a, b).pvalue,
                "wilcoxon": lambda: _stats.wilcoxon(a, b).pvalue,
            }
            if test not in _tests:
                raise ValueError(f"Unknown test {test!r}. Choose from: {['tukey_hsd'] + list(_tests)}")
            pvalue = _tests[test]()

    # bonferroni correction (skip for tukey_hsd — correction is built in)
    if correction == "bonferroni" and test != "tukey_hsd":
        pvalue = min(pvalue * n_comparisons, 1.0)

    label = (
        _format_asterisks(pvalue)
        if label_style == "asterisks"
        else _format_pvalue(pvalue, sigFigs=sigFigs, notation=notation)
    )

    # --- y position ---
    if y is None:
        if df is None or x_col is None or y_col is None:
            raise ValueError("y is required when df, x_col, and y_col are not provided.")
        y = (
            cast(
                float,
                df.filter(pl.col(x_col).is_in([group1, group2]))[y_col].cast(pl.Float64).max() or 0.0,
            )
            + y_pad
        )

    # --- resolve theme-linked defaults ---
    if chartWidth is None:
        chartWidth = _opt("chartWidth")
    if strokeWidth is None:
        strokeWidth = _opt("axisWidth")
    if fontSize is None:
        fontSize = _opt("fontSize")

    # --- categories and text x position ---
    if categories is None:
        if df is None or x_col is None:
            raise ValueError("categories is required when df and x_col are not provided.")
        categories = sorted(df[x_col].unique().to_list())

    g1_idx = categories.index(group1)
    g2_idx = categories.index(group2)

    stroke_cap = _opt("strokeCap")
    _rule_kwargs = {
        "strokeWidth": strokeWidth,
        "strokeDash": [0, 0],
        "strokeCap": stroke_cap,
    }

    # dy offsets in SVG pixels. Asterisk glyphs sit close to the baseline so a small
    # offset seats them flush; alphanumeric labels (including "ns") need more clearance.
    # reverse=False keeps the inherited default baseline (its spacing already looks right).
    # reverse=True sets baseline="top" so the text hangs *below* the bar instead of
    # overlapping it — the inherited baseline left the below-bar text cramped.
    _dy_mag = 2 if label_style == "asterisks" and label != "ns" else 4
    text_dy = _dy_mag if reverse else -_dy_mag
    text_baseline = "top" if reverse else None
    tick_y2 = y + tick_height if reverse else y - tick_height

    bar = (
        alt.Chart(_internal_data([{"x": group1, "x2": group2, "y": y}]))
        .mark_rule(**_rule_kwargs)
        .encode(
            x=alt.X("x:N"),
            x2="x2:N",
            y=alt.Y("y:Q"),
        )
    )

    # Bracket label sits midway between the two bands' centres (xOffset charts lower to
    # the offset band-scale variant - see utils.band_geometry).
    geo = band_geometry(len(categories), chartWidth)
    x_mid_px = (geo.centers[g1_idx] + geo.centers[g2_idx]) / 2
    text = (
        alt.Chart(_internal_data([{"y": y, "label": label}]))
        .mark_text(
            align="center", fontSize=fontSize, dy=text_dy, **({"baseline": text_baseline} if text_baseline else {})
        )
        .encode(
            x=alt.value(x_mid_px),
            y=alt.Y("y:Q"),
            text="label:N",
        )
    )

    if bracket_style == "bracket":
        left_tick = (
            alt.Chart(_internal_data([{"x": group1, "y": y, "y2": tick_y2}]))
            .mark_rule(**_rule_kwargs)
            .encode(
                x=alt.X("x:N"),
                y=alt.Y("y:Q"),
                y2="y2:Q",
            )
        )
        right_tick = (
            alt.Chart(_internal_data([{"x": group2, "y": y, "y2": tick_y2}]))
            .mark_rule(**_rule_kwargs)
            .encode(
                x=alt.X("x:N"),
                y=alt.Y("y:Q"),
                y2="y2:Q",
            )
        )
        return cast(alt.LayerChart, alt.layer(bar, left_tick, right_tick, text))

    return cast(alt.LayerChart, alt.layer(bar, text))


def _reference_label_layer(
    group: Any,
    y: float,
    label: str,
    *,
    categories: list[Any],
    chartWidth: int,
    fontSize: int,
) -> alt.Chart:
    """A bare p-value label centred over one group's band, at data-coordinate ``y`` - the
    reference-mode annotation (no bracket; the comparison to the reference is implicit)."""
    x_px = band_geometry(len(categories), chartWidth).centers[categories.index(group)]
    return (
        alt.Chart(_internal_data([{"y": y, "label": label}]))
        .mark_text(align="center", baseline="bottom", fontSize=fontSize, dy=-4)
        .encode(x=alt.value(x_px), y=alt.Y("y:Q"), text="label:N")
    )


_MATRIX_POSTHOCS = {"tukey_hsd", "dunn", "nemenyi", "games_howell"}


def _omnibus_label(result, *, verbose: bool, notation: str | None, sigFigs: int) -> str:
    """Build the terse or verbose corner-label string from an omnibus result.

    Always uses the p-value format (never asterisks) — ``labelStyle="asterisks"``
    only applies to the pairwise brackets; an omnibus *result* readout like
    ``Kruskal-Wallis ***`` reads oddly.
    """
    p_str = _format_pvalue(result.pvalue, sigFigs=sigFigs, notation=notation)
    if not verbose:
        return f"{result.name} {p_str}"
    df_str = ", ".join(str(d) for d in result.df)
    stat = f"{result.statSymbol}({df_str}) = {result.stat:.2f}"
    eff = f"{result.effectName} = {result.effectSize:.2f}"
    return f"{result.name} {stat}, {p_str}, {eff}"


def _bracket_pvalues(
    method: str,
    groups: list[Any],
    categories: list[Any],
    pairs: list[tuple[str, str]],
    correction: str | None,
    nComparisons: int | None,
) -> list[float]:
    """Resolve bracket p-values for ``pairs`` via a matrix post-hoc or a pairwise test."""
    from scipy import stats as _stats

    from .statistics import _PAIRWISE_TESTS, _adjust, _post_hoc_matrix

    idx = {c: i for i, c in enumerate(categories)}
    if method in _MATRIX_POSTHOCS:
        mat = _post_hoc_matrix(method, groups, correction)
        return [float(mat[idx[g1]][idx[g2]]) for g1, g2 in pairs]
    if method in _PAIRWISE_TESTS:
        funcs = {
            "mannwhitneyu": lambda a, b: _stats.mannwhitneyu(a, b, alternative="two-sided").pvalue,
            "ttest_ind": lambda a, b: _stats.ttest_ind(a, b).pvalue,
            "ttest_rel": lambda a, b: _stats.ttest_rel(a, b).pvalue,
            "wilcoxon": lambda a, b: _stats.wilcoxon(a, b).pvalue,
        }
        raw = [float(funcs[method](groups[idx[g1]], groups[idx[g2]])) for g1, g2 in pairs]
        if correction is not None:
            m = nComparisons if nComparisons is not None else len(pairs)
            raw = _adjust(raw, correction, m)
        return raw
    raise ValueError(f"Unknown test/postHoc {method!r}. Choose from: {sorted(_MATRIX_POSTHOCS | _PAIRWISE_TESTS)}")


def _grouped_bracket_layer(
    x_col: str,
    xoffset_col: str,
    category: Any,
    level1: str,
    level2: str,
    y: float,
    *,
    tick_height: float,
    label: str,
    bracket_style: str,
    label_style: str,
    categories: list[Any],
    level_order: list[str],
    strokeWidth: float,
    fontSize: int,
) -> alt.LayerChart:
    """One within-category bracket for grouped comparisons.

    The top bar spans the two xOffset sub-bars via the SHARED xOffset scale (``sort`` matched to the
    bars so they keep their order), the optional end-ticks drop from it, and the label centres on the
    band. Everything is encoded (no pixel math), so the bracket tracks wherever Vega lays the grouped
    bars out. The label sits at the band centre - exact for two levels / symmetric pairs, slightly off
    the true midpoint only for an asymmetric 3+-level pair (the bar and ticks stay exact).
    """
    rk = {"strokeWidth": strokeWidth, "strokeDash": [0, 0], "strokeCap": _opt("strokeCap")}
    xenc = alt.X(f"{x_col}:N", sort=categories)
    xoff = alt.XOffset(f"{xoffset_col}:N", sort=level_order)

    top = (
        alt.Chart(
            _internal_data(
                [{x_col: category, xoffset_col: level1, "__y": y}, {x_col: category, xoffset_col: level2, "__y": y}]
            )
        )
        .mark_line(**rk)
        .encode(x=xenc, xOffset=xoff, y=alt.Y("__y:Q"))
    )
    # Asterisk glyphs sit close to the baseline; alphanumeric labels ("ns", "P = …") need more.
    dy = -(2 if label_style == "asterisks" and label != "ns" else 4)
    text = (
        alt.Chart(_internal_data([{x_col: category, "__y": y, "__label": label}]))
        .mark_text(align="center", fontSize=fontSize, dy=dy)
        .encode(x=alt.X(f"{x_col}:N", sort=categories), y=alt.Y("__y:Q"), text="__label:N")
    )
    if bracket_style == "bracket":
        ticks = (
            alt.Chart(
                _internal_data(
                    [
                        {x_col: category, xoffset_col: level1, "__y": y, "__y2": y - tick_height},
                        {x_col: category, xoffset_col: level2, "__y": y, "__y2": y - tick_height},
                    ]
                )
            )
            .mark_rule(**rk)
            .encode(x=xenc, xOffset=xoff, y=alt.Y("__y:Q"), y2="__y2:Q")
        )
        return cast(alt.LayerChart, alt.layer(top, ticks, text))
    return cast(alt.LayerChart, alt.layer(top, text))


def _grouped_reference_label_layer(
    x_col: str,
    xoffset_col: str,
    category: Any,
    level: str,
    y: float,
    *,
    label: str,
    label_style: str,
    categories: list[Any],
    level_order: list[str],
    fontSize: int,
) -> alt.Chart:
    """A bare p-value label centred over one (category, level) sub-bar - the grouped reference-mode
    annotation (no bracket). Rides the SHARED x + xOffset scales (sort matched to the bars) so it
    lands on that sub-bar wherever Vega lays the grouped bars out."""
    dy = -(2 if label_style == "asterisks" and label != "ns" else 4)
    return (
        alt.Chart(_internal_data([{x_col: category, xoffset_col: level, "__y": y, "__label": label}]))
        .mark_text(align="center", baseline="bottom", fontSize=fontSize, dy=dy)
        .encode(
            x=alt.X(f"{x_col}:N", sort=categories),
            xOffset=alt.XOffset(f"{xoffset_col}:N", sort=level_order),
            y=alt.Y("__y:Q"),
            text="__label:N",
        )
    )


def _grouped_key(cat: Any, l1: str, l2: str, is_reference: bool) -> Any:
    """Internal lookup key for one grouped comparison. Reference mode keys by ``(category, level)``
    (the non-reference level uniquely identifies it); bracket mode by ``(category, frozenset(pair))``
    (order-insensitive, like single-factor pair matching)."""
    return (cat, l2) if is_reference else (cat, frozenset((l1, l2)))


def _grouped_desc(cat: Any, l1: str, l2: str, is_reference: bool) -> str:
    """Human-readable descriptor of a grouped comparison, for error messages."""
    return f"({cat!r}, {l2!r})" if is_reference else f"({cat!r}, ({l1!r}, {l2!r}))"


def _normalize_grouped_map(mapping: Any, is_reference: bool, name: str) -> dict[Any, Any]:
    """Normalise a user ``{(category, level|pair): value}`` dict to the internal ``_grouped_key``
    scheme. Reference keys are ``(category, level)``; bracket keys ``(category, (l1, l2))``."""
    if not isinstance(mapping, dict):
        shape = "(category, level)" if is_reference else "(category, (level1, level2))"
        raise ValueError(f"grouped {name} must be a dict keyed by {shape}, got {type(mapping).__name__}.")
    out: dict[Any, Any] = {}
    for key, val in mapping.items():
        try:
            cat, second = key
        except (TypeError, ValueError):
            raise ValueError(f"grouped {name} keys must be (category, level|pair) tuples, got {key!r}.") from None
        out[(cat, second) if is_reference else (cat, frozenset(second))] = val
    return out


def _add_grouped_comparisons(
    df: pl.DataFrame,
    x_col: str,
    y_col: str,
    xoffset_col: str,
    pairs: list[tuple[str, str]] | None,
    *,
    reference: Any,
    pvalues: Any,
    yStart: float | dict[Any, Any] | None,
    yPositions: Any,
    xOffsetSort: list[str] | None,
    test: str,
    correction: str | None,
    nComparisons: int | None,
    labelStyle: str,
    bracketStyle: Any,
    notation: Any,
    sigFigs: int | None,
    tickHeight: float | None,
    strokeWidth: float | None,
    fontSize: int | None,
    yPad: float | None,
    yStep: float | None,
    categories: list[Any] | None,
    chartWidth: int | None,
    report: bool,
    save: bool | str,
) -> alt.LayerChart:
    """Grouped (two-factor) comparisons: compare the xOffset levels within each x-category.

    One bracket per (category, pair), each placed above its OWN category's bars (per-category, so
    groups of wildly different magnitude don't push short brackets sky-high), carrying a real
    per-category p-value from ``test`` (corrected over the whole family by ``correction``). A single
    record is registered, its comparisons labelled ``"<category> (<level>)"``.
    """
    from scipy import stats as _stats

    from .statistics import _adjust, _describe_all, _make_record, _pair_effect
    from .utils import frame_checksum

    # Guard the sort footgun: `categories`/`xOffsetSort` must match the chart's x/xOffset sort or the
    # shared scale silently reorders the bars. We can't see the chart to check the *order*, but an
    # explicit list that doesn't even COVER the data's values (a typo or omission) is a guaranteed
    # mismatch - catch it with a clear error instead of a mysterious reorder.
    _check_coverage(
        df,
        x_col,
        categories,
        "categories",
        "values",
        "It must list every x-category, in the same order as your chart's x sort.",
    )
    if categories is None:
        categories = sorted(df[x_col].unique().to_list())
    _check_coverage(
        df,
        xoffset_col,
        xOffsetSort,
        "xOffsetSort",
        "levels",
        "It must list every xOffset level, in the same order as your chart's xOffset sort.",
    )
    level_order = (
        list(xOffsetSort) if xOffsetSort is not None else df[xoffset_col].unique(maintain_order=True).to_list()
    )

    # Reference mode: compare every other level against `reference` WITHIN each category, drawing the
    # p-value above each non-reference sub-bar (no bracket). Derives its own level-pairs.
    is_reference = reference is not None
    if is_reference:
        if reference not in level_order:
            raise ValueError(f"reference {reference!r} is not a level of xOffsetCol {xoffset_col!r}: {level_order}.")
        if pairs is not None:
            raise ValueError("reference derives its own comparisons; don't also pass pairs.")
        pairs = [(reference, lvl) for lvl in level_order if lvl != reference]

    if pairs is None:
        if len(level_order) == 2:
            pairs = [(level_order[0], level_order[1])]
        else:
            raise ValueError(
                f"pairs is required when xOffsetCol has more than two levels (levels: {level_order}); "
                "pass e.g. pairs=[('Ctrl', 'Low'), ('Ctrl', 'High')]."
            )
    if len(pairs) == 0:
        raise ValueError("pairs must not be empty when provided.")
    _lvls = set(level_order)
    for l1, l2 in pairs:
        if l1 not in _lvls or l2 not in _lvls:
            raise ValueError(f"pair ({l1!r}, {l2!r}) names a level not in xOffsetCol {xoffset_col!r} {level_order}.")

    _valid_tests = {"mannwhitneyu", "ttest_ind", "ttest_rel", "wilcoxon"}
    if test not in _valid_tests:
        raise ValueError(f"grouped comparisons (xOffsetCol) support {sorted(_valid_tests)}, got {test!r}.")
    if labelStyle not in ("p", "asterisks"):
        raise ValueError(f"labelStyle must be 'p' or 'asterisks', got {labelStyle!r}.")
    if not isinstance(bracketStyle, str) or bracketStyle not in ("bracket", "line"):
        raise ValueError(f"grouped comparisons take bracketStyle 'bracket' or 'line', got {bracketStyle!r}.")
    notation_val = notation if not isinstance(notation, dict) else None

    chartWidth = chartWidth if chartWidth is not None else _opt("chartWidth")
    chart_height = _opt("chartHeight")
    fontSize = fontSize if fontSize is not None else _opt("fontSize")
    strokeWidth = strokeWidth if strokeWidth is not None else _opt("axisWidth")
    effective_sigfigs = sigFigs if sigFigs is not None else _opt("sigFigs")

    y_all = df[y_col].cast(pl.Float64)
    y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
    yPad, tickHeight, yStep = _resolve_y_spacing(
        bracketStyle == "bracket", y_range, chart_height, yPad, tickHeight, yStep
    )

    parametric = test in ("ttest_ind", "ttest_rel")
    paired = test == "ttest_rel"

    def _pval(a, b) -> float:
        funcs = {
            "mannwhitneyu": lambda: _stats.mannwhitneyu(a, b, alternative="two-sided").pvalue,
            "ttest_ind": lambda: _stats.ttest_ind(a, b).pvalue,
            "ttest_rel": lambda: _stats.ttest_rel(a, b).pvalue,
            "wilcoxon": lambda: _stats.wilcoxon(a, b).pvalue,
        }
        return float(funcs[test]())

    # All comparison keys, in the category-major then pair order the loops use.
    all_keys = [_grouped_key(cat, l1, l2, is_reference) for cat in categories for l1, l2 in pairs]

    # Explicit p-values (a dict keyed by (category, level|pair)) skip the test AND correction, like
    # the single-factor `pvalues` list. Must cover every comparison exactly (no missing, no extra).
    pval_map = _normalize_grouped_map(pvalues, is_reference, "pvalues") if pvalues is not None else None
    if pval_map is not None:
        missing = [
            _grouped_desc(cat, l1, l2, is_reference)
            for cat in categories
            for l1, l2 in pairs
            if _grouped_key(cat, l1, l2, is_reference) not in pval_map
        ]
        if missing:
            raise ValueError(f"pvalues is missing an entry for: {missing}.")
        extra = set(pval_map) - set(all_keys)
        if extra:
            raise ValueError(f"pvalues has {len(extra)} entr(y/ies) not matching any comparison (check keys).")

    # p-values + effects, iterated category-major then pair (the layer loop matches this order).
    raw: list[float] = []
    effects: list[tuple[str | None, float]] = []
    for cat in categories:
        cdf = df.filter(pl.col(x_col) == cat)
        for l1, l2 in pairs:
            a = cdf.filter(pl.col(xoffset_col) == l1)[y_col].to_numpy()
            b = cdf.filter(pl.col(xoffset_col) == l2)[y_col].to_numpy()
            raw.append(_pval(a, b) if pval_map is None else float(pval_map[_grouped_key(cat, l1, l2, is_reference)]))
            effects.append(_pair_effect(a, b, parametric=parametric, paired=paired))
    m = nComparisons if nComparisons is not None else len(raw)
    # User-provided p-values are not corrected by us (they're final); computed ones honour `correction`.
    effective_correction = None if pval_map is not None else correction
    adj = raw if pval_map is not None else (_adjust(raw, correction, m) if correction else raw)

    # Stacking level per pair (identical for every category - same spans): shorter spans sit lower.
    lvl_idx = {lv: i for i, lv in enumerate(level_order)}
    pair_level = _stack_levels([(lvl_idx[l1], lvl_idx[l2]) for l1, l2 in pairs])

    # descriptives over every (category, level) subset
    desc_groups: list[Any] = []
    desc_labels: list[str] = []
    for cat in categories:
        cdf = df.filter(pl.col(x_col) == cat)
        for lv in level_order:
            desc_groups.append(cdf.filter(pl.col(xoffset_col) == lv)[y_col].to_numpy())
            desc_labels.append(f"{cat} ({lv})")
    descriptives = _describe_all(desc_groups, desc_labels)

    # Explicit y control. `yStart` (brackets only) mirrors single-factor: the EXACT stack base -
    # a scalar for all categories, or a dict for a per-category base (partial - unlisted → auto).
    # It does NOT apply to reference mode (no stack); passing it there raises. `yPositions` is the
    # exact per-comparison y (partial). Precedence: yPositions[key] > (yStart base OR auto base).
    ypos_map = _normalize_grouped_map(yPositions, is_reference, "yPositions") if yPositions is not None else None
    if ypos_map is not None:
        unknown = set(ypos_map) - set(all_keys)
        if unknown:
            raise ValueError(f"yPositions has {len(unknown)} entr(y/ies) not matching any comparison (check keys).")
    if yStart is not None:
        if is_reference:
            raise ValueError(
                "yStart does not apply in reference mode; each label sits above its own mark. "
                "Use yPositions for explicit label heights."
            )
        if isinstance(yStart, dict):
            unknown_cats = set(yStart) - set(categories)
            if unknown_cats:
                raise ValueError(f"yStart has categor(y/ies) not in the data: {sorted(unknown_cats)}.")

    def _cat_base(cat: Any, auto_base: float) -> float:
        """The explicit bracket-stack base for a category (dict entry / scalar), or the auto base."""
        if isinstance(yStart, dict):
            return float(yStart[cat]) if cat in yStart else auto_base
        return float(yStart) if yStart is not None else auto_base

    layers: list[Any] = []
    comparisons: list[dict[str, Any]] = []
    k = 0
    for cat in categories:
        cdf = df.filter(pl.col(x_col) == cat)
        cat_max = cast(float, cdf[y_col].cast(pl.Float64).max() or 0.0)
        bracket_base = _cat_base(cat, cat_max + yPad)  # brackets only; reference ignores yStart
        for pi, (l1, l2) in enumerate(pairs):
            p = adj[k]
            en, ev = effects[k]
            k += 1
            key = _grouped_key(cat, l1, l2, is_reference)
            label = (
                _format_asterisks(p)
                if labelStyle == "asterisks"
                else _format_pvalue(p, sigFigs=effective_sigfigs, notation=notation_val)
            )
            if is_reference:
                # yPositions (exact) > the non-reference sub-bar's own data max + yPad.
                if ypos_map is not None and key in ypos_map:
                    y = float(ypos_map[key])
                else:
                    sub_max = cast(float, cdf.filter(pl.col(xoffset_col) == l2)[y_col].cast(pl.Float64).max() or 0.0)
                    y = sub_max + yPad
                layers.append(
                    _grouped_reference_label_layer(
                        x_col,
                        xoffset_col,
                        cat,
                        l2,
                        y,
                        label=label,
                        label_style=labelStyle,
                        categories=categories,
                        level_order=level_order,
                        fontSize=fontSize,
                    )
                )
            else:
                # yPositions (exact) > (yStart base OR category max + yPad), then stack by yStep.
                if ypos_map is not None and key in ypos_map:
                    y = float(ypos_map[key])
                else:
                    y = bracket_base + pair_level[pi] * yStep
                layers.append(
                    _grouped_bracket_layer(
                        x_col,
                        xoffset_col,
                        cat,
                        l1,
                        l2,
                        y,
                        tick_height=tickHeight,
                        label=label,
                        bracket_style=bracketStyle,
                        label_style=labelStyle,
                        categories=categories,
                        level_order=level_order,
                        strokeWidth=strokeWidth,
                        fontSize=fontSize,
                    )
                )
            comparisons.append(
                {"g1": f"{cat} ({l1})", "g2": f"{cat} ({l2})", "pvalue": p, "effectName": en, "effect": ev}
            )

    record = _make_record(
        test=test,
        is_omnibus=False,
        omnibus=None,
        descriptives=descriptives,
        comparisons=comparisons,
        comparison_test=test,
        correction=effective_correction,
        pvalues_provided=pval_map is not None,
        data_checksum=frame_checksum(df),
    )
    marker = _emit_report(record, report, save)

    if not layers:
        layers.append(_empty_layer())
    return cast(alt.LayerChart, alt.layer(*layers).properties(name=marker))


def add_comparisons(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    pairs: list[tuple[str, str]] | None = None,
    *,
    test: str = "mannwhitneyu",
    postHoc: str | None = None,
    pvalues: list[float] | dict[Any, Any] | None = None,
    correction: str | None = None,
    nComparisons: int | None = None,
    reference: Any = None,
    xOffsetCol: str | None = None,
    xOffsetSort: list[str] | None = None,
    yPositions: list[float] | dict[Any, Any] | None = None,
    yStart: float | dict[Any, Any] | None = None,
    yStep: float | None = None,
    yPad: float | None = None,
    categories: list[Any] | None = None,
    chartWidth: int | None = None,
    bracketStyle: str | dict[tuple[str, str], Any] = "bracket",
    labelStyle: str = "p",
    tickHeight: float | None = None,
    strokeWidth: float | None = None,
    fontSize: int | None = None,
    reverse: list[tuple[str, str]] | None = None,
    sigFigs: int | None = None,
    notation: str | dict[str | tuple[str, str], Any] | None = None,
    testLabelPosition: str | None = "auto",
    testLabel: str | None = None,
    omnibusVerbose: bool = False,
    testLabelOffsetX: int = 0,
    testLabelOffsetY: int = 0,
    testLabelX=None,
    testLabelY=None,
    report: bool = False,
    save: bool | str = False,
) -> alt.LayerChart:
    """
    Build p-value annotation layers for one or more group comparisons.

    Two modes, selected by ``test``:

    - **Pairwise** (``'mannwhitneyu'``, ``'ttest_ind'``, ``'ttest_rel'``,
      ``'wilcoxon'``, ``'tukey_hsd'``) — draws a bracket per pair in ``pairs``,
      stacked automatically so they don't overlap (shorter-span pairs sit lower;
      overlapping spans are bumped up a level).
    - **Omnibus** (``'anova'``, ``'kruskal'``, ``'friedman'``,
      ``'alexandergovern'``) — runs one "are *any* groups different?" test and
      places its result as a corner label via ``add_text`` (see
      ``testLabelPosition``). If ``pairs`` is also given, a post-hoc test (see
      ``postHoc``) fills the brackets.

    Setting ``reference`` overrides both with **reference mode**: compare every
    other group against one reference and draw the p-value above each mark with no
    bracket (see ``reference``).

    A descriptive + effect-size report is generated on every call and queued for
    the export metadata written by ``ds.save()`` (see ``report``/``save``).

    Combine with your chart using ``+``:  ``chart + add_comparisons(...)``.

    Parameters
    ----------
    df:
        Polars DataFrame containing the data.
    xCol:
        Column name for the grouping variable (x-axis).
    yCol:
        Column name for the value variable (y-axis). Used to run tests and
        to auto-place the first bracket.
    pairs:
        List of ``(group1, group2)`` tuples identifying the comparisons to
        annotate with brackets. Required for pairwise ``test`` values. Optional
        for omnibus tests — pass ``None`` for an omnibus-only corner label, or a
        list to also draw post-hoc brackets.
    test:
        Statistical test. **Pairwise:** ``'mannwhitneyu'`` (default),
        ``'ttest_ind'``, ``'ttest_rel'``, ``'wilcoxon'`` (run per pair), or
        ``'tukey_hsd'`` (one omnibus run, per-pair p-values from the matrix).
        **Omnibus:** ``'anova'`` (``f_oneway``), ``'kruskal'``, ``'friedman'``,
        ``'alexandergovern'``. Ignored when ``pvalues`` is provided.
    postHoc:
        Post-hoc test that fills the brackets when ``test`` is omnibus and
        ``pairs`` is given. ``None`` (default) picks a sensible default per
        omnibus test: ``anova → 'tukey_hsd'``, ``alexandergovern →
        'games_howell'``, ``kruskal → 'dunn'``, ``friedman → 'nemenyi'``. May
        also be set to any pairwise test name. Dunn, Nemenyi, and Games-Howell
        are computed in-house (validated against scikit-posthocs / pingouin);
        ``correction`` adjusts them over all unique pairs. Ignored for pairwise
        ``test``.
    pvalues:
        Pre-computed p-values - skips the test AND correction (they're final). **Single-
        factor:** a list, one per pair in the same order. **Grouped (`xOffsetCol`):** a
        **dict** keyed by ``(category, level)`` in reference mode or ``(category, (level1,
        level2))`` (order-insensitive) in bracket mode, covering **every** comparison
        (missing or unknown keys raise). Not yet supported with single-factor ``reference``.
    correction:
        Multiple comparison correction: ``'bonferroni'``, ``'holm'``,
        ``'fdr_bh'`` (Benjamini-Hochberg), ``'fdr_by'`` (Benjamini-Yekutieli),
        or ``None``. The two ``fdr_*`` methods control the false discovery rate
        (BH assumes independence / positive dependence; BY is valid under
        arbitrary dependence but more conservative). For pairwise/post-hoc
        bracket p-values; ignored for ``tukey_hsd`` (correction is built in) and
        when ``pvalues`` is provided.
    nComparisons:
        Total family size for the correction (the denominator ``m``). Defaults
        to ``len(pairs)`` when a ``correction`` is set and not given explicitly.
        In grouped mode it defaults to the total number of drawn comparisons
        (``len(categories) * len(pairs)``).
    reference:
        **Reference mode (compare-against-one).** A single group to compare every
        other group against, drawing the p-value **above each non-reference mark
        with no bracket** (the comparison is implicit - a control/many-vs-one
        design). Derives its own comparisons, so ``pairs`` must be left ``None``.
        Only the pairwise tests are supported (not omnibus); ``correction`` adjusts
        over the whole family of ``len(categories) - 1`` comparisons. Labels sit at
        each group's OWN data max, so overlay your points (they clear the data).
        Distinguishing the reference visually (e.g. a darker fill) is left to your
        chart - nothing is injected. Without ``xOffsetCol``, ``reference`` is a
        category of ``xCol``; with ``xOffsetCol`` (grouped mode) it is an xOffset
        **level**, compared within each x-category (one label per non-reference
        sub-bar). ``bracketStyle``/``reverse``/``tickHeight`` are inert here (no
        bracket); ``yStart`` does not apply (no stack) and raises if set - use
        ``yPositions`` to place labels explicitly. In grouped reference mode
        ``pvalues``/``yPositions`` give explicit control (see those params); with
        single-factor ``reference``, ``pvalues`` is not yet supported.
    xOffsetCol:
        **Grouped mode.** Column encoded as the chart's ``xOffset`` (the subgroup
        that splits each x-category into side-by-side bars, e.g. ``"condition"``
        in a qPCR gene × condition panel). When set, ``pairs`` names subgroup
        **levels** (not x-categories) and one bracket is drawn per x-category,
        each above its own bars. With exactly two levels ``pairs`` defaults to
        comparing them. Only the pairwise tests are supported here
        (``'mannwhitneyu'``/``'ttest_ind'``/``'ttest_rel'``/``'wilcoxon'``);
        ``correction`` adjusts over the whole family (``categories × pairs``). The
        bracket label centres on the band - exact for two levels / symmetric
        pairs, slightly off the midpoint only for an asymmetric 3+-level pair.
    xOffsetSort:
        Grouped mode - the subgroup level order. Must match the ``sort`` on your
        chart's ``xOffset`` encoding (and ``categories`` must match the ``x``
        sort), or the shared scale reorders the bars. ``None`` (default) reads the
        data's first-appearance order.
    yPositions:
        Explicit y positions (data units) for the annotations. **Single-factor:** a
        list, one per pair in the same order (overrides all auto-stacking). **Grouped
        (`xOffsetCol`):** a **dict** keyed by ``(category, level)`` in reference mode or
        ``(category, (level1, level2))`` (order-insensitive) in bracket mode; may be
        partial - listed comparisons use the given y, the rest fall back to auto. Beats
        ``yStart``. Unknown keys raise.
    yStart:
        The exact y (data units) of the lowest bracket - the stack base (levels rise from it
        by ``yStep``). Defaults to ``max(annotated groups) + yPad``. **Grouped (`xOffsetCol`)
        brackets** additionally accept a **dict** keyed by category for a per-category base
        (partial - unlisted categories use the auto base). **Does not apply to reference mode**
        (there is no stack - each label sits above its own mark); passing it there raises. Use
        ``yPositions`` for exact per-label heights.
    yStep:
        Vertical distance (data units) between stacking levels. Defaults to
        ``yPad * 1.75``, leaving clearance between a bracket's label and the
        bracket stacked above it.
    yPad:
        Padding above the data maximum when ``yStart`` is auto-placed. Defaults
        to a visual gap of ~8 px (``bracketStyle='line'``) or ~10 px
        (``bracketStyle='bracket'``), expressed in data units as a fraction of
        the **full** data extent over ``chartHeight``. Using the full extent
        (not just the compared groups) keeps the spacing stable - and stops the
        brackets collapsing when an un-annotated group inflates the rendered
        domain - since the gap in pixels tracks ``chartHeight / rendered domain``.
    categories:
        Ordered list of all x-axis categories. Inferred from ``df`` (sorted
        alphabetically) when not provided.
    chartWidth:
        Width of the chart in pixels, used to compute text x positions.
        Auto-detected from ``ds.theme()`` when not set.
    bracketStyle:
        ``'bracket'`` (default; bar + end ticks) or ``'line'`` (horizontal bar only)
        applied to every bracket. Or a ``dict`` mapping a pair to its style for
        per-pair control, e.g. ``{("A", "B"): "line", ("A", "C"): "bracket"}`` —
        keys match either pair order; pairs absent from the dict fall back to
        ``'bracket'``.
    labelStyle:
        ``'p'`` (default) renders ``P = 0.012`` / ``P < 0.001``. ``'asterisks'``
        renders ``*`` / ``**`` / ``***`` / ``ns``.
    tickHeight:
        Height of bracket end ticks in data units. Defaults to the theme's
        ``tickSize`` (converted from px to data units), so bracket ticks match the
        axis ticks. Always positive, so it works with reverse (negative-``yStep``)
        brackets without an explicit override. Only used when ``bracketStyle='bracket'``.
    strokeWidth:
        Stroke width of bracket lines. Inherits ``axisWidth`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size of the p-value / corner labels. Defaults to the theme's primary
        ``fontSize`` (``7`` under the built-in defaults), matching the axis font.
    reverse:
        List of ``(group1, group2)`` tuples identifying brackets to flip —
        text moves below the bar and ticks point upward.
    sigFigs:
        Significant figures for p-value labels (and the correlation readout). Gives
        consistent visual precision across magnitudes — e.g. ``sigFigs=2`` renders both
        ``P = 4.3×10⁻¹⁴`` and ``P = 0.68`` at two figures. Trailing zeros are stripped.
        ``None`` (default) reads the theme's ``sigFigs`` (default ``3``). Plain notation
        floors at a fixed ``P < 0.001``; ``'power'`` is unaffected (integer exponent).
    notation:
        Format style for p-value labels when ``labelStyle='p'``. ``None``
        (default) uses ``P = 0.012`` / ``P < 0.001`` style. ``'scientific'``
        uses ``P = 1.23×10⁻²``. ``'e'`` uses ``P = 1.23e-02``. ``'power'``
        rounds to the nearest power of 10 giving ``P ≈ 10⁻²`` — note that
        values within the same decade (e.g. 0.04 and 0.06) map to the same
        label; best for p-values spanning multiple orders of magnitude.
        A single value applies to every label; or pass a ``dict`` for per-pair
        notation, e.g. ``{("A", "B"): "scientific", "test": "power"}`` — tuple
        keys are pairs (matched either order, unlisted → plain), and the special
        ``"test"`` key sets the omnibus label's notation.
    testLabelPosition:
        Corner preset (an ``add_text`` position, e.g. ``'topLeft'``,
        ``'bottomRight'``) for the single test label. Its content adapts: the
        omnibus **result** (``ANOVA P = 0.003``) for an omnibus ``test``, or the
        pairwise **test name** (``Mann-Whitney U``) for a pairwise ``test``.
        Default ``'auto'`` → shown at ``'topLeft'`` for omnibus, hidden for
        pairwise (opt-in). A preset draws it there; ``None`` hides it (the result
        is still computed for the report/metadata).
    testLabel:
        Override string for the test label. ``None`` (default) builds it from the
        test result / name.
    omnibusVerbose:
        Applies to the omnibus label content: ``False`` (default) → terse
        ``ANOVA P = 0.003``; ``True`` → ``ANOVA F(2, 57) = 6.34, P = 0.003,
        η² = 0.18`` (statistic, df, p, and effect size).
    testLabelOffsetX, testLabelOffsetY:
        Pixel nudges for the test label, forwarded to ``add_text``.
    testLabelX, testLabelY:
        Explicit coordinates for the test label (data values, category names, or
        ``alt.value(px)``), forwarded to ``add_text`` where they override the
        preset. ``None`` (default) uses ``testLabelPosition``.
    report:
        ``True`` prints the full descriptive + effect-size report (per-group
        n/mean/sd/median/IQR/range, the omnibus result, and the post-hoc
        comparisons) to stdout. Default ``False``. For an omnibus ``test`` the
        report lists **all** pairwise post-hoc comparisons — the full table, not
        just the pairs you bracket (and even when ``pairs=None``). For a
        pairwise ``test`` it lists exactly the requested ``pairs``. The report is
        queued for the export metadata regardless of this flag (when
        ``ds.save(..., saveMetadata=True)``); it lands in the next ``ds.save()``.
    save:
        ``True`` writes the report to ``dysonsphere_report_<timestamp>.txt`` in
        the current directory; a string writes it to that directory. Default
        ``False``.

    Examples
    --------
    Single comparison::

        CATEGORIES = ["A", "B", "C"]
        chart = ds.mark_strip(df, "group", "value", CATEGORIES)
        chart + ds.add_comparisons(
            df, "group", "value",
            pairs=[("A", "B")],
            categories=CATEGORIES,
        )

    Multiple comparisons — brackets stacked automatically::

        chart + ds.add_comparisons(
            df, "group", "value",
            pairs=[("A", "B"), ("A", "C"), ("B", "C")],
            test="mannwhitneyu",
            categories=CATEGORIES,
        )

    Omnibus ANOVA in the corner + Tukey post-hoc brackets::

        chart + ds.add_comparisons(
            df, "group", "value",
            pairs=[("A", "B"), ("A", "C")],
            test="anova",
            omnibusVerbose=True,
            categories=CATEGORIES,
        )

    Omnibus-only (no brackets), report printed::

        chart + ds.add_comparisons(
            df, "group", "value",
            test="kruskal",
            categories=CATEGORIES,
            report=True,
        )

    From pre-computed p-values::

        chart + ds.add_comparisons(
            df, "group", "value",
            pairs=[("A", "B"), ("A", "C")],
            pvalues=[0.012, 0.341],
            categories=CATEGORIES,
        )

    Grouped (two-factor) - compare vehicle vs LPS *within* each gene of a grouped
    bar chart (``xOffset="condition"``); one bracket per gene, a real per-gene test::

        GENES = ["GAPDH", "IL6", "TNF"]
        bars = alt.Chart(df).mark_bar().encode(
            x=alt.X("gene:N", sort=GENES),
            xOffset=alt.XOffset("condition:N", sort=["Vehicle", "LPS"]),
            y="mean(expr):Q", color="condition:N",
        )
        bars + ds.add_comparisons(
            df, "gene", "expr",
            xOffsetCol="condition",
            categories=GENES, xOffsetSort=["Vehicle", "LPS"],
            test="ttest_ind", labelStyle="asterisks",
        )

    Reference mode - compare every dose against the control, a bare mark above each
    (no bracket); overlay your points so the marks clear the data::

        CATS = ["Ctrl", "Low", "Mid", "High"]
        chart = ds.mark_strip(df, "group", "value", CATS)
        chart + ds.add_comparisons(
            df, "group", "value",
            reference="Ctrl", categories=CATS,
            test="ttest_ind", correction="holm", labelStyle="asterisks",
        )
    """
    from .statistics import (
        _OMNIBUS_TESTS,
        _PARAMETRIC_POSTHOC,
        _TEST_DISPLAY,
        _describe_all,
        _make_record,
        _pair_effect,
        _run_omnibus,
    )
    from .utils import ensure_polars, frame_checksum

    df = ensure_polars(df)

    # Grouped mode: compare xOffset subgroups WITHIN each x-category (a two-factor design, e.g. a
    # qPCR gene x condition panel). A fully separate path so the single-factor logic below is
    # untouched; see the grouped-comparisons design point.
    if xOffsetCol is not None:
        return _add_grouped_comparisons(
            df,
            xCol,
            yCol,
            xOffsetCol,
            pairs,
            reference=reference,
            xOffsetSort=xOffsetSort,
            test=test,
            correction=correction,
            nComparisons=nComparisons,
            labelStyle=labelStyle,
            bracketStyle=bracketStyle,
            notation=notation,
            sigFigs=sigFigs,
            tickHeight=tickHeight,
            strokeWidth=strokeWidth,
            fontSize=fontSize,
            pvalues=pvalues,
            yStart=yStart,
            yPositions=yPositions,
            yPad=yPad,
            yStep=yStep,
            categories=categories,
            chartWidth=chartWidth,
            report=report,
            save=save,
        )

    # Dict pvalues/yPositions/yStart are the grouped (xOffsetCol) form; single-factor takes scalars/lists.
    if isinstance(pvalues, dict):
        raise ValueError("a dict pvalues is for grouped mode (xOffsetCol); single-factor takes a list.")
    if isinstance(yPositions, dict):
        raise ValueError("a dict yPositions is for grouped mode (xOffsetCol); single-factor takes a list.")
    if isinstance(yStart, dict):
        raise ValueError("a dict yStart is for grouped mode (xOffsetCol); single-factor takes a number.")

    # Guard the categories footgun: brackets are positioned by the order/count of `categories`, so an
    # explicit list that doesn't cover the data's x-values (a typo or omission) mis-sizes the band
    # geometry and silently shifts every bracket. Raise instead (mirrors the grouped path). The
    # order-vs-chart mismatch stays undetectable without the chart (documented).
    _check_coverage(
        df,
        xCol,
        categories,
        "categories",
        "values",
        "It must list every x-category, in the same order as your chart's x sort.",
    )
    if categories is None:
        categories = sorted(df[xCol].unique().to_list())

    is_omnibus = test in _OMNIBUS_TESTS
    groups = [df.filter(pl.col(xCol) == cat)[yCol].to_numpy() for cat in categories]

    # Reference mode: compare every other category against `reference`, drawing the p-value above
    # each mark with NO bracket (the comparison is implicit - a many-vs-one/control design). It
    # derives `pairs` and switches the rendering to bare labels; it is a pairwise-only modifier.
    is_reference = reference is not None
    if is_reference:
        if is_omnibus:
            raise ValueError(
                "reference is a pairwise comparison against one group; it can't be used with an omnibus test."
            )
        if pairs is not None:
            raise ValueError("reference derives its own comparisons; don't also pass pairs.")
        if pvalues is not None:
            raise ValueError("reference with pvalues is not supported yet.")
        if reference not in categories:
            raise ValueError(f"reference {reference!r} is not a category of {xCol!r}: {categories}.")
        pairs = [(reference, c) for c in categories if c != reference]

    if pairs is not None and len(pairs) == 0:
        raise ValueError("pairs must not be empty when provided (pass pairs=None for an omnibus-only annotation).")
    if not is_omnibus and not pairs:
        raise ValueError("pairs is required for pairwise tests.")
    if yPositions is not None and pairs is not None and len(yPositions) != len(pairs):
        raise ValueError(f"yPositions length ({len(yPositions)}) does not match pairs length ({len(pairs)})")

    annotation_layers: list[Any] = []
    omnibus_result = None
    comparisons: list[dict[str, Any]] = []

    if is_omnibus:
        omnibus_result = _run_omnibus(test, groups, categories)

    # --- resolve comparison method (a post-hoc for omnibus, the test itself for pairwise) ---
    idx = {c: i for i, c in enumerate(categories)}
    method = _resolve_method(test, postHoc, pvalues, is_omnibus)
    # tukey_hsd carries its own correction; explicit p-values aren't corrected by us.
    effective_correction = None if (method is None or method == "tukey_hsd") else correction
    # sigFigs: per-call overrides the theme default (3); governs on-plot label precision.
    effective_sigfigs = sigFigs if sigFigs is not None else _opt("sigFigs")

    # Notation: a scalar applies everywhere; a dict is per-pair for the brackets plus an optional
    # "test" key for the omnibus/test label. Pair notations are read below in the bracket loop.
    test_notation, pair_notations = _resolve_notation(notation, pairs)

    # --- unified test label: the omnibus result, or the pairwise/post-hoc test name ---
    # Position "auto" (default) → shown for omnibus (topLeft), hidden for pairwise.
    resolved_pos = ("topLeft" if is_omnibus else None) if testLabelPosition == "auto" else testLabelPosition
    if resolved_pos is not None or testLabelX is not None or testLabelY is not None:
        if testLabel is not None:
            label_text = testLabel
        elif is_omnibus:
            label_text = _omnibus_label(
                omnibus_result, verbose=omnibusVerbose, notation=test_notation, sigFigs=effective_sigfigs
            )
        else:
            label_text = _TEST_DISPLAY.get(test, test)
        annotation_layers.append(
            add_text(
                label_text,
                testLabelX,
                testLabelY,
                position=resolved_pos,
                offsetX=testLabelOffsetX,
                offsetY=testLabelOffsetY,
                fontSize=fontSize if fontSize is not None else _opt("fontSize"),
            )
        )

    # --- report comparisons ---
    # Omnibus reports ALL pairwise post-hoc comparisons (the full picture), even when
    # only a subset is bracketed or none is. Pairwise reports exactly the requested pairs.
    if is_omnibus and method is not None:
        report_pairs = [
            (categories[i], categories[j]) for i in range(len(categories)) for j in range(i + 1, len(categories))
        ]
    else:
        report_pairs = list(pairs) if pairs else []

    pval_lookup: dict[frozenset[str], Any] = {}
    if method is not None and report_pairs:
        report_pvals = _bracket_pvalues(method, groups, categories, report_pairs, correction, nComparisons)
        pval_lookup = {frozenset(p): v for p, v in zip(report_pairs, report_pvals)}
        parametric = method in _PARAMETRIC_POSTHOC
        paired = method == "ttest_rel"
        for g1, g2 in report_pairs:
            en, ev = _pair_effect(groups[idx[g1]], groups[idx[g2]], parametric=parametric, paired=paired)
            comparisons.append(
                {"g1": g1, "g2": g2, "pvalue": pval_lookup[frozenset((g1, g2))], "effectName": en, "effect": ev}
            )

    # --- reference labels (no brackets) ---
    if is_reference and pairs:
        # A bare p-value above each non-reference mark, at that group's OWN data max (per-group,
        # so groups of different magnitude each get a label sitting just above their data).
        y_all = df[yCol].cast(pl.Float64)
        y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
        ref_pad, _, _ = _resolve_y_spacing(False, y_range, _opt("chartHeight"), yPad, None, None)
        cw = chartWidth if chartWidth is not None else _opt("chartWidth")
        fs = fontSize if fontSize is not None else _opt("fontSize")
        for i, (_, g) in enumerate(pairs):
            pval = pval_lookup[frozenset((reference, g))]
            g_max = cast(float, df.filter(pl.col(xCol) == g)[yCol].cast(pl.Float64).max() or 0.0)
            label = (
                _format_asterisks(pval)
                if labelStyle == "asterisks"
                else _format_pvalue(pval, sigFigs=effective_sigfigs, notation=pair_notations[i])
            )
            annotation_layers.append(
                _reference_label_layer(g, g_max + ref_pad, label, categories=categories, chartWidth=cw, fontSize=fs)
            )

    # --- brackets ---
    elif pairs:
        pair_styles = _resolve_bracket_styles(bracketStyle, pairs)

        if pvalues is not None:
            if len(pvalues) != len(pairs):
                raise ValueError(f"pvalues length ({len(pvalues)}) does not match pairs length ({len(pairs)})")
            computed_pvalues = list(pvalues)
            comparisons = [{"g1": g1, "g2": g2, "pvalue": p} for (g1, g2), p in zip(pairs, pvalues)]
        else:
            computed_pvalues = [pval_lookup[frozenset((g1, g2))] for g1, g2 in pairs]

        # --- y positioning ---
        annotated_groups_for_pad = list({g for pair in pairs for g in pair})
        # Base the gap on the FULL data extent, not just the compared groups: Vega fits the
        # rendered domain to every group, and the visual gap is yStep * chartHeight / domain.
        # Using only the annotated groups' range collapses the brackets when an un-annotated
        # group (e.g. a saturating positive control) blows up the domain; the full extent
        # tracks the domain, so the gap stays stable. (yStart still sits above the compared
        # groups - see below.)
        y_all = df[yCol].cast(pl.Float64)
        y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
        # The gap is based on the FULL data extent, not just the compared groups: Vega fits the
        # rendered domain to every group, and the visual gap is yStep * chartHeight / domain, so
        # using only the annotated range collapses the brackets when an un-annotated group blows
        # up the domain. (yStart still sits above the compared groups - see below.) Tick height
        # matches the theme tickSize; always positive so it survives a negative yStep (reverse).
        yPad, tickHeight, yStep = _resolve_y_spacing(
            "bracket" in pair_styles, y_range, _opt("chartHeight"), yPad, tickHeight, yStep
        )

        if yPositions is not None:
            final_y = list(yPositions)
        else:
            if yStart is None:
                yStart = (
                    cast(
                        float,
                        df.filter(pl.col(xCol).is_in(annotated_groups_for_pad))[yCol].cast(pl.Float64).max() or 0.0,
                    )
                    + yPad
                )

            # Assign stacking levels via greedy interval scheduling (shorter spans sit lower).
            pair_levels = _stack_levels([(categories.index(g1), categories.index(g2)) for g1, g2 in pairs])
            final_y = [yStart + pair_levels[i] * yStep for i in range(len(pairs))]

        for i, ((g1, g2), pval) in enumerate(zip(pairs, computed_pvalues)):
            annotation_layers.append(
                _pvalue_layer(
                    group1=g1,
                    group2=g2,
                    pvalue=pval,
                    y=final_y[i],
                    tick_height=tickHeight,
                    bracket_style=pair_styles[i],
                    label_style=labelStyle,
                    categories=categories,
                    chartWidth=chartWidth,
                    strokeWidth=strokeWidth,
                    fontSize=fontSize,
                    reverse=(g1, g2) in reverse if reverse is not None else False,
                    sigFigs=effective_sigfigs,
                    notation=pair_notations[i],
                )
            )

    # --- report: a structured record is always queued for export metadata; ---
    # --- rendered to text when report=True (print) or save is set (file).   ---
    record = _make_record(
        test=test,
        is_omnibus=is_omnibus,
        omnibus=omnibus_result,
        descriptives=_describe_all(groups, categories),
        comparisons=comparisons,
        comparison_test=method,
        correction=effective_correction,
        pvalues_provided=pvalues is not None,
        data_checksum=frame_checksum(df),
    )
    marker = _emit_report(record, report, save)

    if not annotation_layers:
        # no label and no brackets → report-only; return an invisible layer.
        annotation_layers.append(_empty_layer())
    # Tag the layer with the record's marker name so save() can match this record back to
    # the chart it annotates (the name survives ``+``; it's stripped from the written JSON).
    return cast(alt.LayerChart, alt.layer(*annotation_layers).properties(name=marker))


# Correlation


def _correlation_label(
    result: dict[str, Any],
    *,
    coefficient: str,
    includePvalue: bool,
    includeEquation: bool,
    sigFigs: int,
    notation: str | None,
) -> str:
    """Build the corner-readout string from a correlation result, one part at a time."""
    g = f".{sigFigs}g"  # significant figures, no trailing zeros
    is_pearson = result["rSquared"] is not None  # only Pearson has r²/slope
    parts: list[str] = []
    if not is_pearson:
        parts.append(f"{result['symbol']} = {result['coefficient']:{g}}")  # ρ/τ always
    else:
        if coefficient in ("r", "both"):
            parts.append(f"r = {result['coefficient']:{g}}")
        if coefficient in ("r2", "both"):
            parts.append(f"r² = {result['rSquared']:{g}}")
    if includePvalue:
        parts.append(_format_pvalue(result["pvalue"], sigFigs=sigFigs, notation=notation))
    label = ", ".join(parts)
    if includeEquation and result["slope"] is not None:
        sign = "+" if result["intercept"] >= 0 else "-"
        label += f", y = {result['slope']:{g}}x {sign} {abs(result['intercept']):{g}}"
    return label


def _add_grouped_correlation(
    df: pl.DataFrame,
    x_col: str,
    y_col: str,
    group_col: str,
    *,
    method: str,
    line: bool,
    position: str | None,
    coefficient: str,
    includePvalue: bool,
    includeEquation: bool,
    offsetX: int,
    offsetY: int,
    fontSize: int | None,
    sigFigs: int | None,
    notation: str | None,
    color: str | None,
    strokeWidth: float | None,
    strokeDash: bool | list[int] | None,
    opacity: float | None,
    lineStyle: dict[str, Any] | None,
    ci: float | bool,
    interval: str,
    ciOpacity: float,
    report: bool,
    save: bool | str,
) -> alt.LayerChart:
    """A fit + coefficient readout PER group of ``group_col`` (e.g. one line per cell line).

    Every fit line, CI band, and readout is coloured by ``group_col`` on the SAME colour channel the
    scatter uses, so they share one colour scale and match automatically. Colour is a lookup, not a
    position, so there's no reorder hazard like the grouped brackets - no sort param is needed. One
    record is registered per group (tagged onto that group's first layer so ``save()`` finds them
    all); the readouts stack in the ``position`` corner, each in its group's colour.
    """
    import numpy as np

    from .annotations import _TEXT_PRESETS
    from .statistics import _make_correlation_record, _ols_band, _run_correlation
    from .utils import frame_checksum

    fontSize = fontSize if fontSize is not None else _opt("fontSize")
    effective_sigfigs = sigFigs if sigFigs is not None else _opt("sigFigs")
    groups = df[group_col].unique(maintain_order=True).to_list()

    # Curated line-style overrides, shared across groups; colour stays per-group via the encoding,
    # unless a fixed `color` is given (which then overrides every group's line).
    line_kwargs: dict[str, Any] = {}
    if strokeWidth is not None:
        line_kwargs["strokeWidth"] = strokeWidth
    if strokeDash is not None:
        line_kwargs["strokeDash"] = _resolve_dash(strokeDash)
    if opacity is not None:
        line_kwargs["opacity"] = opacity
    if lineStyle:
        line_kwargs.update(lineStyle)
    line_color = alt.value(color) if color is not None else alt.Color(f"{group_col}:N", legend=None)

    ci_level: float | None = None
    if ci:
        ci_level = 0.95 if ci is True else float(ci)
        if not 0.0 < ci_level < 1.0:
            raise ValueError(f"ci must be True or a confidence level in (0, 1), got {ci!r}")
        if interval not in ("confidence", "prediction"):
            raise ValueError(f"interval must be 'confidence' or 'prediction', got {interval!r}")

    # Corner-readout stacking geometry (resolved once).
    if position is not None and position not in _TEXT_PRESETS:
        raise ValueError(f"position must be one of {sorted(_TEXT_PRESETS)} or None, got {position!r}")
    n = len(groups)
    if position is not None:
        preset = _TEXT_PRESETS[position]
        cw, chh = _opt("chartWidth"), _opt("chartHeight")
        pad = 1  # px inset from an edge, matching add_text's edge-inset spirit
        base_x = preset["x_frac"] * cw + (pad if preset["x_frac"] == 0 else -pad if preset["x_frac"] == 1 else 0)
        base_y = preset["y_frac"] * chh + (pad if preset["y_frac"] == 0 else -pad if preset["y_frac"] == 1 else 0)
        line_h = fontSize * 1.5
        # top anchor -> stack down; bottom -> stack up; middle -> centred on the anchor.
        anchor = 0.0 if preset["y_frac"] == 0 else (n - 1) if preset["y_frac"] == 1 else (n - 1) / 2

    layers: list[Any] = []
    for i, g in enumerate(groups):
        gdf = df.filter(pl.col(group_col) == g)
        x = gdf[x_col].cast(pl.Float64).to_numpy()
        y = gdf[y_col].cast(pl.Float64).to_numpy()
        result = _run_correlation(method, x, y)
        g_layers: list[Any] = []

        # CI band (Pearson only), drawn first so it sits under the line; filled by the group colour.
        if ci_level is not None and result["slope"] is not None:
            xs = np.linspace(float(x.min()), float(x.max()), 64)
            lo, hi = _ols_band(x, y, xs, level=ci_level, kind=interval)
            band_df = pl.DataFrame({x_col: xs, y_col: lo, "__ci_hi": hi, group_col: [g] * len(xs)})
            g_layers.append(
                alt.Chart(_internal_data(band_df))
                .mark_area(fillOpacity=ciOpacity, stroke=None, strokeWidth=0)
                .encode(
                    x=alt.X(field=x_col, type="quantitative"),
                    y=alt.Y(field=y_col, type="quantitative"),
                    y2=alt.Y2(field="__ci_hi"),
                    color=line_color,
                )
            )

        # Fit line (Pearson only - slope is None for the rank methods).
        if line and result["slope"] is not None:
            x0, x1 = float(x.min()), float(x.max())
            slope, intercept = result["slope"], result["intercept"]
            fit_df = pl.DataFrame(
                {x_col: [x0, x1], y_col: [slope * x0 + intercept, slope * x1 + intercept], group_col: [g, g]}
            )
            g_layers.append(
                alt.Chart(_internal_data(fit_df))
                .mark_line(**line_kwargs)
                .encode(
                    x=alt.X(field=x_col, type="quantitative"),
                    y=alt.Y(field=y_col, type="quantitative"),
                    color=line_color,
                )
            )

        # Stacked corner readout for this group: a colour SWATCH in the series colour + the readout
        # in the theme's neutral (darkmode-aware) ink. The swatch carries the colour link to the
        # line/points (like a legend entry), so the text stays fully legible even for pale palette
        # colours - colouring the whole readout hurt contrast on light series (e.g. a pale yellow).
        if position is not None:
            text = _correlation_label(
                result,
                coefficient=coefficient,
                includePvalue=includePvalue,
                includeEquation=includeEquation,
                sigFigs=effective_sigfigs,
                notation=notation,
            )
            label = f"{g}: {text}"
            y_i = base_y + (i - anchor) * line_h
            align, baseline = preset["align"], preset["baseline"]
            # A filled point swatch sized like a symbol-legend entry: config.legend.symbolSize is
            # fontSize*6 (so it scales with the font), the default circle shape, and the same
            # darkmode-aware stroke the legend uses (config.point's stroke is a fixed black).
            sym_size = fontSize * 6
            sym_r = (sym_size / math.pi) ** 0.5  # circle radius, for placement
            gap = fontSize * 0.4  # swatch -> text
            tw = len(label) * fontSize * 0.6  # rough text-width estimate (for right/centre swatch x)
            if align == "left":
                text_x, sw_x = base_x + 2 * sym_r + gap, base_x + sym_r
            elif align == "right":
                text_x, sw_x = base_x, base_x - tw - gap - sym_r
            else:  # center
                text_x, sw_x = base_x, base_x - tw / 2 - gap - sym_r
            # Seat the swatch on the text's visual middle, given its baseline.
            _vshift = {"top": 0.35, "middle": 0.0, "alphabetic": -0.35, "bottom": -0.45}.get(baseline, 0.0)
            sw_y = y_i + _vshift * fontSize
            g_layers.append(
                alt.Chart(_internal_data([{group_col: g}]))
                .mark_point(
                    filled=True,
                    size=round(sym_size, 2),
                    stroke="white" if _opt("darkmode") else "black",
                    strokeWidth=_opt("markStrokeWidth"),
                )
                .encode(
                    x=alt.value(round(sw_x + offsetX, 2)),
                    y=alt.value(round(sw_y + offsetY, 2)),
                    color=alt.Color(f"{group_col}:N", legend=None),
                )
            )
            g_layers.append(
                alt.Chart(_internal_data([{}]))
                .mark_text(align=align, baseline=baseline, fontSize=fontSize, dx=offsetX, dy=offsetY)
                .encode(x=alt.value(round(text_x, 2)), y=alt.value(round(y_i, 2)), text=alt.value(label))
            )

        # One record per group; tag it onto this group's first layer so save() matches all of them.
        record = _make_correlation_record(result, x_col, y_col, data_checksum=frame_checksum(gdf), group=g)
        marker = _emit_report(record, report, save)
        if g_layers:
            g_layers[0] = g_layers[0].properties(name=marker)
        layers.extend(g_layers)

    if not layers:
        layers.append(_empty_layer())
    return cast(alt.LayerChart, alt.layer(*layers))


def add_correlation(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    *,
    method: str = "pearson",
    groupCol: str | None = None,
    line: bool = True,
    position: str | None = "topLeft",
    label: str | None = None,
    coefficient: str = "r",
    includePvalue: bool = False,
    includeEquation: bool = False,
    verbose: bool = False,
    offsetX: int = 0,
    offsetY: int = 0,
    fontSize: int | None = None,
    sigFigs: int | None = None,
    notation: str | None = None,
    color: str | None = None,
    strokeWidth: float | None = None,
    strokeDash: bool | list[int] | None = None,
    opacity: float | None = None,
    lineStyle: dict[str, Any] | None = None,
    ci: float | bool = False,
    interval: str = "confidence",
    ciColor: str | None = None,
    ciOpacity: float = 0.15,
    report: bool = False,
    save: bool | str = False,
) -> alt.LayerChart:
    """
    Annotate a scatter with a correlation coefficient (and an OLS fit line for Pearson).

    Reports the coefficient as a corner label, and — for ``method="pearson"``
    only — draws the ordinary-least-squares regression line. A structured record
    (``kind="correlation"``) is queued for the export metadata (see ``ds.save``),
    exactly like ``add_comparisons``.

    Combine with your scatter using ``+``:  ``chart + add_correlation(...)``.

    Parameters
    ----------
    df:
        DataFrame containing the data (polars or pandas).
    xCol, yCol:
        Column names for the two **continuous** variables.
    method:
        ``'pearson'`` (default) — linear correlation ``r`` + ``r²`` + slope/intercept,
        with an OLS line. ``'spearman'`` — rank correlation ``ρ``. ``'kendall'`` —
        rank correlation ``τ``. The rank methods report the coefficient only (no ``r²``,
        no line — a straight line isn't their model). Matches pandas' ``DataFrame.corr``.
    groupCol:
        **Grouped mode.** A column to split the scatter into series (e.g. ``"cell_line"``).
        When set, a fit + coefficient is computed **per group**, each fit line / CI band /
        readout coloured by ``groupCol`` on the *same* colour channel your scatter uses -
        so colour by the same field (``color=alt.Color("cell_line:N")``) and they match
        (colour is a lookup, so no sort param is needed, unlike ``add_comparisons``).
        Readouts stack in the ``position`` corner, each a colour swatch (matching the series)
        plus the coefficient in neutral ink; one record is registered per group. Note: with
        ``ci=True``, give your scatter an explicit
        y-axis title (``alt.Y("val:Q", title="…")``) - otherwise Vega merges the band's
        internal upper-bound field into the axis title (a Vega title-merge quirk that also
        affects the single-series ``ci`` path).
    line:
        Draw the OLS fit line. Default ``True``. Only applies to ``method="pearson"``
        (a no-op for the rank methods). Set ``False`` to suppress it and, e.g., compose
        your own line from the returned/recorded slope and intercept.
    position:
        Corner preset (an ``add_text`` position, e.g. ``'topLeft'``) for the readout.
        Default ``'topLeft'``. ``None`` computes the result for the report/metadata but
        draws no label.
    label:
        Override string for the corner readout. ``None`` builds it from the parts below.
    coefficient:
        Pearson only — which statistic the readout shows: ``'r'`` (default), ``'r2'``
        (just ``r²``, Excel-trendline style), or ``'both'``. Ignored for the rank kinds
        (they always show ``ρ``/``τ``).
    includePvalue:
        Append the p-value to the readout. Default ``False``.
    includeEquation:
        Pearson only — append the fit equation ``, y = 0.84x + 0.27``. Default ``False``.
    verbose:
        Shortcut for the fullest readout: ``True`` is equivalent to
        ``coefficient="both", includePvalue=True, includeEquation=True`` (and overrides
        those three). Default ``False``. So the default readout is just ``r = 0.87``
        (Pearson) / ``ρ = 0.81`` (rank); ``verbose=True`` gives
        ``r = 0.87, r² = 0.76, P < 0.001, y = 0.84x + 0.27``.
    offsetX, offsetY:
        Pixel nudges for the readout, forwarded to ``add_text``.
    fontSize:
        Font size of the readout. Defaults to the theme's primary ``fontSize``
        (``7`` under the built-in defaults), matching the axis font.
    sigFigs, notation:
        Significant figures / number format for the readout (coefficient, r², p-value,
        and fit equation), as in ``add_comparisons``. ``sigFigs=None`` reads the theme.
    color, strokeWidth, strokeDash, opacity:
        Curated style overrides for the fit line (same four knobs as ``add_rule``). Each
        defaults to ``None`` → the line inherits the theme's ``mark_line`` config; set one
        to override just that property.
    lineStyle:
        A dict of raw ``mark_line`` properties merged in last, so any Vega-Lite line
        property is reachable (e.g. ``{"interpolate": "monotone", "strokeCap": "round"}``).
        Keys here **override** the curated ``color``/``strokeWidth``/etc. above.
    ci:
        Draw a shaded interval band around the OLS fit (Pearson only). ``False``
        (default) → no band. ``True`` → a 95% band. A float in ``(0, 1)`` → that
        confidence level (e.g. ``0.99``). The band is hyperbolic - narrowest at the
        mean of ``x``, widening toward the extremes.
    interval:
        Which band ``ci`` draws: ``'confidence'`` (default, the interval for the mean
        response - how well the *line* is pinned down) or ``'prediction'`` (the wider
        interval for a single new observation).
    ciColor:
        Fill colour of the band. ``None`` (default) inherits the fit line's ``color``,
        falling back to the theme's mark colour (black / white, darkmode-aware). Because
        the default resolves darkmode at build time, wrap chart construction in a callable
        passed to ``ds.save()`` for correct light/dark exports (as with ``add_shade``).
    ciOpacity:
        Fill opacity of the band. Default ``0.15``.
    report:
        ``True`` prints the report (coefficient, r², p, fit, n) to stdout. Default
        ``False``. The record is queued for export metadata regardless.
    save:
        ``True`` writes the report to ``dysonsphere_report_<timestamp>.txt`` in the cwd;
        a string writes it to that directory.

    Examples
    --------
    ::

        scatter = alt.Chart(df).mark_point().encode(x="height:Q", y="weight:Q")
        scatter + ds.add_correlation(df, "height", "weight")                 # r + r² + OLS line
        scatter + ds.add_correlation(df, "height", "weight", method="spearman")  # ρ, no line
        scatter + ds.add_correlation(
            df, "height", "weight",
            color="#c0392b", lineStyle={"strokeDash": [4, 2]},
        )
    """
    from .statistics import _make_correlation_record, _ols_band, _run_correlation
    from .utils import ensure_polars, frame_checksum

    if verbose:  # shortcut for the fullest readout; overrides the individual toggles
        coefficient, includePvalue, includeEquation = "both", True, True
    if coefficient not in ("r", "r2", "both"):
        raise ValueError(f"coefficient must be 'r', 'r2', or 'both', got {coefficient!r}")

    df = ensure_polars(df)

    # Grouped mode: a fit + coefficient PER group of `groupCol` (e.g. one line per cell line), each
    # coloured to match the scatter's colour scale. A separate path so the single-series body below
    # is untouched; see the grouped-correlation design point.
    if groupCol is not None:
        return _add_grouped_correlation(
            df,
            xCol,
            yCol,
            groupCol,
            method=method,
            line=line,
            position=position,
            coefficient=coefficient,
            includePvalue=includePvalue,
            includeEquation=includeEquation,
            offsetX=offsetX,
            offsetY=offsetY,
            fontSize=fontSize,
            sigFigs=sigFigs,
            notation=notation,
            color=color,
            strokeWidth=strokeWidth,
            strokeDash=strokeDash,
            opacity=opacity,
            lineStyle=lineStyle,
            ci=ci,
            interval=interval,
            ciOpacity=ciOpacity,
            report=report,
            save=save,
        )

    x = df[xCol].cast(pl.Float64).to_numpy()
    y = df[yCol].cast(pl.Float64).to_numpy()
    result = _run_correlation(method, x, y)

    layers: list[Any] = []

    # Confidence / prediction band around the OLS fit - Pearson only, opt-in via `ci`.
    # Drawn BEFORE the line so it sits underneath. The band is hyperbolic, so sample the
    # x-range densely for a smooth area.
    if ci and result["slope"] is not None:
        import numpy as np

        level = 0.95 if ci is True else float(ci)
        if not 0.0 < level < 1.0:
            raise ValueError(f"ci must be True or a confidence level in (0, 1), got {ci!r}")
        if interval not in ("confidence", "prediction"):
            raise ValueError(f"interval must be 'confidence' or 'prediction', got {interval!r}")
        xs = np.linspace(float(x.min()), float(x.max()), 64)
        lo, hi = _ols_band(x, y, xs, level=level, kind=interval)
        # Lower bound rides on the yCol-named field so its derived axis title dedupes with the
        # base chart (same trick as the fit line); the upper bound goes in y2 (carries no title).
        band_df = pl.DataFrame({xCol: xs, yCol: lo, "__ci_hi": hi})
        # Match the fit line's colour (black/white, darkmode-aware at build → callable needed
        # for save() across backgrounds, like add_shade); pin the stroke off so config.area's
        # grey fill / stroke can't leak through.
        band_fill = ciColor or color or ("white" if _opt("darkmode") else "black")
        layers.append(
            alt.Chart(_internal_data(band_df))
            .mark_area(fill=band_fill, fillOpacity=ciOpacity, stroke=None, strokeWidth=0)
            .encode(
                x=alt.X(field=xCol, type="quantitative"),
                y=alt.Y(field=yCol, type="quantitative"),
                y2=alt.Y2(field="__ci_hi"),
            )
        )

    # OLS fit line — Pearson only (result["slope"] is None for rank kinds).
    if line and result["slope"] is not None:
        x0, x1 = float(x.min()), float(x.max())
        slope, intercept = result["slope"], result["intercept"]
        # The sidecar's fields carry the REAL column names: Vega-Lite merges a shared axis's
        # title by joining the layers' DISTINCT titles, so private names ("_x") concatenated
        # into the base chart's derived title ("height, _x"). Matching names dedupe to one.
        fit_df = pl.DataFrame({xCol: [x0, x1], yCol: [slope * x0 + intercept, slope * x1 + intercept]})
        # By default the line inherits the theme's mark_line config (no overrides).
        # Curated params override only what's passed; lineStyle overrides everything.
        mark_kwargs: dict[str, Any] = {}
        if color is not None:
            mark_kwargs["color"] = color
        if strokeWidth is not None:
            mark_kwargs["strokeWidth"] = strokeWidth
        if strokeDash is not None:
            mark_kwargs["strokeDash"] = _resolve_dash(strokeDash)
        if opacity is not None:
            mark_kwargs["opacity"] = opacity
        if lineStyle:
            mark_kwargs.update(lineStyle)
        # No title/axis override: with matching field names the derived titles dedupe, and
        # an explicit base title still beats this layer's derived one.  (Setting title=None
        # nulls the base title; axis=None suppresses the axis entirely — both wrong here.)
        # field=/type= rather than shorthand, so column names containing ':' survive.
        layers.append(
            alt.Chart(_internal_data(fit_df))
            .mark_line(**mark_kwargs)
            .encode(x=alt.X(field=xCol, type="quantitative"), y=alt.Y(field=yCol, type="quantitative"))
        )

    # Corner readout.
    if position is not None:
        text = (
            label
            if label is not None
            else _correlation_label(
                result,
                coefficient=coefficient,
                includePvalue=includePvalue,
                includeEquation=includeEquation,
                sigFigs=sigFigs if sigFigs is not None else _opt("sigFigs"),
                notation=notation,
            )
        )
        layers.append(
            add_text(
                text,
                position=position,
                offsetX=offsetX,
                offsetY=offsetY,
                fontSize=fontSize if fontSize is not None else _opt("fontSize"),
            )
        )

    # Structured record → export metadata; printed/written on request.
    record = _make_correlation_record(result, xCol, yCol, data_checksum=frame_checksum(df))
    marker = _emit_report(record, report, save)

    if not layers:
        layers.append(_empty_layer())
    # Tag with the marker name so save() matches this record to its chart (stripped on write).
    return cast(alt.LayerChart, alt.layer(*layers).properties(name=marker))

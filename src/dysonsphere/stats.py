"""Statistical annotations: significance brackets, omnibus labels, and correlation readouts.

This module builds Vega-Lite layers for the results computed by ``_statistics.py``:
``comparisons`` draws pairwise brackets and omnibus test labels, and ``correlation`` draws
coefficient readouts and OLS fit lines. Statistical results are registered in the
``_statistics._REPORTS`` registry and embedded in exports by ``save()`` using layer-name markers.
"""

import math
import numbers
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import altair as alt
import polars as pl

if TYPE_CHECKING:
    import pandas as pd

from ._statistics import (
    _clamp_p,
    _validate_computed_pvalue,
    _validate_family_size,
    _validate_group_ids,
    _validate_observations,
    _validate_pvalue,
)
from ._statistics import clear_stats as clear_stats
from .annotations import text as _text
from .theme import _opt
from .utils import (
    _SUP,
    _band_geometry,
    _empty_layer,
    _internal_data,
    _nested_band_centers,
    _nice_domain,
    _resolve_dash,
    _validate_category_order,
)

# Public names in ds.stats; they are not re-exported at the root.
__all__ = ["comparisons", "correlation", "clear_stats"]

# Length of a p-value bracket's end ticks in pixels.
_BRACKET_TICK_PX = 2.0

# Clearance a bracketStyle="drop" tick leaves above the data and above any bracket it passes.
_DROP_PAD_PX = 4.0

# P-value annotations


def _superscript(n: int) -> str:
    sign = "⁻" if n < 0 else ""
    return sign + "".join(_SUP[int(d)] for d in str(abs(n)))


def _scientific_parts(value: float, sigFigs: int) -> tuple[str, int]:
    """Return a rounded mantissa/exponent without arithmetic that underflows subnormal values."""
    text = format(value, f".{max(sigFigs - 1, 0)}e")
    mantissa, exponent = text.split("e")
    return f"{float(mantissa):.{sigFigs}g}", int(exponent)


def _format_pvalue(p: float, sigFigs: int = 3, notation: str | None = None, symbol: bool = True) -> str:
    # `%g` provides the requested precision and removes trailing zeros. Plain notation floors at
    # 0.001; scientific, e, and power notation preserve smaller values. Without the symbol, omit
    # both "P" and "= " but retain the comparison operator.
    if notation not in (None, "scientific", "e", "power"):
        raise ValueError(f"notation must be 'power', 'scientific', or 'e', got {notation!r}")
    lead = "P " if symbol else ""  # the statistical symbol
    eq = "= " if symbol else ""  # the equals is redundant once the symbol is gone
    if p == 0.0:
        # Treat zero as underflow and use the same minimum-normal bound as the report record.
        bound = _clamp_p(p)
        mantissa, exp = _scientific_parts(bound, sigFigs)
        if notation is None:
            return f"{lead}< 0.001"
        if notation == "e":
            return f"{lead}< {mantissa}e{exp:+03d}"
        return f"{lead}< {mantissa}×10{_superscript(exp)}"
    if notation is None:
        if p < 0.001:
            return f"{lead}< 0.001"
        return f"{lead}{eq}{p:.{sigFigs}g}"
    if notation == "power":
        exp = round(math.log10(p))
        return f"{lead}≈ 10{_superscript(exp)}"
    # scientific / e share the mantissa (at `sigFigs` sig figs) and exponent. Python's e-format
    # handles values below the normal range, unlike ``p / 10**exp``.
    mantissa, exp = _scientific_parts(p, sigFigs)
    if notation == "scientific":
        return f"{lead}{eq}{mantissa}×10{_superscript(exp)}"
    if notation == "e":
        return f"{lead}{eq}{mantissa}e{exp:+03d}"
    raise AssertionError("validated notation branch is unreachable")


def _format_label(p: float, label_style: str, sigFigs: int, notation: str | None) -> str:
    """Render one comparison's on-plot label: asterisks, ``P = …`` ("p"), or the bare value
    without the "P" symbol ("value")."""
    if label_style == "asterisks":
        return _format_asterisks(p)
    return _format_pvalue(p, sigFigs=sigFigs, notation=notation, symbol=(label_style != "value"))


def _format_asterisks(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _validate_ci_syntax(ci: float | bool | None) -> None:
    """Validate an interval level before method dispatch; zero remains an explicit disabled value."""
    if ci is None or ci is False or (isinstance(ci, numbers.Real) and ci == 0):
        return
    if ci is True:
        return
    if not isinstance(ci, numbers.Real):
        raise ValueError(f"ci must be True or a confidence level in (0, 1), got {ci!r}")
    level = float(ci)
    if not 0.0 < level < 1.0:
        raise ValueError(f"ci must be True or a confidence level in (0, 1), got {ci!r}")


# Comparison resolvers


_VALID_NOTATIONS = {None, "scientific", "e", "power"}
_VALID_CORRECTIONS = {None, "bonferroni", "holm", "fdr_bh", "fdr_by"}
_VALID_LABEL_STYLES = {"p", "asterisks", "value"}
_VALID_BRACKET_STYLES = {"line", "bracket", "drop"}


def _validate_notation_syntax(notation: Any, *, grouped: bool = False) -> None:
    """Validate notation even when no label will be rendered."""
    if isinstance(notation, dict):
        if grouped:
            raise ValueError("grouped comparisons do not support notation mappings; pass one notation value.")
        bad_values = [
            value
            for value in notation.values()
            if not isinstance(value, (str, type(None))) or value not in _VALID_NOTATIONS
        ]
        if bad_values:
            raise ValueError(f"notation dict values must be None/'scientific'/'e'/'power', got {bad_values}")
        for key in notation:
            if key == "test":
                continue
            if isinstance(key, str):
                raise ValueError("notation dict string keys must be 'test', got " + repr(key))
            if not isinstance(key, (tuple, list)) or len(key) != 2:
                raise ValueError("notation dict keys must be pair tuples or the string 'test'.")
        return
    if not isinstance(notation, (str, type(None))) or notation not in _VALID_NOTATIONS:
        raise ValueError(f"notation must be None/'scientific'/'e'/'power', got {notation!r}")


def _validate_comparison_syntax(
    *,
    test: str,
    post_hoc: str | None,
    correction: str | None,
    label_style: str,
    bracket_style: Any,
    notation: Any,
    test_label_position: Any,
    grouped: bool = False,
) -> None:
    """Validate enum and shape options before a dispatch path can silently ignore them."""
    from ._statistics import _OMNIBUS_TESTS, _PAIRWISE_TESTS

    valid_tests = _OMNIBUS_TESTS | _PAIRWISE_TESTS | _MATRIX_POSTHOCS
    if not isinstance(test, str) or test not in valid_tests:
        raise ValueError(f"Unknown test {test!r}. Choose from: {sorted(valid_tests)}")
    if grouped and post_hoc is not None:
        raise ValueError("grouped comparisons do not support postHoc; use a pairwise test directly.")
    if post_hoc is not None and (not isinstance(post_hoc, str) or post_hoc not in (_MATRIX_POSTHOCS | _PAIRWISE_TESTS)):
        raise ValueError(f"Unknown postHoc {post_hoc!r}. Choose from: {sorted(_MATRIX_POSTHOCS | _PAIRWISE_TESTS)}")
    if not isinstance(correction, (str, type(None))) or correction not in _VALID_CORRECTIONS:
        raise ValueError(f"correction must be None, 'bonferroni', 'holm', 'fdr_bh', or 'fdr_by', got {correction!r}")
    if not isinstance(label_style, str) or label_style not in _VALID_LABEL_STYLES:
        raise ValueError(f"labelStyle must be 'p', 'asterisks', or 'value', got {label_style!r}")
    if grouped and (not isinstance(bracket_style, str) or bracket_style not in _VALID_BRACKET_STYLES):
        raise ValueError(f"grouped comparisons take bracketStyle 'bracket', 'line', or 'drop', got {bracket_style!r}.")
    if isinstance(bracket_style, dict):
        bad_values = [
            value
            for value in bracket_style.values()
            if not isinstance(value, str) or value not in _VALID_BRACKET_STYLES
        ]
        if bad_values:
            raise ValueError(f"bracketStyle dict values must be 'line', 'bracket', or 'drop', got {bad_values!r}")
        for key in bracket_style:
            if not isinstance(key, (tuple, list)) or len(key) != 2:
                raise ValueError("bracketStyle dict keys must be pair tuples.")
    elif not isinstance(bracket_style, str) or bracket_style not in _VALID_BRACKET_STYLES:
        raise ValueError(f"bracketStyle must be 'line', 'bracket', 'drop', or a dict, got {bracket_style!r}")
    _validate_notation_syntax(notation, grouped=grouped)
    if test_label_position == "auto":
        return
    if test_label_position is not None:
        from .annotations import _TEXT_PRESETS

        if not isinstance(test_label_position, str) or test_label_position not in _TEXT_PRESETS:
            raise ValueError(
                f"testLabelPosition must be 'auto', None, or one of {sorted(_TEXT_PRESETS)}, "
                f"got {test_label_position!r}"
            )


def _validate_statistical_data(
    df: pl.DataFrame, x_col: str, y_col: str, *group_cols: str, numeric_x: bool = False
) -> None:
    """Validate only columns used by a statistical annotation.

    Used grouping and value columns must exist and contain no missing or non-finite values. Other
    dataframe columns are ignored.
    """
    for column in (x_col, y_col, *group_cols):
        if column not in df.columns:
            raise ValueError(f"statistical column {column!r} is not present in the data.")
    if df.is_empty():
        raise ValueError(f"statistical column {y_col!r} has no observations.")
    if not numeric_x:
        _validate_group_ids(df[x_col].to_list(), x_col)
    for column in group_cols:
        if column != x_col or numeric_x:
            _validate_group_ids(df[column].to_list(), column)
    value_columns = (x_col, y_col) if numeric_x else (y_col,)
    if not group_cols:
        for column in value_columns:
            _validate_observations(df[column].to_list(), column)
        return
    # Validate per primary group so an invalid observation identifies the affected series.
    for group in df[group_cols[0]].unique(maintain_order=True).to_list():
        subset = df.filter(pl.col(group_cols[0]) == group)
        for column in value_columns:
            _validate_observations(subset[column].to_list(), column, group)


def _resolve_method(test: str, post_hoc: str | None, pvalues: Any, is_omnibus: bool) -> str | None:
    """Resolve the comparison method: post-hoc for omnibus, ``test`` for pairwise, or ``None``
    for supplied final p-values. Omnibus mode still runs its omnibus test when p-values are supplied.
    """
    from ._statistics import _POSTHOC_DEFAULTS

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
    _validate_notation_syntax(notation)
    if isinstance(notation, dict):
        pair_map = {frozenset(k): v for k, v in notation.items() if not isinstance(k, str)}
        return notation.get("test"), [pair_map.get(frozenset(p)) for p in (pairs or [])]
    return notation, [notation] * len(pairs or [])


def _resolve_bracket_styles(bracket_style: str | dict[Any, Any], pairs: list[tuple[str, str]]) -> list[str]:
    """Per-pair bracket style: a string applies to all; a dict maps a pair (order-insensitive) to
    its style, with ``"bracket"`` as the fallback for unlisted pairs."""
    valid = {"line", "bracket", "drop"}
    if isinstance(bracket_style, dict):
        bad = set(bracket_style.values()) - valid
        if bad:
            raise ValueError(f"bracketStyle dict values must be 'line', 'bracket', or 'drop', got {sorted(bad)}")
        style_map = {frozenset(k): v for k, v in bracket_style.items()}
        return [style_map.get(frozenset(p), "bracket") for p in pairs]
    if bracket_style not in valid:
        raise ValueError(f"bracketStyle must be 'line', 'bracket', 'drop', or a dict, got {bracket_style!r}")
    return [bracket_style] * len(pairs)


def _all_pairs(items: list[Any]) -> list[tuple[Any, Any]]:
    """Every unique unordered pair of ``items``, in ``items`` order."""
    return [(items[i], items[j]) for i in range(len(items)) for j in range(i + 1, len(items))]


def _resolve_pairs(
    pairs: list[tuple[str, str]] | str | None, items: list[Any], what: str
) -> list[tuple[str, str]] | None:
    """Expand the ``pairs="all"`` shorthand to every unique pair of ``items``; pass anything else
    through untouched. ``what`` names the compared thing for the error messages."""
    if not isinstance(pairs, str):
        return pairs
    if pairs != "all":
        raise ValueError(f"pairs must be a list of tuples, 'all', or None, got {pairs!r}.")
    if len(items) < 2:
        raise ValueError(f"pairs='all' needs at least two {what} to compare, got {items}.")
    return _all_pairs(items)


def _check_coverage(
    df: pl.DataFrame, col: str, values: list[Any] | None, param_name: str, noun: str, tail: str
) -> None:
    """Require an explicit scale order to cover the observed values exactly once."""
    if values is None:
        return
    _validate_category_order(df, col, values, name=param_name, tail=tail)


def _stack_levels(spans: list[tuple[int, int]]) -> list[int]:
    """Assign each ``(lo, hi)`` index span a level using greedy interval scheduling.

    Spans are processed by left endpoint, then right endpoint, and assigned to the lowest level
    with no overlapping span. The returned levels follow input order. This ordering groups spans
    with the same left endpoint. For interval graphs, greedy coloring in left-endpoint order uses
    the maximum clique size and therefore the minimum number of levels. In a comparison of pair
    subsets, ordering by span length instead used one extra level for about 12% of subsets.
    Spans that share an endpoint overlap because their brackets would otherwise render as one
    continuous line."""
    order = sorted(range(len(spans)), key=lambda i: (min(spans[i]), max(spans[i])))
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
    None. The gap targets ~10 px for brackets / ~8 px for lines and the tick height is
    ``_BRACKET_TICK_PX``, both converted from px to data units via ``chart_height``; ``y_step`` is
    ``1.75 * y_pad``. All three guard ``chart_height == 0``."""
    if y_pad is None:
        y_pad = (10.0 if any_bracket else 8.0) * y_range / chart_height if chart_height else 0.0
    if tick_height is None:
        tick_height = _BRACKET_TICK_PX * y_range / chart_height if chart_height else 0.0
    if y_step is None:
        y_step = y_pad * 1.75
    return y_pad, tick_height, y_step


def _bracket_offsets(
    anchors: list[float],
    spans: list[tuple[int, int]],
    gap_px: float,
    step_px: float,
    to_px,
    downward: bool = False,
) -> list[tuple[float, float]]:
    """Return each bracket's data anchor and pixel offset.

    Overlapping brackets form a ladder with rung spacing ``step_px``. Each connected component
    of the span-overlap graph gets its own ladder, so disjoint comparisons are placed independently.
    The anchor and offsets place the ladder as close to the data as the required ``gap_px`` allows.

    For each component, two rung orders are considered: lexicographic span order and data-demand
    order (brackets nearest the data first). Each is scored by rung count and total pixel distance
    above the compared data; ties favor lexicographic order. This groups comparisons with a shared
    left endpoint when that does not increase either score.

    Rungs use constant pixel offsets from a shared data anchor. Their spacing therefore does not
    depend on the y scale. ``to_px`` estimates the rendered domain only to position the ladder;
    an estimate error can shift the ladder but does not change rung spacing. This also works when
    facets, concatenation, or ``add_multilabel`` rename the y scale."""
    n = len(anchors)
    if not n:
        return []
    # smaller px = higher on screen, so an upward ladder subtracts the gap and a downward one adds
    _dir = 1.0 if downward else -1.0
    required = [to_px(anchors[i]) + _dir * gap_px for i in range(n)]

    def _overlap(i: int, j: int) -> bool:
        return not (spans[i][1] < spans[j][0] or spans[i][0] > spans[j][1])

    # Connected components of the overlap graph; linked spans share one ladder.
    comp = list(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if _overlap(i, j) and comp[i] != comp[j]:
                old, keep = comp[j], comp[i]
                comp = [keep if c == old else c for c in comp]

    pick = max if downward else min

    def _assign(order: list[int]) -> dict[int, int]:
        """Greedy rung per bracket, in the given order: lowest rung it doesn't collide on."""
        level: dict[int, int] = {}
        for i in order:
            taken = {level[j] for j in level if _overlap(i, j)}
            lvl = 0
            while lvl in taken:
                lvl += 1
            level[i] = lvl
        return level

    placed_out: list[tuple[float, float]] = [(anchors[i], 0.0) for i in range(n)]
    for root in set(comp):
        members = [i for i in range(n) if comp[i] == root]
        # Score both rung orders by rung count, then total distance above the compared data.
        candidates = (
            sorted(members, key=lambda i: (spans[i][0], spans[i][1])),
            sorted(members, key=lambda i: (_dir * required[i], i)),
        )
        best: tuple[tuple[int, float], dict[int, int], float] | None = None
        for order in candidates:
            level = _assign(order)
            base = pick(required[i] - _dir * level[i] * step_px for i in members)
            float_px = sum(_dir * ((base + _dir * level[i] * step_px) - required[i]) for i in members)
            # Rounding prevents floating-point noise from deciding a mathematical tie.
            score = (max(level.values()), round(float_px, 6))
            if best is None or score < best[0]:
                best = (score, level, base)
        assert best is not None
        _, level, base = best
        # Use one anchor for the ladder so rung spacing is measured from a single data value.
        shared = (min if downward else max)(anchors[i] for i in members)
        shared_px = to_px(shared)
        for i in members:
            placed_out[i] = (shared, _dir * ((base + _dir * level[i] * step_px) - shared_px))
    return placed_out


def _drop_tick_lengths(
    bar_px: list[float],
    spans: list[tuple[int, int]],
    group_hi_px: list[float],
    styles: list[str],
    col_px: list[float],
    label_edge: list[tuple[float, float, float]],
    reverse_flags: list[bool] | None = None,
    group_lo_px: list[float] | None = None,
) -> list[tuple[float, float]]:
    """Per-bracket ``(left, right)`` end-tick lengths in px, for ``bracketStyle='drop'``.

    A drop tick reaches from its bar toward its OWN endpoint group's data, stopping
    ``_DROP_PAD_PX`` short of it, and stops the same distance short of anything else it would
    run through: another bracket's bar in that column, or another bracket's label, whose
    ``(x_lo, x_hi, edge_px)`` box is given in ``label_edge``. The label matters because a bracket
    stacked beyond a wider one still crosses that one's label, which sits off its bar.

    Everything is measured as distance travelled along the tick's own direction, so an upward
    ``reverse`` tick uses the same comparisons as a downward one. A downward tick approaches a
    group's maximum (``group_hi_px``), an upward one its minimum (``group_lo_px``, defaulting to
    ``group_hi_px`` when no bracket is reversed).

    Falls back to ``_BRACKET_TICK_PX`` where there is no room to drop, and below that only when
    even a fixed cap would touch. Non-drop brackets get the fixed length.
    """
    revs = reverse_flags or [False] * len(spans)
    near = group_lo_px if group_lo_px is not None else group_hi_px
    out: list[tuple[float, float]] = []
    for i, (lo, hi) in enumerate(spans):
        if styles[i] != "drop":
            out.append((_BRACKET_TICK_PX, _BRACKET_TICK_PX))
            continue
        sign = -1.0 if revs[i] else 1.0  # +1 travels down the screen, -1 travels up
        ends: list[float] = []
        for col in (lo, hi):
            x = col_px[col]

            def _dist(p: float, _s: float = sign, _b: float = bar_px[i]) -> float:
                return _s * (p - _b)

            _edge = near[col] if revs[i] else group_hi_px[col]
            padded, hard = _dist(_edge) - _DROP_PAD_PX, _dist(_edge)
            for j, (j_lo, j_hi) in enumerate(spans):
                if j == i or _dist(bar_px[j]) <= 0:  # only what lies ahead of the tick blocks it
                    continue
                if j_lo <= col <= j_hi:
                    padded, hard = min(padded, _dist(bar_px[j]) - _DROP_PAD_PX), min(hard, _dist(bar_px[j]))
                lx0, lx1, ledge = label_edge[j]
                if lx0 <= x <= lx1:
                    padded, hard = min(padded, _dist(ledge) - _DROP_PAD_PX), min(hard, _dist(ledge))
            # Use the padded target for the drop, but keep the cap at least clear of the nearest
            # label or bracket.
            ends.append(max(0.0, min(max(_BRACKET_TICK_PX, padded), hard)))
        out.append((ends[0], ends[1]))
    return out


def _emit_report(record: dict[str, Any], report: bool, save: bool | str | Path) -> str:
    """Register ``record`` for the export metadata and, if requested, print the rendered report
    and/or write it to a timestamped ``.txt``. Returns the marker name tagged onto the layer."""
    from datetime import datetime
    from pathlib import Path

    from ._statistics import _register_report, _render_report

    marker = _register_report(record)
    if report or save:
        report_text = _render_report(record)
        if report:
            print(report_text)
        if save:
            directory = Path(save) if not isinstance(save, bool) else Path.cwd()
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
    width: float | None = None,
    strokeWidth: float | None = None,
    fontSize: float | None = None,
    reverse: bool = False,
    sigFigs: int = 3,
    notation: str | None = None,
    offset_px: float = 0.0,
    tick_px: float | tuple[float, float] | None = None,
    tick_data: tuple[float, float] | None = None,
    domain_max: float | None = None,
) -> alt.LayerChart:
    from scipy import stats as _stats

    if pvalue is None:
        if df is None or x_col is None or y_col is None:
            raise ValueError("df, x_col, and y_col are required when pvalue is not provided.")

        if test == "tukey_hsd":
            _cats = categories if categories is not None else sorted(df[x_col].unique().to_list())
            all_groups = [df.filter(pl.col(x_col) == cat)[y_col].to_numpy() for cat in _cats]
            result = _stats.tukey_hsd(*all_groups)
            pvalue = _validate_computed_pvalue(
                result.pvalue[_cats.index(group1)][_cats.index(group2)],
                f"tukey_hsd comparison {group1!r} vs {group2!r}",
            )
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
            pvalue = _validate_computed_pvalue(_tests[test](), f"{test} comparison {group1!r} vs {group2!r}")
    else:
        pvalue = _validate_pvalue(pvalue, "p-value")

    # Bonferroni correction (skip for tukey_hsd – correction is built in)
    if correction == "bonferroni" and test != "tukey_hsd":
        pvalue = min(pvalue * n_comparisons, 1.0)

    label = _format_label(pvalue, label_style, sigFigs, notation)

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

    if width is None:
        width = _opt("width")
    if strokeWidth is None:
        strokeWidth = _opt("axisWidth")
    if fontSize is None:
        fontSize = _opt("fontSize")

    if categories is None:
        if df is None or x_col is None:
            raise ValueError("categories is required when df and x_col are not provided.")
        categories = sorted(df[x_col].unique().to_list())

    g1_idx = categories.index(group1)
    g2_idx = categories.index(group2)

    stroke_cap = _opt("strokeCap")
    # Keep the anchor in data units and apply the lift as a pixel offset, outside the domain.
    _sign = 1 if reverse else -1
    _rule_kwargs = {
        "strokeWidth": strokeWidth,
        "strokeDash": [0, 0],
        "strokeCap": stroke_cap,
    }
    # A pixel offset is independent of the y domain and survives facet/concat composition.
    if offset_px:
        _rule_kwargs["yOffset"] = _sign * offset_px

    # Asterisk labels need less baseline clearance than alphanumeric labels such as "ns".
    # Reverse labels use the top baseline so the text extends below the bar.
    _dy_mag = 2 if label_style == "asterisks" and label != "ns" else 4
    text_dy = (_dy_mag if reverse else -_dy_mag) + _sign * offset_px
    text_baseline = "top" if reverse else None
    # Use pixel offsets for end legs in pixel mode and data coordinates otherwise.
    tick_y2 = y if tick_px is not None else (y + tick_height if reverse else y - tick_height)
    # Each drop tick can have a different length, so its mark properties are set separately.
    _lens = (tick_px, tick_px) if isinstance(tick_px, (int, float)) else tick_px
    _tick_kwargs_l, _tick_kwargs_r = dict(_rule_kwargs), dict(_rule_kwargs)
    # Drop ticks end at data positions. This layer cannot read the base y domain, so converting
    # pixel lengths using an estimated domain can place a tick through the data.
    tick_y2_l, tick_y2_r = tick_data if tick_data is not None else (tick_y2, tick_y2)
    if _lens is not None and tick_data is None:
        _tick_kwargs_l["y2Offset"] = _sign * offset_px - _sign * _lens[0]
        _tick_kwargs_r["y2Offset"] = _sign * offset_px - _sign * _lens[1]

    # Set domain_max on one bracket layer. Its explicit bound wins the scale merge and makes
    # room for a top-preset test label. Only the upper bound changes; the lower bound, zero,
    # nice-rounding, and other scale settings are preserved.
    _y_enc = alt.Y("y:Q") if domain_max is None else alt.Y("y:Q", scale=alt.Scale(domainMax=domain_max))
    # Pixel positions avoid adding an x scale that cannot merge when the base resolves x
    # independently, as in mark_violin.
    geo = _band_geometry(len(categories), width)
    x1_px, x2_px = geo.centers[g1_idx], geo.centers[g2_idx]
    x_mid_px = (x1_px + x2_px) / 2
    bar = (
        alt.Chart(_internal_data([{"x": group1, "x2": group2, "y": y}]))
        .mark_rule(**_rule_kwargs)
        .encode(
            x=alt.value(x1_px),
            x2=alt.value(x2_px),
            y=_y_enc,
        )
    )
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

    if bracket_style in ("bracket", "drop"):
        left_tick = (
            alt.Chart(_internal_data([{"x": group1, "y": y, "y2": tick_y2_l}]))
            .mark_rule(**_tick_kwargs_l)
            .encode(
                x=alt.value(x1_px),
                y=alt.Y("y:Q"),
                y2="y2:Q",
            )
        )
        right_tick = (
            alt.Chart(_internal_data([{"x": group2, "y": y, "y2": tick_y2_r}]))
            .mark_rule(**_tick_kwargs_r)
            .encode(
                x=alt.value(x2_px),
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
    width: float,
    fontSize: float,
    offset_px: float = 0.0,
) -> alt.Chart:
    """Place a reference-mode p-value label over one group's band at data coordinate ``y``.

    The comparison to the reference is implicit, so the label has no bracket. ``offset_px`` sets a
    fixed pixel offset; this layer does not calculate label collisions."""
    x_px = _band_geometry(len(categories), width).centers[categories.index(group)]
    return (
        alt.Chart(_internal_data([{"y": y, "label": label}]))
        .mark_text(align="center", baseline="bottom", fontSize=fontSize, dy=-4 - offset_px)
        .encode(x=alt.value(x_px), y=alt.Y("y:Q"), text="label:N")
    )


_MATRIX_POSTHOCS = {"tukey_hsd", "dunn", "nemenyi", "games_howell"}


def _omnibus_label(result, *, verbose: bool, notation: str | None, sigFigs: int) -> str:
    """Build the terse or verbose corner label for an omnibus result.

    Omnibus labels use p-value notation. ``labelStyle="asterisks"`` applies only to pairwise
    brackets.
    """
    p_str = _format_pvalue(result.pvalue, sigFigs=sigFigs, notation=notation)
    if not verbose:
        return f"{result.name} {p_str}"
    df_str = ", ".join(str(d) for d in result.df)
    stat = f"{result.stat_symbol}({df_str}) = {result.stat:.2f}"
    eff = f"{result.effect_name} = {result.effect_size:.2f}"
    return f"{result.name} {stat}, {p_str}, {eff}"


def _bracket_pvalues(
    method: str,
    groups: list[Any],
    categories: list[Any],
    pairs: list[tuple[str, str]],
    correction: str | None,
    nComparisons: int | None,
) -> tuple[list[float], list[float] | None, list[float] | None]:
    """Return final, raw, and correction-input p-values in requested pair order.

    Correction inputs are returned only when intrinsically adjusted results receive an additional
    generic correction. Unavailable lists are ``None``; each underlying test is calculated once.
    """
    from scipy import stats as _stats

    from ._statistics import _INTRINSICALLY_ADJUSTED, _PAIRWISE_TESTS, _adjust, _post_hoc_matrix

    idx = {c: i for i, c in enumerate(categories)}
    if method in _MATRIX_POSTHOCS:
        matrix_inputs: list[float] = []
        mat = _post_hoc_matrix(
            method,
            groups,
            correction,
            nComparisons,
            labels=categories,
            correction_input_values=matrix_inputs,
        )
        final = [float(mat[idx[g1]][idx[g2]]) for g1, g2 in pairs]
        if method == "tukey_hsd":
            return final, None, None
        input_lookup = {frozenset(pair): value for pair, value in zip(_all_pairs(categories), matrix_inputs)}
        inputs = [input_lookup[frozenset((g1, g2))] for g1, g2 in pairs]
        if method in _INTRINSICALLY_ADJUSTED:
            return final, None, inputs if correction is not None else None
        return final, inputs, None
    if method in _PAIRWISE_TESTS:
        funcs = {
            "mannwhitneyu": lambda a, b: _stats.mannwhitneyu(a, b, alternative="two-sided").pvalue,
            "ttest_ind": lambda a, b: _stats.ttest_ind(a, b).pvalue,
            "ttest_rel": lambda a, b: _stats.ttest_rel(a, b).pvalue,
            "wilcoxon": lambda a, b: _stats.wilcoxon(a, b).pvalue,
        }
        raw = [
            _validate_computed_pvalue(
                funcs[method](groups[idx[g1]], groups[idx[g2]]), f"{method} comparison {g1!r} vs {g2!r}"
            )
            for g1, g2 in pairs
        ]
        if correction is not None:
            m = (
                len(pairs)
                if nComparisons is None
                else _validate_family_size(nComparisons, len(pairs), correction=correction)
            )
            return _adjust(raw, correction, m), raw, None
        return raw, raw, None
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
    fontSize: float,
    width: float,
    offset_px: float = 0.0,
    tick_px: float | tuple[float, float] | None = None,
    tick_data: tuple[float, float] | None = None,
    reverse: bool = False,
) -> alt.LayerChart:
    """Build one bracket between two xOffset levels within a category.

    The bar and optional end ticks use the shared xOffset scale, with a sort order matching the
    bars. The label is positioned in pixels at the bracket midpoint. ``reverse`` places the
    bracket below the groups with the ticks pointing up.
    """
    rk: dict[str, Any] = {"strokeWidth": strokeWidth, "strokeDash": [0, 0], "strokeCap": _opt("strokeCap")}
    # Anchor in data coordinates and apply the pixel offset at render time, independent of the y domain.
    _sign = 1 if reverse else -1
    if offset_px:
        rk["yOffset"] = _sign * offset_px
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
    # Alphanumeric labels need more baseline clearance than asterisk labels.
    _dym = 2 if label_style == "asterisks" and label != "ns" else 4
    dy = (_dym if reverse else -_dym) + _sign * offset_px
    # The subset xOffset domain would reorder the bars. Use the bracket midpoint in pixels;
    # the category band center is not the midpoint for an asymmetric pair.
    _sub = _nested_band_centers(len(categories), len(level_order), width)[categories.index(category)]
    _mid_px = (_sub[level_order.index(level1)] + _sub[level_order.index(level2)]) / 2
    text = (
        alt.Chart(_internal_data([{"__y": y, "__label": label}]))
        .mark_text(align="center", fontSize=fontSize, dy=dy, **({"baseline": "top"} if reverse else {}))
        .encode(x=alt.value(_mid_px), y=alt.Y("__y:Q"), text="__label:N")
    )
    if bracket_style in ("bracket", "drop"):
        # In pixel mode, y2Offset sets each tick's length. Drop ticks can have different lengths,
        # so each end uses a separate layer.
        _lens = (tick_px, tick_px) if isinstance(tick_px, (int, float)) else tick_px
        legs = []
        _ends = tick_data if tick_data is not None else (None, None)
        for level, tlen, tend in zip((level1, level2), _lens if _lens is not None else (None, None), _ends):
            tk = dict(rk)
            y2_val = y + tick_height if reverse else y - tick_height
            if tend is not None:
                # Drop ticks end at data positions. This layer cannot read the base chart's y
                # domain, so converting pixel lengths using an estimated domain can cross the data.
                y2_val = tend
            elif tlen is not None:
                tk["y2Offset"] = _sign * offset_px - _sign * tlen
                y2_val = y
            legs.append(
                alt.Chart(_internal_data([{x_col: category, xoffset_col: level, "__y": y, "__y2": y2_val}]))
                .mark_rule(**tk)
                .encode(x=xenc, xOffset=xoff, y=alt.Y("__y:Q"), y2="__y2:Q")
            )
        return cast(alt.LayerChart, alt.layer(top, *legs, text))
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
    fontSize: float,
    offset_px: float = 0.0,
) -> alt.Chart:
    """Place a grouped reference-mode p-value label over one (category, level) sub-bar.

    The label uses the chart's shared x and xOffset scales, with sort orders matching the bars.
    ``offset_px`` sets its pixel distance from the data anchor, independent of the rendered y domain.
    """
    dy = -(2 if label_style == "asterisks" and label != "ns" else 4) - offset_px
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
    """Return the lookup key for a grouped comparison.

    Reference mode uses ``(category, level)``; bracket mode uses
    ``(category, frozenset(pair))`` so pair order does not matter.
    """
    return (cat, l2) if is_reference else (cat, frozenset((l1, l2)))


def _grouped_desc(cat: Any, l1: str, l2: str, is_reference: bool) -> str:
    """Human-readable descriptor of a grouped comparison, for error messages."""
    return f"({cat!r}, {l2!r})" if is_reference else f"({cat!r}, ({l1!r}, {l2!r}))"


def _normalize_grouped_map(mapping: Any, is_reference: bool, name: str) -> dict[Any, Any]:
    """Normalize a user ``{(category, level|pair): value}`` dict to the internal ``_grouped_key``
    scheme. Reference keys are ``(category, level)``; bracket keys are ``(category, (l1, l2))``."""
    if not isinstance(mapping, dict):
        shape = "(category, level)" if is_reference else "(category, (level1, level2))"
        raise ValueError(f"grouped {name} must be a dict keyed by {shape}, got {type(mapping).__name__}.")
    out: dict[Any, Any] = {}
    for key, val in mapping.items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError(f"grouped {name} keys must be (category, level|pair) tuples, got {key!r}.") from None
        cat, second = key
        if not is_reference and (not isinstance(second, (tuple, list)) or len(second) != 2):
            raise ValueError(f"grouped {name} keys must be (category, (level1, level2)) tuples, got {key!r}.")
        out[(cat, second) if is_reference else (cat, frozenset(second))] = val
    return out


def _add_grouped_comparisons(
    df: pl.DataFrame,
    x_col: str,
    y_col: str,
    xoffset_col: str,
    pairs: list[tuple[str, str]] | str | None,
    *,
    reference: Any,
    reverse: list[tuple[str, str]] | None,
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
    testLabelPosition: str | None,
    testLabel: str | None,
    testLabelOffsetX: float,
    testLabelOffsetY: float,
    testLabelX: Any,
    testLabelY: Any,
    sigFigs: int | None,
    tickHeight: float | None,
    strokeWidth: float | None,
    fontSize: float | None,
    yPad: float | None,
    yStep: float | None,
    categories: list[Any] | None,
    width: float | None,
    report: bool,
    save: bool | str | Path,
) -> alt.LayerChart:
    """Compare xOffset levels within each x-category.

    Draw one bracket per category and pair. Each bracket is positioned using that category's data.
    P-values are computed per category and adjusted over the full family when ``correction`` is set.
    One report record is registered, with comparisons labeled ``"<category> (<level>)"``.
    """
    from scipy import stats as _stats

    from ._statistics import _TEST_DISPLAY, _adjust, _describe_all, _make_record, _pair_effect
    from .utils import _frame_checksum

    # Require complete category and level orders so the shared scales match the chart's bar order.
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
    # Resolve first so reference mode can reject an explicitly supplied pairs value.
    pairs = _resolve_pairs(pairs, level_order, f"xOffset {xoffset_col!r} levels")

    # Record explicit spacing arguments; any one selects data-unit placement below.
    # Reference mode compares each non-reference level with `reference` within each category,
    # placing a p-value label above each compared sub-bar without a bracket.
    _y_step_arg, _y_pad_arg = yStep, yPad
    is_reference = reference is not None
    if is_reference:
        if reference not in level_order:
            raise ValueError(f"reference {reference!r} is not a level of xOffset {xoffset_col!r}: {level_order}.")
        if pairs is not None:
            raise ValueError("reference derives its own comparisons; don't also pass pairs.")
        pairs = [(reference, lvl) for lvl in level_order if lvl != reference]

    if pairs is None:
        if len(level_order) == 2:
            pairs = [(level_order[0], level_order[1])]
        else:
            raise ValueError(
                f"pairs is required when xOffset has more than two levels (levels: {level_order}); "
                "pass e.g. pairs=[('Ctrl', 'Low'), ('Ctrl', 'High')]."
            )
    if len(pairs) == 0:
        raise ValueError("pairs must not be empty when provided.")
    _lvls = set(level_order)
    for l1, l2 in pairs:
        if l1 not in _lvls or l2 not in _lvls:
            raise ValueError(f"pair ({l1!r}, {l2!r}) names a level not in xOffset {xoffset_col!r} {level_order}.")

    _valid_tests = {"mannwhitneyu", "ttest_ind", "ttest_rel", "wilcoxon"}
    if test not in _valid_tests:
        raise ValueError(f"grouped comparisons (xOffset) support {sorted(_valid_tests)}, got {test!r}.")
    if labelStyle not in ("p", "asterisks", "value"):
        raise ValueError(f"labelStyle must be 'p', 'asterisks', or 'value', got {labelStyle!r}.")
    if not isinstance(bracketStyle, str) or bracketStyle not in ("bracket", "line", "drop"):
        raise ValueError(f"grouped comparisons take bracketStyle 'bracket', 'line', or 'drop', got {bracketStyle!r}.")
    notation_val = notation
    if isinstance(notation, dict):
        raise ValueError("grouped comparisons do not support notation mappings; pass one notation value.")
    if isinstance(yPositions, list):
        raise ValueError("grouped yPositions accepts a number or a supported dict, not a list.")
    if yPositions is not None and (isinstance(yPositions, bool) or not isinstance(yPositions, (numbers.Real, dict))):
        raise ValueError("grouped yPositions accepts a number or a supported dict, not this value.")
    if yStart is not None and (isinstance(yStart, bool) or not isinstance(yStart, (numbers.Real, dict))):
        raise ValueError("grouped yStart accepts a number or a category mapping, not this value.")

    width = width if width is not None else _opt("width")
    chart_height = _opt("height")
    fontSize = fontSize if fontSize is not None else _opt("fontSize")
    strokeWidth = strokeWidth if strokeWidth is not None else _opt("axisWidth")
    effective_sigfigs = sigFigs if sigFigs is not None else _opt("sigFigs")

    y_all = df[y_col].cast(pl.Float64)
    y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
    if tickHeight is not None and bracketStyle == "drop":
        raise ValueError(
            "tickHeight sets a fixed end-tick length, which bracketStyle='drop' computes per end. "
            "Pass one or the other."
        )
    # Automatic tick height is measured in pixels.
    _tick_arg = tickHeight
    yPad, tickHeight, yStep = _resolve_y_spacing(
        bracketStyle in ("bracket", "drop"), y_range, chart_height, yPad, tickHeight, yStep
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

    # Comparison keys follow category order, then pair order.
    all_keys = [_grouped_key(cat, l1, l2, is_reference) for cat in categories for l1, l2 in pairs]

    # Supplied p-values skip tests and correction and must cover every comparison exactly.
    pval_map = _normalize_grouped_map(pvalues, is_reference, "pvalues") if pvalues is not None else None
    if pval_map is not None:
        pval_map = {key: _validate_pvalue(value, f"pvalues entry {key!r}") for key, value in pval_map.items()}
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

    # Compute p-values and effects in the order used to build the layers.
    raw: list[float] = []
    effects: list[tuple[str | None, float | None]] = []
    for cat in categories:
        cdf = df.filter(pl.col(x_col) == cat)
        for l1, l2 in pairs:
            a = cdf.filter(pl.col(xoffset_col) == l1)[y_col].to_numpy()
            b = cdf.filter(pl.col(xoffset_col) == l2)[y_col].to_numpy()
            if pval_map is None:
                raw.append(_validate_computed_pvalue(_pval(a, b), f"{test} comparison {cat!r}"))
                effects.append(_pair_effect(a, b, parametric=parametric, paired=paired))
            else:
                raw.append(pval_map[_grouped_key(cat, l1, l2, is_reference)])
                effects.append((None, None))
    actual_family = len(raw)
    if nComparisons is not None:
        _validate_family_size(nComparisons, actual_family, correction=correction if pval_map is None else None)
    m = nComparisons if nComparisons is not None else actual_family
    # Supplied p-values are final; apply correction only to computed p-values.
    effective_correction = None if pval_map is not None else correction
    adj = raw if pval_map is not None else (_adjust(raw, correction, m) if correction else raw)

    # Each pair uses the same stacking level in every category because the spans are identical.
    lvl_idx = {lv: i for i, lv in enumerate(level_order)}
    pair_level = _stack_levels([(lvl_idx[l1], lvl_idx[l2]) for l1, l2 in pairs])

    # Compute descriptives for every (category, level) subset.
    desc_groups: list[Any] = []
    desc_labels: list[str] = []
    for cat in categories:
        cdf = df.filter(pl.col(x_col) == cat)
        for lv in level_order:
            values = cdf.filter(pl.col(xoffset_col) == lv)[y_col].to_list()
            desc_groups.append(_validate_observations(values, y_col, f"{cat!r} / {lv!r}"))
            desc_labels.append(f"{cat} ({lv})")
    descriptives = _describe_all(desc_groups, desc_labels)

    # yStart sets a scalar or per-category bracket base; yPositions takes precedence and can be
    # global, per-category, or per-comparison. Dict keys must use one form. Precedence is global,
    # per-category, per-comparison, then yStart or automatic placement.
    ypos_flat = float(yPositions) if isinstance(yPositions, (int, float)) and not isinstance(yPositions, bool) else None
    ypos_cat: dict[Any, float] | None = None
    ypos_map: dict[Any, Any] | None = None
    if isinstance(yPositions, dict):
        tuple_keys = {k for k in yPositions if isinstance(k, tuple)}
        if tuple_keys and len(tuple_keys) != len(yPositions):
            raise ValueError(
                "yPositions dict keys must be uniform: all category names, or all (category, level) tuples."
            )
        if tuple_keys:  # per-comparison
            ypos_map = _normalize_grouped_map(yPositions, is_reference, "yPositions")
            unknown = set(ypos_map) - set(all_keys)
            if unknown:
                raise ValueError(f"yPositions has {len(unknown)} entr(y/ies) not matching any comparison (check keys).")
        elif yPositions:  # keyed by category → a flat row per category
            unknown_cats = set(yPositions) - set(categories)
            if unknown_cats:
                raise ValueError(f"yPositions has categor(y/ies) not in the data: {sorted(unknown_cats)}.")
            ypos_cat = {c: float(v) for c, v in yPositions.items()}
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

    _rev_lvl_pairs = [frozenset(p) for p in (reverse or [])]
    rev_flags = [frozenset((l1, l2)) in _rev_lvl_pairs for l1, l2 in pairs]

    layers: list[Any] = []
    comparisons: list[dict[str, Any]] = []
    k = 0
    resolved_test_label_position = None if testLabelPosition == "auto" else testLabelPosition
    if resolved_test_label_position is not None or testLabelX is not None or testLabelY is not None:
        label_text = (
            testLabel
            if testLabel is not None
            else ("user p-values" if pval_map is not None else _TEST_DISPLAY.get(test, test))
        )
        layers.append(
            _text(
                label_text,
                testLabelX,
                testLabelY,
                position=resolved_test_label_position,
                offsetX=testLabelOffsetX,
                offsetY=testLabelOffsetY,
                fontSize=fontSize,
            )
        )
    for cat in categories:
        cdf = df.filter(pl.col(x_col) == cat)
        cat_max = cast(float, cdf[y_col].cast(pl.Float64).max() or 0.0)
        bracket_base = _cat_base(cat, cat_max + yPad)  # brackets only; reference ignores yStart
        # In pixel mode, anchor each bracket at the maximum of the levels it spans in this
        # category. Vega resolves the pixel offsets against the rendered y scale.
        grp_pixel_mode = (
            not is_reference and yPositions is None and yStart is None and _y_step_arg is None and _y_pad_arg is None
        )
        cat_pair_anchor: list[float] = []
        cat_offsets: list[float] = []
        cat_drop: list[tuple[float, float]] | None = None
        cat_drop_data: list[tuple[float, float]] | None = None
        if grp_pixel_mode:
            cat_spans = [
                (min(level_order.index(a), level_order.index(b)), max(level_order.index(a), level_order.index(b)))
                for a, b in pairs
            ]
            # Include every sub-bar spanned by the bracket; an intermediate level can exceed both
            # endpoints. Reverse brackets anchor at the minimum.
            cat_pair_anchor = [
                cast(
                    float,
                    (
                        cdf.filter(pl.col(xoffset_col).is_in(level_order[lo : hi + 1]))[y_col].cast(pl.Float64).min()
                        if rev_flags[pi]
                        else cdf.filter(pl.col(xoffset_col).is_in(level_order[lo : hi + 1]))[y_col]
                        .cast(pl.Float64)
                        .max()
                    )
                    or 0.0,
                )
                for pi, (lo, hi) in enumerate(cat_spans)
            ]
            _clo, _chi = _nice_domain(
                min(0.0, cast(float, cdf[y_col].cast(pl.Float64).min() or 0.0)),
                cast(float, cdf[y_col].cast(pl.Float64).max() or 0.0),
            )
            _cspan = (_chi - _clo) or 1.0
            _ch = float(_opt("height"))
            _cpx = lambda v, _lo=_clo, _sp=_cspan, _h=_ch: _h * (1.0 - (v - _lo) / _sp)  # noqa: E731
            # Place upward and reverse brackets on separate ladders.
            cat_pair_anchor = list(cat_pair_anchor)
            cat_offsets = [0.0] * len(pairs)
            for _down in (False, True):
                _sel = [i for i, r in enumerate(rev_flags) if r is _down]
                if not _sel:
                    continue
                for _slot, (_a, _o) in zip(
                    _sel,
                    _bracket_offsets(
                        [cat_pair_anchor[i] for i in _sel],
                        [cat_spans[i] for i in _sel],
                        6.0,
                        float(fontSize or _opt("fontSize")) + 6.0,
                        _cpx,
                        downward=_down,
                    ),
                ):
                    cat_pair_anchor[_slot], cat_offsets[_slot] = _a, _o
            if bracketStyle == "drop":
                # The y scale is shared across categories. Measure drop lengths against the full
                # frame's domain rather than a per-category domain.
                _dlo, _dhi = _nice_domain(
                    min(0.0, cast(float, df[y_col].cast(pl.Float64).min() or 0.0)),
                    cast(float, df[y_col].cast(pl.Float64).max() or 0.0),
                )
                _dspan = (_dhi - _dlo) or 1.0

                def _cat_px(v: float, _lo: float = _dlo, _sp: float = _dspan, _h: float = _ch) -> float:
                    return _h * (1.0 - (v - _lo) / _sp)

                _cbars = [
                    _cat_px(cat_pair_anchor[i]) + (cat_offsets[i] if rev_flags[i] else -cat_offsets[i])
                    for i in range(len(pairs))
                ]
                _lvl_col = [cdf.filter(pl.col(xoffset_col) == lv)[y_col].cast(pl.Float64) for lv in level_order]
                _clevel_px = [_cat_px(cast(float, c.max() or 0.0)) for c in _lvl_col]
                _clevel_lo = [_cat_px(cast(float, c.min() or 0.0)) for c in _lvl_col] if any(rev_flags) else _clevel_px
                # Vega positions the sub-bars, so treat each label as spanning the category band.
                # This can shorten a tick but prevents it from crossing a label.
                _cfs = float(fontSize or _opt("fontSize"))
                _clabels = [
                    _format_label(adj[k + i], labelStyle, effective_sigfigs, notation_val) for i in range(len(pairs))
                ]
                _cedges = [
                    (
                        float("-inf"),
                        float("inf"),
                        _cbars[i]
                        - (-1.0 if rev_flags[i] else 1.0)
                        * ((2.0 if labelStyle == "asterisks" and lb != "ns" else 4.0) + _cfs),
                    )
                    for i, lb in enumerate(_clabels)
                ]
                cat_drop = _drop_tick_lengths(
                    _cbars,
                    cat_spans,
                    _clevel_px,
                    ["drop"] * len(pairs),
                    [0.0] * len(level_order),
                    _cedges,
                    rev_flags,
                    _clevel_lo,
                )

                def _cat_data(i: int, length: float) -> float:
                    end = _cbars[i] + (-1.0 if rev_flags[i] else 1.0) * length
                    return _dlo + (1.0 - end / _ch) * _dspan

                cat_drop_data = [(_cat_data(i, a), _cat_data(i, b)) for i, (a, b) in enumerate(cat_drop)]
        if not is_reference:
            # Resolve every bracket's y position before calculating drop ticks.
            cat_y = []
            for pi, (l1, l2) in enumerate(pairs):
                _key = _grouped_key(cat, l1, l2, is_reference)
                if ypos_flat is not None:
                    cat_y.append(ypos_flat)
                elif ypos_cat is not None and cat in ypos_cat:
                    cat_y.append(ypos_cat[cat])
                elif ypos_map is not None and _key in ypos_map:
                    cat_y.append(float(ypos_map[_key]))
                elif grp_pixel_mode:
                    cat_y.append(cat_pair_anchor[pi])
                else:
                    cat_y.append(bracket_base + pair_level[pi] * yStep)
            if bracketStyle == "drop" and cat_drop is None:
                _elo, _ehi = _nice_domain(
                    min(0.0, cast(float, df[y_col].cast(pl.Float64).min() or 0.0), min(cat_y)),
                    max(cast(float, df[y_col].cast(pl.Float64).max() or 0.0), max(cat_y)),
                )
                _esp = (_ehi - _elo) or 1.0
                _ech = float(_opt("height"))

                def _epx(v: float, _lo: float = _elo, _sp: float = _esp, _h: float = _ech) -> float:
                    return _h * (1.0 - (v - _lo) / _sp)

                _espans = [
                    (min(level_order.index(a), level_order.index(b)), max(level_order.index(a), level_order.index(b)))
                    for a, b in pairs
                ]
                _ebars = [_epx(v) for v in cat_y]
                _elvl = [
                    _epx(cast(float, cdf.filter(pl.col(xoffset_col) == lv)[y_col].cast(pl.Float64).max() or 0.0))
                    for lv in level_order
                ]
                _efs = float(fontSize or _opt("fontSize"))
                _elabels = [
                    _format_label(adj[k + i], labelStyle, effective_sigfigs, notation_val) for i in range(len(pairs))
                ]
                _eedges = [
                    (
                        float("-inf"),
                        float("inf"),
                        _ebars[i] - (2.0 if labelStyle == "asterisks" and lb != "ns" else 4.0) - _efs,
                    )
                    for i, lb in enumerate(_elabels)
                ]
                cat_drop = _drop_tick_lengths(
                    _ebars, _espans, _elvl, ["drop"] * len(pairs), [0.0] * len(level_order), _eedges
                )

                def _ext_data(i: int, length: float) -> float:
                    return _elo + (1.0 - (_ebars[i] + length) / _ech) * _esp

                cat_drop_data = [(_ext_data(i, a), _ext_data(i, b)) for i, (a, b) in enumerate(cat_drop)]

        for pi, (l1, l2) in enumerate(pairs):
            p = adj[k]
            en, ev = effects[k]
            k += 1
            key = _grouped_key(cat, l1, l2, is_reference)
            ref_offset_px = 0.0
            label = _format_label(p, labelStyle, effective_sigfigs, notation_val)
            if is_reference:
                # Position precedence: global, per-category, per-comparison, then automatic.
                if ypos_flat is not None:
                    y = ypos_flat
                elif ypos_cat is not None and cat in ypos_cat:
                    y = ypos_cat[cat]
                elif ypos_map is not None and key in ypos_map:
                    y = float(ypos_map[key])
                else:
                    sub_max = cast(float, cdf.filter(pl.col(xoffset_col) == l2)[y_col].cast(pl.Float64).max() or 0.0)
                    # Automatic placement anchors at the sub-bar maximum and uses a pixel offset.
                    y, ref_offset_px = (sub_max, 6.0) if _y_pad_arg is None else (sub_max + yPad, 0.0)
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
                        offset_px=ref_offset_px,
                    )
                )
            else:
                y = cat_y[pi]  # resolved above: yPositions flat > per-category > per-comparison > stack
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
                        width=width,
                        reverse=rev_flags[pi],
                        offset_px=(cat_offsets[pi] if grp_pixel_mode else 0.0),
                        tick_px=(
                            cat_drop[pi] if cat_drop is not None else (_BRACKET_TICK_PX if _tick_arg is None else None)
                        ),
                        tick_data=(cat_drop_data[pi] if cat_drop_data is not None else None),
                    )
                )
            comparisons.append(
                {
                    "g1": f"{cat} ({l1})",
                    "g2": f"{cat} ({l2})",
                    "pvalue": p,
                    "unadjustedPvalue": None if pval_map is not None else raw[k - 1],
                    "effectName": en,
                    "effect": ev,
                }
            )

    record = _make_record(
        test=test,
        is_omnibus=False,
        omnibus=None,
        descriptives=descriptives,
        comparisons=comparisons,
        comparison_test=None if pval_map is not None else test,
        correction=effective_correction,
        pvalues_provided=pval_map is not None,
        n_comparisons=m if effective_correction is not None else None,
        data_checksum=_frame_checksum(df),
    )
    marker = _emit_report(record, report, save)

    if not layers:
        layers.append(_empty_layer())
    return cast(alt.LayerChart, alt.layer(*layers).properties(name=marker))


def comparisons(
    data: "pl.DataFrame | pd.DataFrame",
    x: str,
    y: str,
    pairs: list[tuple[str, str]] | str | None = None,
    *,
    test: str = "mannwhitneyu",
    postHoc: str | None = None,
    pvalues: list[float] | dict[Any, Any] | None = None,
    correction: str | None = None,
    nComparisons: int | None = None,
    reference: Any = None,
    xOffset: str | None = None,
    xOffsetSort: list[str] | None = None,
    yPositions: float | list[float] | dict[Any, Any] | None = None,
    yStart: float | dict[Any, Any] | None = None,
    yStep: float | None = None,
    yPad: float | None = None,
    categories: list[Any] | None = None,
    width: float | None = None,
    bracketStyle: str | dict[tuple[str, str], Any] = "bracket",
    labelStyle: str = "p",
    tickHeight: float | None = None,
    strokeWidth: float | None = None,
    fontSize: float | None = None,
    reverse: list[tuple[str, str]] | None = None,
    sigFigs: int | None = None,
    notation: str | dict[str | tuple[str, str], Any] | None = None,
    testLabelPosition: str | None = "auto",
    testLabel: str | None = None,
    omnibusVerbose: bool = False,
    testLabelOffsetX: float = 0,
    testLabelOffsetY: float = 0,
    testLabelX=None,
    testLabelY=None,
    report: bool = False,
    saveReport: bool | str | Path = False,
) -> alt.LayerChart:
    """
    Build p-value annotation layers for one or more group comparisons.

    Two modes, selected by ``test``:

    - **Pairwise** (``'mannwhitneyu'``, ``'ttest_ind'``, ``'ttest_rel'``,
      ``'wilcoxon'``, ``'tukey_hsd'``) computes the requested pairwise results and
      draws one bracket per pair in ``pairs``. Overlapping brackets use separate
      stacking levels.
    - **Omnibus** (``'anova'``, ``'kruskal'``, ``'friedman'``,
      ``'alexandergovern'``) computes one test and places its result in a corner
      label (see ``testLabelPosition``). If ``pairs`` is also given, a post-hoc
      test (see ``postHoc``) supplies the bracket results.

    Setting ``reference`` selects reference mode: each other group is compared
    with the reference, and its p-value is shown above the mark without a bracket
    (see ``reference``).

    A descriptive and effect-size report is generated on every call and queued for
    the export metadata written by ``ds.save()`` (see ``report`` and ``saveReport``).
    Comparison records include ``pvalue`` (adjusted when a correction applies) and
    ``unadjustedPvalue`` for ordinary computed values, including when no correction is requested.
    ``pvalueOrigin`` distinguishes computed, supplied, and intrinsically adjusted values;
    ``nComparisons`` is the effective generic correction-family size or null when none applies.
    Supplied values and Tukey HSD have null unadjusted values and family sizes. Games-Howell and
    Nemenyi also have null unadjusted values because their base results are intrinsically adjusted;
    if additionally corrected, each pair includes ``correctionInputPvalue`` and the section records
    the generic correction and family size.

    **Placement.** In automatic pixel mode, each bracket anchors at the maximum of the
    categories it spans and uses a pixel offset. Overlapping brackets are assigned separate
    ladder levels spaced by the effective label font size plus 6 pixels; brackets in disjoint spans
    independently. Reverse brackets
    anchor at the minimum, hang below the data, and use a separate ladder. Pixel offsets are
    applied through the rendered y scale, so their distance does not depend on the y domain.

    Ladder collision checks estimate the rendered domain as linear. On a log axis, this estimate
    can place the lowest bracket inside its data; use ``yPositions`` to set explicit positions.
    Passing any of ``yStart``, ``yStep``, ``yPad``, or ``yPositions`` selects data-unit placement
    instead of automatic pixel placement.

    The upper y-scale bound (``domainMax``) is raised to make room for brackets when a test label
    uses a ``top`` preset or when ``ds.theme(closed=True)`` draws a plot border. Only the upper
    bound changes; the lower bound, ``zero``, and nice-rounding are left unchanged. This adjustment
    is made only when brackets need the space.

    Combine with your chart using ``+``:  ``chart + ds.stats.comparisons(...)``.

    Parameters
    ----------
    data:
        Polars or pandas DataFrame containing the data.
    x:
        Column name for the grouping variable (x-axis).
    y:
        Column name for the value variable (y-axis). Used to run tests and
        to auto-place the first bracket.
    pairs:
        List of ``(group1, group2)`` tuples identifying comparisons to annotate
        with brackets. Required for pairwise ``test`` values. For omnibus tests,
        pass ``None`` for a corner label only, or a list to also draw post-hoc
        brackets.

        ``"all"`` expands to every unique pair, in ``categories`` order (in
        grouped mode, every unique pair of ``xOffset`` levels). The bracket count
        is ``n(n-1)/2``: 6 pairs at 4 groups, 10 at 5, and 15 at 6. A correction
        normally covers only the comparisons computed for the call; use
        ``nComparisons`` to include other tests in the family. With an omnibus test,
        ``pairs=None`` reports every post-hoc comparison without drawing brackets.
    test:
        Statistical test. **Pairwise:** ``'mannwhitneyu'`` (default),
        ``'ttest_ind'``, ``'ttest_rel'``, ``'wilcoxon'`` (run per pair), or
        ``'tukey_hsd'`` (one omnibus run, per-pair p-values from the matrix).
        **Omnibus:** ``'anova'`` (``f_oneway``), ``'kruskal'``, ``'friedman'``,
        ``'alexandergovern'``. In pairwise mode, supplying ``pvalues`` skips the pairwise test.
        In omnibus mode, the omnibus test still runs and supplied values replace only the requested
        pairwise results.
    postHoc:
        Post-hoc test that fills the brackets when ``test`` is omnibus and
        ``pairs`` is given. ``None`` (default) selects a default for each
        omnibus test: ``anova → 'tukey_hsd'``, ``alexandergovern →
        'games_howell'``, ``kruskal → 'dunn'``, ``friedman → 'nemenyi'``. May
        also be set to any pairwise test name. Dunn, Nemenyi, and Games-Howell
        are computed in-house (validated against scikit-posthocs / pingouin);
        ``correction`` adjusts them over all unique pairs. Ignored for pairwise
        ``test``. Grouped ``xOffset`` mode does not accept ``postHoc``; use one
        of its supported pairwise tests directly.
    pvalues:
        Precomputed final p-values skip pairwise calculation and correction. **Pairwise:**
        a list, one per pair in the same order. **Reference mode:** a **dict** keyed by the
        non-reference **group** (single-factor) or ``(category, level)`` (grouped). **Grouped
        brackets:** a dict keyed by ``(category, (level1, level2))`` (order-insensitive). The
        dict must cover **every** comparison; missing or unknown keys raise. Values must be real,
        finite, non-bool numbers in ``[0, 1]``. In omnibus mode, only the supplied requested pairs
        are reported; the omnibus result remains in the report.
    correction:
        Multiple comparison correction: ``'bonferroni'``, ``'holm'``,
        ``'fdr_bh'`` (Benjamini-Hochberg), ``'fdr_by'`` (Benjamini-Yekutieli),
        or ``None``. The two ``fdr_*`` methods control the false discovery rate
        (BH assumes independence or positive dependence; BY is valid under
        arbitrary dependence but is more conservative). Applies to pairwise or
        post-hoc bracket p-values. Ignored for ``'tukey_hsd'`` (correction is built
        in) and when ``pvalues`` is provided.
    nComparisons:
        Total family size for the correction (the denominator ``m``). For pairwise tests, it
        defaults to the number of requested pairs when ``correction`` is set. For an omnibus test
        with post-hoc comparisons, it defaults to the number of all unique pairs, even if only some
        are drawn. In grouped mode, it defaults to ``len(categories) * len(pairs)``. It must be a
        positive, non-bool integer and, when correction applies, at least the computed family size.
        Larger values are allowed. Supplied final p-values and Tukey HSD are not readjusted.
    reference:
        **Reference mode (compare against one).** A single group compared with
        every other group. The function derives the comparisons, so ``pairs`` must
        be ``None``. Only pairwise tests are supported. Correction applies to all
        comparisons: ``len(categories) - 1`` in single-factor mode, and the number
        of categories times the number of non-reference levels in grouped mode.
        Each label is placed at its non-reference group's data maximum. Without
        ``xOffset``, ``reference`` is
        a category of ``x``; with ``xOffset``, it is an xOffset **level** compared
        within each x-category, with one label per non-reference sub-bar.
        ``bracketStyle``, ``reverse``, and ``tickHeight`` do not affect reference
        labels. ``yStart`` is unsupported and raises an error. ``pvalues`` is a
        group-keyed dict of supplied values. ``yPositions`` accepts one number for
        a flat row or a group-keyed dict for per-label positions.
    xOffset:
        **Grouped mode.** Column encoded as the chart's ``xOffset`` (the subgroup
        that splits each x-category into side-by-side bars, e.g. ``"condition"``
        in a qPCR gene × condition panel). When set, ``pairs`` names subgroup
        **levels** (not x-categories) and one bracket is drawn per x-category.
        With exactly two levels, ``pairs`` defaults to comparing them. Only the
        pairwise tests are supported here
        (``'mannwhitneyu'``/``'ttest_ind'``/``'ttest_rel'``/``'wilcoxon'``);
        ``correction`` adjusts over the whole family (``categories × pairs``).
        Labels are centered between the compared sub-bars.
    xOffsetSort:
        Grouped mode – the subgroup level order. Must match the ``sort`` on your
        chart's ``xOffset`` encoding (and ``categories`` must match the ``x`` sort), or the shared
        scale reorders the bars. Explicit values must match observed levels exactly once; tuple/
        list order and numeric category values are preserved. ``None`` (default) reads the data's
        first-appearance order.
    yPositions:
        Explicit y positions (data units) for the annotations. **A single number** puts
        *every* annotation at that y, one global flat row. **Pairwise:** a list, one per
        pair in order (overrides auto-stacking). **Reference mode:** a **dict** keyed by the
        non-reference **group** (single-factor) or ``(category, level)`` (grouped) for a
        per-label height. **Grouped** accepts a number or supported dict, not a list. It additionally
        accepts a dict keyed by **category** for a separate flat row per category; grouped
        brackets also accept ``(category, (level1, level2))``
        keys (order-insensitive). Dicts are partial (unlisted → auto) and their keys must be
        uniform (all category names or all tuples). Takes precedence over ``yStart``; unknown
        keys raise.
    yStart:
        The exact y (data units) of the lowest bracket, the stack base (levels rise from it
        by ``yStep``). **Setting it opts the whole stack into data-unit placement** (see the
        note below). **Grouped (`xOffset`) brackets** additionally accept a **dict** keyed by
        category for a per-category base (partial; unlisted categories use the auto base).
        **Does not apply to reference mode**; passing it there raises. Use ``yPositions``
        for exact per-label heights.
    yStep:
        Vertical distance (data units) between stacking levels, when placement is in data
        units. Setting it opts out of automatic pixel placement.
    yPad:
        Padding (data units) above the data maximum, when placement is in data units. Setting
        it opts out of the automatic pixel placement described above.
    categories:
        Ordered list of all x-axis categories. Supplied values must match observed values exactly
        once; tuple/list order and numeric values are preserved. Inferred from ``data`` (sorted
        alphabetically) when not provided.
    width:
        Width of the chart in pixels, used to compute annotation x positions.
        Inherits ``width`` from ``ds.theme()`` when not set.
    bracketStyle:
        ``'bracket'`` (default; bar + end ticks), ``'line'`` (horizontal bar only)
        or ``'drop'`` (end ticks extending toward each endpoint group's data)
        applied to every bracket. Or a ``dict`` mapping a pair to its style for
        per-pair control, e.g. ``{("A", "B"): "line", ("A", "C"): "bracket"}`` –
        keys match either pair order; pairs absent from the dict fall back to
        ``'bracket'``.
    labelStyle:
        ``'p'`` (default) renders ``P = 0.012`` / ``P < 0.001``. ``'asterisks'``
        renders ``*`` / ``**`` / ``***`` / ``ns``. ``'value'`` renders the bare
        value without the ``P`` symbol or redundant ``= `` (for example, ``0.012``).
        It retains comparison operators such as ``< 0.001`` and ``≈ 10⁻⁵`` with
        ``notation='power'``. ``notation`` still applies.
    tickHeight:
        Height of bracket end ticks in data units when set. If unset, automatic pixel placement
        uses 2-pixel ticks; data-unit placement resolves a default height from the chart size and
        y range. The value must be positive, including for reverse brackets. Only used with
        ``bracketStyle='bracket'``; raises with ``bracketStyle='drop'``, which computes a length
        for each end.
    strokeWidth:
        Stroke width of bracket lines. Inherits ``axisWidth`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size of the p-value / corner labels. Defaults to the theme's primary
        ``fontSize`` (``6`` under the built-in defaults), matching the axis font.
    reverse:
        List of ``(group1, group2)`` tuples identifying brackets to flip: text moves
        below the bar, ticks point upward, and brackets hang below their groups.
        In single-factor mode, tuple order must match ``pairs``. In grouped mode
        (``xOffset``), tuples name ``xOffset`` levels, like ``pairs``, and apply in
        every category regardless of tuple order.
    sigFigs:
        Significant figures for p-value labels. Gives
        consistent precision across magnitudes – e.g. ``sigFigs=2`` renders both
        ``P = 4.3×10⁻¹⁴`` and ``P = 0.68`` at two figures. Trailing zeros are stripped.
        ``None`` (default) reads the theme's ``sigFigs`` (default ``3``). Plain notation
        floors at a fixed ``P < 0.001``; ``'power'`` is unaffected (integer exponent).
        Positive subnormal p-values are supported; a computed zero is shown as a bound in every
        notation using the minimum normal positive float stored in the report record.
    notation:
        Format style for p-value labels when ``labelStyle='p'``. ``None``
        (default) uses ``P = 0.012`` / ``P < 0.001`` style. ``'scientific'``
        uses ``P = 1.23×10⁻²``. ``'e'`` uses ``P = 1.23e-02``. ``'power'``
        rounds to the nearest power of 10, producing ``P ≈ 10⁻²``. Values
        within the same decade (e.g. 0.04 and 0.06) map to the same label. This
        notation is useful when p-values span multiple orders of magnitude.
        A single value applies to every label; or pass a ``dict`` for per-pair
        notation, e.g. ``{("A", "B"): "scientific", "test": "power"}``; tuple
        keys are pairs (matched either order, unlisted → plain), and the special
        ``"test"`` key sets the omnibus label's notation.
    testLabelPosition:
        Corner preset (a ``text`` position, e.g. ``'topLeft'``,
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
        Pixel nudges for the test label, forwarded to ``text``.
    testLabelX, testLabelY:
        Explicit coordinates for the test label (data values, category names, or
        ``alt.value(px)``), forwarded to ``text`` where they override the
        preset. ``None`` (default) uses ``testLabelPosition``.
    report:
        ``True`` prints the full descriptive + effect-size report (per-group
        n/mean/sd/median/IQR/range, the omnibus result, and the post-hoc
        comparisons) to stdout. Default ``False``. Without supplied ``pvalues``, an omnibus
        ``test`` lists all pairwise post-hoc comparisons, including pairs without brackets
        and when ``pairs=None``. With supplied values, it lists only the
        requested pairs and retains the omnibus result; supplied pairs have no test, correction,
        or effect size. A pairwise ``test`` lists exactly the requested ``pairs``. The report is
        queued for the export metadata regardless of this flag (when
        ``ds.save(..., saveMetadata=True)``); it lands in the next ``ds.save()``.
    saveReport:
        ``True`` writes the report to ``dysonsphere_report_<timestamp>.txt`` in
        the current directory; a path writes it to that directory. Default
        ``False``.

    Examples
    --------
    Single comparison::

        CATEGORIES = ["A", "B", "C"]
        chart = ds.mark_strip(data, "group", "value", CATEGORIES)
        chart + ds.stats.comparisons(
            data, "group", "value",
            pairs=[("A", "B")],
            categories=CATEGORIES,
        )

    Multiple comparisons – brackets stacked automatically::

        chart + ds.stats.comparisons(
            data, "group", "value",
            pairs=[("A", "B"), ("A", "C"), ("B", "C")],
            test="mannwhitneyu",
            categories=CATEGORIES,
        )

    Every pair, corrected over the whole family::

        chart + ds.stats.comparisons(
            data, "group", "value",
            pairs="all",
            correction="holm",
            categories=CATEGORIES,
        )

    Omnibus ANOVA in the corner + Tukey post-hoc brackets::

        chart + ds.stats.comparisons(
            data, "group", "value",
            pairs=[("A", "B"), ("A", "C")],
            test="anova",
            omnibusVerbose=True,
            categories=CATEGORIES,
        )

    Omnibus-only (no brackets), report printed::

        chart + ds.stats.comparisons(
            data, "group", "value",
            test="kruskal",
            categories=CATEGORIES,
            report=True,
        )

    From pre-computed p-values::

        chart + ds.stats.comparisons(
            data, "group", "value",
            pairs=[("A", "B"), ("A", "C")],
            pvalues=[0.012, 0.341],
            categories=CATEGORIES,
        )

    Grouped (two-factor) – compare vehicle vs LPS *within* each gene of a grouped
    bar chart (``xOffset="condition"``); one bracket per gene, a real per-gene test::

        GENES = ["GAPDH", "IL6", "TNF"]
        bars = alt.Chart(data).mark_bar().encode(
            x=alt.X("gene:N", sort=GENES),
            xOffset=alt.XOffset("condition:N", sort=["Vehicle", "LPS"]),
            y="mean(expr):Q", color="condition:N",
        )
        bars + ds.stats.comparisons(
            data, "gene", "expr",
            xOffset="condition",
            categories=GENES, xOffsetSort=["Vehicle", "LPS"],
            test="ttest_ind", labelStyle="asterisks",
        )

    Reference mode – compare every dose against the control, a bare mark above each
    (no bracket); overlay your points so the marks clear the data::

        CATS = ["Ctrl", "Low", "Mid", "High"]
        chart = ds.mark_strip(data, "group", "value", CATS)
        chart + ds.stats.comparisons(
            data, "group", "value",
            reference="Ctrl", categories=CATS,
            test="ttest_ind", correction="holm", labelStyle="asterisks",
        )
    """
    y_col = y
    from ._statistics import (
        _INTRINSICALLY_ADJUSTED,
        _OMNIBUS_TESTS,
        _PARAMETRIC_POSTHOC,
        _TEST_DISPLAY,
        _describe_all,
        _make_record,
        _pair_effect,
        _run_omnibus,
    )
    from .utils import _ensure_polars, _frame_checksum

    data = _ensure_polars(data)

    _validate_comparison_syntax(
        test=test,
        post_hoc=postHoc,
        correction=correction,
        label_style=labelStyle,
        bracket_style=bracketStyle,
        notation=notation,
        test_label_position=testLabelPosition,
        grouped=xOffset is not None,
    )
    if nComparisons is not None:
        _validate_family_size(nComparisons, 0, correction=None)
    if xOffset is not None:
        _validate_statistical_data(data, x, y_col, x, xOffset)
    else:
        _validate_statistical_data(data, x, y_col, x)

    if xOffset is not None:
        return _add_grouped_comparisons(
            data,
            x,
            y_col,
            xOffset,
            pairs,
            reference=reference,
            reverse=reverse,
            xOffsetSort=xOffsetSort,
            test=test,
            correction=correction,
            nComparisons=nComparisons,
            labelStyle=labelStyle,
            bracketStyle=bracketStyle,
            notation=notation,
            testLabelPosition=testLabelPosition,
            testLabel=testLabel,
            testLabelOffsetX=testLabelOffsetX,
            testLabelOffsetY=testLabelOffsetY,
            testLabelX=testLabelX,
            testLabelY=testLabelY,
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
            width=width,
            report=report,
            save=saveReport,
        )

    # Outside reference mode, dict forms of these arguments are valid only for grouped comparisons.
    if reference is None:
        if isinstance(pvalues, dict):
            raise ValueError("a dict pvalues is for grouped mode (xOffset) or reference mode; pairwise takes a list.")
        if isinstance(yPositions, dict):
            raise ValueError(
                "a dict yPositions is for grouped mode (xOffset) or reference mode; pairwise takes a list."
            )
    if isinstance(yStart, dict) and reference is None:
        raise ValueError("a dict yStart is for grouped mode (xOffset); single-factor takes a number.")

    # Bracket positions use the category order and count. Require complete coverage to prevent
    # incorrect band geometry. Matching this order to the chart's sort cannot be checked here.
    _check_coverage(
        data,
        x,
        categories,
        "categories",
        "values",
        "It must list every x-category, in the same order as your chart's x sort.",
    )
    if categories is None:
        categories = sorted(data[x].unique().to_list())
    # Resolve first so reference mode can reject an explicitly supplied pairs value.
    pairs = _resolve_pairs(pairs, categories, f"{x!r} categories")

    is_omnibus = test in _OMNIBUS_TESTS
    groups = [data.filter(pl.col(x) == cat)[y_col].to_numpy() for cat in categories]
    for category, group in zip(categories, groups):
        if group.size == 0:
            raise ValueError(f"grouping column {x!r} has no observations for group {category!r}.")
        _validate_observations(group.tolist(), y_col, category)

    # Record explicit spacing arguments; any one selects data-unit placement below.
    _y_step_arg, _y_pad_arg = yStep, yPad

    # Reference mode derives one pair for every non-reference category and applies only to pairwise tests.
    is_reference = reference is not None
    if is_reference:
        if is_omnibus:
            raise ValueError(
                "reference is a pairwise comparison against one group; it can't be used with an omnibus test."
            )
        if pairs is not None:
            raise ValueError("reference derives its own comparisons; don't also pass pairs.")
        if yStart is not None:
            raise ValueError(
                "yStart does not apply in reference mode; each label sits above its own mark. "
                "Use yPositions for explicit label heights (a single number sets a flat row)."
            )
        if reference not in categories:
            raise ValueError(f"reference {reference!r} is not a category of {x!r}: {categories}.")
        pairs = [(reference, c) for c in categories if c != reference]
        non_ref = [c for c in categories if c != reference]
        # Explicit p-values are keyed by each non-reference group and must cover them all.
        if pvalues is not None:
            if not isinstance(pvalues, dict):
                raise ValueError("reference pvalues must be a dict keyed by group (the non-reference category).")
            missing = [g for g in non_ref if g not in pvalues]
            if missing:
                raise ValueError(f"pvalues is missing an entry for: {missing}.")
            extra = [k for k in pvalues if k not in non_ref]
            if extra:
                raise ValueError(f"pvalues has entr(y/ies) not matching any group: {sorted(extra)}.")
        # A number sets one y position for all labels; a group-keyed dict sets per-label positions.
        # Lists are reserved for bracket positions.
        if isinstance(yPositions, dict):
            ypos_extra = [k for k in yPositions if k not in non_ref]
            if ypos_extra:
                raise ValueError(f"yPositions has entr(y/ies) not matching any group: {sorted(ypos_extra)}.")
        elif isinstance(yPositions, list):
            raise ValueError("reference yPositions must be a single number (flat row) or a dict keyed by group.")

    if pairs is not None and len(pairs) == 0:
        raise ValueError("pairs must not be empty when provided (pass pairs=None for an omnibus-only annotation).")
    if not is_omnibus and not pairs:
        raise ValueError("pairs is required for pairwise tests.")
    if isinstance(yPositions, list) and pairs is not None and len(yPositions) != len(pairs):
        raise ValueError(f"yPositions length ({len(yPositions)}) does not match pairs length ({len(pairs)})")

    if pvalues is not None:
        if is_reference:
            if not isinstance(pvalues, dict):
                raise ValueError("reference pvalues must be a dict keyed by group (the non-reference category).")
            pvalues = {group: _validate_pvalue(value, f"pvalues entry {group!r}") for group, value in pvalues.items()}
        else:
            if not isinstance(pvalues, (list, tuple)):
                raise ValueError("pairwise pvalues must be a list of final p-values.")
            pvalues = [_validate_pvalue(value, f"pvalues entry {index}") for index, value in enumerate(pvalues)]
            if pairs is None:
                raise ValueError("pvalues requires pairs so each supplied value has a comparison.")

    annotation_layers: list[Any] = []
    omnibus_result = None
    comparisons: list[dict[str, Any]] = []

    if is_omnibus:
        omnibus_result = _run_omnibus(test, groups, categories)

    idx = {c: i for i, c in enumerate(categories)}
    method = _resolve_method(test, postHoc, pvalues, is_omnibus)
    # Tukey HSD includes its correction; supplied p-values are final.
    effective_correction = None if (method is None or method == "tukey_hsd") else correction
    # Use the per-call significant-figure setting or the theme default.
    effective_sigfigs = sigFigs if sigFigs is not None else _opt("sigFigs")

    # Resolve one notation for all labels or per-pair notation and an optional test-label notation.
    test_notation, pair_notations = _resolve_notation(notation, pairs)

    # By default, show the omnibus label at topLeft and hide the pairwise test label.
    resolved_pos = ("topLeft" if is_omnibus else None) if testLabelPosition == "auto" else testLabelPosition
    if resolved_pos is not None or testLabelX is not None or testLabelY is not None:
        if testLabel is not None:
            label_text = testLabel
        elif is_omnibus:
            label_text = _omnibus_label(
                omnibus_result, verbose=omnibusVerbose, notation=test_notation, sigFigs=effective_sigfigs
            )
        else:
            label_text = "user p-values" if pvalues is not None else _TEST_DISPLAY.get(test, test)
        annotation_layers.append(
            _text(
                label_text,
                testLabelX,
                testLabelY,
                position=resolved_pos,
                offsetX=testLabelOffsetX,
                offsetY=testLabelOffsetY,
                fontSize=fontSize if fontSize is not None else _opt("fontSize"),
            )
        )

    # Omnibus reports include all post-hoc pairs; pairwise reports include the requested pairs.
    if is_omnibus and method is not None:
        report_pairs = _all_pairs(categories)
    else:
        report_pairs = list(pairs) if pairs else []

    if effective_correction is not None:
        actual_family = len(report_pairs)
        if nComparisons is not None:
            _validate_family_size(nComparisons, actual_family, correction=effective_correction)

    pval_lookup: dict[frozenset[str], Any] = {}
    if method is not None and report_pairs:
        report_pvals, report_raw_pvals, report_correction_inputs = _bracket_pvalues(
            method, groups, categories, report_pairs, correction, nComparisons
        )
        pval_lookup = {frozenset(p): v for p, v in zip(report_pairs, report_pvals)}
        parametric = method in _PARAMETRIC_POSTHOC
        paired = method == "ttest_rel"
        for pair_index, (g1, g2) in enumerate(report_pairs):
            en, ev = _pair_effect(groups[idx[g1]], groups[idx[g2]], parametric=parametric, paired=paired)
            comparisons.append(
                {
                    "g1": g1,
                    "g2": g2,
                    "pvalue": pval_lookup[frozenset((g1, g2))],
                    "unadjustedPvalue": None if report_raw_pvals is None else report_raw_pvals[pair_index],
                    "correctionInputPvalue": (
                        None if report_correction_inputs is None else report_correction_inputs[pair_index]
                    ),
                    "effectName": en,
                    "effect": ev,
                }
            )
    elif is_reference and isinstance(pvalues, dict):
        # Supplied reference-mode p-values bypass testing and correction.
        pval_lookup = {frozenset((reference, g)): pvalues[g] for _, g in (pairs or [])}
        comparisons = [
            {"g1": reference, "g2": g, "pvalue": pvalues[g], "unadjustedPvalue": None} for _, g in (pairs or [])
        ]

    if is_reference and pairs:
        # Place one p-value above each non-reference group's data maximum.
        y_all = data[y_col].cast(pl.Float64)
        y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
        ref_pad, _, _ = _resolve_y_spacing(False, y_range, _opt("height"), yPad, None, None)
        resolved_width = width if width is not None else _opt("width")
        fs = fontSize if fontSize is not None else _opt("fontSize")
        # A number sets one y position for all labels; a group-keyed dict sets per-label positions.
        # Unlisted groups use automatic positions.
        ypos_flat = (
            float(yPositions) if isinstance(yPositions, (int, float)) and not isinstance(yPositions, bool) else None
        )
        for i, (_, g) in enumerate(pairs):
            ref_offset_px = 0.0
            pval = pval_lookup[frozenset((reference, g))]
            if ypos_flat is not None:
                label_y = ypos_flat
            elif isinstance(yPositions, dict) and g in yPositions:
                label_y = float(yPositions[g])
            else:
                g_max = cast(float, data.filter(pl.col(x) == g)[y_col].cast(pl.Float64).max() or 0.0)
                # Automatic placement uses a pixel offset from each group's maximum. An explicit yPad
                # retains its data-unit meaning.
                label_y, ref_offset_px = (g_max, 6.0) if _y_pad_arg is None else (g_max + ref_pad, 0.0)
            label = _format_label(pval, labelStyle, effective_sigfigs, pair_notations[i])
            annotation_layers.append(
                _reference_label_layer(
                    g,
                    label_y,
                    label,
                    categories=categories,
                    width=resolved_width,
                    fontSize=fs,
                    offset_px=ref_offset_px,
                )
            )

    elif pairs:
        pair_styles = _resolve_bracket_styles(bracketStyle, pairs)
        if tickHeight is not None and "drop" in pair_styles:
            raise ValueError(
                "tickHeight sets a fixed end-tick length, which bracketStyle='drop' computes per end. "
                "Pass one or the other."
            )

        if pvalues is not None:
            if len(pvalues) != len(pairs):
                raise ValueError(f"pvalues length ({len(pvalues)}) does not match pairs length ({len(pairs)})")
            computed_pvalues = list(pvalues)
            comparisons = [
                {"g1": g1, "g2": g2, "pvalue": p, "unadjustedPvalue": None} for (g1, g2), p in zip(pairs, pvalues)
            ]
        else:
            computed_pvalues = [pval_lookup[frozenset((g1, g2))] for g1, g2 in pairs]

        annotated_groups_for_pad = list({g for pair in pairs for g in pair})
        # The rendered domain includes all groups. Use the full data extent to resolve spacing;
        # using only compared groups would make the pixel gap inaccurate when another group expands
        # the domain. yStart remains based on the compared groups.
        y_all = data[y_col].cast(pl.Float64)
        y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
        # End legs use pixel lengths through y2Offset. Converting an automatic tickHeight to data
        # units would assume a linear axis and make the ticks too short on a log axis.
        _tick_arg = tickHeight
        # In data-unit mode, tickHeight is a positive fixed length, including for reverse brackets.
        yPad, tickHeight, yStep = _resolve_y_spacing(
            any(s in ("bracket", "drop") for s in pair_styles),
            y_range,
            _opt("height"),
            yPad,
            tickHeight,
            yStep,
        )

        # Automatic placement uses pixel offsets; explicit positions and spacing use data units.
        pixel_mode = yPositions is None and yStart is None and _y_step_arg is None and _y_pad_arg is None
        offsets_px = [0.0] * len(pairs)
        tick_px = _BRACKET_TICK_PX if _tick_arg is None else None
        drop_px: list[tuple[float, float]] | None = None
        drop_data: list[tuple[float, float]] | None = None
        bracket_domain_max: float | None = None
        idx_span = [
            (min(categories.index(g1), categories.index(g2)), max(categories.index(g1), categories.index(g2)))
            for g1, g2 in pairs
        ]
        _rev_pairs: list[tuple[str, str]] = reverse or []
        rev_flags = [(g1, g2) in _rev_pairs for g1, g2 in pairs]

        def _solve_drop(bars_px: list[float], to_px_fn: Any) -> list[tuple[float, float]]:
            """Per-end drop lengths for bars already resolved to pixels."""
            any_rev = any(rev_flags)
            cols = [data.filter(pl.col(x) == c)[y_col].cast(pl.Float64) for c in categories]
            hi_px = [to_px_fn(cast(float, s.max() or 0.0)) for s in cols]
            lo_px = [to_px_fn(cast(float, s.min() or 0.0)) for s in cols] if any_rev else hi_px
            centers = list(_band_geometry(len(categories), width).centers)
            fs = float(fontSize or _opt("fontSize"))
            edges: list[tuple[float, float, float]] = []
            for i, (lo, hi) in enumerate(idx_span):
                lbl = _format_label(computed_pvalues[i], labelStyle, effective_sigfigs, pair_notations[i])
                mid = (centers[lo] + centers[hi]) / 2
                half = len(lbl) * fs * 0.6 / 2
                dy = 2.0 if labelStyle == "asterisks" and lbl != "ns" else 4.0
                sgn = -1.0 if rev_flags[i] else 1.0
                edges.append((mid - half, mid + half, bars_px[i] - sgn * (dy + fs)))
            return _drop_tick_lengths(bars_px, idx_span, hi_px, pair_styles, centers, edges, rev_flags, lo_px)

        if isinstance(yPositions, (int, float)) and not isinstance(yPositions, bool):
            final_y = [float(yPositions)] * len(pairs)  # a single number → every bracket at that y
        elif isinstance(yPositions, list):
            final_y = [float(v) for v in yPositions]
        else:
            # Assign stacking levels by span order using greedy interval scheduling.
            pair_levels = _stack_levels([(categories.index(g1), categories.index(g2)) for g1, g2 in pairs])
            anchor = cast(
                float,
                data.filter(pl.col(x).is_in(annotated_groups_for_pad))[y_col].cast(pl.Float64).max() or 0.0,
            )
            if pixel_mode:
                # Each bracket anchors to the maximum of the categories it spans and uses a pixel
                # offset. Overlap checks use estimated pixel positions; errors can shift ladder
                # placement but do not change rung spacing.
                gap_px = 6.0 if any(s in ("bracket", "drop") for s in pair_styles) else 5.0
                # Include label height and its 4 px offset in the minimum rung spacing to keep
                # the label clear of the next bracket.
                min_step_px = float(fontSize or _opt("fontSize")) + 6.0
                # Anchor across every category spanned by the bracket. An intermediate category
                # may have a taller bar than either endpoint. Reverse brackets anchor at the
                # minimum and descend; they are placed separately from upward brackets.
                pair_anchor = [
                    cast(
                        float,
                        (
                            data.filter(pl.col(x).is_in(categories[lo : hi + 1]))[y_col].cast(pl.Float64).min()
                            if rev
                            else data.filter(pl.col(x).is_in(categories[lo : hi + 1]))[y_col].cast(pl.Float64).max()
                        )
                        or 0.0,
                    )
                    for (lo, hi), rev in zip(idx_span, rev_flags)
                ]
                _ylo, _yhi = _nice_domain(
                    min(0.0, cast(float, data[y_col].cast(pl.Float64).min() or 0.0)),
                    cast(float, data[y_col].cast(pl.Float64).max() or 0.0),
                )
                _ch = float(_opt("height"))

                # Resolve the domain lift before ladder placement because raising the upper bound
                # changes the pixel distance between anchors. In one measured case, calculating
                # the ladder before the lift rendered a requested 13 px step as 6 px. The lift
                # allows space for the stack, including the case where all brackets overlap.
                _label_on_top = isinstance(resolved_pos, str) and resolved_pos.startswith("top")
                if _label_on_top or _opt("closed"):
                    stack_px = gap_px + len(pairs) * min_step_px
                    _lifted = _yhi + stack_px * ((_yhi - _ylo) or 1.0) / _ch
                    # Round it the way Vega will, and pin that value – otherwise Vega
                    # nice-rounds past it and compresses the plot further than we allowed for.
                    _ylo, _yhi = _nice_domain(_ylo, _lifted)
                    bracket_domain_max = _yhi

                _yspan = (_yhi - _ylo) or 1.0

                def _to_px(v: float, _lo=_ylo, _sp=_yspan, _h=_ch) -> float:
                    return _h * (1.0 - (v - _lo) / _sp)

                def _un_px(px: float, _lo=_ylo, _sp=_yspan, _h=_ch) -> float:
                    return _lo + (1.0 - px / _h) * _sp

                # Each ladder returns the shared anchor its rungs hang from, so `final_y` is that
                # anchor rather than the bracket's own; this makes rung spacing use pixels only.
                final_y = list(pair_anchor)
                offsets_px = [0.0] * len(pairs)
                for _down in (False, True):
                    _idx = [i for i, rev in enumerate(rev_flags) if rev is _down]
                    if not _idx:
                        continue
                    for slot, (anch, off) in zip(
                        _idx,
                        _bracket_offsets(
                            [pair_anchor[i] for i in _idx],
                            [idx_span[i] for i in _idx],
                            gap_px,
                            min_step_px,
                            _to_px,
                            downward=_down,
                        ),
                    ):
                        final_y[slot], offsets_px[slot] = anch, off

                if "drop" in pair_styles:
                    # Resolve drop ticks after the ladder determines bracket positions.
                    drop_px = _solve_drop(
                        [
                            _to_px(final_y[i]) + (offsets_px[i] if rev_flags[i] else -offsets_px[i])
                            for i in range(len(pairs))
                        ],
                        _to_px,
                    )
                    _dbars = [
                        _to_px(final_y[i]) + (offsets_px[i] if rev_flags[i] else -offsets_px[i])
                        for i in range(len(pairs))
                    ]

                    def _from_px(i: int, length: float, _b: list[float] = _dbars) -> float:
                        return _un_px(_b[i] + (-1.0 if rev_flags[i] else 1.0) * length)

                    drop_data = [(_from_px(i, a), _from_px(i, b)) for i, (a, b) in enumerate(drop_px)]

            else:
                # In data-unit mode, start at yStart or at the compared groups' maximum plus yPad.
                base = cast(float, yStart) if yStart is not None else anchor + yPad
                final_y = [base + pair_levels[i] * yStep for i in range(len(pairs))]

        if "drop" in pair_styles and drop_px is None:
            # Include explicit y positions in the domain estimate so drop ticks clear brackets
            # pinned outside the data range. Reverse brackets also require the lower bound.
            _dlo, _dhi = _nice_domain(
                min(0.0, cast(float, y_all.min() or 0.0), min(final_y)),
                max(cast(float, y_all.max() or 0.0), max(final_y)),
            )
            _dsp = (_dhi - _dlo) or 1.0
            _dch = float(_opt("height"))

            def _dpx(v: float, _lo: float = _dlo, _sp: float = _dsp, _h: float = _dch) -> float:
                return _h * (1.0 - (v - _lo) / _sp)

            _dbars2 = [_dpx(v) for v in final_y]
            drop_px = _solve_drop(_dbars2, _dpx)

            def _un_dpx(p: float, _lo: float = _dlo, _sp: float = _dsp, _h: float = _dch) -> float:
                return _lo + (1.0 - p / _h) * _sp

            drop_data = [
                (
                    _un_dpx(_dbars2[i] + (-1.0 if rev_flags[i] else 1.0) * a),
                    _un_dpx(_dbars2[i] + (-1.0 if rev_flags[i] else 1.0) * b),
                )
                for i, (a, b) in enumerate(drop_px)
            ]

        def _pair_order(ends: tuple[float, float], g1: str, i: int) -> tuple[float, float]:
            """Reorder a column-ordered (low, high) pair to (group1, group2)."""
            return ends if categories.index(g1) == idx_span[i][0] else (ends[1], ends[0])

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
                    width=width,
                    strokeWidth=strokeWidth,
                    fontSize=fontSize,
                    reverse=(g1, g2) in reverse if reverse is not None else False,
                    sigFigs=effective_sigfigs,
                    notation=pair_notations[i],
                    offset_px=offsets_px[i],
                    # Tick lengths follow column order, so reverse them when the pair order differs.
                    tick_px=(_pair_order(drop_px[i], g1, i) if drop_px is not None else tick_px),
                    tick_data=(_pair_order(drop_data[i], g1, i) if drop_data is not None else None),
                    domain_max=bracket_domain_max if i == 0 else None,
                )
            )

    # Queue the report for export metadata and render it when requested.
    record = _make_record(
        test=test,
        is_omnibus=is_omnibus,
        omnibus=omnibus_result,
        descriptives=_describe_all(groups, categories),
        comparisons=comparisons,
        comparison_test=method,
        correction=effective_correction,
        pvalues_provided=pvalues is not None,
        n_comparisons=(nComparisons if nComparisons is not None else len(report_pairs))
        if effective_correction is not None
        else None,
        intrinsically_adjusted=method in _INTRINSICALLY_ADJUSTED,
        data_checksum=_frame_checksum(data),
    )
    marker = _emit_report(record, report, saveReport)

    if not annotation_layers:
        # With no label or brackets, return an invisible layer for report-only use.
        annotation_layers.append(_empty_layer())
    # The marker links this layer to its report during save(); it is stripped from written JSON.
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
    """Build a corner-readout string from a correlation result."""
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
    label: str | None,
    coefficient: str,
    includePvalue: bool,
    includeEquation: bool,
    offsetX: float,
    offsetY: float,
    fontSize: float | None,
    sigFigs: int | None,
    notation: str | None,
    color: str | None,
    strokeWidth: float | None,
    strokeDash: bool | list[int] | None,
    opacity: float | None,
    lineStyle: dict[str, Any] | None,
    ci: float | bool,
    interval: str,
    ciColor: str | None,
    ciOpacity: float,
    report: bool,
    save: bool | str | Path,
) -> alt.LayerChart:
    """Build a fit and coefficient readout for each value of ``group_col``.

    Fit lines, confidence bands, and readouts use the ``group_col`` color encoding, allowing them
    to share the scatter's color scale. Color is looked up by value, so no sort parameter is needed.
    One report record is registered per group and attached to that group's first layer. Readouts
    stack in the ``position`` corner with a swatch in each group's color.
    """
    import numpy as np

    from ._statistics import _make_correlation_record, _ols_band, _run_correlation
    from .annotations import _TEXT_PRESETS
    from .utils import _frame_checksum

    fontSize = fontSize if fontSize is not None else _opt("fontSize")
    effective_sigfigs = sigFigs if sigFigs is not None else _opt("sigFigs")
    groups = df[group_col].unique(maintain_order=True).to_list()

    # Share style overrides across groups; the color encoding assigns group colors unless color is fixed.
    line_kwargs: dict[str, Any] = {}
    if strokeWidth is not None:
        line_kwargs["strokeWidth"] = strokeWidth
    if strokeDash is not None:
        line_kwargs["strokeDash"] = _resolve_dash(strokeDash)
    if opacity is not None:
        line_kwargs["opacity"] = opacity
    if lineStyle:
        line_kwargs.update(lineStyle)
    line_style_color = lineStyle.get("color") if lineStyle is not None else None
    if line_style_color is not None:
        line_color = None
    else:
        line_color = alt.value(color) if color is not None else alt.Color(f"{group_col}:N", legend=None)

    ci_level: float | None = None
    if ci:
        ci_level = 0.95 if ci is True else float(ci)
        if not 0.0 < ci_level < 1.0:
            raise ValueError(f"ci must be True or a confidence level in (0, 1), got {ci!r}")

    # Corner-readout stacking geometry (resolved once).
    if position is not None and position not in _TEXT_PRESETS:
        raise ValueError(f"position must be one of {sorted(_TEXT_PRESETS)} or None, got {position!r}")
    n = len(groups)
    if position is not None:
        preset = _TEXT_PRESETS[position]
        cw, chh = _opt("width"), _opt("height")
        pad = 1  # px inset from an edge, matching text's edge-inset spirit
        base_x = preset["x_frac"] * cw + (pad if preset["x_frac"] == 0 else -pad if preset["x_frac"] == 1 else 0)
        base_y = preset["y_frac"] * chh + (pad if preset["y_frac"] == 0 else -pad if preset["y_frac"] == 1 else 0)
        line_h = fontSize * 1.5
        # Stack down from top anchors, up from bottom anchors, and around middle anchors.
        anchor = 0.0 if preset["y_frac"] == 0 else (n - 1) if preset["y_frac"] == 1 else (n - 1) / 2

    # Validate and compute every group before registering any report records.
    prepared: list[tuple[Any, Any, Any, dict[str, Any], np.ndarray | None, np.ndarray | None]] = []
    for g in groups:
        gdf = df.filter(pl.col(group_col) == g)
        x = _validate_observations(gdf[x_col].to_list(), x_col, g)
        y = _validate_observations(gdf[y_col].to_list(), y_col, g)
        try:
            result = _run_correlation(method, x, y)
        except ValueError as exc:
            raise ValueError(f"correlation group {g!r}: {exc}") from exc
        band: tuple[np.ndarray, np.ndarray] | None = None
        if ci_level is not None and result["slope"] is not None:
            xs = np.linspace(float(x.min()), float(x.max()), 64)
            try:
                band = _ols_band(x, y, xs, level=ci_level, kind=interval)
            except ValueError as exc:
                raise ValueError(f"correlation group {g!r}: {exc}") from exc
        prepared.append((g, gdf, x, result, None if band is None else band[0], None if band is None else band[1]))

    layers: list[Any] = []
    staged: list[tuple[list[Any], dict[str, Any]]] = []
    for i, (g, gdf, x, result, band_lo, band_hi) in enumerate(prepared):
        g_layers: list[Any] = []

        # Draw the Pearson confidence band before the fit line, using the group's color.
        if band_lo is not None and band_hi is not None:
            xs = np.linspace(float(x.min()), float(x.max()), 64)
            band_df = pl.DataFrame({x_col: xs, y_col: band_lo, "__ci_hi": band_hi, group_col: [g] * len(xs)})
            band_fill = ciColor if ciColor is not None else line_style_color if line_style_color is not None else color
            area_kwargs: dict[str, Any] = {"fillOpacity": ciOpacity, "stroke": None, "strokeWidth": 0}
            if band_fill is not None:
                area_kwargs["fill"] = band_fill
            area = alt.Chart(_internal_data(band_df)).mark_area(**area_kwargs)
            area_enc: dict[str, Any] = {
                "x": alt.X(field=x_col, type="quantitative"),
                "y": alt.Y(field=y_col, type="quantitative"),
                "y2": alt.Y2(field="__ci_hi"),
            }
            if band_fill is None and line_color is not None:
                area_enc["color"] = line_color
            g_layers.append(area.encode(**area_enc))

        # Rank-correlation results have no slope; only Pearson results produce a fit line.
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
                    **({"color": line_color} if line_color is not None else {}),
                )
            )

        # Pair a group-colored swatch with readout text in the theme's neutral ink. Coloring the
        # text with the series color can reduce contrast for light colors.
        if position is not None:
            text = _correlation_label(
                result,
                coefficient=coefficient,
                includePvalue=includePvalue,
                includeEquation=includeEquation,
                sigFigs=effective_sigfigs,
                notation=notation,
            )
            readout_label = f"{g}: {label if label is not None else text}"
            y_i = base_y + (i - anchor) * line_h
            align, baseline = preset["align"], preset["baseline"]
            # Match the legend symbol size and stroke. The point mark's configured stroke is fixed
            # black, while the legend stroke changes for dark mode.
            sym_size = fontSize * 6
            sym_r = (sym_size / math.pi) ** 0.5  # circle radius, for placement
            gap = fontSize * 0.4  # swatch -> text
            tw = len(readout_label) * fontSize * 0.6  # rough text-width estimate (for right/center swatch x)
            if align == "left":
                text_x, sw_x = base_x + 2 * sym_r + gap, base_x + sym_r
            elif align == "right":
                text_x, sw_x = base_x, base_x - tw - gap - sym_r
            else:  # center
                text_x, sw_x = base_x, base_x - tw / 2 - gap - sym_r
            # Adjust the swatch's vertical position for the text baseline.
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
                .encode(x=alt.value(round(text_x, 2)), y=alt.value(round(y_i, 2)), text=alt.value(readout_label))
            )

        record = _make_correlation_record(result, x_col, y_col, data_checksum=_frame_checksum(gdf), group=g)
        if not g_layers:
            g_layers.append(_empty_layer())
        staged.append((g_layers, record))

    # Register reports after all groups build successfully.
    for g_layers, record in staged:
        marker = _emit_report(record, report, save)
        layers.append(alt.layer(*g_layers).properties(name=marker))

    if not layers:
        layers.append(_empty_layer())
    return cast(alt.LayerChart, alt.layer(*layers))


def correlation(
    data: "pl.DataFrame | pd.DataFrame",
    x: str,
    y: str,
    *,
    method: str = "pearson",
    groupBy: str | None = None,
    line: bool = True,
    position: str | None = "topLeft",
    label: str | None = None,
    coefficient: str = "r",
    includePvalue: bool = False,
    includeEquation: bool = False,
    verbose: bool = False,
    offsetX: float = 0,
    offsetY: float = 0,
    fontSize: float | None = None,
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
    saveReport: bool | str | Path = False,
) -> alt.LayerChart:
    """
    Annotate a scatter with a correlation readout and an OLS fit line for Pearson.

    A structured record (``kind="correlation"``) is queued for export metadata
    (see ``ds.save``), as it is for ``comparisons``.

    Combine with your scatter using ``+``:  ``chart + ds.stats.correlation(...)``.

    Parameters
    ----------
    data:
        DataFrame containing the data (polars or pandas).
    x, y:
        Column names for the two **continuous** variables.
    method:
        ``'pearson'`` (default) reports linear correlation ``r``, ``r²``, and the
        slope/intercept of an OLS line. ``'spearman'`` reports rank correlation
        ``ρ``; ``'kendall'`` reports rank correlation ``τ``. Rank methods do not
        report ``r²`` or draw a line. Results match pandas' ``DataFrame.corr``.
    groupBy:
        **Grouped mode.** A column that splits the scatter into series (e.g. ``"cell_line"``).
        A fit, coefficient, and optional confidence band are computed per group. Lines, bands,
        and readouts use the same color encoding as the scatter; encode color by the same field
        (for example, ``color=alt.Color("cell_line:N")``) to match the colors. The color scale
        does not require a sort parameter. Readouts stack at ``position`` and pair a series-color
        swatch with coefficient text in the theme's neutral color. One record is registered per
        group. With ``ci=True``, give the scatter an explicit y-axis title such as
        ``alt.Y("val:Q", title="…")``. Vega can otherwise merge the band's internal upper-bound
        field into the axis title. A custom ``label`` is prefixed with each group's label.
    line:
        Draw the OLS fit line. Default ``True``. Applies only to ``method="pearson"``
        and has no effect for rank methods. Set ``False`` to suppress it and, for example, compose
        your own line from the returned/recorded slope and intercept.
    position:
        Corner preset (a ``text`` position, e.g. ``'topLeft'``) for the readout.
        Default ``'topLeft'``. ``None`` computes the result for the report/metadata but
        draws no label.
    label:
        Override string for the corner readout. ``None`` builds it from the parts below.
    coefficient:
        For Pearson, select ``'r'`` (default), ``'r2'`` (``r²``), or ``'both'``.
        Ignored for rank methods, which report ``ρ`` or ``τ``.
    includePvalue:
        Append the p-value to the readout. Default ``False``.
    includeEquation:
        Pearson only – append the fit equation ``, y = 0.84x + 0.27``. Default ``False``.
    verbose:
        When ``True``, equivalent to ``coefficient="both", includePvalue=True,
        includeEquation=True``; these settings override the individual arguments.
        Default ``False``. The default readout is ``r = 0.87``
        (Pearson) / ``ρ = 0.81`` (rank); ``verbose=True`` gives
        ``r = 0.87, r² = 0.76, P < 0.001, y = 0.84x + 0.27``.
    offsetX, offsetY:
        Pixel offsets for the readout, forwarded to ``text``.
    fontSize:
        Font size of the readout. Defaults to the theme's primary ``fontSize``
        (``6`` under the built-in defaults), matching the axis font.
    sigFigs, notation:
        Significant figures / number format for the readout (coefficient, r², p-value,
        and fit equation), as in ``comparisons``. ``sigFigs=None`` reads the theme.
    color, strokeWidth, strokeDash, opacity:
        Style overrides for the fit line. Each defaults to ``None``, in which case the
        line inherits that property from the theme's ``mark_line`` config.
    lineStyle:
        Raw ``mark_line`` properties applied after the curated style arguments, for example
        ``{"interpolate": "monotone", "strokeCap": "round"}``. These keys override the
        corresponding ``color``, ``strokeWidth``, and other curated arguments in single and
        grouped modes.
    ci:
        Draw a shaded interval band around the OLS fit (Pearson only). ``False``
        (default) draws no band. ``True`` draws a 95% band. A float in ``(0, 1)`` sets
        the confidence level (e.g. ``0.99``). The band is narrowest at the mean of ``x``
        and widens toward its extremes. Its syntax is validated for rank methods, although
        they do not draw a band.
    interval:
        Which band ``ci`` draws: ``'confidence'`` (default, an interval for the mean
        response) or ``'prediction'`` (an interval for a single new observation).
    ciColor:
        Fill color of the band. ``None`` (default) uses the effective fit-line color,
        including a ``lineStyle`` color, or the theme's mark color (black or white,
        depending on dark mode). This default is resolved when the chart is built. To
        resolve it separately for light and dark exports, pass a chart-building callable
        to ``ds.save()`` (as with ``shade``).
    ciOpacity:
        Fill opacity of the band. Default ``0.15``.
    report:
        ``True`` prints the report (coefficient, r², p, fit, n) to stdout. Default
        ``False``. The record is queued for export metadata regardless.
    saveReport:
        ``True`` writes the report to ``dysonsphere_report_<timestamp>.txt`` in the cwd;
        a path writes it to that directory.

    Examples
    --------
    ::

        scatter = alt.Chart(data).mark_point().encode(x="height:Q", y="weight:Q")
        scatter + ds.stats.correlation(data, "height", "weight")                 # r + r² + OLS line
        scatter + ds.stats.correlation(data, "height", "weight", method="spearman")  # ρ, no line
        scatter + ds.stats.correlation(
            data, "height", "weight",
            color="#c0392b", lineStyle={"strokeDash": [4, 2]},
        )
    """
    x_col, y_col = x, y
    from ._statistics import _make_correlation_record, _ols_band, _run_correlation
    from .utils import _ensure_polars, _frame_checksum

    if verbose:  # shortcut for the fullest readout; overrides the individual toggles
        coefficient, includePvalue, includeEquation = "both", True, True
    if coefficient not in ("r", "r2", "both"):
        raise ValueError(f"coefficient must be 'r', 'r2', or 'both', got {coefficient!r}")
    if method not in ("pearson", "spearman", "kendall"):
        raise ValueError(f"method must be one of ['kendall', 'pearson', 'spearman'], got {method!r}")
    _validate_ci_syntax(ci)
    if lineStyle is not None and not isinstance(lineStyle, dict):
        raise ValueError(f"lineStyle must be a dict of mark_line properties, got {type(lineStyle).__name__}")
    if isinstance(notation, dict):
        raise ValueError("correlation notation must be one of None/'scientific'/'e'/'power'.")
    _validate_notation_syntax(notation)
    if interval not in ("confidence", "prediction"):
        raise ValueError(f"interval must be 'confidence' or 'prediction', got {interval!r}")
    if position is not None:
        from .annotations import _TEXT_PRESETS

        if not isinstance(position, str) or position not in _TEXT_PRESETS:
            raise ValueError(f"position must be one of {sorted(_TEXT_PRESETS)} or None, got {position!r}")

    data = _ensure_polars(data)
    if groupBy is not None:
        _validate_statistical_data(data, x_col, y_col, groupBy, numeric_x=True)
    else:
        _validate_statistical_data(data, x_col, y_col, numeric_x=True)

    # Grouped mode computes separate results and layers for each group.
    if groupBy is not None:
        return _add_grouped_correlation(
            data,
            x_col,
            y_col,
            groupBy,
            method=method,
            line=line,
            position=position,
            label=label,
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
            ciColor=ciColor,
            ciOpacity=ciOpacity,
            report=report,
            save=saveReport,
        )

    x_values = data[x_col].cast(pl.Float64).to_numpy()
    y_values = data[y_col].cast(pl.Float64).to_numpy()
    try:
        result = _run_correlation(method, x_values, y_values)
    except ValueError as exc:
        raise ValueError(f"correlation {x_col!r} vs {y_col!r}: {exc}") from exc

    layers: list[Any] = []

    # Draw the optional Pearson confidence or prediction band beneath the fit line.
    # Sample the x range at 64 points to render the curved band.
    if ci and result["slope"] is not None:
        import numpy as np

        level = 0.95 if ci is True else float(ci)
        if not 0.0 < level < 1.0:
            raise ValueError(f"ci must be True or a confidence level in (0, 1), got {ci!r}")
        if interval not in ("confidence", "prediction"):
            raise ValueError(f"interval must be 'confidence' or 'prediction', got {interval!r}")
        xs = np.linspace(float(x_values.min()), float(x_values.max()), 64)
        try:
            lo, hi = _ols_band(x_values, y_values, xs, level=level, kind=interval)
        except ValueError as exc:
            raise ValueError(f"correlation {x_col!r} vs {y_col!r}: {exc}") from exc
        # Use y_col for the lower bound so its derived axis title matches the base chart;
        # y2 holds the upper bound and has no axis title.
        band_df = pl.DataFrame({x_col: xs, y_col: lo, "__ci_hi": hi})
        # Match the fit line's color. Dark-mode color is resolved when the chart is built, so
        # use a callable with save() when exporting against different backgrounds. Disable the
        # area mark's stroke to prevent the theme's area styling from adding one.
        style_color = lineStyle.get("color") if lineStyle is not None else None
        band_fill = (
            ciColor
            if ciColor is not None
            else style_color
            if style_color is not None
            else color
            if color is not None
            else ("white" if _opt("darkmode") else "black")
        )
        layers.append(
            alt.Chart(_internal_data(band_df))
            .mark_area(fill=band_fill, fillOpacity=ciOpacity, stroke=None, strokeWidth=0)
            .encode(
                x=alt.X(field=x_col, type="quantitative"),
                y=alt.Y(field=y_col, type="quantitative"),
                y2=alt.Y2(field="__ci_hi"),
            )
        )

    # Rank-correlation results have no slope; only Pearson results produce an OLS fit line.
    if line and result["slope"] is not None:
        x0, x1 = float(x_values.min()), float(x_values.max())
        slope, intercept = result["slope"], result["intercept"]
        # Use the original column names so the derived axis titles match the base chart and do
        # not add duplicate title text.
        fit_df = pl.DataFrame({x_col: [x0, x1], y_col: [slope * x0 + intercept, slope * x1 + intercept]})
        # The line inherits the theme's mark_line config unless style arguments override it;
        # lineStyle is applied after the curated arguments.
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
        # Leave titles and axes unset so the base chart's titles remain. Use field/type arguments
        # so column names containing ':' are treated as field names.
        layers.append(
            alt.Chart(_internal_data(fit_df))
            .mark_line(**mark_kwargs)
            .encode(x=alt.X(field=x_col, type="quantitative"), y=alt.Y(field=y_col, type="quantitative"))
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
            _text(
                text,
                position=position,
                offsetX=offsetX,
                offsetY=offsetY,
                fontSize=fontSize if fontSize is not None else _opt("fontSize"),
            )
        )

    # Queue the record for export metadata and render it when requested.
    record = _make_correlation_record(result, x_col, y_col, data_checksum=_frame_checksum(data))
    marker = _emit_report(record, report, saveReport)

    if not layers:
        layers.append(_empty_layer())
    # The marker links this layer to its report during save(); it is stripped from written JSON.
    return cast(alt.LayerChart, alt.layer(*layers).properties(name=marker))

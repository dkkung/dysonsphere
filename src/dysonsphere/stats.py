"""Statistical inference annotations - significance brackets, omnibus labels, correlation readouts.

The annotation wrappers for what ``_statistics.py`` computes: ``comparisons`` (pairwise
brackets and omnibus test labels) and ``correlation`` (coefficient readout + OLS fit line).
Pure computation stays in ``_statistics.py`` (no Altair there); this module builds the Vega-Lite
layers that present it. Statistical results are registered in the ``_statistics._REPORTS``
registry and embedded into exports by ``save()`` via layer-name markers.
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

# The public ds.stats API; its contents are not star-imported into the root namespace.
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
    # `sigFigs` sets the significant-figure precision; `%g` gives that and strips trailing
    # zeros. Plain notation floors at a fixed 0.001 convention (`P < 0.001`); scientific/e/
    # power never floor (they represent any magnitude at `sigFigs` figures). `symbol=False`
    # (labelStyle="value") drops the "P" symbol AND the redundant "= ", but keeps a MEANINGFUL
    # operator - "< " (the flooring convention) and "≈ " (power's nearest-power rounding).
    if notation not in (None, "scientific", "e", "power"):
        raise ValueError(f"notation must be 'power', 'scientific', or 'e', got {notation!r}")
    lead = "P " if symbol else ""  # the statistical symbol
    eq = "= " if symbol else ""  # the equals is redundant once the symbol is gone
    if p == 0.0:
        # A zero from a floating-point statistical routine is an underflow, not an exact probability.
        # Use the same minimum-normal bound as the report record, and keep the bound operator in
        # every notation so notation never turns underflow into an exact value or log10(0) failure.
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


# --- shared resolvers for comparisons / _add_grouped_comparisons ---------------------------
# Extracted so the single-factor and grouped paths share one implementation (they had drifted -
# see the y-spacing chart_height guard). Pure functions; error messages are load-bearing (pinned
# by `match=` tests in test_statistics.py) - keep them verbatim.


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
    """Assign a stacking level to each ``(lo, hi)`` index span via greedy interval scheduling:
    left endpoint first, ties by right endpoint, each placed on the lowest level whose occupants
    it doesn't overlap. Returns the level per span, in input order.

    Lexicographic order groups every comparison sharing a left group into one nested staircase
    (all of 1v2, 1v3, 1v4, then 2v3, 2v4, ...), which reads far better than interleaved anchors.
    It is also provably level-minimal: the overlap graph of intervals is perfect, so greedy
    coloring in left-endpoint order uses exactly the maximum clique. (Ordering by span length
    instead - narrow brackets lowest, through 3.10.1 - reads worse AND overflows by a level on
    ~12% of pair subsets.) Brackets sharing an endpoint count as overlapping, since two on one
    level would render as a single continuous line."""
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
    """Each bracket's ``(anchor, pixel offset)`` - the data value to hang it from, and how far.

    Brackets are placed on a **ladder**: within a set of brackets that overlap, consecutive rungs
    are exactly ``step_px`` apart and the whole ladder sits as low as every bracket's own data
    allows. A ladder rather than per-bracket bumping so the stack reads as one deliberate rhythm
    instead of leaving a short bracket stranded well below the rest.

    Ladders are per **connected component** of the span-overlap graph, so brackets with nothing in
    common are never tied to each other - two comparisons at opposite ends of a chart each hug
    their own groups instead of the shorter one floating up to meet the taller.

    Rung ORDER within a component is chosen per component from two candidates, scored as
    ``(rungs used, total pixels the brackets float above their own data)`` with ties going to the
    first: **lexicographic** by span, which reads as a fan (every comparison sharing a left group
    runs consecutively - 1v2, 1v3, 1v4, then 2v3, 2v4), and **by data demand**, which puts the
    bracket nearest the data on the first rung and so keeps the ladder tight. On ordered groups
    the two cost the same and the fan is free; on unordered groups the fan would drag brackets
    far above the data they compare, and demand order wins.

    The rungs are CONSTANT pixel offsets off a datum anchor, so they are exact at any y domain
    without the scale being consulted - which is what makes this survive facets, concats and
    ``add_multilabel``, where Vega renames the y scale. Only the ladder arithmetic needs pixel
    positions, and for that ``to_px`` estimates the rendered domain; a mis-estimate shifts a
    ladder slightly, it cannot change the gap between rungs."""
    n = len(anchors)
    if not n:
        return []
    # smaller px = higher on screen, so an upward ladder subtracts the gap and a downward one adds
    _dir = 1.0 if downward else -1.0
    required = [to_px(anchors[i]) + _dir * gap_px for i in range(n)]

    def _overlap(i: int, j: int) -> bool:
        return not (spans[i][1] < spans[j][0] or spans[i][0] > spans[j][1])

    # Connected components of the overlap graph (transitively - a chain shares one ladder).
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
        # Two candidate rung orders, scored and the better one taken. LEXICOGRAPHIC reads as a
        # fan - every comparison sharing a left group runs consecutively (1v2, 1v3, 1v4, then
        # 2v3, 2v4) instead of alternating anchors. BY DATA DEMAND puts the bracket nearest the
        # data on the first rung, which is what lets the ladder sit tight against its groups.
        # Neither wins outright: on ordered groups (a dose response) they cost the same, so the
        # fan is free; on unordered groups the fan drags brackets far above the data they
        # compare, and demand order stays tight. Score = (rungs used, total pixels the brackets
        # float above their own data), lower better, ties to lexicographic.
        candidates = (
            sorted(members, key=lambda i: (spans[i][0], spans[i][1])),
            sorted(members, key=lambda i: (_dir * required[i], i)),
        )
        best: tuple[tuple[int, float], dict[int, int], float] | None = None
        for order in candidates:
            level = _assign(order)
            base = pick(required[i] - _dir * level[i] * step_px for i in members)
            float_px = sum(_dir * ((base + _dir * level[i] * step_px) - required[i]) for i in members)
            # Rounded: the two orders often tie mathematically and differ only in summation order,
            # by ~1e-14 px - without this that noise, not the tie-break, picks the layout.
            score = (max(level.values()), round(float_px, 6))
            if best is None or score < best[0]:
                best = (score, level, base)
        assert best is not None
        _, level, base = best
        # One anchor for the whole ladder - the member furthest into the margin, so the rungs are
        # measured from a single data value and their spacing is pure arithmetic.
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
            # The pad is a target for the DROP; the minimum cap only has to avoid touching, so it
            # is held back by `hard` rather than `padded` - otherwise a label directly beneath
            # deletes the tick instead of just stopping it from dropping.
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
    chartWidth: float | None = None,
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

    # --- p-value ---
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

    # bonferroni correction (skip for tukey_hsd — correction is built in)
    if correction == "bonferroni" and test != "tukey_hsd":
        pvalue = min(pvalue * n_comparisons, 1.0)

    label = _format_label(pvalue, label_style, sigFigs, notation)

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
        chartWidth = _opt("width")
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
    # `offset_px` lifts the bracket off its data anchor in PIXELS, so the gap does not depend on
    # the rendered y domain (which Vega only fixes after nice-rounding and the layer domain union
    # - the circularity that made data-unit gaps drift). Everything above the anchor is a pixel
    # offset and contributes nothing to the domain; the anchor itself is already in the data.
    _sign = 1 if reverse else -1
    _rule_kwargs = {
        "strokeWidth": strokeWidth,
        "strokeDash": [0, 0],
        "strokeCap": stroke_cap,
    }
    # A CONSTANT pixel offset off the data anchor: exact at any y domain, and it survives being
    # placed inside a facet/concat, which a scale expression does not.
    if offset_px:
        _rule_kwargs["yOffset"] = _sign * offset_px

    # dy offsets in SVG pixels. Asterisk glyphs sit close to the baseline so a small
    # offset seats them flush; alphanumeric labels (including "ns") need more clearance.
    # reverse=False keeps the inherited default baseline (its spacing already looks right).
    # reverse=True sets baseline="top" so the text hangs *below* the bar instead of
    # overlapping it — the inherited baseline left the below-bar text cramped.
    _dy_mag = 2 if label_style == "asterisks" and label != "ns" else 4
    text_dy = (_dy_mag if reverse else -_dy_mag) + _sign * offset_px
    text_baseline = "top" if reverse else None
    # In pixel mode the end legs are a pixel offset off the same anchor; otherwise data units.
    tick_y2 = y if tick_px is not None else (y + tick_height if reverse else y - tick_height)
    # drop ticks differ per end, so each gets its own kwargs
    _lens = (tick_px, tick_px) if isinstance(tick_px, (int, float)) else tick_px
    _tick_kwargs_l, _tick_kwargs_r = dict(_rule_kwargs), dict(_rule_kwargs)
    # A drop tick ends at a DATA position. comparisons cannot see the base chart's y domain,
    # so a pixel length measured against a guessed one overshoots through the data it should stop
    # above - the further the rendered domain is from that guess, the worse.
    tick_y2_l, tick_y2_r = tick_data if tick_data is not None else (tick_y2, tick_y2)
    if _lens is not None and tick_data is None:
        _tick_kwargs_l["y2Offset"] = _sign * offset_px - _sign * _lens[0]
        _tick_kwargs_r["y2Offset"] = _sign * offset_px - _sign * _lens[1]

    # `domain_max` raises ONLY the top of the shared y scale, leaving the lower bound, `zero`,
    # nice-rounding and any user setting on the other end intact. It is set on one bracket layer
    # (an explicit bound wins the scale merge) to make room for a top-preset test label above the
    # stack; without it the label would sit flush at the plot edge, on top of the brackets.
    _y_enc = alt.Y("y:Q") if domain_max is None else alt.Y("y:Q", scale=alt.Scale(domainMax=domain_max))
    # Pixels, not x:N - an encoding contributes a scale that cannot merge when the base
    # resolves x independently (mark_violin), stranding it as its own axis.
    geo = _band_geometry(len(categories), chartWidth)
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
    chartWidth: float,
    fontSize: float,
    offset_px: float = 0.0,
) -> alt.Chart:
    """A bare p-value label centred over one group's band, anchored at data-coordinate ``y`` and
    lifted ``offset_px`` pixels - the reference-mode annotation (no bracket; the comparison to the
    reference is implicit). A lone label has nothing to collide with, so a constant pixel offset is
    already exact - no scale expression needed, unlike the stacked brackets."""
    x_px = _band_geometry(len(categories), chartWidth).centers[categories.index(group)]
    return (
        alt.Chart(_internal_data([{"y": y, "label": label}]))
        .mark_text(align="center", baseline="bottom", fontSize=fontSize, dy=-4 - offset_px)
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

    from ._statistics import _PAIRWISE_TESTS, _adjust, _post_hoc_matrix

    idx = {c: i for i, c in enumerate(categories)}
    if method in _MATRIX_POSTHOCS:
        mat = _post_hoc_matrix(method, groups, correction, nComparisons, labels=categories)
        return [float(mat[idx[g1]][idx[g2]]) for g1, g2 in pairs]
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
    fontSize: float,
    chartWidth: float,
    offset_px: float = 0.0,
    tick_px: float | tuple[float, float] | None = None,
    tick_data: tuple[float, float] | None = None,
    reverse: bool = False,
) -> alt.LayerChart:
    """One within-category bracket for grouped comparisons.

    The top bar spans the two xOffset sub-bars via the SHARED xOffset scale (``sort`` matched to the
    bars so they keep their order), the optional end-ticks drop from it, and the label centres on the
    bracket's own midpoint. The bar and ticks are encoded (no pixel math), so they track wherever
    Vega lays the grouped bars out; only the label is positioned in pixels, since it has no sub-bar
    of its own to ride. ``reverse`` hangs the bracket below its groups with the ticks pointing up.
    """
    rk: dict[str, Any] = {"strokeWidth": strokeWidth, "strokeDash": [0, 0], "strokeCap": _opt("strokeCap")}
    # Same placement contract as the single-factor path: anchor in data, lift in pixels via a
    # render-time scale expression, so the gap does not follow the rendered y domain.
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
    # Asterisk glyphs sit close to the baseline; alphanumeric labels ("ns", "P = …") need more.
    _dym = 2 if label_style == "asterisks" and label != "ns" else 4
    dy = (_dym if reverse else -_dym) + _sign * offset_px
    # Centred on the bracket's own midpoint in PIXELS. The label cannot ride the xOffset
    # encoding (a subset domain there reorders the bars), and the band centre it used through
    # 3.10.1 drifts a whole sub-bar away from an asymmetric pair - far enough to sit over a
    # group the comparison does not involve.
    _sub = _nested_band_centers(len(categories), len(level_order), chartWidth)[categories.index(category)]
    _mid_px = (_sub[level_order.index(level1)] + _sub[level_order.index(level2)]) / 2
    text = (
        alt.Chart(_internal_data([{"__y": y, "__label": label}]))
        .mark_text(align="center", fontSize=fontSize, dy=dy, **({"baseline": "top"} if reverse else {}))
        .encode(x=alt.value(_mid_px), y=alt.Y("__y:Q"), text="__label:N")
    )
    if bracket_style in ("bracket", "drop"):
        # In pixel mode both ends sit at the anchor and the leg length rides in y2Offset. Drop
        # ticks differ per end, and y2Offset is a mark property, so each end needs its own layer.
        _lens = (tick_px, tick_px) if isinstance(tick_px, (int, float)) else tick_px
        legs = []
        _ends = tick_data if tick_data is not None else (None, None)
        for level, tlen, tend in zip((level1, level2), _lens if _lens is not None else (None, None), _ends):
            tk = dict(rk)
            y2_val = y + tick_height if reverse else y - tick_height
            if tend is not None:
                # A drop tick ends at a DATA position, not a pixel distance. comparisons
                # cannot see the base chart's y domain - an explicit scale=alt.Scale(domain=...)
                # is invisible to it - so a pixel length measured against a guessed domain runs
                # straight through the data it should stop above.
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
    """A bare p-value label centred over one (category, level) sub-bar - the grouped reference-mode
    annotation (no bracket). Rides the SHARED x + xOffset scales (sort matched to the bars) so it
    lands on that sub-bar wherever Vega lays the grouped bars out. ``offset_px`` lifts it off its
    anchor in pixels, so the gap does not vary with the rendered y domain."""
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
    chartWidth: float | None,
    report: bool,
    save: bool | str | Path,
) -> alt.LayerChart:
    """Grouped (two-factor) comparisons: compare the xOffset levels within each x-category.

    One bracket per (category, pair), each placed above its OWN category's bars (per-category, so
    groups of wildly different magnitude don't push short brackets sky-high), carrying a real
    per-category p-value from ``test`` (corrected over the whole family by ``correction``). A single
    record is registered, its comparisons labelled ``"<category> (<level>)"``.
    """
    from scipy import stats as _stats

    from ._statistics import _TEST_DISPLAY, _adjust, _describe_all, _make_record, _pair_effect
    from .utils import _frame_checksum

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
    # Resolved before the reference block so `reference` + pairs="all" hits its don't-also-pass raise.
    pairs = _resolve_pairs(pairs, level_order, f"xOffset {xoffset_col!r} levels")

    # Reference mode: compare every other level against `reference` WITHIN each category, drawing the
    # p-value above each non-reference sub-bar (no bracket). Derives its own level-pairs.
    # Remember which spacing args the caller passed: any one of them opts out of pixel
    # placement below, since an explicit number is data units on the user's own scale.
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

    chartWidth = chartWidth if chartWidth is not None else _opt("width")
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
    # See the single-factor path: an auto leg height is pixels, not data units.
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

    # All comparison keys, in the category-major then pair order the loops use.
    all_keys = [_grouped_key(cat, l1, l2, is_reference) for cat in categories for l1, l2 in pairs]

    # Explicit p-values (a dict keyed by (category, level|pair)) skip the test AND correction, like
    # the single-factor `pvalues` list. Must cover every comparison exactly (no missing, no extra).
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

    # p-values + effects, iterated category-major then pair (the layer loop matches this order).
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
            values = cdf.filter(pl.col(xoffset_col) == lv)[y_col].to_list()
            desc_groups.append(_validate_observations(values, y_col, f"{cat!r} / {lv!r}"))
            desc_labels.append(f"{cat} ({lv})")
    descriptives = _describe_all(desc_groups, desc_labels)

    # Explicit y control. `yStart` (brackets only) mirrors single-factor: the EXACT stack base -
    # a scalar for all categories, or a dict for a per-category base (partial - unlisted → auto).
    # It does NOT apply to reference mode (no stack); passing it there raises. `yPositions` is the
    # exact y in three forms: a single number → one global flat row; a dict keyed by CATEGORY → a
    # flat row per category; a dict keyed by (category, level)/(category, pair) → per-comparison.
    # Dict keys must be uniform. Precedence: flat > per-category > per-comparison > (yStart / auto).
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
        # Pixel placement, matching the single-factor path: each bracket anchors at its own
        # level-pair's maximum WITHIN this category, and overlapping pairs are pushed apart by a
        # label's worth of pixels - all resolved by Vega against the real scale.
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
            # Over every sub-bar the bracket SPANS, not just its endpoints - see the single-factor
            # path: a taller level in the middle would otherwise sit above the bracket. A reverse
            # bracket hangs BELOW its groups, so it anchors on their minimum instead.
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
            # Up and down brackets sit on opposite sides of the data and never collide, so each
            # direction gets its own ladder (same as the single-factor path).
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
                # The y scale is shared across categories, so drop lengths - unlike the ladder
                # offsets above, which are relative - must be measured against the WHOLE frame's
                # domain. A per-category domain sends the ticks straight through the data.
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
                # Every label in a category centres on the same band, and the sub-bar pixel
                # positions are Vega's, not _band_geometry's - so a label is treated as covering
                # the whole category. Conservative: it can only shorten a tick, never overlap one.
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
            # Every bracket's y, resolved before emitting so drop ticks can be solved against it
            # whichever placement mode is in use.
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
                # yPositions flat > per-category > per-comparison > the sub-bar's own data max + yPad.
                if ypos_flat is not None:
                    y = ypos_flat
                elif ypos_cat is not None and cat in ypos_cat:
                    y = ypos_cat[cat]
                elif ypos_map is not None and key in ypos_map:
                    y = float(ypos_map[key])
                else:
                    sub_max = cast(float, cdf.filter(pl.col(xoffset_col) == l2)[y_col].cast(pl.Float64).max() or 0.0)
                    # Auto: anchor at the sub-bar's own maximum, lift in pixels (see single-factor).
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
                        chartWidth=chartWidth,
                        reverse=rev_flags[pi],
                        offset_px=(cat_offsets[pi] if grp_pixel_mode else 0.0),
                        tick_px=(
                            cat_drop[pi] if cat_drop is not None else (_BRACKET_TICK_PX if _tick_arg is None else None)
                        ),
                        tick_data=(cat_drop_data[pi] if cat_drop_data is not None else None),
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
        comparison_test=None if pval_map is not None else test,
        correction=effective_correction,
        pvalues_provided=pval_map is not None,
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
    chartWidth: float | None = None,
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
      ``'wilcoxon'``, ``'tukey_hsd'``) — draws a bracket per pair in ``pairs``,
      stacked automatically so they don't overlap (shorter-span pairs sit lower;
      overlapping spans are bumped up a level).
    - **Omnibus** (``'anova'``, ``'kruskal'``, ``'friedman'``,
      ``'alexandergovern'``) — runs one "are *any* groups different?" test and
      places its result as a corner label via ``text`` (see
      ``testLabelPosition``). If ``pairs`` is also given, a post-hoc test (see
      ``postHoc``) fills the brackets.

    Setting ``reference`` overrides both with **reference mode**: compare every
    other group against one reference and draw the p-value above each mark with no
    bracket (see ``reference``).

    A descriptive + effect-size report is generated on every call and queued for
    the export metadata written by ``ds.save()`` (see ``report``/``saveReport``).

    **Placement.** By default each annotation anchors at the data maximum of the pair it
    compares and is lifted a fixed number of pixels, so it stays with its own groups rather
    than riding the tallest annotated one, and the gap looks the same on every chart whatever
    the y range. Brackets that overlap sit on an evenly spaced **ladder** - one step of a
    label's height between rungs - placed as low as every bracket's own data allows, so a short
    comparison joins the rhythm instead of being stranded below the rest. Brackets sharing no
    category form separate ladders, so a comparison at one end of the chart is never dragged up
    by a taller one elsewhere, and a ``reverse`` bracket hangs below its groups on a ladder of
    its own - the two directions never push each other around.

    On a log axis the rung spacing is exact, but the lowest bracket of a stack can start inside
    its own data - deciding how low a stack may sit needs the data-to-pixel mapping, which is
    estimated as linear. Pass ``yPositions`` to place them yourself there.
    The lift is a Vega expression over the rendered y scale, so an explicit ``domain``,
    ``zero=False`` and nice-rounding all work without being predicted in advance - and because
    the offsets are not data values, the y axis ends at your data and the annotations sit in
    the margin above it. Pass any of ``yStart``/``yStep``/``yPad``/``yPositions`` to place them
    in data units on your own scale instead.

    The top of the y scale is raised (``domainMax``) far enough for the stack to fit inside the
    plot in two cases: a test label at one of the ``top`` presets, which would otherwise sit on
    the brackets, and a closed plot (``ds.theme(closed=True)``), whose border would leave them
    outside the box. Only the upper bound moves - the lower bound, ``zero`` and nice-rounding are
    untouched - and only when there are brackets to clear.

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
        List of ``(group1, group2)`` tuples identifying the comparisons to
        annotate with brackets. Required for pairwise ``test`` values. Optional
        for omnibus tests — pass ``None`` for an omnibus-only corner label, or a
        list to also draw post-hoc brackets.

        ``"all"`` expands to every unique pair, in ``categories`` order (in
        grouped mode, every unique pair of ``xOffset`` levels). Besides being
        shorter, it keeps ``correction`` honest: the family size defaults to
        ``len(pairs)``, so hand-listing a subset of the comparisons you actually
        ran under-corrects them. Note the bracket count grows as
        ``n(n-1)/2`` — 6 brackets at 4 groups, 10 at 5, 15 at 6 — so beyond
        4 or 5 groups prefer an omnibus ``test`` with ``pairs=None`` (which
        already reports every post-hoc comparison) and bracket only the few
        pairs worth showing.
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
        ``pairs`` is given. ``None`` (default) picks a sensible default per
        omnibus test: ``anova → 'tukey_hsd'``, ``alexandergovern →
        'games_howell'``, ``kruskal → 'dunn'``, ``friedman → 'nemenyi'``. May
        also be set to any pairwise test name. Dunn, Nemenyi, and Games-Howell
        are computed in-house (validated against scikit-posthocs / pingouin);
        ``correction`` adjusts them over all unique pairs. Ignored for pairwise
        ``test``. Grouped ``xOffset`` mode does not accept ``postHoc``; use one
        of its supported pairwise tests directly.
    pvalues:
        Pre-computed final p-values skip pairwise calculation and correction. **Pairwise:**
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
        (BH assumes independence / positive dependence; BY is valid under
        arbitrary dependence but more conservative). For pairwise/post-hoc
        bracket p-values; ignored for ``tukey_hsd`` (correction is built in) and
        when ``pvalues`` is provided.
    nComparisons:
        Total family size for the correction (the denominator ``m``). Defaults
        to ``len(pairs)`` when a ``correction`` is set and not given explicitly.
        In grouped mode it is the total computed matrix family (``len(categories) * len(pairs)``),
        even when only a subset is drawn. It must be a positive, non-bool integer and, when
        correction applies, at least that family size. Larger values are allowed. Supplied final
        p-values and Tukey HSD are not readjusted.
    reference:
        **Reference mode (compare-against-one).** A single group to compare every
        other group against, drawing the p-value **above each non-reference mark
        with no bracket** (the comparison is implicit - a control/many-vs-one
        design). Derives its own comparisons, so ``pairs`` must be left ``None``.
        Only the pairwise tests are supported (not omnibus); ``correction`` adjusts
        over the whole family of ``len(categories) - 1`` comparisons. Labels sit at
        each group's OWN data max, so overlay your points (they clear the data).
        Distinguishing the reference visually (e.g. a darker fill) is left to your
        chart - nothing is injected. Without ``xOffset``, ``reference`` is a
        category of ``x``; with ``xOffset`` (grouped mode) it is an xOffset
        **level**, compared within each x-category (one label per non-reference
        sub-bar). ``bracketStyle``/``reverse``/``tickHeight`` are inert here (no
        bracket); ``yStart`` does not apply (no stack) and raises if set. ``pvalues``
        (a group-keyed dict) supplies precomputed p-values, and ``yPositions`` places
        labels - a single number for a flat row, or a group-keyed dict per label (see
        those params).
    xOffset:
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
        chart's ``xOffset`` encoding (and ``categories`` must match the ``x`` sort), or the shared
        scale reorders the bars. Explicit values must match observed levels exactly once; tuple/
        list order and numeric category values are preserved. ``None`` (default) reads the data's
        first-appearance order.
    yPositions:
        Explicit y positions (data units) for the annotations. **A single number** puts
        *every* annotation at that y - one global flat row. **Pairwise:** a list, one per
        pair in order (overrides auto-stacking). **Reference mode:** a **dict** keyed by the
        non-reference **group** (single-factor) or ``(category, level)`` (grouped) for a
        per-label height. **Grouped** accepts a number or supported dict, not a list. It additionally
        accepts a dict keyed by **category** -
        a flat row per category, each at its own height (handy when categories span very
        different magnitudes); and grouped brackets take ``(category, (level1, level2))``
        keys (order-insensitive). Dicts are partial (unlisted → auto) and their keys must be
        uniform (all category names, or all tuples). Beats ``yStart``; unknown keys raise.
    yStart:
        The exact y (data units) of the lowest bracket - the stack base (levels rise from it
        by ``yStep``). **Setting it opts the whole stack into data-unit placement** (see the
        note below). **Grouped (`xOffset`) brackets** additionally accept a **dict** keyed by
        category for a per-category base (partial - unlisted categories use the auto base).
        **Does not apply to reference mode** (there is no stack - each label sits above its own
        mark); passing it there raises. Use ``yPositions`` for exact per-label heights.
    yStep:
        Vertical distance (data units) between stacking levels, when placement is in data
        units. Setting it opts out of automatic pixel placement.
    yPad:
        Padding (data units) above the data maximum, when placement is in data units. Setting
        it opts out of the automatic pixel placement described above.
    categories:
        Ordered list of all x-axis categories. For data-backed comparisons, supplied values must
        match observed values exactly once; tuple/list order and numeric values are preserved.
        Inferred from ``data`` (sorted alphabetically) when not provided. Standalone reference
        annotations without data do not receive observed-coverage validation.
    chartWidth:
        Width of the chart in pixels, used to compute text x positions.
        Auto-detected from ``ds.theme()`` when not set.
    bracketStyle:
        ``'bracket'`` (default; bar + end ticks), ``'line'`` (horizontal bar only)
        or ``'drop'`` (end ticks reaching down toward each group's own data)
        applied to every bracket. Or a ``dict`` mapping a pair to its style for
        per-pair control, e.g. ``{("A", "B"): "line", ("A", "C"): "bracket"}`` —
        keys match either pair order; pairs absent from the dict fall back to
        ``'bracket'``.
    labelStyle:
        ``'p'`` (default) renders ``P = 0.012`` / ``P < 0.001``. ``'asterisks'``
        renders ``*`` / ``**`` / ``***`` / ``ns``. ``'value'`` renders the bare
        value to save room - the same as ``'p'`` but without the ``P`` symbol and
        the redundant ``= `` (``0.012``), keeping a meaningful operator (``< 0.001``
        when floored, ``≈ 10⁻⁵`` for ``notation='power'``). ``notation`` still applies.
    tickHeight:
        Height of bracket end ticks in data units, used when placement is in data units.
        Under automatic placement the ticks are a fixed 2 **pixels** on any y range. Always
        positive, so it works with reverse
        (negative-``yStep``) brackets without an explicit override. Only used when
        ``bracketStyle='bracket'``; raises with ``bracketStyle='drop'``, which computes a
        length per end.
    strokeWidth:
        Stroke width of bracket lines. Inherits ``axisWidth`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size of the p-value / corner labels. Defaults to the theme's primary
        ``fontSize`` (``6`` under the built-in defaults), matching the axis font.
    reverse:
        List of ``(group1, group2)`` tuples identifying brackets to flip —
        text moves below the bar and ticks point upward, and the bracket hangs
        below its groups rather than above them. In grouped mode (``xOffset``)
        the tuples name ``xOffset`` levels, like ``pairs``, and apply in every
        category.
    sigFigs:
        Significant figures for p-value labels (and the correlation readout). Gives
        consistent visual precision across magnitudes — e.g. ``sigFigs=2`` renders both
        ``P = 4.3×10⁻¹⁴`` and ``P = 0.68`` at two figures. Trailing zeros are stripped.
        ``None`` (default) reads the theme's ``sigFigs`` (default ``3``). Plain notation
        floors at a fixed ``P < 0.001``; ``'power'`` is unaffected (integer exponent).
        Positive subnormal p-values are supported; a computed zero is shown as a bound in every
        notation using the minimum normal positive float stored in the report record.
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
        ``test`` lists **all** pairwise post-hoc comparisons - the full table, not just the pairs
        you bracket (and even when ``pairs=None``). With supplied values, it lists only the
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

    Multiple comparisons — brackets stacked automatically::

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

    Grouped (two-factor) - compare vehicle vs LPS *within* each gene of a grouped
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

    Reference mode - compare every dose against the control, a bare mark above each
    (no bracket); overlay your points so the marks clear the data::

        CATS = ["Ctrl", "Low", "Mid", "High"]
        chart = ds.mark_strip(data, "group", "value", CATS)
        chart + ds.stats.comparisons(
            data, "group", "value",
            reference="Ctrl", categories=CATS,
            test="ttest_ind", correction="holm", labelStyle="asterisks",
        )
    """
    yCol = y
    from ._statistics import (
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
        _validate_statistical_data(data, x, yCol, x, xOffset)
    else:
        _validate_statistical_data(data, x, yCol, x)

    # Grouped mode: compare xOffset subgroups WITHIN each x-category (a two-factor design, e.g. a
    # qPCR gene x condition panel). A fully separate path so the single-factor logic below is
    # untouched; see the grouped-comparisons design point.
    if xOffset is not None:
        return _add_grouped_comparisons(
            data,
            x,
            yCol,
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
            chartWidth=chartWidth,
            report=report,
            save=saveReport,
        )

    # Dict pvalues/yPositions/yStart are the grouped (xOffset) form; single-factor takes scalars/lists.
    # Reference mode is exempt: it uses a group-keyed dict (pvalues/yPositions) or a scalar (flat row),
    # validated in the reference block below - so only guard these OUTSIDE reference mode.
    if reference is None:
        if isinstance(pvalues, dict):
            raise ValueError("a dict pvalues is for grouped mode (xOffset) or reference mode; pairwise takes a list.")
        if isinstance(yPositions, dict):
            raise ValueError(
                "a dict yPositions is for grouped mode (xOffset) or reference mode; pairwise takes a list."
            )
    if isinstance(yStart, dict) and reference is None:
        raise ValueError("a dict yStart is for grouped mode (xOffset); single-factor takes a number.")

    # Guard the categories footgun: brackets are positioned by the order/count of `categories`, so an
    # explicit list that doesn't cover the data's x-values (a typo or omission) mis-sizes the band
    # geometry and silently shifts every bracket. Raise instead (mirrors the grouped path). The
    # order-vs-chart mismatch stays undetectable without the chart (documented).
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
    # Resolved before the reference block so `reference` + pairs="all" hits its don't-also-pass raise.
    pairs = _resolve_pairs(pairs, categories, f"{x!r} categories")

    is_omnibus = test in _OMNIBUS_TESTS
    groups = [data.filter(pl.col(x) == cat)[yCol].to_numpy() for cat in categories]
    for category, group in zip(categories, groups):
        if group.size == 0:
            raise ValueError(f"grouping column {x!r} has no observations for group {category!r}.")
        _validate_observations(group.tolist(), yCol, category)

    # Remember which spacing args the caller passed: any one of them opts out of the pixel
    # placement below, since an explicit number is data units on the user's own scale.
    _y_step_arg, _y_pad_arg = yStep, yPad

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
        if yStart is not None:
            raise ValueError(
                "yStart does not apply in reference mode; each label sits above its own mark. "
                "Use yPositions for explicit label heights (a single number sets a flat row)."
            )
        if reference not in categories:
            raise ValueError(f"reference {reference!r} is not a category of {x!r}: {categories}.")
        pairs = [(reference, c) for c in categories if c != reference]
        non_ref = [c for c in categories if c != reference]
        # Explicit p-values: a dict keyed by the non-reference GROUP (the single-factor analogue of
        # grouped reference's (category, level) dict). Must cover every non-reference group exactly.
        if pvalues is not None:
            if not isinstance(pvalues, dict):
                raise ValueError("reference pvalues must be a dict keyed by group (the non-reference category).")
            missing = [g for g in non_ref if g not in pvalues]
            if missing:
                raise ValueError(f"pvalues is missing an entry for: {missing}.")
            extra = [k for k in pvalues if k not in non_ref]
            if extra:
                raise ValueError(f"pvalues has entr(y/ies) not matching any group: {sorted(extra)}.")
        # Explicit y: a single number → flat row (all labels at that y); a dict keyed by group →
        # per-label (partial, unlisted → auto). A list is the bracket form and is rejected here.
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

    # --- report comparisons ---
    # Omnibus reports ALL pairwise post-hoc comparisons (the full picture), even when
    # only a subset is bracketed or none is. Pairwise reports exactly the requested pairs.
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
        report_pvals = _bracket_pvalues(method, groups, categories, report_pairs, correction, nComparisons)
        pval_lookup = {frozenset(p): v for p, v in zip(report_pairs, report_pvals)}
        parametric = method in _PARAMETRIC_POSTHOC
        paired = method == "ttest_rel"
        for g1, g2 in report_pairs:
            en, ev = _pair_effect(groups[idx[g1]], groups[idx[g2]], parametric=parametric, paired=paired)
            comparisons.append(
                {"g1": g1, "g2": g2, "pvalue": pval_lookup[frozenset((g1, g2))], "effectName": en, "effect": ev}
            )
    elif is_reference and isinstance(pvalues, dict):
        # User p-values for reference mode: use them directly (test + correction skipped).
        pval_lookup = {frozenset((reference, g)): pvalues[g] for _, g in (pairs or [])}
        comparisons = [{"g1": reference, "g2": g, "pvalue": pvalues[g]} for _, g in (pairs or [])]

    # --- reference labels (no brackets) ---
    if is_reference and pairs:
        # A bare p-value above each non-reference mark, at that group's OWN data max (per-group,
        # so groups of different magnitude each get a label sitting just above their data).
        y_all = data[yCol].cast(pl.Float64)
        y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
        ref_pad, _, _ = _resolve_y_spacing(False, y_range, _opt("height"), yPad, None, None)
        cw = chartWidth if chartWidth is not None else _opt("width")
        fs = fontSize if fontSize is not None else _opt("fontSize")
        # yPositions: a number → flat row (every label at that y); a dict keyed by group → per-label
        # (unlisted → auto); None → each above its own mark.
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
                g_max = cast(float, data.filter(pl.col(x) == g)[yCol].cast(pl.Float64).max() or 0.0)
                # Auto: anchor at the group's own maximum and lift in pixels, so the gap is the
                # same on every chart. An explicit yPad keeps its data-unit meaning.
                label_y, ref_offset_px = (g_max, 6.0) if _y_pad_arg is None else (g_max + ref_pad, 0.0)
            label = _format_label(pval, labelStyle, effective_sigfigs, pair_notations[i])
            annotation_layers.append(
                _reference_label_layer(
                    g, label_y, label, categories=categories, chartWidth=cw, fontSize=fs, offset_px=ref_offset_px
                )
            )

    # --- brackets ---
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
            comparisons = [{"g1": g1, "g2": g2, "pvalue": p} for (g1, g2), p in zip(pairs, pvalues)]
        else:
            computed_pvalues = [pval_lookup[frozenset((g1, g2))] for g1, g2 in pairs]

        # --- y positioning ---
        annotated_groups_for_pad = list({g for pair in pairs for g in pair})
        # Base the gap on the FULL data extent, not just the compared groups: Vega fits the
        # rendered domain to every group, and the visual gap is yStep * panel height / domain.
        # Using only the annotated groups' range collapses the brackets when an un-annotated
        # group (e.g. a saturating positive control) blows up the domain; the full extent
        # tracks the domain, so the gap stays stable. (yStart still sits above the compared
        # groups - see below.)
        y_all = data[yCol].cast(pl.Float64)
        y_range = cast(float, y_all.max() or 0.0) - cast(float, y_all.min() or 0.0)
        # End legs are a PIXEL length by definition ("matching the axis ticks"), so an auto
        # tickHeight rides in y2Offset whatever the placement mode. Converting it to data units
        # assumes a linear axis - on a log axis the legs collapse to a fraction of a pixel.
        _tick_arg = tickHeight
        # Data-unit fallbacks for that opted-out path. Tick height is the fixed cap length;
        # always positive so it survives a negative yStep (reverse).
        yPad, tickHeight, yStep = _resolve_y_spacing(
            any(s in ("bracket", "drop") for s in pair_styles),
            y_range,
            _opt("height"),
            yPad,
            tickHeight,
            yStep,
        )

        # Pixel mode is the AUTO path only: anchor every bracket at the annotated groups' data
        # maximum and lift it in pixels, so the gap and the stack step are exact regardless of the
        # rendered domain. Any explicit yStart/yPositions keeps data-unit semantics (the escape
        # hatch), because those are the user's own numbers on their own scale.
        # Pixel mode is the AUTO path only. ANY explicit spacing argument opts back into
        # data-unit semantics - those are the user's own numbers on their own scale, and
        # silently ignoring one would make a documented parameter a no-op.
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
            cols = [data.filter(pl.col(x) == c)[yCol].cast(pl.Float64) for c in categories]
            hi_px = [to_px_fn(cast(float, s.max() or 0.0)) for s in cols]
            lo_px = [to_px_fn(cast(float, s.min() or 0.0)) for s in cols] if any_rev else hi_px
            centers = list(_band_geometry(len(categories), chartWidth).centers)
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
            # Assign stacking levels via greedy interval scheduling (shorter spans sit lower).
            pair_levels = _stack_levels([(categories.index(g1), categories.index(g2)) for g1, g2 in pairs])
            anchor = cast(
                float,
                data.filter(pl.col(x).is_in(annotated_groups_for_pad))[yCol].cast(pl.Float64).max() or 0.0,
            )
            if pixel_mode:
                # Each bracket anchors above ITS OWN pair's data and lifts a CONSTANT number of
                # pixels, so it stays with the groups it compares instead of riding the tallest
                # annotated group, and the gap is exact at any y domain. Only the collision test
                # between overlapping brackets needs pixel positions, and for that the rendered
                # domain is estimated - a mis-estimate moves a bump slightly, never the gaps.
                gap_px = 6.0 if any(s in ("bracket", "drop") for s in pair_styles) else 5.0
                # A bracket occupies its bar plus the label above it - `fontSize` of glyph and the
                # 4 px label dy, plus a margin. Less than this lets a label meet the bar above.
                min_step_px = float(fontSize or _opt("fontSize")) + 6.0
                # Anchor over every category the bracket SPANS, not just its two endpoints: a
                # bracket from a to c passes over b, so a taller b would sit above the bar - on a
                # bar chart the bracket would cross straight through it. (statannotations does the
                # same; ggsignif sidesteps it by anchoring everything at the global maximum.)
                # A `reverse` bracket hangs BELOW its groups, so it anchors on their MINIMUM and
                # its ladder descends. The two directions never collide with each other (opposite
                # sides of the data), so each gets its own placement pass.
                pair_anchor = [
                    cast(
                        float,
                        (
                            data.filter(pl.col(x).is_in(categories[lo : hi + 1]))[yCol].cast(pl.Float64).min()
                            if rev
                            else data.filter(pl.col(x).is_in(categories[lo : hi + 1]))[yCol].cast(pl.Float64).max()
                        )
                        or 0.0,
                    )
                    for (lo, hi), rev in zip(idx_span, rev_flags)
                ]
                _ylo, _yhi = _nice_domain(
                    min(0.0, cast(float, data[yCol].cast(pl.Float64).min() or 0.0)),
                    cast(float, data[yCol].cast(pl.Float64).max() or 0.0),
                )
                _ch = float(_opt("height"))

                # Decide the domain lift BEFORE placing the ladder. Raising the top compresses the
                # whole plot, which moves the anchors closer together - so a ladder computed against
                # the unlifted domain renders with its rungs too close (measured: 6 px where 13 was
                # asked for). The lift is bounded by every bracket colliding into one chain, which
                # needs no offsets, so there is no circularity here.
                _label_on_top = isinstance(resolved_pos, str) and resolved_pos.startswith("top")
                if _label_on_top or _opt("closed"):
                    stack_px = gap_px + len(pairs) * min_step_px
                    _lifted = _yhi + stack_px * ((_yhi - _ylo) or 1.0) / _ch
                    # Round it the way Vega will, and pin that rounded value - otherwise Vega
                    # nice-rounds past it and compresses the plot further than we allowed for.
                    _ylo, _yhi = _nice_domain(_ylo, _lifted)
                    bracket_domain_max = _yhi

                _yspan = (_yhi - _ylo) or 1.0

                def _to_px(v: float, _lo=_ylo, _sp=_yspan, _h=_ch) -> float:
                    return _h * (1.0 - (v - _lo) / _sp)

                def _un_px(px: float, _lo=_ylo, _sp=_yspan, _h=_ch) -> float:
                    return _lo + (1.0 - px / _h) * _sp

                # Each ladder returns the shared anchor its rungs hang from, so `final_y` is that
                # anchor rather than the bracket's own - the rung spacing is then pure pixels.
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
                    # Solved after the ladder, which fixes every bar. A reverse bracket's offset
                    # lifts it DOWN the screen (_pvalue_layer's _sign).
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
                # Data-unit path: the stack base is the caller's yStart, else the annotated
                # groups' maximum plus yPad (the pre-pixel-mode behaviour, unchanged).
                base = cast(float, yStart) if yStart is not None else anchor + yPad
                final_y = [base + pair_levels[i] * yStep for i in range(len(pairs))]

        if "drop" in pair_styles and drop_px is None:
            # Explicit y positions opt out of pixel placement, so the bars are plain data values
            # with no offset. The domain estimate has to include them: a caller can pin a bracket
            # far above the data, and a domain taken from the data alone would send ticks through
            # it. Reverse brackets need the low end for the same reason.
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
                    chartWidth=chartWidth,
                    strokeWidth=strokeWidth,
                    fontSize=fontSize,
                    reverse=(g1, g2) in reverse if reverse is not None else False,
                    sigFigs=effective_sigfigs,
                    notation=pair_notations[i],
                    offset_px=offsets_px[i],
                    # Solved lengths come back in COLUMN order (the span's low end first), but
                    # the legs are drawn for group1/group2 - which a pair written against the
                    # category order reverses.
                    tick_px=(_pair_order(drop_px[i], g1, i) if drop_px is not None else tick_px),
                    tick_data=(_pair_order(drop_data[i], g1, i) if drop_data is not None else None),
                    domain_max=bracket_domain_max if i == 0 else None,
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
        data_checksum=_frame_checksum(data),
    )
    marker = _emit_report(record, report, saveReport)

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
    """A fit + coefficient readout PER group of ``group_col`` (e.g. one line per cell line).

    Every fit line, CI band, and readout is coloured by ``group_col`` on the SAME colour channel the
    scatter uses, so they share one colour scale and match automatically. Colour is a lookup, not a
    position, so there's no reorder hazard like the grouped brackets - no sort param is needed. One
    record is registered per group (tagged onto that group's first layer so ``save()`` finds them
    all); the readouts stack in the ``position`` corner, each in its group's colour.
    """
    import numpy as np

    from ._statistics import _make_correlation_record, _ols_band, _run_correlation
    from .annotations import _TEXT_PRESETS
    from .utils import _frame_checksum

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
        # top anchor -> stack down; bottom -> stack up; middle -> centred on the anchor.
        anchor = 0.0 if preset["y_frac"] == 0 else (n - 1) if preset["y_frac"] == 1 else (n - 1) / 2

    # Compute and validate every group before emitting any report record. A later degenerate group
    # must not leave earlier grouped records in the global registry.
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

        # CI band (Pearson only), drawn first so it sits under the line; filled by the group colour.
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
                    **({"color": line_color} if line_color is not None else {}),
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
            readout_label = f"{g}: {label if label is not None else text}"
            y_i = base_y + (i - anchor) * line_h
            align, baseline = preset["align"], preset["baseline"]
            # A filled point swatch sized like a symbol-legend entry: config.legend.symbolSize is
            # fontSize*6 (so it scales with the font), the default circle shape, and the same
            # darkmode-aware stroke the legend uses (config.point's stroke is a fixed black).
            sym_size = fontSize * 6
            sym_r = (sym_size / math.pi) ** 0.5  # circle radius, for placement
            gap = fontSize * 0.4  # swatch -> text
            tw = len(readout_label) * fontSize * 0.6  # rough text-width estimate (for right/centre swatch x)
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
                .encode(x=alt.value(round(text_x, 2)), y=alt.value(round(y_i, 2)), text=alt.value(readout_label))
            )

        record = _make_correlation_record(result, x_col, y_col, data_checksum=_frame_checksum(gdf), group=g)
        if not g_layers:
            g_layers.append(_empty_layer())
        staged.append((g_layers, record))

    # Register only after every group has built successfully, so a grouped validation/rendering
    # failure cannot leave earlier groups in the global report queue.
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
    Annotate a scatter with a correlation coefficient (and an OLS fit line for Pearson).

    Reports the coefficient as a corner label, and — for ``method="pearson"``
    only — draws the ordinary-least-squares regression line. A structured record
    (``kind="correlation"``) is queued for the export metadata (see ``ds.save``),
    exactly like ``comparisons``.

    Combine with your scatter using ``+``:  ``chart + ds.stats.correlation(...)``.

    Parameters
    ----------
    data:
        DataFrame containing the data (polars or pandas).
    x, y:
        Column names for the two **continuous** variables.
    method:
        ``'pearson'`` (default) — linear correlation ``r`` + ``r²`` + slope/intercept,
        with an OLS line. ``'spearman'`` — rank correlation ``ρ``. ``'kendall'`` —
        rank correlation ``τ``. The rank methods report the coefficient only (no ``r²``,
        no line — a straight line isn't their model). Matches pandas' ``DataFrame.corr``.
    groupBy:
        **Grouped mode.** A column to split the scatter into series (e.g. ``"cell_line"``).
        When set, a fit + coefficient is computed **per group**, each fit line / CI band /
        readout coloured by ``groupBy`` on the *same* colour channel your scatter uses -
        so colour by the same field (``color=alt.Color("cell_line:N")``) and they match
        (colour is a lookup, so no sort param is needed, unlike ``comparisons``).
        Readouts stack in the ``position`` corner, each a colour swatch (matching the series)
        plus the coefficient in neutral ink; one record is registered per group. Note: with
        ``ci=True``, give your scatter an explicit
        y-axis title (``alt.Y("val:Q", title="…")``) - otherwise Vega merges the band's
        internal upper-bound field into the axis title (a Vega title-merge quirk that also
         affects the single-series ``ci`` path).
         A custom ``label`` is prefixed with each group's label.
    line:
        Draw the OLS fit line. Default ``True``. Only applies to ``method="pearson"``
        (a no-op for the rank methods). Set ``False`` to suppress it and, e.g., compose
        your own line from the returned/recorded slope and intercept.
    position:
        Corner preset (a ``text`` position, e.g. ``'topLeft'``) for the readout.
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
        Pixel nudges for the readout, forwarded to ``text``.
    fontSize:
        Font size of the readout. Defaults to the theme's primary ``fontSize``
        (``6`` under the built-in defaults), matching the axis font.
    sigFigs, notation:
        Significant figures / number format for the readout (coefficient, r², p-value,
        and fit equation), as in ``comparisons``. ``sigFigs=None`` reads the theme.
    color, strokeWidth, strokeDash, opacity:
        Curated style overrides for the fit line (same four knobs as ``rule``). Each
        defaults to ``None`` → the line inherits the theme's ``mark_line`` config; set one
        to override just that property.
    lineStyle:
        A dict of raw ``mark_line`` properties merged in last, so any Vega-Lite line
        property is reachable (e.g. ``{"interpolate": "monotone", "strokeCap": "round"}``).
        Keys here **override** the curated ``color``/``strokeWidth``/etc. above in both single
        and grouped modes.
    ci:
        Draw a shaded interval band around the OLS fit (Pearson only). ``False``
        (default) → no band. ``True`` → a 95% band. A float in ``(0, 1)`` → that
        confidence level (e.g. ``0.99``). The band is hyperbolic - narrowest at the
        mean of ``x``, widening toward the extremes. Its syntax is validated even for rank
        methods, where the band is inactive.
    interval:
        Which band ``ci`` draws: ``'confidence'`` (default, the interval for the mean
        response - how well the *line* is pinned down) or ``'prediction'`` (the wider
        interval for a single new observation).
    ciColor:
        Fill colour of the band. ``None`` (default) inherits the effective fit-line color,
        including a ``lineStyle`` color,
        falling back to the theme's mark colour (black / white, darkmode-aware). Because
        the default resolves darkmode at build time, wrap chart construction in a callable
        passed to ``ds.save()`` for correct light/dark exports (as with ``shade``).
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
    xCol, yCol = x, y
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
        _validate_statistical_data(data, xCol, yCol, groupBy, numeric_x=True)
    else:
        _validate_statistical_data(data, xCol, yCol, numeric_x=True)

    # Grouped mode: a fit + coefficient PER group of `groupBy` (e.g. one line per cell line), each
    # coloured to match the scatter's colour scale. A separate path so the single-series body below
    # is untouched; see the grouped-correlation design point.
    if groupBy is not None:
        return _add_grouped_correlation(
            data,
            xCol,
            yCol,
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

    x_values = data[xCol].cast(pl.Float64).to_numpy()
    y_values = data[yCol].cast(pl.Float64).to_numpy()
    try:
        result = _run_correlation(method, x_values, y_values)
    except ValueError as exc:
        raise ValueError(f"correlation {xCol!r} vs {yCol!r}: {exc}") from exc

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
        xs = np.linspace(float(x_values.min()), float(x_values.max()), 64)
        try:
            lo, hi = _ols_band(x_values, y_values, xs, level=level, kind=interval)
        except ValueError as exc:
            raise ValueError(f"correlation {xCol!r} vs {yCol!r}: {exc}") from exc
        # Lower bound rides on the yCol-named field so its derived axis title dedupes with the
        # base chart (same trick as the fit line); the upper bound goes in y2 (carries no title).
        band_df = pl.DataFrame({xCol: xs, yCol: lo, "__ci_hi": hi})
        # Match the fit line's colour (black/white, darkmode-aware at build → callable needed
        # for save() across backgrounds, like shade); pin the stroke off so config.area's
        # grey fill / stroke can't leak through.
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
                x=alt.X(field=xCol, type="quantitative"),
                y=alt.Y(field=yCol, type="quantitative"),
                y2=alt.Y2(field="__ci_hi"),
            )
        )

    # OLS fit line — Pearson only (result["slope"] is None for rank kinds).
    if line and result["slope"] is not None:
        x0, x1 = float(x_values.min()), float(x_values.max())
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
            _text(
                text,
                position=position,
                offsetX=offsetX,
                offsetY=offsetY,
                fontSize=fontSize if fontSize is not None else _opt("fontSize"),
            )
        )

    # Structured record → export metadata; printed/written on request.
    record = _make_correlation_record(result, xCol, yCol, data_checksum=_frame_checksum(data))
    marker = _emit_report(record, report, saveReport)

    if not layers:
        layers.append(_empty_layer())
    # Tag with the marker name so save() matches this record to its chart (stripped on write).
    return cast(alt.LayerChart, alt.layer(*layers).properties(name=marker))

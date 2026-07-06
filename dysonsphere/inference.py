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
    categories: list | None = None,
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
    groups: list,
    categories: list,
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
        if correction in ("bonferroni", "holm"):
            m = nComparisons if nComparisons is not None else len(pairs)
            raw = _adjust(raw, correction, m)
        return raw
    raise ValueError(f"Unknown test/postHoc {method!r}. Choose from: {sorted(_MATRIX_POSTHOCS | _PAIRWISE_TESTS)}")


def add_comparisons(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    pairs: list[tuple[str, str]] | None = None,
    *,
    test: str = "mannwhitneyu",
    postHoc: str | None = None,
    pvalues: list[float] | None = None,
    correction: str | None = None,
    nComparisons: int | None = None,
    yPositions: list[float] | None = None,
    yStart: float | None = None,
    yStep: float | None = None,
    yPad: float | None = None,
    categories: list | None = None,
    chartWidth: int | None = None,
    bracketStyle: str | dict = "bracket",
    labelStyle: str = "p",
    tickHeight: float | None = None,
    strokeWidth: float | None = None,
    fontSize: int | None = None,
    reverse: list[tuple[str, str]] | None = None,
    sigFigs: int | None = None,
    notation: str | dict | None = None,
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
        Pre-computed p-values, one per pair in the same order. Skips all
        statistical tests for the brackets when provided.
    correction:
        Multiple comparison correction: ``'bonferroni'``, ``'holm'``, or
        ``None``. For pairwise/post-hoc bracket p-values; ignored for
        ``tukey_hsd`` (correction is built in) and when ``pvalues`` is provided.
    nComparisons:
        Total number of comparisons for Bonferroni correction. Defaults to
        ``len(pairs)`` when ``correction='bonferroni'`` and not set explicitly.
    yPositions:
        Explicit y positions (data units) for each bracket, one per pair in
        the same order. When provided, overrides all auto-stacking logic
        (``yStart``, ``yStep``, ``yPad`` are ignored).
    yStart:
        Y position (data units) of the lowest bracket. Defaults to
        ``max(y values for all annotated groups) + yPad``.
    yStep:
        Vertical distance (data units) between stacking levels. Defaults to
        ``yPad * 1.5``.
    yPad:
        Padding above the data maximum when ``yStart`` is auto-placed. Defaults
        to a fixed visual gap of ~8 px (``bracketStyle='line'``) or ~10 px
        (``bracketStyle='bracket'``), expressed in data units via ``chartHeight``
        so the gap stays visually consistent regardless of chart height.
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
    """
    from datetime import datetime
    from pathlib import Path

    from .statistics import (
        _OMNIBUS_TESTS,
        _PARAMETRIC_POSTHOC,
        _POSTHOC_DEFAULTS,
        _TEST_DISPLAY,
        _describe_all,
        _make_record,
        _pair_effect,
        _register_report,
        _render_report,
        _run_omnibus,
    )
    from .utils import ensure_polars, frame_checksum

    df = ensure_polars(df)

    if categories is None:
        categories = sorted(df[xCol].unique().to_list())

    is_omnibus = test in _OMNIBUS_TESTS
    groups = [df.filter(pl.col(xCol) == cat)[yCol].to_numpy() for cat in categories]

    if pairs is not None and len(pairs) == 0:
        raise ValueError("pairs must not be empty when provided (pass pairs=None for an omnibus-only annotation).")
    if not is_omnibus and not pairs:
        raise ValueError("pairs is required for pairwise tests.")
    if yPositions is not None and pairs is not None and len(yPositions) != len(pairs):
        raise ValueError(f"yPositions length ({len(yPositions)}) does not match pairs length ({len(pairs)})")

    annotation_layers: list = []
    omnibus_result = None
    comparisons: list[dict] = []
    comparison_name: str | None = None

    if is_omnibus:
        omnibus_result = _run_omnibus(test, groups, categories)

    # --- resolve comparison method (a post-hoc for omnibus, the test itself for pairwise) ---
    idx = {c: i for i, c in enumerate(categories)}
    method: str | None
    if pvalues is not None:
        method = None
    elif is_omnibus:
        method = postHoc if postHoc is not None else _POSTHOC_DEFAULTS[test]
    else:
        method = test
    comparison_name = method
    # tukey_hsd carries its own correction; explicit p-values aren't corrected by us.
    effective_correction = None if (method is None or method == "tukey_hsd") else correction
    # sigFigs: per-call overrides the theme default (3); governs on-plot label precision.
    effective_sigfigs = sigFigs if sigFigs is not None else _opt("sigFigs")

    # Resolve notation: a scalar applies everywhere; a dict is per-pair for the brackets
    # (order-insensitive keys, unlisted → plain) plus an optional "test" string key for the
    # test/omnibus label. Pair notations are read below in the bracket loop.
    if isinstance(notation, dict):
        _valid_notations = {None, "scientific", "e", "power"}
        bad_vals = [v for v in notation.values() if v not in _valid_notations]
        if bad_vals:
            raise ValueError(f"notation dict values must be None/'scientific'/'e'/'power', got {bad_vals}")
        bad_keys = [k for k in notation if isinstance(k, str) and k != "test"]
        if bad_keys:
            raise ValueError(f"notation dict string keys must be 'test', got {sorted(bad_keys)}")
        _notation_map = {frozenset(k): v for k, v in notation.items() if not isinstance(k, str)}
        test_notation = notation.get("test")
        pair_notations = [_notation_map.get(frozenset(p)) for p in (pairs or [])]
    else:
        test_notation = notation
        pair_notations = [notation] * len(pairs or [])

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

    pval_lookup: dict = {}
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

    # --- brackets ---
    if pairs:
        # Per-pair bracket style: a string applies to all; a dict maps a pair (order-
        # insensitive, matched by frozenset) to its style, with "bracket" as the fallback.
        _valid_styles = {"line", "bracket"}
        if isinstance(bracketStyle, dict):
            bad = set(bracketStyle.values()) - _valid_styles
            if bad:
                raise ValueError(f"bracketStyle dict values must be 'line' or 'bracket', got {sorted(bad)}")
            _style_map = {frozenset(k): v for k, v in bracketStyle.items()}
            pair_styles = [_style_map.get(frozenset(p), "bracket") for p in pairs]
        else:
            if bracketStyle not in _valid_styles:
                raise ValueError(f"bracketStyle must be 'line', 'bracket', or a dict, got {bracketStyle!r}")
            pair_styles = [bracketStyle] * len(pairs)

        if pvalues is not None:
            if len(pvalues) != len(pairs):
                raise ValueError(f"pvalues length ({len(pvalues)}) does not match pairs length ({len(pairs)})")
            computed_pvalues = list(pvalues)
            comparisons = [{"g1": g1, "g2": g2, "pvalue": p} for (g1, g2), p in zip(pairs, pvalues)]
        else:
            computed_pvalues = [pval_lookup[frozenset((g1, g2))] for g1, g2 in pairs]

        # --- y positioning ---
        annotated_groups_for_pad = list({g for pair in pairs for g in pair})
        y_vals = df.filter(pl.col(xCol).is_in(annotated_groups_for_pad))[yCol]
        y_range = cast(float, y_vals.cast(pl.Float64).max() or 0.0) - cast(float, y_vals.cast(pl.Float64).min() or 0.0)
        chart_height = _opt("chartHeight")
        if yPad is None:
            # Use the larger (bracket) gap if any pair is a bracket, so ticks clear the data.
            yPad = (10.0 if "bracket" in pair_styles else 8.0) * y_range / chart_height
        # Bracket end-tick height matches the theme's tickSize (px → data units). Always
        # positive, so it no longer flips sign with a negative yStep (reverse brackets).
        if tickHeight is None:
            tickHeight = _opt("tickSize") * y_range / chart_height if chart_height else 0.0

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

            if yStep is None:
                yStep = yPad * 1.5

            # Assign stacking levels via greedy interval scheduling.
            # Shorter spans go to lower levels so narrow brackets sit closer to the data.
            pair_indices = [(categories.index(g1), categories.index(g2)) for g1, g2 in pairs]
            sort_order = sorted(
                range(len(pairs)),
                key=lambda i: abs(pair_indices[i][1] - pair_indices[i][0]),
            )

            levels: list[list[tuple[int, int]]] = []
            pair_levels = [0] * len(pairs)

            for i in sort_order:
                lo, hi = min(pair_indices[i]), max(pair_indices[i])
                placed = False
                for level_idx, occupied in enumerate(levels):
                    overlaps = any(not (hi < occ_lo or lo > occ_hi) for occ_lo, occ_hi in occupied)
                    if not overlaps:
                        occupied.append((lo, hi))
                        pair_levels[i] = level_idx
                        placed = True
                        break
                if not placed:
                    levels.append([(lo, hi)])
                    pair_levels[i] = len(levels) - 1

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
        comparison_test=comparison_name,
        correction=effective_correction,
        pvalues_provided=pvalues is not None,
        data_checksum=frame_checksum(df),
    )
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

    if not annotation_layers:
        # no label and no brackets → report-only; return an invisible layer.
        annotation_layers.append(_empty_layer())
    # Tag the layer with the record's marker name so save() can match this record back to
    # the chart it annotates (the name survives ``+``; it's stripped from the written JSON).
    return cast(alt.LayerChart, alt.layer(*annotation_layers).properties(name=marker))


# Correlation


def _correlation_label(
    result: dict, *, coefficient: str, includePvalue: bool, includeEquation: bool, sigFigs: int, notation: str | None
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


def add_correlation(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    *,
    method: str = "pearson",
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
    lineStyle: dict | None = None,
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
    from datetime import datetime
    from pathlib import Path

    from .statistics import _make_correlation_record, _register_report, _render_report, _run_correlation
    from .utils import ensure_polars, frame_checksum

    if verbose:  # shortcut for the fullest readout; overrides the individual toggles
        coefficient, includePvalue, includeEquation = "both", True, True
    if coefficient not in ("r", "r2", "both"):
        raise ValueError(f"coefficient must be 'r', 'r2', or 'both', got {coefficient!r}")

    df = ensure_polars(df)
    x = df[xCol].cast(pl.Float64).to_numpy()
    y = df[yCol].cast(pl.Float64).to_numpy()
    result = _run_correlation(method, x, y)

    layers: list = []

    # OLS fit line — Pearson only (result["slope"] is None for rank kinds).
    if line and result["slope"] is not None:
        x0, x1 = float(x.min()), float(x.max())
        slope, intercept = result["slope"], result["intercept"]
        fit_df = pl.DataFrame({"_x": [x0, x1], "_y": [slope * x0 + intercept, slope * x1 + intercept]})
        # By default the line inherits the theme's mark_line config (no overrides).
        # Curated params override only what's passed; lineStyle overrides everything.
        mark_kwargs: dict = {}
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
        # Plain x:Q/y:Q with no title/axis override: the fit line shares the main chart's
        # scale, and because the base chart is the first layer, its axis (titles, ticks)
        # wins the shared-axis resolution.  (Setting title=None nulls the base title;
        # axis=None suppresses the axis entirely — both wrong here.)
        layers.append(
            alt.Chart(_internal_data(fit_df)).mark_line(**mark_kwargs).encode(x=alt.X("_x:Q"), y=alt.Y("_y:Q"))
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

    if not layers:
        layers.append(_empty_layer())
    # Tag with the marker name so save() matches this record to its chart (stripped on write).
    return cast(alt.LayerChart, alt.layer(*layers).properties(name=marker))

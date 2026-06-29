from typing import Any, cast

import altair as alt
import polars as pl

from .utils import ensure_polars


def _format_pvalue(p: float, decimals: int = 3) -> str:
    if p < 0.001:
        return "P < 0.001"
    return f"P = {p:.{decimals}f}"


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
    bracket_style: str = "line",
    label_style: str = "p",
    categories: list | None = None,
    chartWidth: int | None = None,
    strokeWidth: float | None = None,
    fontSize: int | None = None,
    reverse: bool = False,
    decimals: int = 3,
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
                raise ValueError(
                    f"Unknown test {test!r}. Choose from: {['tukey_hsd'] + list(_tests)}"
                )
            pvalue = _tests[test]()

    # bonferroni correction (skip for tukey_hsd — correction is built in)
    if correction == "bonferroni" and test != "tukey_hsd":
        pvalue = min(pvalue * n_comparisons, 1.0)

    label = (
        _format_asterisks(pvalue)
        if label_style == "asterisks"
        else _format_pvalue(pvalue, decimals=decimals)
    )

    # --- y position ---
    if y is None:
        if df is None or x_col is None or y_col is None:
            raise ValueError("y is required when df, x_col, and y_col are not provided.")
        y = cast(float, df.filter(pl.col(x_col).is_in([group1, group2]))[y_col].cast(pl.Float64).max() or 0.0) + y_pad

    # --- resolve theme-linked defaults ---
    if chartWidth is None:
        chartWidth = alt.theme.options.get("chartWidth", 100)
    if strokeWidth is None:
        strokeWidth = alt.theme.options.get("axisWidth", 0.5)
    if fontSize is None:
        fontSize = 6

    # --- categories and text x position ---
    if categories is None:
        if df is None or x_col is None:
            raise ValueError("categories is required when df and x_col are not provided.")
        categories = sorted(df[x_col].unique().to_list())

    g1_idx = categories.index(group1)
    g2_idx = categories.index(group2)

    stroke_cap = alt.theme.options.get("strokeCap", "round")
    _rule_kwargs = {"strokeWidth": strokeWidth, "strokeDash": [0, 0], "strokeCap": stroke_cap}

    # dy offsets in SVG pixels. Asterisk glyphs sit close to the baseline so a small
    # offset seats them flush; alphanumeric labels (including "ns") need more clearance.
    _dy_mag = 2 if label_style == "asterisks" and label != "ns" else 4
    text_dy = _dy_mag if reverse else -_dy_mag
    tick_y2 = y + tick_height if reverse else y - tick_height

    bar = (
        alt.Chart(alt.Data(values=[{"x": group1, "x2": group2, "y": y}]))
        .mark_rule(**_rule_kwargs)
        .encode(
            x=alt.X("x:N"),
            x2="x2:N",
            y=alt.Y("y:Q"),
        )
    )

    # Band center formula for xOffset charts (paddingInner=0 forced by xOffset,
    # paddingOuter = bandPadding from theme):
    #   step = chartWidth / (n + 2*bandPadding)
    #   center_i = step * (bandPadding + i + 0.5)
    # Verified against SVG tick positions.
    band_padding = alt.theme.options.get("bandPadding", 0.1)
    n = len(categories)
    step = chartWidth / (n + 2 * band_padding)
    x_mid_px = step * (2 * band_padding + g1_idx + g2_idx + 1) / 2
    text = (
        alt.Chart(alt.Data(values=[{"y": y, "label": label}]))
        .mark_text(align="center", fontSize=fontSize, dy=text_dy)
        .encode(
            x=alt.value(x_mid_px),
            y=alt.Y("y:Q"),
            text="label:N",
        )
    )

    if bracket_style == "bracket":
        left_tick = (
            alt.Chart(alt.Data(values=[{"x": group1, "y": y, "y2": tick_y2}]))
            .mark_rule(**_rule_kwargs)
            .encode(
                x=alt.X("x:N"),
                y=alt.Y("y:Q"),
                y2="y2:Q",
            )
        )
        right_tick = (
            alt.Chart(alt.Data(values=[{"x": group2, "y": y, "y2": tick_y2}]))
            .mark_rule(**_rule_kwargs)
            .encode(
                x=alt.X("x:N"),
                y=alt.Y("y:Q"),
                y2="y2:Q",
            )
        )
        return cast(alt.LayerChart, alt.layer(bar, left_tick, right_tick, text))

    return cast(alt.LayerChart, alt.layer(bar, text))


def add_pvalue(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    pairs: list[tuple[str, str]],
    *,
    test: str = "mannwhitneyu",
    pvalues: list[float] | None = None,
    correction: str | None = None,
    nComparisons: int | None = None,
    yPositions: list[float] | None = None,
    yStart: float | None = None,
    yStep: float | None = None,
    yPad: float | None = None,
    categories: list | None = None,
    chartWidth: int | None = None,
    bracketStyle: str = "line",
    labelStyle: str = "p",
    tickHeight: float | None = None,
    strokeWidth: float | None = None,
    fontSize: int | None = None,
    reverse: list[tuple[str, str]] | None = None,
    decimals: int = 3,
) -> alt.LayerChart:
    """
    Build p-value annotation layers for one or more group comparisons.

    Brackets are stacked automatically so they don't overlap. Shorter-span
    pairs are placed lower; pairs whose x-ranges overlap are bumped to the
    next level.

    Combine with your chart using ``+``:  ``chart + add_pvalue(...)``.

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
        annotate. Pass a single-element list for one comparison.
    test:
        Scipy test to run for each pair: ``'mannwhitneyu'``, ``'ttest_ind'``,
        ``'ttest_rel'``, ``'wilcoxon'``, or ``'tukey_hsd'``. Ignored when
        ``pvalues`` is provided. For ``tukey_hsd``, one omnibus test is run and
        p-values for each pair are extracted from the result matrix.
    pvalues:
        Pre-computed p-values, one per pair in the same order. Skips all
        statistical tests when provided.
    correction:
        Multiple comparison correction applied after testing: ``'bonferroni'``
        or ``None``. Ignored for ``tukey_hsd`` (correction is built in).
        Also ignored when ``pvalues`` is provided.
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
        ``yPad * 2``.
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
        ``'line'`` (horizontal bar only) or ``'bracket'`` (bar + end ticks).
    labelStyle:
        ``'p'`` (default) renders ``P = 0.012`` / ``P < 0.001``. ``'asterisks'``
        renders ``*`` / ``**`` / ``***`` / ``ns``.
    tickHeight:
        Height of bracket end ticks in data units. Defaults to
        ``yStep * 0.25`` so ticks scale naturally with bracket spacing.
        Only used when ``bracketStyle='bracket'``.
    strokeWidth:
        Stroke width of bracket lines. Inherits ``axisWidth`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size of p-value labels. Defaults to ``6``.
    reverse:
        List of ``(group1, group2)`` tuples identifying brackets to flip —
        text moves below the bar and ticks point upward.
    decimals:
        Decimal places for p-value labels when ``labelStyle='p'`` and
        ``p >= 0.001``.

    Examples
    --------
    Single comparison::

        CATEGORIES = ["A", "B", "C"]
        chart = ds.mark_strip(df, "group", "value", CATEGORIES)
        chart + ds.add_pvalue(
            df, "group", "value",
            pairs=[("A", "B")],
            categories=CATEGORIES,
        )

    Multiple comparisons — brackets stacked automatically::

        chart + ds.add_pvalue(
            df, "group", "value",
            pairs=[("A", "B"), ("A", "C"), ("B", "C")],
            test="mannwhitneyu",
            categories=CATEGORIES,
        )

    From pre-computed p-values::

        chart + ds.add_pvalue(
            df, "group", "value",
            pairs=[("A", "B"), ("A", "C")],
            pvalues=[0.012, 0.341],
            categories=CATEGORIES,
        )
    """
    from scipy import stats as _stats

    df = ensure_polars(df)
    if not pairs:
        raise ValueError("pairs must not be empty")

    if yPositions is not None and len(yPositions) != len(pairs):
        raise ValueError(
            f"yPositions length ({len(yPositions)}) does not match pairs length ({len(pairs)})"
        )

    if categories is None:
        categories = sorted(df[xCol].unique().to_list())

    # --- compute p-values ---
    if pvalues is not None:
        if len(pvalues) != len(pairs):
            raise ValueError(
                f"pvalues length ({len(pvalues)}) does not match pairs length ({len(pairs)})"
            )
        computed_pvalues = list(pvalues)
    elif test == "tukey_hsd":
        all_groups = [df.filter(pl.col(xCol) == cat)[yCol].to_numpy() for cat in categories]
        result = _stats.tukey_hsd(*all_groups)
        computed_pvalues = [
            float(result.pvalue[categories.index(g1)][categories.index(g2)]) for g1, g2 in pairs
        ]
    else:
        _tests = {
            "mannwhitneyu": lambda a, b: _stats.mannwhitneyu(a, b, alternative="two-sided").pvalue,
            "ttest_ind": lambda a, b: _stats.ttest_ind(a, b).pvalue,
            "ttest_rel": lambda a, b: _stats.ttest_rel(a, b).pvalue,
            "wilcoxon": lambda a, b: _stats.wilcoxon(a, b).pvalue,
        }
        if test not in _tests:
            raise ValueError(f"Unknown test {test!r}. Choose from: {['tukey_hsd'] + list(_tests)}")
        computed_pvalues = []
        for g1, g2 in pairs:
            a = df.filter(pl.col(xCol) == g1)[yCol].to_numpy()
            b = df.filter(pl.col(xCol) == g2)[yCol].to_numpy()
            computed_pvalues.append(float(_tests[test](a, b)))

    # bonferroni correction (skip for tukey_hsd — built in; skip when pvalues provided)
    if correction == "bonferroni" and test != "tukey_hsd" and pvalues is None:
        n = nComparisons if nComparisons is not None else len(pairs)
        computed_pvalues = [min(p * n, 1.0) for p in computed_pvalues]

    # --- y positioning ---
    if yPad is None:
        annotated_groups_for_pad = list({g for pair in pairs for g in pair})
        y_vals = df.filter(pl.col(xCol).is_in(annotated_groups_for_pad))[yCol]
        y_range = cast(float, y_vals.cast(pl.Float64).max() or 0.0) - cast(float, y_vals.cast(pl.Float64).min() or 0.0)
        chart_height = alt.theme.options.get("chartHeight", 100)
        yPad = (10.0 if bracketStyle == "bracket" else 8.0) * y_range / chart_height

    if yPositions is not None:
        final_y = list(yPositions)
        if tickHeight is None:
            tickHeight = (yPad * 2) * 0.25
    else:
        if yStart is None:
            annotated_groups = list({g for pair in pairs for g in pair})
            yStart = cast(float, df.filter(pl.col(xCol).is_in(annotated_groups))[yCol].cast(pl.Float64).max() or 0.0) + yPad

        if yStep is None:
            yStep = yPad * 2

        if tickHeight is None:
            tickHeight = yStep * 0.25

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

    # --- build one layer per pair ---
    layer_charts = []
    for i, ((g1, g2), pval) in enumerate(zip(pairs, computed_pvalues)):
        layer_charts.append(
            _pvalue_layer(
                group1=g1,
                group2=g2,
                pvalue=pval,
                y=final_y[i],
                tick_height=tickHeight,
                bracket_style=bracketStyle,
                label_style=labelStyle,
                categories=categories,
                chartWidth=chartWidth,
                strokeWidth=strokeWidth,
                fontSize=fontSize,
                reverse=(g1, g2) in reverse if reverse is not None else False,
                decimals=decimals,
            )
        )

    return cast(alt.LayerChart, alt.layer(*layer_charts))

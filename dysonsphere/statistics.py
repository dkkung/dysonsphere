from typing import Any

import altair as alt
import polars as pl

from .utils import ensure_polars


def _format_pvalue(p: float, decimals: int = 3) -> str:
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.{decimals}f}"


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
        y = float(df.filter(pl.col(x_col).is_in([group1, group2]))[y_col].max()) + y_pad

    # --- resolve theme-linked defaults ---
    if chartWidth is None:
        chartWidth = alt.theme.options.get("chartWidth", 100)
    if strokeWidth is None:
        strokeWidth = alt.theme.options.get("axisWidth", 0.5)
    if fontSize is None:
        fontSize = alt.theme.options.get("fontSize", 7)

    # --- categories and text x position ---
    if categories is None:
        if df is None or x_col is None:
            raise ValueError("categories is required when df and x_col are not provided.")
        categories = sorted(df[x_col].unique().to_list())

    g1_idx = categories.index(group1)
    g2_idx = categories.index(group2)

    _rule_kwargs = {"strokeWidth": strokeWidth, "strokeDash": [0, 0]}

    # Asterisk glyphs sit above the baseline with no descenders; p-value text
    # has a 'p' descender that visually closes the gap. Reduce dy for asterisks
    # so the whitespace above the bracket matches the p-value label appearance.
    _dy_mag = 2 if label_style == "asterisks" else 6
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
        return alt.layer(bar, left_tick, right_tick, text)

    return alt.layer(bar, text)


def add_pvalue(
    df: pl.DataFrame | Any,
    x_col: str,
    y_col: str,
    pairs: list[tuple[str, str]],
    *,
    test: str = "mannwhitneyu",
    pvalues: list[float] | None = None,
    correction: str | None = None,
    n_comparisons: int | None = None,
    y_positions: list[float] | None = None,
    y_start: float | None = None,
    y_step: float | None = None,
    y_pad: float = 5,
    categories: list | None = None,
    chartWidth: int | None = None,
    bracket_style: str = "line",
    label_style: str = "p",
    tick_height: float = 0.5,
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
    x_col:
        Column name for the grouping variable (x-axis).
    y_col:
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
    n_comparisons:
        Total number of comparisons for Bonferroni correction. Defaults to
        ``len(pairs)`` when ``correction='bonferroni'`` and not set explicitly.
    y_positions:
        Explicit y positions (data units) for each bracket, one per pair in
        the same order. When provided, overrides all auto-stacking logic
        (``y_start``, ``y_step``, ``y_pad`` are ignored).
    y_start:
        Y position (data units) of the lowest bracket. Defaults to
        ``max(y values for all annotated groups) + y_pad``.
    y_step:
        Vertical distance (data units) between stacking levels. Defaults to
        ``y_pad * 2``.
    y_pad:
        Padding above the data maximum when ``y_start`` is auto-placed.
    categories:
        Ordered list of all x-axis categories. Inferred from ``df`` (sorted
        alphabetically) when not provided.
    chartWidth:
        Width of the chart in pixels, used to compute text x positions.
    bracket_style:
        ``'line'`` (horizontal bar only) or ``'bracket'`` (bar + end ticks).
    label_style:
        ``'p'`` (default) renders ``p = 0.012`` / ``p < 0.001``. ``'asterisks'``
        renders ``*`` / ``**`` / ``***`` / ``ns``.
    tick_height:
        Height of bracket end ticks in data units. Only used when
        ``bracket_style='bracket'``.
    strokeWidth:
        Stroke width of bracket lines. Inherits ``axisWidth`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size of p-value labels. Inherits ``fontSize`` from
        ``ds.theme()`` when not set.
    reverse:
        List of ``(group1, group2)`` tuples identifying brackets to flip —
        text moves below the bar and ticks point upward.
    decimals:
        Decimal places for p-value labels when ``label_style='p'`` and
        ``p >= 0.001``.

    Examples
    --------
    Single comparison::

        CATEGORIES = ["Control", "Drug A", "Drug B"]
        chart = ds.mark_strip(df, "group", "value", CATEGORIES)
        chart + ds.add_pvalue(
            df, "group", "value",
            pairs=[("Control", "Drug A")],
            categories=CATEGORIES,
        )

    Multiple comparisons — brackets stacked automatically::

        chart + ds.add_pvalue(
            df, "group", "value",
            pairs=[("Control", "Drug A"), ("Control", "Drug B"), ("Drug A", "Drug B")],
            test="mannwhitneyu",
            categories=CATEGORIES,
        )

    From pre-computed p-values::

        chart + ds.add_pvalue(
            df, "group", "value",
            pairs=[("Control", "Drug A"), ("Control", "Drug B")],
            pvalues=[0.012, 0.341],
            categories=CATEGORIES,
        )
    """
    from scipy import stats as _stats

    df = ensure_polars(df)
    if not pairs:
        raise ValueError("pairs must not be empty")

    if y_positions is not None and len(y_positions) != len(pairs):
        raise ValueError(
            f"y_positions length ({len(y_positions)}) does not match pairs length ({len(pairs)})"
        )

    if categories is None:
        categories = sorted(df[x_col].unique().to_list())

    # --- compute p-values ---
    if pvalues is not None:
        if len(pvalues) != len(pairs):
            raise ValueError(
                f"pvalues length ({len(pvalues)}) does not match pairs length ({len(pairs)})"
            )
        computed_pvalues = list(pvalues)
    elif test == "tukey_hsd":
        all_groups = [df.filter(pl.col(x_col) == cat)[y_col].to_numpy() for cat in categories]
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
            a = df.filter(pl.col(x_col) == g1)[y_col].to_numpy()
            b = df.filter(pl.col(x_col) == g2)[y_col].to_numpy()
            computed_pvalues.append(float(_tests[test](a, b)))

    # bonferroni correction (skip for tukey_hsd — built in; skip when pvalues provided)
    if correction == "bonferroni" and test != "tukey_hsd" and pvalues is None:
        n = n_comparisons if n_comparisons is not None else len(pairs)
        computed_pvalues = [min(p * n, 1.0) for p in computed_pvalues]

    # --- y positioning ---
    if y_positions is not None:
        final_y = list(y_positions)
    else:
        if y_start is None:
            annotated_groups = list({g for pair in pairs for g in pair})
            y_start = float(df.filter(pl.col(x_col).is_in(annotated_groups))[y_col].max()) + y_pad

        if y_step is None:
            y_step = y_pad * 2

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

        final_y = [y_start + pair_levels[i] * y_step for i in range(len(pairs))]

    # --- build one layer per pair ---
    layer_charts = []
    for i, ((g1, g2), pval) in enumerate(zip(pairs, computed_pvalues)):
        layer_charts.append(
            _pvalue_layer(
                group1=g1,
                group2=g2,
                pvalue=pval,
                y=final_y[i],
                tick_height=tick_height,
                bracket_style=bracket_style,
                label_style=label_style,
                categories=categories,
                chartWidth=chartWidth,
                strokeWidth=strokeWidth,
                fontSize=fontSize,
                reverse=(g1, g2) in reverse if reverse is not None else False,
                decimals=decimals,
            )
        )

    return alt.layer(*layer_charts)

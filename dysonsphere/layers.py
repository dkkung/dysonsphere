import altair as alt
import numpy as np
import polars as pl

from .transforms import add_beeswarm, add_jitter

_UNSET = object()


def mark_violin(
    df: pl.DataFrame,
    x_col: str,
    y_col: str,
    categories: list[str],
    *,
    boxplot_size: int | None = None,  # defaults to theme markSize * 0.8
    boxplot_color: str = "black",
    palette: str | list[str] | None = None,
    fillOpacity: float | None = None,
    stroke: str | None = None,
    strokeWidth: float | None = None,
    legend: bool = False,
    angledX: bool | None = None,
    steps: int = 200,
    y_title: str | None = _UNSET,
) -> alt.LayerChart:
    """
    Build an Altair layer combining a violin plot behind a boxplot.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``theme.add_pvalue``).

    Parameters
    ----------
    df:
        Polars DataFrame containing the data.
    x_col:
        Column name for the grouping variable (x-axis).
    y_col:
        Column name for the value variable (y-axis).
    categories:
        Ordered list of all x-axis categories, used for positioning and
        axis labels.
    boxplot_size:
        Width of the boxplot box in pixels.
    boxplot_color:
        Fill color of the boxplot.
    palette:
        Fill color of all violins. When ``None``, each group inherits its
        color from the theme's active category palette.
    fillOpacity:
        Fill opacity of the violin. Inherits ``markFillOpacity`` from theme
        when ``None``.
    stroke:
        Outline color of the violin. Defaults to ``None`` (no outline).
    strokeWidth:
        Width of the violin outline. Inherits ``markStrokeWidth`` from theme
        when ``None``.
    steps:
        Number of y grid points used for KDE estimation (per group).

    Examples
    --------
    ::

        theme.options(chartWidth=250)
        chart = theme.mark_violin(df, "group", "value", CATEGORIES)
        theme.save(chart, "violin")

        # with optional outline and custom colors
        chart = theme.mark_violin(
            df, "group", "value", CATEGORIES,
            boxplot_size=10,
            palette="#AAAAAA",
            stroke="black",
            strokeWidth=0.5,
        )
    """
    from scipy.stats import gaussian_kde

    if fillOpacity is None:
        fillOpacity = alt.theme.options.get("markFillOpacity", 1.0)
    if strokeWidth is None:
        strokeWidth = alt.theme.options.get("markStrokeWidth", 0.5)
    mark_size = alt.theme.options.get("markSize", 10)
    band_padding = alt.theme.options.get("bandPadding", 0.1)
    chart_width = alt.theme.options.get("chartWidth", 100)
    step = chart_width / (len(categories) + 2 * band_padding)
    band_center = step * (0.5 - band_padding)

    violin_rows = []
    for group in categories:
        vals = df.filter(pl.col(x_col) == group)[y_col].to_numpy()
        y_grid = np.linspace(float(vals.min()) - 1, float(vals.max()) + 1, steps)
        kde = gaussian_kde(vals)
        density = kde(y_grid)
        density_norm = density / density.max()

        for order, (y, d) in enumerate(zip(y_grid, density_norm)):
            violin_rows.append(
                {
                    "__group": group,
                    "__y": float(y),
                    "__violin_px": float(d),
                    "__order": order,
                }
            )
        for order, (y, d) in enumerate(zip(reversed(y_grid), reversed(density_norm))):
            violin_rows.append(
                {
                    "__group": group,
                    "__y": float(y),
                    "__violin_px": float(-d),
                    "__order": steps + order,
                }
            )

    violin_df = pl.DataFrame(violin_rows)

    if angledX is None:
        angledX = alt.theme.options.get("angledX", False)
    x_axis = alt.Axis(labelAngle=315, labelAlign="right") if angledX else alt.Axis()

    mark_kwargs = {
        "filled": True,
        "strokeWidth": strokeWidth,
        "fillOpacity": fillOpacity,
        "strokeOpacity": 0 if stroke is None else 1,
    }
    if stroke is not None:
        mark_kwargs["stroke"] = stroke

    violin = (
        alt.Chart(violin_df)
        .mark_line(**mark_kwargs)
        .encode(
            x=alt.X("__group:N", sort=categories, title=None, axis=x_axis),
            xOffset=alt.XOffset(
                "__violin_px:Q",
                scale=alt.Scale(
                    domain=[-1, 1],
                    range=[band_center - mark_size * 0.75, band_center + mark_size * 0.75],
                ),
            ),
            y=alt.Y("__y:Q", title=y_col if y_title is _UNSET else y_title),
            order=alt.Order("__order:Q"),
            color=alt.Color(
                "__group:N",
                sort=categories,
                title=None,
                legend=alt.Legend(symbolType="circle") if legend else None,
                **(
                    {"scale": alt.Scale(range=palette if isinstance(palette, list) else [palette])}
                    if palette is not None
                    else {}
                ),
            ),
        )
    )

    boxplot = (
        alt.Chart(df)
        .mark_boxplot(
            color=boxplot_color,
            ticks=False,
            rule={"stroke": boxplot_color},
            **({"size": boxplot_size} if boxplot_size is not None else {}),
        )
        .encode(
            x=alt.X(f"{x_col}:N", sort=categories),
            y=alt.Y(f"{y_col}:Q", title=y_col if y_title is _UNSET else y_title),
        )
    )

    return alt.layer(violin, boxplot)


def mark_strip(
    df: pl.DataFrame,
    x_col: str,
    y_col: str,
    categories: list[str],
    *,
    scatter: str = "jitter",
    palette: list[str] | None = None,
    point_size: int | None = None,
    point_opacity: float | None = None,
    spread: float | None = None,
    legend: bool = False,
    errorbars: bool = True,
    errorbar_extent: str = "sem",
) -> alt.LayerChart:
    """
    Build an Altair layer combining jittered or beeswarm points with a median indicator.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``theme.add_pvalue``).

    Parameters
    ----------
    df:
        Polars DataFrame containing the data.
    x_col:
        Column name for the grouping variable (x-axis).
    y_col:
        Column name for the value variable (y-axis).
    categories:
        Ordered list of all x-axis categories.
    scatter:
        Point distribution method: ``'jitter'`` (faster, random Gaussian offset)
        or ``'beeswarm'`` (collision-avoidance, better for smaller n).
    point_size:
        Size of individual points. Inherits ``markSize`` from theme when ``None``.
    point_opacity:
        Opacity of individual points.
    spread:
        Controls point spread in pixels. For ``'jitter'``: standard deviation
        of the Gaussian offsets (~68% of points within ±spread). For
        ``'beeswarm'``: collision radius (points placed so no two centres are
        closer than 2·spread); total width grows with n.
    median_size:
        Width of the median/mean indicator in pixels.
    errorbars:
        Whether to show error bars around the group mean. When ``True``,
        the mean is shown as a tick with error bars. When ``False``, the
        median is shown instead.
    errorbar_extent:
        Statistic to use for error bars: ``'sem'`` (standard error of the
        mean, default) or ``'sd'`` (standard deviation).
    Examples
    --------
    ::

        theme.options()
        chart = theme.mark_strip(df, "group", "value", CATEGORIES)
        theme.save(chart, "strip")

        # beeswarm variant
        chart = theme.mark_strip(df, "group", "value", CATEGORIES, scatter="beeswarm")
    """
    if point_size is None:
        point_size = alt.theme.options.get("markSize", 10)
    if point_opacity is None:
        point_opacity = alt.theme.options.get("markFillOpacity", 1.0)

    if scatter == "jitter":
        df = add_jitter(df, spread=spread)
        offset_col = "jitter_x"
    elif scatter == "beeswarm":
        df = add_beeswarm(df, y_col=y_col, group_by=[x_col], spread=spread)
        offset_col = "beeswarm_x"
    else:
        raise ValueError(f"scatter must be 'jitter' or 'beeswarm', got {scatter!r}")

    band_padding = alt.theme.options.get("bandPadding", 0.1)
    chart_width = alt.theme.options.get("chartWidth", 100)
    step = chart_width / (len(categories) + 2 * band_padding)
    band_center = step * (0.5 - band_padding)
    max_offset = float(df[offset_col].abs().max())
    offset_scale = alt.Scale(
        domain=[-max_offset, max_offset],
        range=[band_center - max_offset, band_center + max_offset],
    )

    x = alt.X(f"{x_col}:N", sort=categories, title=None)

    points = (
        alt.Chart(df)
        .mark_circle(size=point_size, opacity=point_opacity)
        .encode(
            x=x,
            y=alt.Y(f"{y_col}:Q", title=y_col),
            xOffset=alt.XOffset(f"{offset_col}:Q", scale=offset_scale),
            color=alt.Color(
                f"{x_col}:N",
                sort=categories,
                title=x_col if legend else None,
                legend=alt.Legend() if legend else None,
                **({"scale": alt.Scale(range=palette)} if palette is not None else {}),
            ),
        )
    )

    median = (
        alt.Chart(df)
        .mark_boxplot(
            ticks=False,
            box={"fillOpacity": 0, "strokeOpacity": 0},
            rule={"strokeOpacity": 0},
            outliers={"opacity": 0},
        )
        .encode(
            x=x,
            y=alt.Y(f"{y_col}:Q", title=y_col),
        )
    )

    if not errorbars:
        return alt.layer(points, median)

    if errorbar_extent == "sem":
        error_expr = (pl.col(y_col).std() / pl.col(y_col).count().sqrt()).alias("__error")
    elif errorbar_extent == "sd":
        error_expr = pl.col(y_col).std().alias("__error")
    else:
        raise ValueError(f"errorbar_extent must be 'sem' or 'sd', got {errorbar_extent!r}")

    summary = df.group_by(x_col).agg([pl.col(y_col).median().alias("__median"), error_expr])

    errorbar_layer = (
        alt.Chart(summary)
        .mark_errorbar()
        .encode(
            x=x,
            y=alt.Y("__median:Q", title=y_col),
            yError=alt.YError("__error:Q"),
        )
    )

    return alt.layer(points, errorbar_layer, median)


def _format_pvalue(p: float, decimals: int = 3) -> str:
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.{decimals}f}"


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
    style: str = "line",
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

    label = _format_pvalue(pvalue, decimals=decimals)

    # --- y position ---
    if y is None:
        if df is None or x_col is None or y_col is None:
            raise ValueError("y is required when df, x_col, and y_col are not provided.")
        y = float(df.filter(pl.col(x_col).is_in([group1, group2]))[y_col].max()) + y_pad

    # --- resolve theme-linked defaults ---
    if chartWidth is None:
        chartWidth = alt.theme.options.get("chartWidth", 400)
    if strokeWidth is None:
        strokeWidth = alt.theme.options.get("axisWidth", 0.5)
    if fontSize is None:
        fontSize = alt.theme.options.get("fontSize", 7)

    # --- categories and text x position ---
    if categories is None:
        if df is None or x_col is None:
            raise ValueError("categories is required when df and x_col are not provided.")
        categories = sorted(df[x_col].unique().to_list())

    band_w = chartWidth / len(categories)
    g1_idx = categories.index(group1)
    g2_idx = categories.index(group2)
    x_mid_px = ((g1_idx + g2_idx + 1) / 2) * band_w

    _rule_kwargs = {"strokeWidth": strokeWidth, "strokeDash": [0, 0]}

    text_dy = 6 if reverse else -6
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

    text = (
        alt.Chart(alt.Data(values=[{"y": y, "label": label}]))
        .mark_text(align="center", fontSize=fontSize, dy=text_dy)
        .encode(
            x=alt.value(x_mid_px),
            y=alt.Y("y:Q"),
            text="label:N",
        )
    )

    if style == "bracket":
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
    df: pl.DataFrame,
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
    style: str = "line",
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
    style:
        ``'line'`` (horizontal bar only) or ``'bracket'`` (bar + end ticks).
    tick_height:
        Height of bracket end ticks in data units. Only used when
        ``style='bracket'``.
    strokeWidth:
        Stroke width of bracket lines. Inherits ``axisWidth`` from
        ``theme.options()`` when not set.
    fontSize:
        Font size of p-value labels. Inherits ``fontSize`` from
        ``theme.options()`` when not set.
    reverse:
        List of ``(group1, group2)`` tuples identifying brackets to flip —
        text moves below the bar and ticks point upward.
    decimals:
        Decimal places for p-value labels when ``p >= 0.001``.

    Examples
    --------
    Single comparison::

        CATEGORIES = ["Control", "Drug A", "Drug B"]
        chart = theme.mark_strip(df, "group", "value", CATEGORIES)
        chart + theme.add_pvalue(
            df, "group", "value",
            pairs=[("Control", "Drug A")],
            categories=CATEGORIES,
        )

    Multiple comparisons — brackets stacked automatically::

        chart + theme.add_pvalue(
            df, "group", "value",
            pairs=[("Control", "Drug A"), ("Control", "Drug B"), ("Drug A", "Drug B")],
            test="mannwhitneyu",
            categories=CATEGORIES,
        )

    From pre-computed p-values::

        chart + theme.add_pvalue(
            df, "group", "value",
            pairs=[("Control", "Drug A"), ("Control", "Drug B")],
            pvalues=[0.012, 0.341],
            categories=CATEGORIES,
        )
    """
    from scipy import stats as _stats

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
                style=style,
                categories=categories,
                chartWidth=chartWidth,
                strokeWidth=strokeWidth,
                fontSize=fontSize,
                reverse=(g1, g2) in reverse if reverse is not None else False,
                decimals=decimals,
            )
        )

    return alt.layer(*layer_charts)


def add_grid_labels_detached(
    groups: dict[str, list[str]],
    categories: list[str],
    *,
    order: list[str] | None = None,
    style: str = "plusminus",
    label_align: str = "left",
    label_padding: int = 0,
    dot_size: int | None = None,
    palette: list[str] | None = None,
    strokeWidth: float | None = None,
    connecting_line: bool = True,
    y_padding: float | None = None,
    chartWidth: int | None = None,
    fontSize: int | None = None,
    row_height: int = 14,
) -> alt.LayerChart:
    """
    Build a condition-table annotation chart to place below a strip/violin/boxplot.

    Each key in ``groups`` is a row label; its value is a list of ``"+"`` or ``"-"``
    strings, one per category (in the same order as ``categories``). Combine with the
    main chart using ``alt.vconcat(chart, add_grid_labels_detached(...)).resolve_scale(x="shared")``.

    Parameters
    ----------
    groups:
        Mapping of row-label → list of ``"+"`` / ``"-"`` values. Length of each list
        must equal ``len(categories)``.
    categories:
        Ordered list of x-axis categories — the same list passed to ``mark_strip``
        or ``mark_violin``.
    order:
        Row display order (top to bottom). Defaults to ``dict`` insertion order.
    style:
        ``"plusminus"`` renders literal ``+`` / ``−`` characters. ``"dots"`` renders
        filled circles — black for ``"+"`` and ``greys[0]`` for ``"-"`` — with a
        horizontal line connecting the leftmost to rightmost ``"+"`` in each row.
        ``"text"`` renders the raw values from the ``groups`` dict as center-aligned
        text, suitable for arbitrary labels.
    label_align:
        ``"left"`` (default) places row labels to the left of the grid with
        right-aligned text. ``"right"`` places them to the right with left-aligned text.
    label_padding:
        Gap in pixels between the plot boundary and the label text. Vega-Lite's
        default is 2. Negative values pull the labels into the plot area.
    dot_size:
        Area (in square pixels) of each dot in ``"dots"`` style. Defaults to
        ``markSize * 4`` from ``theme.options()``.
    palette:
        List of colors used to fill annotation marks. ``palette[0]`` is applied to
        ``"-"`` marks and ``palette[-1]`` to ``"+"`` marks. Overrides the darkmode
        defaults when provided. Pass the result of ``theme.palette()`` directly.
    strokeWidth:
        Stroke width applied to dot marks and the connecting rule. Defaults
        to ``markStrokeWidth`` from ``theme.options()``.
    connecting_line:
        When ``True`` (default), draws a horizontal rule spanning the
        leftmost to rightmost ``"+"`` in each row. Set to ``False`` to show
        dots only.
    y_padding:
        Inner padding between rows as a fraction of the band step (0–1).
        ``0`` means no gap; ``1`` means bands collapse to zero width.
        Defaults to Vega-Lite's band scale default of ``0.1``.
    chartWidth:
        Width of the annotation chart in pixels. Inherits ``chartWidth`` from
        ``theme.options()`` when not set.
    fontSize:
        Font size for ``"text"`` style symbols and row labels. Inherits ``fontSize``
        from ``theme.options()`` when not set.
    row_height:
        Height in pixels per annotation row.

    Notes
    -----
    **Row label alignment.** Row labels are rendered as explicit ``mark_text`` marks
    (not as y-axis labels) so they share the exact same y coordinate as the content
    marks. Vega-Lite's axis label rendering pipeline does not guarantee pixel-perfect
    alignment with ``mark_text`` even when both use ``baseline="middle"``, so the y
    axis is suppressed and labels are placed via ``alt.value(x)`` instead.

    **``bandPosition=0.5``** is set explicitly on the shared ``y_enc`` rather than
    relying on each mark type's default, which differs across mark types and may
    change between Vega-Lite versions.

    **``align="center"``** is required on all ``mark_text`` content marks. Without it,
    Vega-Lite's vertical band placement drifts relative to other marks on some versions.

    **Darkmode dot colours** (``positive_color``, ``negative_fill``, ``negative_stroke``)
    are resolved from ``alt.theme.options`` at call time. When using ``style="dots"``
    with ``theme.save()``, pass a callable so the chart is rebuilt after each darkmode
    toggle::

        theme.save(
            lambda: theme.add_grid_labels(chart, groups, style="dots", ...),
            "my_plot",
        )

    **hconcat label overflow.** Row label marks are positioned outside the declared
    ``width`` (at ``x < 0`` or ``x > chartWidth``). Vega-Lite does not clip them by
    default and does not reserve space for them in auto-layout. In an ``hconcat``,
    labels from one panel can bleed into adjacent panels; add explicit ``spacing``
    or outer padding to compensate.

    Examples
    --------
    ::

        CATEGORIES = ["Ctrl", "Drug A", "Drug B", "Drug C"]
        theme.options(chartWidth=300)
        chart = theme.mark_strip(df, "group", "value", CATEGORIES)
        ann = theme.add_grid_labels_detached(
            {
                "dTAG^V-1":       ["-", "+", "+", "+"],
                "ZFC3H1 WT":      ["-", "-", "+", "-"],
                "ZFC3H1(Δ730–747)": ["-", "-", "-", "+"],
            },
            categories=CATEGORIES,
            style="dots",
        )
        alt.vconcat(chart, ann).resolve_scale(x="shared")
    """
    from .palettes import colors

    row_order = order if order is not None else list(groups.keys())

    for label in row_order:
        if len(groups[label]) != len(categories):
            raise ValueError(
                f"groups[{label!r}] has {len(groups[label])} values but categories has "
                f"{len(categories)}. Each row must have one value per x-axis category, "
                f"in the same left-to-right order as the main chart."
            )

    if style not in ("plusminus", "text", "dots"):
        raise ValueError(f"style must be 'plusminus', 'text', or 'dots', got {style!r}")
    if label_align not in ("left", "right"):
        raise ValueError(f"label_align must be 'left' or 'right', got {label_align!r}")

    if chartWidth is None:
        chartWidth = alt.theme.options.get("chartWidth", 400)
    if fontSize is None:
        fontSize = alt.theme.options.get("fontSize", 7)

    rows = [
        {"__label": label, "__category": cat, "__value": val}
        for label in row_order
        for cat, val in zip(categories, groups[label])
    ]
    marks_df = pl.DataFrame(rows)

    chart_h = len(row_order) * row_height

    x_enc = alt.X(
        "__category:N",
        sort=categories,
        axis=alt.Axis(labels=False, ticks=False, domain=False, title=None),
    )
    y_scale = alt.Scale(paddingInner=y_padding) if y_padding is not None else alt.Undefined
    # Axis suppressed; row labels are explicit mark_text in row_labels layer below.
    # bandPosition=0.5 is explicit because per-mark defaults vary across mark types.
    y_enc = alt.Y(
        "__label:N",
        sort=row_order,
        bandPosition=0.5,
        scale=y_scale,
        axis=alt.Axis(labels=False, ticks=False, domain=False, title=None),
    )

    label_x = alt.value(chartWidth + label_padding) if label_align == "right" else alt.value(-label_padding)
    label_text_align = "left" if label_align == "right" else "right"
    label_df = pl.DataFrame({"__label": row_order})
    row_labels = (
        alt.Chart(label_df)
        .mark_text(fontSize=fontSize, align=label_text_align, baseline="middle")
        .encode(x=label_x, y=y_enc, text=alt.Text("__label:N"))
    )

    if style == "plusminus":
        text_df = marks_df.with_columns(
            pl.col("__value").replace({"-": "−"})
        )
        # align="center" is required — without it Vega-Lite's vertical band
        # placement drifts relative to other marks on some versions.
        layer = (
            alt.Chart(text_df)
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, text=alt.Text("__value:N"))
        )
        return alt.layer(row_labels, layer).properties(width=chartWidth, height=chart_h)

    if style == "text":
        layer = (
            alt.Chart(marks_df)
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, text=alt.Text("__value:N"))
        )
        return alt.layer(row_labels, layer).properties(width=chartWidth, height=chart_h)

    # --- dot style ---
    # Colours are resolved at call time from alt.theme.options so that darkmode
    # variants are correct. Use a callable with theme.save() to rebuild per variant.
    darkmode = alt.theme.options.get("darkmode", False)
    if darkmode:
        positive_color = "white"
        negative_fill = colors["greys"][6]
        negative_stroke = "white"
    else:
        positive_color = "black"
        negative_fill = colors["greys"][0]
        negative_stroke = alt.Undefined

    if palette is not None:
        negative_fill = palette[0]
        positive_color = palette[-1]

    if dot_size is None:
        dot_size = alt.theme.options.get("markSize", 10) * 4
    if strokeWidth is None:
        strokeWidth = alt.theme.options.get("markStrokeWidth", 0.25)

    plus_df = marks_df.filter(pl.col("__value") == "+")
    minus_df = marks_df.filter(pl.col("__value") == "-")

    positive = (
        alt.Chart(plus_df)
        .mark_point(filled=True, color=positive_color, strokeWidth=0, size=dot_size)
        .encode(x=x_enc, y=y_enc)
    )
    negative = (
        alt.Chart(minus_df)
        .mark_point(
            filled=True,
            fill=negative_fill,
            stroke=negative_stroke,
            strokeWidth=strokeWidth,
            size=dot_size,
        )
        .encode(x=x_enc, y=y_enc)
    )

    line_rows = []
    for label in row_order:
        plus_idxs = [i for i, v in enumerate(groups[label]) if v == "+"]
        if len(plus_idxs) >= 2:
            line_rows.append(
                {
                    "__label": label,
                    "__x_start": categories[plus_idxs[0]],
                    "__x_end": categories[plus_idxs[-1]],
                }
            )

    if connecting_line and line_rows:
        lines_df = pl.DataFrame(line_rows)
        lines = (
            alt.Chart(lines_df)
            # strokeDash=[0, 0] overrides the theme's dashedRule=True default.
            .mark_rule(color=positive_color, strokeWidth=strokeWidth, strokeDash=[0, 0])
            .encode(
                x=alt.X("__x_start:N", sort=categories),
                x2="__x_end:N",
                y=y_enc,
            )
        )
        chart = alt.layer(row_labels, lines, negative, positive)
    else:
        chart = alt.layer(row_labels, negative, positive)

    return chart.properties(width=chartWidth, height=chart_h)


def add_grid_labels(
    chart: alt.Chart,
    groups: dict[str, list[str]],
    categories: list[str],
    *,
    spacing: int = 0,
    **kwargs,
) -> alt.VConcatChart:
    """
    Compose a chart with a grid annotation table, replacing its x-axis labels.

    Strips x-axis labels and ticks from ``chart``, builds a :func:`add_grid_labels_detached`
    layer, and returns ``alt.vconcat(chart, annotation, spacing=spacing).resolve_scale(x="shared")``.

    All keyword arguments beyond ``spacing`` are forwarded to :func:`add_grid_labels_detached`.

    Parameters
    ----------
    chart:
        The main Altair chart (any type: ``Chart``, ``LayerChart``, etc.).
    groups:
        Passed to :func:`add_grid_labels_detached`.
    categories:
        Passed to :func:`add_grid_labels_detached`.
    spacing:
        Vertical gap in pixels between the chart and the annotation table.
        Defaults to 0 so the annotation sits flush below the axis line.

    Examples
    --------
    ::

        chart = theme.mark_strip(df, "group", "value", CATEGORIES)
        composed = theme.add_grid_labels(
            chart,
            {"dTAG^V-1": ["-", "+", "+", "+"], "ZFC3H1 WT": ["-", "-", "+", "-"]},
            categories=CATEGORIES,
            style="dots",
            label_align="right",
        )
        theme.save(composed, "my_plot")
    """
    import copy

    modified = copy.deepcopy(chart)

    def _strip_x_labels(node: alt.SchemaBase) -> None:
        # _kwds is used directly because `.axis` on alt.X returns a _PropertySetter
        # descriptor, not the stored value — reading it would not give the Axis object.
        if isinstance(node, alt.Chart):
            enc = node._kwds.get("encoding", alt.Undefined)
            if enc is not alt.Undefined:
                x = enc._kwds.get("x", alt.Undefined)
                if x is not alt.Undefined and isinstance(x, alt.X):
                    axis = x._kwds.get("axis", alt.Undefined)
                    if axis is alt.Undefined or axis is None:
                        x._kwds["axis"] = alt.Axis(labels=False, title=None)
                    elif isinstance(axis, alt.Axis):
                        axis._kwds["labels"] = False
                        axis._kwds["title"] = None
        if isinstance(node, alt.LayerChart):
            for layer in node._kwds.get("layer", []):
                _strip_x_labels(layer)
        if hasattr(node, "_kwds"):
            for sub in node._kwds.get("vconcat", []):
                _strip_x_labels(sub)
            for sub in node._kwds.get("hconcat", []):
                _strip_x_labels(sub)

    _strip_x_labels(modified)
    ann = add_grid_labels_detached(groups, categories, **kwargs)
    return alt.vconcat(modified, ann, spacing=spacing).resolve_scale(x="shared")

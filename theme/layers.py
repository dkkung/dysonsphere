import numpy as np
import polars as pl
import altair as alt


def mark_violin(
    df: pl.DataFrame,
    x_col: str,
    y_col: str,
    categories: list[str],
    *,
    boxplot_size: int = 8,
    boxplot_color: str = "black",
    violin_color: str | None = None,
    fillOpacity: float | None = None,
    stroke: str | None = None,
    strokeWidth: float | None = None,
    labelAngle: int = -45,
    steps: int = 200,
) -> alt.LayerChart:
    """
    Build an Altair layer combining a violin plot behind a boxplot.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``theme.pvalue_layer``).

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
    violin_color:
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
            violin_color="#AAAAAA",
            stroke="black",
            strokeWidth=0.5,
        )
    """
    from scipy.stats import gaussian_kde

    if fillOpacity is None:
        fillOpacity = alt.theme.options.get("markFillOpacity", 1.0)
    if strokeWidth is None:
        strokeWidth = alt.theme.options.get("markStrokeWidth", 0.5)

    n_groups = len(categories)

    violin_rows = []
    for group in categories:
        vals = df.filter(pl.col(x_col) == group)[y_col].to_numpy()
        y_grid = np.linspace(float(vals.min()) - 1, float(vals.max()) + 1, steps)
        kde = gaussian_kde(vals)
        density = kde(y_grid)
        density_norm = density / density.max()

        for order, (y, d) in enumerate(zip(y_grid, density_norm)):
            violin_rows.append({"__group": group, "__y": float(y), "__violin_px": float(d), "__order": order})
        for order, (y, d) in enumerate(zip(reversed(y_grid), reversed(density_norm))):
            violin_rows.append({"__group": group, "__y": float(y), "__violin_px": float(-d), "__order": steps + order})

    violin_df = pl.DataFrame(violin_rows)

    x_axis = alt.Axis(
        labelAngle=labelAngle,
        labelAlign="center" if labelAngle == 0 else "right",
    )

    mark_kwargs = {
        "filled": True,
        "strokeWidth": strokeWidth,
        "fillOpacity": fillOpacity,
    }
    if stroke is not None:
        mark_kwargs["stroke"] = stroke

    violin = (
        alt.Chart(violin_df)
        .mark_line(**mark_kwargs)
        .encode(
            x=alt.X("__group:N", sort=categories, title=x_col, axis=x_axis),
            xOffset=alt.XOffset("__violin_px:Q"),
            y=alt.Y("__y:Q", title=y_col),
            order=alt.Order("__order:Q"),
            color=alt.Color(
                "__group:N",
                sort=categories,
                legend=None,
                **(
                    {"scale": alt.Scale(range=[violin_color])}
                    if violin_color is not None
                    else {}
                ),
            ),
        )
    )

    boxplot = (
        alt.Chart(df)
        .mark_boxplot(color=boxplot_color, size=boxplot_size, ticks=False)
        .encode(
            x=alt.X(f"{x_col}:N", sort=categories),
            y=alt.Y(f"{y_col}:Q", title=y_col),
        )
    )

    return alt.layer(violin, boxplot)


def save(
    chart: alt.Chart,
    filename: str,
    ppi: int = 600,
) -> None:
    """
    Save a chart as light and dark PNG and SVG files.

    Produces four files from a single call:

    - ``<filename>_light.png`` and ``<filename>_light.svg``
    - ``<filename>_dark.png`` and ``<filename>_dark.svg``

    Dark and light versions are rendered by temporarily toggling
    ``darkmode`` in the theme options, leaving all other options intact.

    Parameters
    ----------
    chart:
        The Altair chart to save.
    filename:
        Extensionless path for the output files (e.g. ``"myplot"`` or
        ``"plots/myplot"``). A bare name saves to the current working
        directory, matching Altair's default behaviour.
    ppi:
        Pixel density for PNG output.

    Examples
    --------
    ::

        theme.options()
        chart = alt.Chart(df).mark_point().encode(...)
        theme.save(chart, "plots/myplot")
        # writes: plots/myplot_light.png, plots/myplot_light.svg,
        #         plots/myplot_dark.png,  plots/myplot_dark.svg
    """
    from pathlib import Path

    if not alt.theme.options:
        raise RuntimeError("theme.options() must be called before theme.save().")

    base = Path(filename)
    original_darkmode = alt.theme.options.get("darkmode", False)

    try:
        for mode, suffix in [(False, "_light"), (True, "_dark")]:
            alt.theme.options["darkmode"] = mode
            chart.save(str(base.parent / f"{base.name}{suffix}.png"), ppi=ppi)
            chart.save(str(base.parent / f"{base.name}{suffix}.svg"))
    finally:
        alt.theme.options["darkmode"] = original_darkmode


def _format_pvalue(p: float, decimals: int = 3) -> str:
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.{decimals}f}"


def pvalue_layer(
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
    """
    Build an Altair layer with a p-value annotation between two groups.

    Combine with your chart using ``+``:  ``chart + pvalue_layer(...)``.

    Parameters
    ----------
    df:
        Polars DataFrame. Required unless both ``pvalue`` and ``y`` are provided.
    x_col:
        Column name for the grouping variable (x-axis).
    y_col:
        Column name for the value variable (y-axis). Used to extract group
        data for the test and to auto-place the bracket when ``y`` is omitted.
    group1, group2:
        Values in ``x_col`` identifying the two groups to compare.
    test:
        Scipy test to run: ``'mannwhitneyu'``, ``'ttest_ind'``, ``'ttest_rel'``,
        ``'wilcoxon'``, or ``'tukey_hsd'``. Ignored when ``pvalue`` is provided.
    pvalue:
        Pre-computed p-value. Skips the statistical test entirely.
    correction:
        Multiple comparison correction: ``'bonferroni'`` or ``None``.
        Ignored for ``tukey_hsd`` (correction is built in).
    n_comparisons:
        Total number of comparisons for Bonferroni correction.
    y:
        Y position of the bracket in data units. Defaults to
        ``max(group data) + y_pad``.
    y_pad:
        Padding above the group maximum when ``y`` is auto-placed.
    tick_height:
        Height of the bracket end ticks in data units. Only used when
        ``style='bracket'``.
    style:
        ``'line'`` (horizontal bar only) or ``'bracket'`` (bar + end ticks).
    categories:
        Ordered list of all x-axis categories, used to compute the midpoint
        pixel position for the text label. Inferred from ``df`` if not provided
        (sorted alphabetically, matching Vega-Lite's default nominal ordering).
    chartWidth:
        Width of the chart in pixels. Used with ``categories`` to compute
        text x position. Should match ``.properties(width=...)``.
    strokeWidth:
        Stroke width of bracket lines. Defaults to ``axisWidth`` from
        ``theme.options()``, or 0.5 if the theme has not been configured.
    fontSize:
        Font size of the p-value label in points. Defaults to ``fontSize``
        from ``theme.options()``, or 7 if the theme has not been configured.
    reverse:
        If True, flips the annotation to the other side of the line/bracket —
        text moves below the bar and ticks point upward.
    decimals:
        Decimal places for the p-value label when ``p >= 0.001``.

    Examples
    --------
    From a DataFrame::

        chart = alt.Chart(df).mark_point().encode(x="group:N", y="value:Q")
        ann = theme.pvalue_layer(
            df, "group", "value", "Control", "Drug A",
            test="mannwhitneyu", y=210,
            categories=["Control", "Drug A", "Drug B"],
            chart_width=300,
        )
        chart + ann

    From a pre-computed p-value::

        _, p = scipy.stats.mannwhitneyu(ctrl, drug_a)
        ann = theme.pvalue_layer(
            group1="Control", group2="Drug A",
            pvalue=p, y=210,
            categories=["Control", "Drug A", "Drug B"],
            chart_width=300,
        )
    """
    from scipy import stats as _stats

    # --- p-value ---
    if pvalue is None:
        if df is None or x_col is None or y_col is None:
            raise ValueError(
                "df, x_col, and y_col are required when pvalue is not provided."
            )

        if test == "tukey_hsd":
            _cats = (
                categories
                if categories is not None
                else sorted(df[x_col].unique().to_list())
            )
            all_groups = [
                df.filter(pl.col(x_col) == cat)[y_col].to_numpy() for cat in _cats
            ]
            result = _stats.tukey_hsd(*all_groups)
            pvalue = float(result.pvalue[_cats.index(group1)][_cats.index(group2)])
        else:
            a = df.filter(pl.col(x_col) == group1)[y_col].to_numpy()
            b = df.filter(pl.col(x_col) == group2)[y_col].to_numpy()
            _tests = {
                "mannwhitneyu": lambda: (
                    _stats.mannwhitneyu(a, b, alternative="two-sided").pvalue
                ),
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
            raise ValueError(
                "y is required when df, x_col, and y_col are not provided."
            )
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
            raise ValueError(
                "categories is required when df and x_col are not provided."
            )
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

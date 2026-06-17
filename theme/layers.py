import altair as alt
import numpy as np
import polars as pl

from .transforms import add_beeswarm_offsets, add_jitter_offsets


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
    # When xOffset is present, Vega-Lite sets paddingInner=0 on the outer band scale
    # so step = W / (n + 2*paddingOuter) rather than W / (n + paddingInner).
    # band_center is the xOffset value that places the violin over the boxplot center.
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
            y=alt.Y("__y:Q", title=y_col),
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
            y=alt.Y(f"{y_col}:Q", title=y_col),
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
    jitter_scale: float = 4.0,
    legend: bool = False,
    errorbars: bool = True,
    errorbar_extent: str = "sem",
) -> alt.LayerChart:
    """
    Build an Altair layer combining jittered or beeswarm points with a median indicator.

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
        Ordered list of all x-axis categories.
    scatter:
        Point distribution method: ``'jitter'`` (faster, random Gaussian offset)
        or ``'beeswarm'`` (collision-avoidance, better for smaller n).
    point_size:
        Size of individual points. Inherits ``markSize`` from theme when ``None``.
    point_opacity:
        Opacity of individual points.
    jitter_scale:
        Standard deviation of jitter offsets in pixels. Only used when
        ``scatter='jitter'``.
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
        df = add_jitter_offsets(df, scale=jitter_scale)
        offset_col = "jitter_x"
    elif scatter == "beeswarm":
        df = add_beeswarm_offsets(df, y_col=y_col, group_by=[x_col])
        offset_col = "beeswarm_x"
    else:
        raise ValueError(f"scatter must be 'jitter' or 'beeswarm', got {scatter!r}")

    x = alt.X(f"{x_col}:N", sort=categories, title=None)

    points = (
        alt.Chart(df)
        .mark_circle(size=point_size, opacity=point_opacity)
        .encode(
            x=x,
            y=alt.Y(f"{y_col}:Q", title=y_col),
            xOffset=alt.XOffset(f"{offset_col}:Q"),
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


def save(
    chart: alt.Chart,
    filename: str,
    ppi: int = 1200,
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
    original_transparent = alt.theme.options.get("transparentBackground", False)

    try:
        alt.theme.options["transparentBackground"] = True
        for mode, suffix in [(False, "_light"), (True, "_dark")]:
            alt.theme.options["darkmode"] = mode
            chart.save(str(base.parent / f"{base.name}{suffix}.png"), ppi=ppi)
            svg_path = str(base.parent / f"{base.name}{suffix}.svg")
            chart.save(svg_path)
            _simplify_svg(svg_path)
    finally:
        alt.theme.options["darkmode"] = original_darkmode
        alt.theme.options["transparentBackground"] = original_transparent


def _simplify_svg(path: str) -> None:
    """
    Reduce SVG grouping depth by inlining structurally redundant ``<g>`` elements.

    Altair/Vega generates deeply nested ``<g>`` wrappers for its internal mark
    grouping system (e.g. ``role-frame``, ``role-mark``, ``mark-symbol``). These
    groups carry only a ``class`` attribute and have no effect on visual output,
    but they require extra double-clicks to navigate in Adobe Illustrator and
    other SVG editors.

    This function removes those wrappers by inlining their children directly into
    the parent element. Groups that carry any of the following attributes are
    preserved because they affect rendering or layout: ``transform``,
    ``clip-path``, ``opacity``, ``mask``, ``filter``, ``style``, ``id``.
    Definition blocks (``<defs>``, ``<clipPath>``, ``<symbol>``) are left
    entirely untouched.

    The result is a flatter, editor-friendly SVG that renders identically to the
    original.
    """
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    # Groups with any of these attributes affect rendering or layout — keep them
    KEEP_ATTRS = {"transform", "clip-path", "opacity", "mask", "filter", "style", "id"}
    # Don't recurse into definition blocks
    SKIP_TAGS = {f"{{{NS}}}defs", f"{{{NS}}}clipPath", f"{{{NS}}}symbol"}

    def _flatten(parent):
        if parent.tag in SKIP_TAGS:
            return
        i = 0
        while i < len(parent):
            child = parent[i]
            _flatten(child)
            if child.tag == f"{{{NS}}}g" and not (set(child.attrib) & KEEP_ATTRS):
                grandchildren = list(child)
                parent.remove(child)
                for j, gc in enumerate(grandchildren):
                    parent.insert(i + j, gc)
                if not grandchildren:
                    i += 1
            else:
                i += 1

    tree = ET.parse(path)
    _flatten(tree.getroot())
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(ET.tostring(tree.getroot(), encoding="unicode"))


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

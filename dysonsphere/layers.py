import math

import altair as alt
import numpy as np
import polars as pl

from .transforms import add_beeswarm_offsets, add_jitter_offsets

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


def save(
    chart: alt.Chart,
    filename: str,
    ppi: int = 1200,
    description: str | None = None,
    save_vega_spec: bool = True,
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
    description:
        Optional description embedded in the chart via ``chart.properties(description=...)``.
        Appears as a ``<desc>`` element in SVG output.
    save_vega_spec:
        If ``True``, also writes ``<filename>.json`` containing the full Vega-Lite spec.

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

    if description is not None:
        chart = chart.properties(description=description)

    base = Path(filename)
    original_darkmode = alt.theme.options.get("darkmode", False)
    original_transparent = alt.theme.options.get("transparentBackground", False)

    if save_vega_spec:
        chart.save(str(base.parent / f"{base.name}_vegalite.json"))

    try:
        import vl_convert as vlc

        alt.theme.options["transparentBackground"] = True
        for mode, suffix in [(False, "_light"), (True, "_dark")]:
            alt.theme.options["darkmode"] = mode
            svg_path = str(base.parent / f"{base.name}{suffix}.svg")
            chart.save(svg_path)
            _fix_tick_alignment(
                svg_path,
                band_padding=alt.theme.options.get("bandPadding", 0.1),
                chart_width=alt.theme.options.get("chartWidth", 100),
            )
            _simplify_svg(svg_path)
            with open(svg_path, encoding="utf-8") as f:
                svg_content = f.read()
            png_path = str(base.parent / f"{base.name}{suffix}.png")
            Path(png_path).write_bytes(vlc.svg_to_png(svg_content, ppi=ppi))
    finally:
        alt.theme.options["darkmode"] = original_darkmode
        alt.theme.options["transparentBackground"] = original_transparent


def _fix_tick_alignment(
    path: str, band_padding: float = 0.1, chart_width: float = 100.0
) -> None:
    """Move x-axis tick lines from Vega's floor'd integer positions to exact mark centers.

    Vega snaps axis tick group transforms to integers for crisp screen rendering but
    keeps mark coordinates as floats.  At high DPI (scale ≥ 4) this produces visible
    misalignment.

    For bar charts: tick centers are read from the bar path data (aria-roledescription="bar").
    For all other charts (strip, violin, scatter, etc.): band centers are computed
    analytically from the number of categories and theme scale parameters, then ticks
    are moved to those float positions.  This aligns ticks with every element in the
    group — circles, median ticks, violin bodies — without any data manipulation.
    """
    import re
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    tree = ET.parse(path)
    root = tree.getroot()

    # --- bar charts: read centers from path data ---
    bar_centers: list[float] = []
    for el in root.iter(f"{{{NS}}}path"):
        if el.get("aria-roledescription") != "bar":
            continue
        d = el.get("d", "")
        m = re.match(r"M([\d.]+),[-\d.e+]+h([\d.]+)", d)
        if m:
            bar_centers.append(round(float(m.group(1)) + float(m.group(2)) / 2, 4))

    if bar_centers:
        unique_centers = sorted(set(bar_centers))

        def nearest(tick_x: float) -> float | None:
            c = min(unique_centers, key=lambda v: abs(v - tick_x))
            return c if abs(c - tick_x) < 2.0 else None

        def apply_bar_fix(el: ET.Element) -> None:
            for child in el:
                if child.get("class", "") == "mark-rule role-axis-tick":
                    for line in child:
                        t = line.get("transform", "")
                        m = re.match(r"translate\((\d+(?:\.\d+)?),0\)$", t)
                        if m:
                            c = nearest(float(m.group(1)))
                            if c is not None:
                                line.set("transform", f"translate({c},0)")
                else:
                    apply_bar_fix(child)

        apply_bar_fix(root)

    else:
        # --- non-bar charts: compute band centers analytically ---
        # Collect integer tick x positions from all x-axis tick groups.
        tick_xs: list[float] = []

        def collect_ticks(el: ET.Element) -> None:
            for child in el:
                if child.get("class", "") == "mark-rule role-axis-tick":
                    for line in child:
                        t = line.get("transform", "")
                        m = re.match(r"translate\((\d+(?:\.\d+)?),0\)$", t)
                        if m:
                            v = float(m.group(1))
                            if v > 0:
                                tick_xs.append(v)
                else:
                    collect_ticks(child)

        collect_ticks(root)
        if not tick_xs:
            return

        # With xOffset encoding Vega sets paddingInner=0, so
        # step = chart_width / (n + 2·paddingOuter)
        # band_center_i = step · (paddingOuter + i + 0.5)
        n = len(tick_xs)
        step = chart_width / (n + 2 * band_padding)
        sorted_ticks = sorted(tick_xs)
        center_map = {
            t: round(step * (band_padding + i + 0.5), 4)
            for i, t in enumerate(sorted_ticks)
        }

        def apply_analytic_fix(el: ET.Element) -> None:
            for child in el:
                if child.get("class", "") == "mark-rule role-axis-tick":
                    for line in child:
                        t = line.get("transform", "")
                        m = re.match(r"translate\((\d+(?:\.\d+)?),0\)$", t)
                        if m:
                            c = center_map.get(float(m.group(1)))
                            if c is not None:
                                line.set("transform", f"translate({c},0)")
                else:
                    apply_analytic_fix(child)

        apply_analytic_fix(root)

    with open(path, "w", encoding="utf-8") as f:
        f.write(ET.tostring(root, encoding="unicode"))


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


def pvalue_layers(
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
    decimals: int = 3,
) -> alt.LayerChart:
    """
    Build stacked p-value annotation layers for multiple group comparisons.

    A batch version of :func:`pvalue_layer` that automatically stacks brackets
    so they don't overlap. Shorter-span pairs are placed lower; pairs whose
    x-ranges overlap are bumped to the next level.

    Combine with your chart using ``+``:  ``chart + pvalue_layers(...)``.

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
        List of ``(group1, group2)`` tuples identifying the comparisons to annotate.
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
    decimals:
        Decimal places for p-value labels when ``p >= 0.001``.

    Examples
    --------
    Run tests and annotate three pairs::

        CATEGORIES = ["Control", "Drug A", "Drug B"]
        theme.options(chartWidth=300)
        chart = theme.mark_strip(df, "group", "value", CATEGORIES)
        ann = theme.pvalue_layers(
            df, "group", "value",
            pairs=[("Control", "Drug A"), ("Control", "Drug B"), ("Drug A", "Drug B")],
            test="mannwhitneyu",
            categories=CATEGORIES,
        )
        chart + ann

    From pre-computed p-values::

        ann = theme.pvalue_layers(
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
            pvalue_layer(
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
                decimals=decimals,
            )
        )

    return alt.layer(*layer_charts)

import numpy as np
import polars as pl
import altair as alt

from .colors import colors


def palette_range(
    name: str,
    n: int | None = None,
    start: int = 0,
    stop: int | None = None,
    step: int = 1,
    reverse: bool = False,
) -> list[str]:
    """
    Sample colors from a named palette with control over start, stop, and spacing.

    When ``n`` is provided, evenly samples ``n`` colors between ``start`` and
    ``stop`` (linspace). Otherwise, returns every ``step``-th color from
    ``start`` to ``stop`` — with default ``step=1`` this returns the full slice.

    Parameters
    ----------
    name:
        Key in the ``colors`` dict (e.g. ``"mpl_YlGnBu"``).
    n:
        Number of colors to return (evenly spaced). Takes priority over ``step``.
    start:
        Index of the first color to include. Defaults to 0.
    stop:
        Index of the last color to include (inclusive). Defaults to the last
        index in the palette.
    step:
        Step between color indices. Defaults to 1 (every color).
    reverse:
        If True, reverse the returned list.

    Examples
    --------
    All colors in the palette:

        palette_range("mpl_YlGnBu")

    Last 4 colors:

        palette_range("mpl_YlGnBu", start=5)

    Four evenly-spaced colors across the full palette:

        palette_range("mpl_YlGnBu", n=4)

    Every second color from index 0 to 6 (returns indices 0, 2, 4, 6):

        palette_range("mpl_YlGnBu", stop=6, step=2)

    Four evenly-spaced colors, reversed:

        palette_range("mpl_YlGnBu", n=4, reverse=True)
    """
    palette = colors[name]
    total = len(palette)
    if stop is None:
        stop = total - 1

    if n is not None:
        if n == 1:
            indices = [start]
        else:
            indices = [round(start + i * (stop - start) / (n - 1)) for i in range(n)]
    else:
        indices = list(range(start, stop + 1, step))

    result = [palette[i] for i in indices]
    return result[::-1] if reverse else result


def beeswarm_offsets(
    y_vals,
    height_px: int | None = None,
    markSize: float = 10,
    step: float | None = None,
) -> np.ndarray:
    """
    Compute x offsets (pixels) for a beeswarm plot using collision avoidance.

    Converts y values to pixel space, then places each point at the nearest
    x position (outward from 0) that does not overlap any already-placed point.
    Use the result as an ``xOffset`` column in Altair.

    Parameters
    ----------
    y_vals:
        Array of y values for one group (e.g. one treatment × time combination).
    height_px:
        Chart height in pixels. Should match ``.properties(height=...)``.
    markSize:
        Altair mark size (area in sq px). Should match the ``size=`` kwarg on
        the mark. Defaults to the theme's ``markSize`` default of 10.
    step:
        x step size (px) between candidate positions. Defaults to the point
        radius derived from ``markSize``.

    Returns
    -------
    numpy.ndarray
        x offsets in pixels, one per input value, in the same order.

    Examples
    --------
    Compute offsets per group with Polars then plot in Altair::

        df = (
            df
            .with_row_index("__idx")
            .group_by(["Metadata_Treatment", "Metadata_Time"])
            .map_groups(lambda g: g.with_columns(
                pl.Series("beeswarm_x", theme.beeswarm_offsets(
                    g["my_column"].to_numpy(),
                    height_px=200,
                    markSize=10,
                ))
            ))
            .sort("__idx")
            .drop("__idx")
        )

        alt.Chart(df).mark_circle(size=10).encode(
            x=alt.X("Metadata_Time:O"),
            y=alt.Y("my_column:Q"),
            xOffset=alt.XOffset("beeswarm_x:Q"),
        )
    """
    if height_px is None:
        height_px = alt.theme.options.get("chartHeight", 300)

    y_vals = np.asarray(y_vals, dtype=float)
    n = len(y_vals)
    if n == 0:
        return np.array([])

    r = np.sqrt(markSize / np.pi)
    if step is None:
        step = r

    y_min, y_max = y_vals.min(), y_vals.max()
    y_px = (y_vals - y_min) / max(y_max - y_min, 1e-9) * height_px

    min_dist_sq = (2 * r) ** 2
    order = np.argsort(y_px)
    placed_y = np.empty(n)
    placed_x = np.empty(n)
    offsets = np.zeros(n)
    n_placed = 0

    for idx in order:
        y = y_px[idx]
        nearby = np.abs(placed_y[:n_placed] - y) <= 4 * r
        for k in range(1000):
            for cx in [0.0] if k == 0 else [k * step, -k * step]:
                ny = placed_y[:n_placed][nearby]
                nx = placed_x[:n_placed][nearby]
                if len(ny) == 0 or np.all(
                    (ny - y) ** 2 + (nx - cx) ** 2 >= min_dist_sq
                ):
                    placed_y[n_placed] = y
                    placed_x[n_placed] = cx
                    n_placed += 1
                    offsets[idx] = cx
                    break
            else:
                continue
            break

    return offsets


def add_beeswarm_offsets(
    df: pl.DataFrame,
    y_col: str,
    group_by: list[str],
    height_px: int | None = None,
    markSize: float = 10,
    step: float | None = None,
    out_col: str = "beeswarm_x",
) -> pl.DataFrame:
    """
    Add a beeswarm x-offset column to a Polars DataFrame, computed per group.

    A convenience wrapper around :func:`beeswarm_offsets` that handles the
    ``with_row_index`` / ``map_groups`` / ``sort`` / ``drop`` pattern.

    Parameters
    ----------
    df:
        Input DataFrame.
    y_col:
        Name of the column containing y values.
    group_by:
        Column name(s) that define each beeswarm group (e.g.
        ``["Metadata_Treatment", "Metadata_Time"]``).
    height_px:
        Chart height in pixels.
    markSize:
        Altair mark size (area in sq px).
    step:
        x step size (px). Defaults to the point radius.
    out_col:
        Name of the output offset column added to the DataFrame.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``out_col`` column.

    Examples
    --------
    ::

        df = theme.add_beeswarm_offsets(
            df,
            y_col="percent",
            group_by=["Metadata_Treatment", "Metadata_Time"],
            height_px=200,
            markSize=10,
        )

        alt.Chart(df).mark_circle(size=10).encode(
            x=alt.X("Metadata_Time:O"),
            y=alt.Y("percent:Q"),
            xOffset=alt.XOffset("beeswarm_x:Q"),
        )
    """
    return (
        df.with_row_index("__beeswarm_idx")
        .group_by(group_by)
        .map_groups(
            lambda g: g.with_columns(
                pl.Series(
                    out_col,
                    beeswarm_offsets(
                        g[y_col].to_numpy(),
                        height_px=height_px,
                        markSize=markSize,
                        step=step,
                    ),
                )
            )
        )
        .sort("__beeswarm_idx")
        .drop("__beeswarm_idx")
    )


def add_jitter_offsets(
    df: pl.DataFrame,
    scale: float = 5.0,
    out_col: str = "jitter_x",
    seed: int | None = 2022_07_01,
) -> pl.DataFrame:
    """
    Add a column of random Gaussian x-offsets to a Polars DataFrame.

    Each point receives an independent offset drawn from N(0, scale). Use the
    result as an ``xOffset`` column in Altair to jitter points horizontally.

    Unlike :func:`add_beeswarm_offsets`, there is no collision avoidance —
    points can overlap. This is faster and simpler for large datasets where
    some overlap is acceptable.

    Parameters
    ----------
    df:
        Input DataFrame.
    scale:
        Standard deviation of the jitter in pixels.
    out_col:
        Name of the output offset column added to the DataFrame.
    seed:
        Optional random seed for reproducibility.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``out_col`` column.

    Examples
    --------
    ::

        df = theme.add_jitter_offsets(df, scale=5)

        alt.Chart(df).mark_circle().encode(
            x=alt.X("group:N"),
            y=alt.Y("value:Q"),
            xOffset=alt.XOffset("jitter_x:Q"),
        )
    """
    rng = np.random.default_rng(seed)
    return df.with_columns(
        pl.Series(out_col, rng.normal(0, scale, len(df)))
    )


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
        raise RuntimeError(
            "theme.options() must be called before theme.save()."
        )

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

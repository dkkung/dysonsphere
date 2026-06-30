from typing import Any, Final, cast

import altair as alt
import numpy as np
import polars as pl

from .transforms import add_beeswarm, add_jitter
from .utils import ensure_polars


class _UnsetType:
    pass


_UNSET: Final[_UnsetType] = _UnsetType()


def mark_violin(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    categories: list[str],
    *,
    boxplotSize: int | None = None,
    boxplotColor: str = "black",
    palette: str | list[str] | None = None,
    fillOpacity: float | None = None,
    stroke: str | None = None,
    strokeWidth: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    steps: int = 200,
    yTitle: str | None | _UnsetType = _UNSET,
    xTitle: str | None | _UnsetType = _UNSET,
) -> alt.LayerChart:
    """
    Build an Altair layer combining a violin plot behind a boxplot.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``ds.add_pvalue``).

    Parameters
    ----------
    df:
        Polars DataFrame containing the data.
    xCol:
        Column name for the grouping variable (x-axis).
    yCol:
        Column name for the value variable (y-axis).
    categories:
        Ordered list of all x-axis categories, used for positioning and
        axis labels.
    boxplotSize:
        Width of the boxplot box in pixels.
    boxplotColor:
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
    xLabelAngle:
        X-axis label rotation in degrees. Negative tilts left (e.g. ``-45``),
        positive tilts right; ``labelAlign`` is derived automatically from the
        sign. ``None`` inherits from ``theme(xLabelAngle)``.
    steps:
        Number of y grid points used for KDE estimation (per group).
    yTitle:
        Y-axis title. Defaults to ``yCol``. Pass ``None`` to suppress.
    xTitle:
        X-axis title. Defaults to ``xCol``. Pass ``None`` to suppress.

    The returned ``LayerChart`` is safe to place in ``alt.hconcat()`` alongside
    ``mark_strip()`` or any other chart — the violin uses absolute ``x:Q``
    coordinates internally rather than ``xOffset``, so Vega-Lite's xOffset
    scale resolution never squishes the violin shape.

    Examples
    --------
    ::

        ds.theme(chartWidth=250)
        chart = ds.mark_violin(df, "group", "value", CATEGORIES)
        ds.save(chart, "violin")

        # safe in hconcat with mark_strip
        left = ds.mark_strip(df, "group", "value", CATEGORIES)
        right = ds.mark_violin(df, "group", "value", CATEGORIES)
        ds.save(alt.hconcat(left, right), "comparison")

        # with optional outline and custom colors
        chart = ds.mark_violin(
            df, "group", "value", CATEGORIES,
            boxplotSize=10,
            palette="#AAAAAA",
            stroke="black",
            strokeWidth=0.5,
        )
    """
    from scipy.stats import gaussian_kde

    df = ensure_polars(df)
    if fillOpacity is None:
        fillOpacity = alt.theme.options.get("markFillOpacity", 1.0)
    if strokeWidth is None:
        strokeWidth = alt.theme.options.get("markStrokeWidth", 0.5)
    mark_size = alt.theme.options.get("markSize", 10)
    band_padding = alt.theme.options.get("bandPadding", 0.1)
    chart_width = alt.theme.options.get("chartWidth", 100)
    # mark_boxplot uses paddingInner=paddingOuter=band_padding, so the D3 band
    # scale formula is step = W / (n - paddingInner + 2*paddingOuter) = W / (n + bp).
    # Band center for index i = step * (0.5 + bp/2 + i).  This differs from the
    # xOffset/mark_circle formula (W / (n + 2*bp); center = step*(bp + 0.5 + i)).
    step = chart_width / (len(categories) + band_padding)
    half_width = mark_size * 0.75

    # Precompute absolute x positions for each violin point so the violin
    # layer uses x:Q (not xOffset), avoiding Vega-Lite's shared xOffset
    # scale resolution that squishes the violin when hconcated with any
    # chart that also uses xOffset (e.g. mark_strip).
    violin_rows = []
    for i, group in enumerate(categories):
        x_center = step * (0.5 + band_padding / 2 + i)
        vals = df.filter(pl.col(xCol) == group)[yCol].to_numpy()
        y_min = float(vals.min()) - 1
        y_max = float(vals.max()) + 1
        y_grid = np.linspace(y_min, y_max, steps)
        kde = gaussian_kde(vals)
        density = kde(y_grid)
        density_norm = density / density.max()

        for order, (y, d) in enumerate(zip(y_grid, density_norm)):
            violin_rows.append(
                {
                    "__group": group,
                    "__y": float(y),
                    "__x": x_center + d * half_width,
                    "__order": order,
                }
            )
        for order, (y, d) in enumerate(zip(reversed(y_grid), reversed(density_norm))):
            violin_rows.append(
                {
                    "__group": group,
                    "__y": float(y),
                    "__x": x_center - d * half_width,
                    "__order": steps + order,
                }
            )

    violin_df = pl.DataFrame(violin_rows)
    _y_title: str | None = yCol if isinstance(yTitle, _UnsetType) else yTitle
    _x_title: str | None = xCol if isinstance(xTitle, _UnsetType) else xTitle

    if xLabelAngle is None:
        xLabelAngle = alt.theme.options.get("xLabelAngle", 0)
    if xLabelAngle != 0:
        align = "right" if xLabelAngle < 0 else "left"
        x_axis = alt.Axis(labelAngle=xLabelAngle % 360, labelAlign=align)
    else:
        x_axis = alt.Axis()

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
            x=alt.X("__x:Q", scale=alt.Scale(domain=[0, chart_width]), axis=None),
            y=alt.Y("__y:Q", title=_y_title),
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
            color=boxplotColor,
            ticks=False,
            rule={"stroke": boxplotColor},
            **({"size": boxplotSize} if boxplotSize is not None else {}),
        )
        .encode(
            x=alt.X(f"{xCol}:N", sort=categories, title=_x_title, axis=x_axis),
            y=alt.Y(f"{yCol}:Q", title=_y_title),
        )
    )

    return cast(alt.LayerChart, alt.layer(violin, boxplot).resolve_axis(x="independent"))


def mark_strip(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    categories: list[str],
    *,
    scatter: str = "jitter",
    palette: list[str] | None = None,
    markSize: int | None = None,
    markOpacity: float | None = None,
    spread: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    errorbars: bool = True,
    errorbarExtent: str = "sem",
    yTitle: str | None | _UnsetType = _UNSET,
    xTitle: str | None | _UnsetType = _UNSET,
) -> alt.LayerChart:
    """
    Build an Altair layer combining jittered or beeswarm points with a median indicator.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``ds.add_pvalue``).

    Parameters
    ----------
    df:
        Polars DataFrame containing the data.
    xCol:
        Column name for the grouping variable (x-axis).
    yCol:
        Column name for the value variable (y-axis).
    categories:
        Ordered list of all x-axis categories.
    scatter:
        Point distribution method: ``'jitter'`` (faster, random Gaussian offset)
        or ``'beeswarm'`` (collision-avoidance, better for smaller n).
    markSize:
        Size of individual points. Inherits ``markSize`` from theme when ``None``.
    markOpacity:
        Opacity of individual points. Inherits ``markFillOpacity`` from theme when ``None``.
    spread:
        Controls point spread in pixels. For ``'jitter'``: standard deviation
        of the Gaussian offsets (~68% of points within ±spread). For
        ``'beeswarm'``: collision radius (points placed so no two centres are
        closer than 2·spread); total width grows with n.
    xLabelAngle:
        X-axis label rotation in degrees. Negative tilts left (e.g. ``-45``),
        positive tilts right; ``labelAlign`` is derived automatically from the
        sign. ``None`` inherits from ``theme(xLabelAngle)``.
    errorbars:
        Whether to show error bars around the group mean. When ``True``,
        the mean is shown as a tick with error bars. When ``False``, the
        median is shown instead.
    errorbarExtent:
        Statistic to use for error bars: ``'sem'`` (standard error of the
        mean, default) or ``'sd'`` (standard deviation).
    yTitle:
        Y-axis title. Defaults to ``yCol``. Pass ``None`` to suppress.
    xTitle:
        X-axis title. Defaults to ``xCol``. Pass ``None`` to suppress.

    Examples
    --------
    ::

        ds.theme()
        chart = ds.mark_strip(df, "group", "value", CATEGORIES)
        ds.save(chart, "strip")

        # beeswarm variant
        chart = ds.mark_strip(df, "group", "value", CATEGORIES, scatter="beeswarm")
    """
    df = ensure_polars(df)
    _y_title: str | None = yCol if isinstance(yTitle, _UnsetType) else yTitle
    _x_title: str | None = xCol if isinstance(xTitle, _UnsetType) else xTitle
    if markSize is None:
        markSize = alt.theme.options.get("markSize", 10)
    if markOpacity is None:
        markOpacity = alt.theme.options.get("markFillOpacity", 1.0)

    if scatter == "jitter":
        df = add_jitter(df, spread=spread)
        offset_col = "jitter_x"
    elif scatter == "beeswarm":
        df = add_beeswarm(df, yCol=yCol, groupBy=[xCol], spread=spread)
        offset_col = "beeswarm_x"
    else:
        raise ValueError(f"scatter must be 'jitter' or 'beeswarm', got {scatter!r}")

    band_padding = alt.theme.options.get("bandPadding", 0.1)
    chart_width = alt.theme.options.get("chartWidth", 100)
    step = chart_width / (len(categories) + 2 * band_padding)
    band_center = step * (0.5 - band_padding)
    max_offset = cast(float, df[offset_col].abs().cast(pl.Float64).max() or 0.0)
    offset_scale = alt.Scale(
        domain=[-max_offset, max_offset],
        range=[band_center - max_offset, band_center + max_offset],
    )

    if xLabelAngle is None:
        xLabelAngle = alt.theme.options.get("xLabelAngle", 0)
    if xLabelAngle != 0:
        align = "right" if xLabelAngle < 0 else "left"
        x_axis = alt.Axis(labelAngle=xLabelAngle % 360, labelAlign=align)
    else:
        x_axis = alt.Axis()

    x = alt.X(f"{xCol}:N", sort=categories, title=_x_title, axis=x_axis)

    points = (
        alt.Chart(df)
        .mark_circle(size=markSize, opacity=markOpacity)
        .encode(
            x=x,
            y=alt.Y(f"{yCol}:Q", title=_y_title),
            xOffset=alt.XOffset(f"{offset_col}:Q", scale=offset_scale),
            color=alt.Color(
                f"{xCol}:N",
                sort=categories,
                title=xCol if legend else None,
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
            y=alt.Y(f"{yCol}:Q", title=_y_title),
        )
    )

    if not errorbars:
        return cast(alt.LayerChart, alt.layer(points, median))

    if errorbarExtent == "sem":
        error_expr = (pl.col(yCol).std() / pl.col(yCol).count().sqrt()).alias("__error")
    elif errorbarExtent == "sd":
        error_expr = pl.col(yCol).std().alias("__error")
    else:
        raise ValueError(f"errorbarExtent must be 'sem' or 'sd', got {errorbarExtent!r}")

    summary = df.group_by(xCol).agg([pl.col(yCol).mean().alias("__mean"), error_expr])

    errorbar_layer = (
        alt.Chart(summary)
        .mark_errorbar()
        .encode(
            x=x,
            y=alt.Y("__mean:Q", title=_y_title),
            yError=alt.YError("__error:Q"),
        )
    )

    return cast(alt.LayerChart, alt.layer(points, errorbar_layer, median))

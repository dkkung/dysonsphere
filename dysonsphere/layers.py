import math
from typing import Any

import altair as alt
import numpy as np
import polars as pl

from .transforms import add_beeswarm, add_jitter
from .utils import count_n, ensure_polars

_UNSET = object()


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
    angledX: bool | None = None,
    steps: int = 200,
    yTitle: str | None = _UNSET,
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
    steps:
        Number of y grid points used for KDE estimation (per group).

    Examples
    --------
    ::

        ds.theme(chartWidth=250)
        chart = ds.mark_violin(df, "group", "value", CATEGORIES)
        ds.save(chart, "violin")

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
    step = chart_width / (len(categories) + 2 * band_padding)
    band_center = step * (0.5 - band_padding)

    violin_rows = []
    for group in categories:
        vals = df.filter(pl.col(xCol) == group)[yCol].to_numpy()
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
            y=alt.Y("__y:Q", title=yCol if yTitle is _UNSET else yTitle),
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
            x=alt.X(f"{xCol}:N", sort=categories),
            y=alt.Y(f"{yCol}:Q", title=yCol if yTitle is _UNSET else yTitle),
        )
    )

    return alt.layer(violin, boxplot)


def mark_strip(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    categories: list[str],
    *,
    scatter: str = "jitter",
    palette: list[str] | None = None,
    pointSize: int | None = None,
    pointOpacity: float | None = None,
    spread: float | None = None,
    legend: bool = False,
    errorbars: bool = True,
    errorbarExtent: str = "sem",
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
    pointSize:
        Size of individual points. Inherits ``markSize`` from theme when ``None``.
    pointOpacity:
        Opacity of individual points.
    spread:
        Controls point spread in pixels. For ``'jitter'``: standard deviation
        of the Gaussian offsets (~68% of points within ±spread). For
        ``'beeswarm'``: collision radius (points placed so no two centres are
        closer than 2·spread); total width grows with n.
    errorbars:
        Whether to show error bars around the group mean. When ``True``,
        the mean is shown as a tick with error bars. When ``False``, the
        median is shown instead.
    errorbarExtent:
        Statistic to use for error bars: ``'sem'`` (standard error of the
        mean, default) or ``'sd'`` (standard deviation).

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
    if pointSize is None:
        pointSize = alt.theme.options.get("markSize", 10)
    if pointOpacity is None:
        pointOpacity = alt.theme.options.get("markFillOpacity", 1.0)

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
    max_offset = float(df[offset_col].abs().max())
    offset_scale = alt.Scale(
        domain=[-max_offset, max_offset],
        range=[band_center - max_offset, band_center + max_offset],
    )

    x = alt.X(f"{xCol}:N", sort=categories, title=None)

    points = (
        alt.Chart(df)
        .mark_circle(size=pointSize, opacity=pointOpacity)
        .encode(
            x=x,
            y=alt.Y(f"{yCol}:Q", title=yCol),
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
            y=alt.Y(f"{yCol}:Q", title=yCol),
        )
    )

    if not errorbars:
        return alt.layer(points, median)

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
            y=alt.Y("__mean:Q", title=yCol),
            yError=alt.YError("__error:Q"),
        )
    )

    return alt.layer(points, errorbar_layer, median)


def add_shade(
    categories: list[str] | None = None,
    xCol: str | None = None,
    *,
    positions: list[tuple] | None = None,
    axis: str = 'x',
    palette: list[str] | None = None,
    repeat: int = 1,
    opacity: float = 1.0,
    stroke: bool = False,
    strokeWidth: float | None = None,
    strokeDash: list[float] | bool | None = None,
    flush: bool | None = None,
) -> alt.LayerChart:
    """
    Build a background shading layer as filled ``mark_rect`` bands.

    Two modes, selected by which parameters are provided:

    **Band mode** (``categories`` provided, ``positions`` omitted): shades every
    band on the x-axis, cycling colors through ``palette`` with ``repeat``
    consecutive ticks per color. Consecutive same-color categories are merged
    into a single wider rect to eliminate sub-pixel antialiasing seams in PNG
    output. Always operates on ``axis='x'``.

    **Positions mode** (``positions`` provided): shades explicit coordinate
    ranges given as ``(start, end)`` tuples, one rect per tuple. Colors cycle
    across positions (``palette[i % len(palette)]``).

    - *String tuples* — category names on a nominal axis. Requires
      ``categories`` for index lookup. Uses pixel coordinates via
      ``alt.value`` so it does not interfere with the main chart's scale.
      Supports ``axis='x'``, ``'y'``, and ``'both'``.
    - *Numeric tuples* — data-space coordinates on a quantitative axis.
      Uses ``x:Q``/``x2:Q`` or ``y:Q``/``y2:Q`` encoding, which
      auto-shares the scale with the main chart's matching channel.
      Supports ``axis='x'``, ``'y'``, and ``'both'``.

    With ``axis='both'`` each position is a nested pair
    ``((x_start, x_end), (y_start, y_end))``. The two halves are resolved
    independently so mixed types work (e.g. a nominal x-range combined with
    a quantitative y-range).

    In both modes, compose behind the main chart with ``+``::

        # band mode
        shade = ds.add_shade(CATEGORIES, "group")
        chart = shade + main_chart

        # positions mode — shade two category spans on x
        shade = ds.add_shade(
            positions=[("Control", "Drug B"), ("Drug D", "Drug E")],
            categories=CATEGORIES,
        )

        # positions mode — reference band on y (quantitative)
        shade = ds.add_shade(
            positions=[(5.0, 10.0)], axis='y', palette=["#E8F4F8"]
        )

        # positions mode — intersection rect, nominal x + quantitative y
        shade = ds.add_shade(
            positions=[(("Control", "Drug B"), (8.0, 12.0))],
            axis='both',
            categories=CATEGORIES,
        )

    Parameters
    ----------
    categories:
        Ordered list of axis categories. Required for band mode. Also
        required in positions mode when any tuple values are strings.
    xCol:
        Column name for the x-axis grouping variable (band mode only;
        not used internally).
    positions:
        List of ``(start, end)`` tuples (single-axis) or
        ``((x_start, x_end), (y_start, y_end))`` tuples (``axis='both'``)
        defining explicit shade regions. Activates positions mode;
        ``repeat`` and ``flush`` are used only when tuple values are strings.
    axis:
        ``'x'`` (default), ``'y'``, or ``'both'``. Controls which axis the
        shading runs along. ``'both'`` draws intersection rects spanning an
        explicit x-range and y-range simultaneously. Ignored in band mode
        (always ``'x'``).
    palette:
        List of hex color strings to cycle through. Defaults to the first
        two stops of the ``"greys"`` palette.
    repeat:
        Number of consecutive ticks sharing the same color before
        advancing (band mode only). Defaults to ``1``.
    opacity:
        Fill opacity of the shade rects. Defaults to ``1.0``.
    stroke:
        Enable a border on the shade rects. ``False`` (default) → no stroke.
        ``True`` → axis-style stroke: color from theme darkmode state
        (black / white), width from ``axisWidth``.
    strokeWidth:
        Explicit border width in pixels. Overrides ``axisWidth`` when
        ``stroke=True``. Has no effect when ``stroke=False``.
    strokeDash:
        Dash pattern for the rect border. ``None`` (default) → solid.
        ``True`` → inherit ``dashedWidth`` from the active theme.
        A list (e.g. ``[4, 2]``) → use that pattern directly.
    flush:
        Extend the outermost rects to the axis domain edge (band mode and
        string positions only). ``None`` inherits from the theme's
        ``closed`` setting.
    """
    if palette is None:
        from .palettes import colors as _colors
        palette = _colors["greys"][:2]

    n_colors = len(palette)
    resolved_dash = (
        alt.theme.options.get("dashedWidth", [2, 2]) if strokeDash is True else strokeDash
    )
    resolved_stroke_width = (
        strokeWidth if strokeWidth is not None
        else alt.theme.options.get("axisWidth", 0.25)
    ) if stroke else 0
    axis_stroke_color = "white" if alt.theme.options.get("darkmode", False) else "black"
    mark_kwargs: dict = {
        "opacity": opacity,
        "stroke": axis_stroke_color if stroke else None,
        "strokeWidth": resolved_stroke_width,
        "strokeOpacity": 1 if stroke else 0,
    }
    if resolved_dash is not None:
        mark_kwargs["strokeDash"] = resolved_dash

    dummy_df = pl.DataFrame({"__dummy": [0]})

    # ── positions mode ────────────────────────────────────────────────────────
    if positions is not None:
        layers: list[alt.Chart] = []

        if axis == 'both':
            # Nested tuples: ((x_start, x_end), (y_start, y_end)).
            # Each half is resolved independently — string → pixel value via
            # band scale; numeric → Q field that shares the main chart's scale.
            band_padding = alt.theme.options.get("bandPadding", 0.1)
            chart_width = alt.theme.options.get("chartWidth", 100)
            chart_height = alt.theme.options.get("chartHeight", 100)
            n = len(categories) if categories else 0
            cat_index = {cat: i for i, cat in enumerate(categories)} if categories else {}
            x_step = chart_width / (n + 2 * band_padding) if n else None
            y_step = chart_height / (n + 2 * band_padding) if n else None
            if flush is None:
                flush = alt.theme.options.get("closed", False)

            for k, (x_range, y_range) in enumerate(positions):
                x_start, x_end = x_range
                y_start, y_end = y_range
                color = palette[k % n_colors]
                enc: dict = {}
                data_fields: dict = {}

                if isinstance(x_start, str):
                    if categories is None:
                        raise ValueError(
                            "categories is required when positions contains string x-ranges."
                        )
                    si, ei = cat_index[x_start], cat_index[x_end]
                    lo = 0 if (flush and si == 0) else x_step * (band_padding + si)
                    hi = (
                        chart_width if (flush and ei == n - 1)
                        else x_step * (band_padding + ei + 1)
                    )
                    enc["x"] = alt.value(lo)
                    enc["x2"] = alt.value(hi)
                else:
                    data_fields["__x_start"] = [float(x_start)]
                    data_fields["__x_end"] = [float(x_end)]
                    enc["x"] = alt.X("__x_start:Q")
                    enc["x2"] = alt.X2("__x_end:Q")

                if isinstance(y_start, str):
                    if categories is None:
                        raise ValueError(
                            "categories is required when positions contains string y-ranges."
                        )
                    si, ei = cat_index[y_start], cat_index[y_end]
                    lo = 0 if (flush and si == 0) else y_step * (band_padding + si)
                    hi = (
                        chart_height if (flush and ei == n - 1)
                        else y_step * (band_padding + ei + 1)
                    )
                    enc["y"] = alt.value(lo)
                    enc["y2"] = alt.value(hi)
                else:
                    data_fields["__y_start"] = [float(y_start)]
                    data_fields["__y_end"] = [float(y_end)]
                    enc["y"] = alt.Y("__y_start:Q")
                    enc["y2"] = alt.Y2("__y_end:Q")

                df = pl.DataFrame(data_fields) if data_fields else dummy_df
                layers.append(
                    alt.Chart(df).mark_rect(**mark_kwargs, color=color).encode(**enc)
                )

        elif len(positions) > 0 and isinstance(positions[0][0], str):
            # String tuples: category names on a nominal axis.
            # Convert to pixel coordinates using the band scale formula so the
            # shade layer does not participate in scale merging.
            if categories is None:
                raise ValueError(
                    "categories is required when positions contains string tuples."
                )
            band_padding = alt.theme.options.get("bandPadding", 0.1)
            n = len(categories)
            span = (
                alt.theme.options.get("chartHeight", 100)
                if axis == 'y'
                else alt.theme.options.get("chartWidth", 100)
            )
            step = span / (n + 2 * band_padding)
            cat_index = {cat: i for i, cat in enumerate(categories)}

            if flush is None:
                flush = alt.theme.options.get("closed", False)

            for k, (start, end) in enumerate(positions):
                si, ei = cat_index[start], cat_index[end]
                lo = 0 if (flush and si == 0) else step * (band_padding + si)
                hi = span if (flush and ei == n - 1) else step * (band_padding + ei + 1)
                color = palette[k % n_colors]
                enc = (
                    {"y": alt.value(lo), "y2": alt.value(hi)}
                    if axis == 'y'
                    else {"x": alt.value(lo), "x2": alt.value(hi)}
                )
                layers.append(
                    alt.Chart(dummy_df).mark_rect(**mark_kwargs, color=color).encode(**enc)
                )

        else:
            # Numeric tuples: data-space coordinates on a quantitative axis.
            # Encode as Q fields so the shade shares the main chart's scale.
            for k, (start, end) in enumerate(positions):
                color = palette[k % n_colors]
                pos_df = pl.DataFrame({"__start": [float(start)], "__end": [float(end)]})
                if axis == 'y':
                    chart = (
                        alt.Chart(pos_df)
                        .mark_rect(**mark_kwargs, color=color)
                        .encode(y=alt.Y("__start:Q"), y2=alt.Y2("__end:Q"))
                    )
                else:
                    chart = (
                        alt.Chart(pos_df)
                        .mark_rect(**mark_kwargs, color=color)
                        .encode(x=alt.X("__start:Q"), x2=alt.X2("__end:Q"))
                    )
                layers.append(chart)

        return alt.layer(*layers)

    # ── band mode ─────────────────────────────────────────────────────────────
    if categories is None:
        raise ValueError(
            "categories is required for band mode. "
            "Pass positions= to shade explicit coordinate ranges instead."
        )

    n = len(categories)
    color_map = [palette[(i // repeat) % n_colors] for i in range(n)]

    band_padding = alt.theme.options.get("bandPadding", 0.1)
    chart_width = alt.theme.options.get("chartWidth", 100)
    # step = range / (n + 2*bandPadding); band i spans [step*(bandPadding+i), step*(bandPadding+i+1)].
    step = chart_width / (n + 2 * band_padding)

    if flush is None:
        flush = alt.theme.options.get("closed", False)

    # Merge consecutive same-color categories so there is no coincident edge
    # between two rects of the same fill — that edge would show as a faint seam
    # in rasterized PNG output regardless of opacity.
    run_layers: list[alt.Chart] = []
    i = 0
    while i < n:
        j = i
        while j < n and color_map[j] == color_map[i]:
            j += 1
        left = 0 if (flush and i == 0) else step * (band_padding + i)
        right = chart_width if (flush and j == n) else step * (band_padding + j)
        run_layers.append(
            alt.Chart(dummy_df)
            .mark_rect(**mark_kwargs, color=color_map[i])
            .encode(x=alt.value(left), x2=alt.value(right))
        )
        i = j

    return alt.layer(*run_layers)


def _multilabel_layer(
    groups: dict[str, list],
    categories: list[str],
    *,
    order: list[str] | None = None,
    style: str = "plusminus",
    rowStyles: dict[str, str] | list[str] | None = None,
    labelAlign: str = "left",
    labelPadding: int = 0,
    symbol: str = "circle",
    symbolSize: int | None = None,
    palette: list[str] | None = None,
    strokeWidth: float | None = None,
    connectingLine: bool = True,
    orientation: str = "vertical",
    yPadding: float | None = None,
    chartWidth: int | None = None,
    fontSize: int | None = None,
    rowHeight: int | float | None = None,
    categoryLabel: bool = False,
    categoryLabelPosition: str = "bottom",
    categoryLabelAngle: int = -45,
    categoryLabelHeight: int | None = None,
) -> alt.LayerChart:
    """
    Build a condition-table annotation chart to place below a strip/violin/boxplot.

    Each key in ``groups`` is a row label; its value is a list of booleans (or
    arbitrary strings/numbers), one per category. Combine with the main chart using
    ``alt.vconcat(chart, _multilabel_layer(...)).resolve_scale(x="shared")``.

    Parameters
    ----------
    groups:
        Mapping of row-label → list of values, one per category. Values may be:

        - **bool** — ``True`` renders a positive mark; ``False`` renders a negative
          mark. The ``style`` parameter controls how positive/negative are displayed
          (``"plusminus"`` or ``"dots"``).
        - **str, int, or float** — any non-bool value triggers automatic ``style="text"``
          regardless of the ``style`` parameter, and each value is rendered verbatim as
          a string.

        Length of each list must equal ``len(categories)``.
    categories:
        Ordered list of x-axis categories — the same list passed to ``mark_strip``
        or ``mark_violin``.
    order:
        Row display order (top to bottom). Defaults to ``dict`` insertion order.
    style:
        Global default style for all rows. ``"plusminus"`` renders ``True`` as ``+``
        and ``False`` as ``−``. ``"symbol"`` renders ``True`` as a filled mark and
        ``False`` as an unfilled mark, with a connecting rule between consecutive
        ``True`` values (direction set by ``orientation``). The mark shape is
        controlled by ``symbol``. ``"text"`` renders raw group values as
        center-aligned strings and is forced automatically per row when any value in
        that row is non-bool. Override per row with ``rowStyles``.
    rowStyles:
        Per-row style overrides. Accepts either a ``dict`` mapping row labels to
        style strings (``{"Row A": "symbol", "Row B": "text"}``) or a ``list`` of
        style strings in row-display order (``["symbol", "text"]``). Accepts the
        same values as ``style``. Non-bool rows always render as ``"text"``
        regardless of this setting. Connecting rules only span between ``"symbol"``
        rows; rows of other styles between symbol rows are skipped in run detection.
    labelAlign:
        ``"left"`` (default) places row labels to the left of the grid with
        right-aligned text. ``"right"`` places them to the right with left-aligned text.
    labelPadding:
        Gap in pixels between the plot boundary and the label text. Vega-Lite's
        default is 2. Negative values pull the labels into the plot area.
    symbol:
        Vega-Lite shape name for ``"symbol"`` style marks (e.g. ``"circle"``,
        ``"square"``, ``"diamond"``, ``"triangle-up"``). Defaults to ``"circle"``.
    symbolSize:
        Area (in square pixels) of each symbol. Defaults to ``markSize * 4``
        from ``ds.theme()``.
    palette:
        List of colors used to fill annotation marks in ``"symbol"`` style.
        ``palette[0]`` overrides the ``False`` mark color and ``palette[-1]`` the
        ``True`` mark color. Overrides darkmode defaults when provided. Pass the
        result of ``ds.palette()`` directly.
    strokeWidth:
        Stroke width applied to dot marks and the connecting rule. Defaults
        to ``markStrokeWidth`` from ``ds.theme()``.
    connectingLine:
        When ``True`` (default), draws a rule spanning each consecutive run of
        ``True`` values (``"symbol"`` style only). Set to ``False`` to show
        symbols only. Direction is controlled by ``orientation``.
    orientation:
        Direction of the connecting rule. ``"vertical"`` (default) draws a rule
        down each column spanning consecutive ``True`` rows. ``"horizontal"``
        draws a rule across each row spanning consecutive ``True`` columns.
    yPadding:
        Inner padding between rows as a fraction of the band step (0–1).
        ``0`` means no gap; ``1`` means bands collapse to zero width.
        Defaults to Vega-Lite's band scale default of ``0.1``.
    chartWidth:
        Width of the annotation chart in pixels. Inherits ``chartWidth`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size for ``"text"`` style symbols and row labels. Inherits ``fontSize``
        from ``ds.theme()`` when not set.
    rowHeight:
        Height in pixels per annotation row. Defaults to ``fontSize * 1.5``.
    categoryLabel:
        When ``True``, renders the x-axis category names as angled text in a
        dedicated row, replacing the main chart's stripped axis labels within the
        annotation. Defaults to ``False``.
    categoryLabelPosition:
        Where to place the category label row relative to the data rows.
        ``"bottom"`` (default) places labels below all rows; ``"top"`` places
        them above.
    categoryLabelAngle:
        Rotation angle of the category name text in degrees. Defaults to ``-45``.
    categoryLabelHeight:
        Height in pixels reserved for the x-label row. Auto-computed from
        ``fontSize``, ``categoryLabelAngle``, and the longest category name when ``None``
        (default): ``ceil(fontSize × 0.6 × max_len × |sin(angle)| + fontSize ×
        |cos(angle)|)``.

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

    **Darkmode symbol colours** (``positive_color``, ``negative_fill``, ``negative_stroke``)
    are resolved from ``alt.theme.options`` at call time. When using ``style="symbol"``
    with ``ds.save()``, pass a callable so the chart is rebuilt after each darkmode
    toggle::

        ds.save(
            lambda: ds.add_multilabel(chart, groups, style="symbol", ...),
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
        ds.theme(chartWidth=300)
        chart = ds.mark_strip(df, "group", "value", CATEGORIES)
        ann = ds._multilabel_layer(
            {
                "Group A":         [False, True,  True,  True],
                "Group B":        [False, False, True,  False],
                "Group C": [False, False, False, True],
            },
            categories=CATEGORIES,
            style="symbol",
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

    if style not in ("plusminus", "text", "symbol"):
        raise ValueError(f"style must be 'plusminus', 'text', or 'symbol', got {style!r}")
    if labelAlign not in ("left", "right"):
        raise ValueError(f"labelAlign must be 'left' or 'right', got {labelAlign!r}")
    if orientation not in ("vertical", "horizontal"):
        raise ValueError(f"orientation must be 'vertical' or 'horizontal', got {orientation!r}")

    # Normalise rowStyles to a dict so the rest of the code has a single code path.
    if isinstance(rowStyles, list):
        if len(rowStyles) != len(row_order):
            raise ValueError(
                f"rowStyles list has {len(rowStyles)} entries but there are {len(row_order)} rows."
            )
        rowStyles = dict(zip(row_order, rowStyles))

    # Per-row style resolution: rowStyles overrides global style; non-bool values always
    # force "text" regardless. Check isinstance(v, bool) before isinstance(v, int) because
    # bool subclasses int.
    def _row_style(label: str) -> str:
        s = (rowStyles or {}).get(label, style)
        if s not in ("plusminus", "text", "symbol"):
            raise ValueError(
                f"rowStyles[{label!r}] must be 'plusminus', 'text', or 'symbol', got {s!r}"
            )
        if any(not isinstance(v, bool) for v in groups[label]):
            return "text"
        return s

    row_styles = {label: _row_style(label) for label in row_order}
    plusminus_rows = [l for l in row_order if row_styles[l] == "plusminus"]
    text_rows = [l for l in row_order if row_styles[l] == "text"]
    symbol_rows = [l for l in row_order if row_styles[l] == "symbol"]

    if chartWidth is None:
        chartWidth = alt.theme.options.get("chartWidth", 100)
    if fontSize is None:
        fontSize = alt.theme.options.get("fontSize", 7)
    if rowHeight is None:
        rowHeight = 10

    band_range = None
    label_y = 0.0
    if categoryLabel:
        if categoryLabelPosition not in ("top", "bottom"):
            raise ValueError(
                f"categoryLabelPosition={categoryLabelPosition!r} is invalid."
                " Use 'top' or 'bottom'."
            )
        max_len = max(len(cat) for cat in categories)
        angle_rad = abs(math.radians(categoryLabelAngle))
        tight_height = (
            fontSize * 0.6 * max_len * math.sin(angle_rad)
            + fontSize * math.cos(angle_rad)
        )
        if categoryLabelHeight is None:
            categoryLabelHeight = math.ceil(tight_height)
        k = 0 if categoryLabelPosition == "top" else len(row_order)
        # Upward extent from anchor for align="right", baseline="middle":
        # min y' = -H/2 * |cos(angle)|. Offset label_y down by this amount so
        # the text stays within the label row and doesn't clip above y=0.
        label_y_offset = fontSize / 2 * abs(math.cos(math.radians(categoryLabelAngle)))
        # Extra space beyond the tight-fit height; for the bottom case this
        # shifts the anchor into the label row so the gap is on the data side.
        extra = max(0.0, categoryLabelHeight - tight_height)
        if k == 0:
            band_range = [categoryLabelHeight, len(row_order) * rowHeight + categoryLabelHeight]
            label_y = label_y_offset
        else:
            band_range = [0, len(row_order) * rowHeight]
            label_y = len(row_order) * rowHeight + label_y_offset + extra

    def _norm(v: object) -> str:
        if isinstance(v, bool):
            return "+" if v else "-"
        return str(v)

    rows = [
        {"__label": label, "__category": cat, "__value": _norm(val)}
        for label in row_order
        for cat, val in zip(categories, groups[label])
    ]
    marks_df = pl.DataFrame(rows)

    chart_h = len(row_order) * rowHeight + (categoryLabelHeight if categoryLabel else 0)

    x_enc = alt.X(
        "__category:N",
        sort=categories,
        axis=alt.Axis(labels=False, ticks=False, domain=False, title=None),
    )
    y_scale = alt.Scale(
        domain=row_order,
        **({"range": band_range} if band_range is not None else {}),
        **({"paddingInner": yPadding} if yPadding is not None else {}),
    )
    # Axis suppressed; row labels are explicit mark_text in row_labels layer below.
    # bandPosition=0.5 is explicit because per-mark defaults vary across mark types.
    y_enc = alt.Y(
        "__label:N",
        sort=row_order,
        bandPosition=0.5,
        scale=y_scale,
        axis=alt.Axis(labels=False, ticks=False, domain=False, title=None),
    )

    if labelAlign == "right":
        label_x = alt.value(chartWidth + labelPadding)
    else:
        label_x = alt.value(-labelPadding)
    label_text_align = "left" if labelAlign == "right" else "right"
    label_df = pl.DataFrame({"__label": row_order})
    row_labels = (
        alt.Chart(label_df)
        .mark_text(fontSize=fontSize, align=label_text_align, baseline="middle")
        .encode(x=label_x, y=y_enc, text=alt.Text("__label:N"))
    )

    layers: list = [row_labels]

    # --- plusminus rows ---
    if plusminus_rows:
        pm_df = marks_df.filter(pl.col("__label").is_in(plusminus_rows)).with_columns(
            pl.col("__value").replace({"-": "−"})
        )
        # align="center" is required — without it Vega-Lite's vertical band
        # placement drifts relative to other marks on some versions.
        layers.append(
            alt.Chart(pm_df)
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, text=alt.Text("__value:N"))
        )

    # --- text rows ---
    if text_rows:
        text_df = marks_df.filter(pl.col("__label").is_in(text_rows))
        layers.append(
            alt.Chart(text_df)
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, text=alt.Text("__value:N"))
        )

    # --- symbol rows ---
    if symbol_rows:
        # Colours are resolved at call time from alt.theme.options so that darkmode
        # variants are correct. Use a callable with ds.save() to rebuild per variant.
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

        if symbolSize is None:
            symbolSize = alt.theme.options.get("markSize", 10) * 4
        if strokeWidth is None:
            strokeWidth = alt.theme.options.get("markStrokeWidth", 0.25)

        plus_df = marks_df.filter(pl.col("__label").is_in(symbol_rows) & (pl.col("__value") == "+"))
        minus_df = marks_df.filter(
            pl.col("__label").is_in(symbol_rows) & (pl.col("__value") == "-")
        )

        symbol_dy = -fontSize * 0.1

        positive = (
            alt.Chart(plus_df)
            .mark_point(
                shape=symbol,
                filled=True,
                color=positive_color,
                strokeWidth=strokeWidth,
                size=symbolSize,
                dy=symbol_dy,
            )
            .encode(x=x_enc, y=y_enc)
        )
        negative = (
            alt.Chart(minus_df)
            .mark_point(
                shape=symbol,
                filled=True,
                fill=negative_fill,
                stroke=negative_stroke,
                strokeWidth=strokeWidth,
                size=symbolSize,
                dy=symbol_dy,
            )
            .encode(x=x_enc, y=y_enc)
        )

        # Connecting lines only span between symbol rows; non-symbol rows between
        # two symbol rows are skipped in run detection (they don't break runs).
        symbol_row_set = set(symbol_rows)
        line_rows = []
        if orientation == "horizontal":
            for label in row_order:
                if label not in symbol_row_set:
                    continue
                run: list[int] = []
                for i, v in enumerate(groups[label]):
                    if v is True:
                        run.append(i)
                    else:
                        if len(run) >= 2:
                            line_rows.append(
                                {
                                    "__label": label,
                                    "__x_start": categories[run[0]],
                                    "__x_end": categories[run[-1]],
                                }
                            )
                        run = []
                if len(run) >= 2:
                    line_rows.append(
                        {
                            "__label": label,
                            "__x_start": categories[run[0]],
                            "__x_end": categories[run[-1]],
                        }
                    )
        else:  # vertical
            # Emit two rows per segment (start + end) so mark_line can connect them
            # using only __label — avoiding a second ordinal field on the shared y
            # scale, which would corrupt paddingInner and shift row spacing.
            for i, cat in enumerate(categories):
                run = []
                for j, label in enumerate(row_order):
                    if label not in symbol_row_set:
                        continue
                    if groups[label][i] is True:
                        run.append(j)
                    else:
                        if len(run) >= 2:
                            _id = f"{cat}_{run[0]}_{run[-1]}"
                            line_rows.append({"__category": cat, "__label": row_order[run[0]], "__line_id": _id})
                            line_rows.append({"__category": cat, "__label": row_order[run[-1]], "__line_id": _id})
                        run = []
                if len(run) >= 2:
                    _id = f"{cat}_{run[0]}_{run[-1]}"
                    line_rows.append({"__category": cat, "__label": row_order[run[0]], "__line_id": _id})
                    line_rows.append({"__category": cat, "__label": row_order[run[-1]], "__line_id": _id})

        if connectingLine and line_rows:
            lines_df = pl.DataFrame(line_rows)
            if orientation == "horizontal":
                lines = (
                    alt.Chart(lines_df)
                    # strokeDash=[0, 0] overrides the theme's dashedRule=True default.
                    .mark_rule(strokeWidth=strokeWidth, strokeDash=[0, 0])
                    .encode(
                        x=alt.X("__x_start:N", sort=categories),
                        x2="__x_end:N",
                        y=y_enc,
                    )
                )
            else:  # vertical
                lines = (
                    alt.Chart(lines_df)
                    .mark_line(strokeWidth=strokeWidth, strokeDash=[0, 0])
                    .encode(
                        x=x_enc,
                        y=y_enc,
                        detail="__line_id:N",
                    )
                )
            layers.extend([lines, negative, positive])
        else:
            layers.extend([negative, positive])

    if categoryLabel:
        label_df = pl.DataFrame({"__category": categories})
        layers.append(
            alt.Chart(label_df)
            .mark_text(
                fontSize=fontSize,
                angle=categoryLabelAngle % 360,
                align="center" if categoryLabelAngle % 360 == 0 else "right",
                baseline="middle",
            )
            .encode(x=x_enc, y=alt.value(label_y), text=alt.Text("__category:N"))
        )

    return alt.layer(*layers).properties(width=chartWidth, height=chart_h)


def add_multilabel(
    chart: alt.Chart,
    groups: dict[str, list] | None = None,
    categories: list[str] | None = None,
    *,
    spacing: int = 0,
    showSampleSize: bool = False,
    df=None,
    xCol: str | None = None,
    sampleSizeIndex: int = 0,
    sampleSizeLabel: str = "n =",
    **kwargs,
) -> alt.VConcatChart:
    """
    Compose a chart with a grid annotation table, replacing its x-axis labels.

    Strips x-axis labels and ticks from ``chart``, builds a condition table via
    :func:`_multilabel_layer`, and returns
    ``alt.vconcat(chart, annotation, spacing=spacing).resolve_scale(x="shared")``.

    Both ``groups`` and ``categories`` are optional. Omit ``groups`` (or pass
    ``{}``) when you only need sample sizes or category labels.

    All keyword arguments beyond the named parameters are forwarded to
    :func:`_multilabel_layer` — see its docstring for the full parameter list,
    including ``style``, ``rowStyles``, ``categoryLabel``,
    ``categoryLabelPosition``, ``categoryLabelAngle``, and ``categoryLabelHeight``.

    Parameters
    ----------
    chart:
        The main Altair chart (any type: ``Chart``, ``LayerChart``, etc.).
    groups:
        ``{row_label: [value, ...]}`` mapping, one value per category. Defaults
        to ``{}`` — omit entirely when only ``showSampleSize`` or
        ``categoryLabel`` is needed.
    categories:
        Ordered list of x-axis categories matching the main chart. Defaults to
        ``None`` (empty list); must be provided when ``showSampleSize=True`` or
        when ``categoryLabel=True``.
    spacing:
        Vertical gap in pixels between the chart and the annotation table.
        Defaults to ``0`` so the annotation sits flush below the axis line.
    showSampleSize:
        When ``True``, injects a per-category sample size row computed from
        ``df``. Requires ``df`` and ``xCol``. The row always renders as
        ``"text"`` regardless of the global ``style`` setting.
    df:
        Source DataFrame (Polars or Pandas) for counting samples per category.
        Only used when ``showSampleSize=True``.
    xCol:
        Column name in ``df`` used for x-axis grouping.
        Only used when ``showSampleSize=True``.
    sampleSizeIndex:
        Insertion index among the ``groups`` rows, using ``list.insert()``
        semantics. ``0`` (default) places the n-row first; ``len(groups)``
        places it last. Negative indices follow Python convention (``-1`` is
        second-to-last, not last).
    sampleSizeLabel:
        Row label for the sample size row. Defaults to ``"n ="``.

    Examples
    --------
    ::

        chart = ds.mark_strip(df, "group", "value", CATEGORIES)

        # Full multilabel with sample sizes and category labels
        composed = ds.add_multilabel(
            chart,
            {"Condition A": [False, True, True, True]},
            categories=CATEGORIES,
            style="symbol",
            showSampleSize=True,
            df=df,
            xCol="group",
            categoryLabel=True,
        )
        ds.save(composed, "my_plot")

        # Sample sizes only — no groups needed
        ds.add_multilabel(chart, categories=CATEGORIES, showSampleSize=True, df=df, xCol="group")
    """
    import copy

    if groups is None:
        groups = {}
    if categories is None:
        categories = []

    if showSampleSize:
        if df is None or xCol is None:
            raise ValueError("showSampleSize=True requires both 'df' and 'xCol'.")
        counts = count_n(df, xCol, categories)
        # Normalize rowStyles before modifying groups so that list indices
        # still correspond to the original row order.
        raw_styles = kwargs.pop("rowStyles", None)
        if isinstance(raw_styles, list):
            row_styles = dict(zip(groups.keys(), raw_styles))
        elif isinstance(raw_styles, dict):
            row_styles = dict(raw_styles)
        else:
            row_styles = {}
        # Explicitly force the n-row to text style regardless of the global
        # style setting (e.g. "symbol") — counts always render as plain text.
        row_styles[sampleSizeLabel] = "text"
        kwargs["rowStyles"] = row_styles
        items = list(groups.items())
        items.insert(sampleSizeIndex, (sampleSizeLabel, counts))
        groups = dict(items)

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
    ann = _multilabel_layer(groups, categories, **kwargs)
    return alt.vconcat(modified, ann, spacing=spacing).resolve_scale(x="shared")

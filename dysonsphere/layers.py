from typing import Any

import altair as alt
import numpy as np
import polars as pl

from .transforms import add_beeswarm, add_jitter
from .utils import ensure_polars

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
    categories: list[str],
    xCol: str,
    *,
    palette: list[str] | None = None,
    repeat: int = 2,
    opacity: float = 1.0,
    strokeWidth: float = 0,
    flush: bool | None = None,
) -> alt.LayerChart:
    """
    Build a background shading layer with one ``mark_rect`` band per x-tick.

    Each rect spans the full chart height. Bands are flush with one another
    (no inter-band gap). Colors cycle through ``palette``, using each color for
    ``repeat`` consecutive ticks before advancing to the next.

    Consecutive categories that share the same color are merged into a single
    wider rect. This eliminates sub-pixel antialiasing seams that would
    otherwise appear between same-color adjacent rects in PNG output. Rect
    positions are computed as literal pixel values (``alt.value``) so the
    shade layer does not participate in x-scale merging with the main chart.

    Compose this layer behind a main chart with ``+``::

        shade = ds.add_shade(CATEGORIES, "group", palette=ds.palette("greys", n=2), repeat=2)
        chart = shade + main_chart

    Parameters
    ----------
    categories:
        Ordered list of x-axis categories — the same list passed to
        ``mark_strip`` or ``mark_violin``.
    xCol:
        Column name for the x-axis grouping variable, matching the field used
        in the main chart's x encoding.
    palette:
        List of hex color strings to cycle through. Defaults to the first
        two stops of the ``"greys"`` palette.
    repeat:
        Number of consecutive ticks that share the same palette color before
        advancing to the next color. Defaults to ``2``.
    opacity:
        Fill opacity of the shade rects. Defaults to ``1.0``.
    strokeWidth:
        Width of the rect border in pixels. Defaults to ``0`` (no stroke).
        When set, the stroke inherits the theme's ``markStroke`` color and
        is rendered fully opaque.
    flush:
        When ``True``, the first rect extends to ``x=0`` and the last rect
        extends to ``x=chartWidth``, making the shading flush with the axis
        domain line. When ``None`` (default), inherits from the theme's
        ``closed`` setting. When ``False``, the natural band outer-padding
        gap is preserved on both sides.
    """
    if palette is None:
        from .palettes import colors as _colors
        palette = _colors["greys"][:2]

    n = len(categories)
    n_colors = len(palette)
    color_map = [palette[(i // repeat) % n_colors] for i in range(n)]

    band_padding = alt.theme.options.get("bandPadding", 0.1)
    chart_width = alt.theme.options.get("chartWidth", 100)
    # Vega-Lite uses bandPadding as paddingOuter only for scale positioning;
    # bandPaddingInner only affects bar mark widths, not band boundaries.
    # step = range / (n + 2*bandPadding); band i spans [step*(bandPadding+i), step*(bandPadding+i+1)].
    step = chart_width / (n + 2 * band_padding)

    if flush is None:
        flush = alt.theme.options.get("closed", False)

    mark_kwargs: dict = {
        "opacity": opacity,
        "strokeWidth": strokeWidth,
        "strokeOpacity": 0 if strokeWidth == 0 else 1,
    }
    if strokeWidth > 0:
        mark_kwargs["stroke"] = alt.theme.options.get("markStroke", "black")

    # Merge consecutive same-color categories so there is no coincident edge
    # between two rects of the same fill — that edge would show as a faint seam
    # in rasterized PNG output regardless of opacity.
    dummy_df = pl.DataFrame({"__dummy": [0]})
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


def add_multilabel_detached(
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
) -> alt.LayerChart:
    """
    Build a condition-table annotation chart to place below a strip/violin/boxplot.

    Each key in ``groups`` is a row label; its value is a list of booleans (or
    arbitrary strings/numbers), one per category. Combine with the main chart using
    ``alt.vconcat(chart, add_multilabel_detached(...)).resolve_scale(x="shared")``.

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
        ann = ds.add_multilabel_detached(
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

    chart_h = len(row_order) * rowHeight

    x_enc = alt.X(
        "__category:N",
        sort=categories,
        axis=alt.Axis(labels=False, ticks=False, domain=False, title=None),
    )
    y_scale = alt.Scale(
        domain=row_order,
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

    return alt.layer(*layers).properties(width=chartWidth, height=chart_h)


def add_multilabel(
    chart: alt.Chart,
    groups: dict[str, list],
    categories: list[str],
    *,
    spacing: int = 0,
    **kwargs,
) -> alt.VConcatChart:
    """
    Compose a chart with a grid annotation table, replacing its x-axis labels.

    Strips x-axis labels and ticks from ``chart``, builds a
    :func:`add_multilabel_detached` layer, and returns
    ``alt.vconcat(chart, annotation, spacing=spacing).resolve_scale(x="shared")``.

    All keyword arguments beyond ``spacing`` are forwarded to :func:`add_multilabel_detached`.

    Parameters
    ----------
    chart:
        The main Altair chart (any type: ``Chart``, ``LayerChart``, etc.).
    groups:
        Passed to :func:`add_multilabel_detached`.
    categories:
        Passed to :func:`add_multilabel_detached`.
    spacing:
        Vertical gap in pixels between the chart and the annotation table.
        Defaults to 0 so the annotation sits flush below the axis line.

    Examples
    --------
    ::

        chart = ds.mark_strip(df, "group", "value", CATEGORIES)
        composed = ds.add_multilabel(
            chart,
            {"Group A": [False, True, True, True], "Group B": [False, False, True, False]},
            categories=CATEGORIES,
            style="symbol",
            labelAlign="right",
        )
        ds.save(composed, "my_plot")
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
    ann = add_multilabel_detached(groups, categories, **kwargs)
    return alt.vconcat(modified, ann, spacing=spacing).resolve_scale(x="shared")

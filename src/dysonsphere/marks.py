import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, cast

import altair as alt
import numpy as np
import polars as pl

if TYPE_CHECKING:
    import pandas as pd

from ._statistics import _validate_observations
from .display_labels import label_expr
from .palettes import colors
from .theme import _opt
from .transforms import _fit_kde, _normalised_kde_density, beeswarm, jitter
from .utils import _band_geometry, _ensure_polars, _internal_data, _nice_domain, _validate_category_order

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["mark_violin", "mark_strip"]


class _UnsetType:
    pass


_UNSET: Final[_UnsetType] = _UnsetType()


@dataclass
class _MarkScaffold:
    """Shared chart chrome for the custom mark constructors (composition, NOT a base class).

    Owns everything every ``mark_*`` function repeats - dataframe coercion, the ``_UNSET``
    title sentinel resolution, the x-axis (label angle + ``labelMap`` -> ``labelExpr``),
    the x/y/color encodings with category sorting and palette handling - so a new shared
    parameter lands here once and every mark inherits it. The marks stay plain functions
    returning Altair objects (the composition algebra belongs to Altair); their bodies
    hold only the per-mark geometry and layers.
    """

    df: "pl.DataFrame | pd.DataFrame"
    xCol: str
    yCol: str
    categories: list[Any]
    palette: str | list[str] | None = None
    fill: str | None = None
    legend: bool = False
    xLabelAngle: float | None = None
    labelMap: Mapping[Any, str | list[str]] | None = None
    xTitle: str | list[str] | None | _UnsetType = _UNSET
    yTitle: str | list[str] | None | _UnsetType = _UNSET

    def __post_init__(self) -> None:
        self.df = _ensure_polars(self.df)
        for column in (self.xCol, self.yCol):
            if column not in self.df.columns:
                raise ValueError(f"mark data column {column!r} is not present in the data.")
        self.categories = _validate_category_order(self.df, self.xCol, self.categories)
        if self.fill is not None and (not isinstance(self.fill, str) or not self.fill.strip()):
            raise ValueError("fill must be a non-empty color string or None")
        if self.fill is not None and self.palette is not None:
            raise ValueError("fill and palette cannot both be non-None")
        if isinstance(self.palette, str):
            if self.palette not in colors:
                raise ValueError(f"unknown palette name {self.palette!r}; use fill=... for a fixed color")
            self.palette = colors[self.palette]
        if isinstance(self.palette, list):
            if not self.palette:
                raise ValueError("palette must be a non-empty list of color strings")
            if any(not isinstance(color, str) or not color.strip() for color in self.palette):
                raise ValueError("palette must be a non-empty list of non-empty color strings")
        elif self.palette is not None:
            raise ValueError("palette must be a palette name, a list of color strings, or None")
        if self.xLabelAngle is None:
            self.xLabelAngle = _opt("xLabelAngle")
        self.x_title: str | list[str] | None = self.xCol if isinstance(self.xTitle, _UnsetType) else self.xTitle
        self.y_title: str | list[str] | None = self.yCol if isinstance(self.yTitle, _UnsetType) else self.yTitle

    def x_axis(self) -> alt.Axis:
        """The x-axis: label rotation (align derived from the angle's sign) + label mapping."""
        kwargs: dict[str, Any] = {}
        angle = cast(float, self.xLabelAngle)
        if angle != 0:
            kwargs["labelAngle"] = angle % 360
            kwargs["labelAlign"] = "right" if angle < 0 else "left"
        if self.labelMap:
            kwargs["labelExpr"] = label_expr(self.labelMap)
        return alt.Axis(**kwargs)

    def x(self, *, padding_inner: float | None = None, padding_outer: float | None = None) -> alt.X:
        # Pin the DOMAIN (a literal list), not just sort=, so the category order survives
        # Vega-Lite's shared-scale domain union when marks are layered/concatenated - a `sort=`
        # order gets re-sorted (alphabetically) through a scale merge, whereas an explicit
        # literal domain wins the union. Same reason the multilabel y scale pins domain=row_order.
        scale_kwargs = {
            **({"paddingInner": padding_inner} if padding_inner is not None else {}),
            **({"paddingOuter": padding_outer} if padding_outer is not None else {}),
        }
        return alt.X(
            f"{self.xCol}:N",
            sort=self.categories,
            scale=alt.Scale(domain=self.categories, **scale_kwargs),
            title=self.x_title,
            axis=self.x_axis(),
        )

    def y(self, field: str | None = None) -> alt.Y:
        return alt.Y(field if field is not None else f"{self.yCol}:Q", title=self.y_title)

    def color(
        self,
        field: str | None = None,
        title: str | None | _UnsetType = _UNSET,
        symbolType: str | None = None,
    ) -> alt.Color:
        """Category colour encoding: palette resolution + legend flag + category sort.

        ``field`` defaults to the x column; ``title`` defaults to the x column when the
        legend is shown; ``symbolType`` picks the legend symbol.
        """
        if isinstance(title, _UnsetType):
            title = self.xCol if self.legend else None
        legend_kwargs: dict[str, Any] = {"symbolType": symbolType} if symbolType else {}
        pal = self.palette
        # Pin the domain (a literal list) so the category->colour mapping survives a shared-scale
        # merge when marks are layered/concatenated - see x(). Without it, `sort=` alone is
        # re-sorted alphabetically through the merge and colours stop matching their categories.
        range_kwargs: dict[str, Any] = {} if pal is None else {"range": pal}
        scale = alt.Scale(domain=self.categories, **range_kwargs)
        return alt.Color(
            field if field is not None else f"{self.xCol}:N",
            sort=self.categories,
            title=title,
            legend=alt.Legend(**legend_kwargs) if self.legend else None,
            scale=scale,
        )


def mark_violin(
    data: "pl.DataFrame | pd.DataFrame",
    x: str,
    y: str,
    categories: list[Any],
    *,
    inner: str | None = "quartiles",
    innerColor: str | None = None,
    boxplotWidth: float | None = None,
    boxplotColor: str = "black",
    boxplotMedianColor: str = "white",
    palette: str | list[str] | None = None,
    fill: str | None = None,
    fillOpacity: float | None = None,
    stroke: str | bool | None = True,
    strokeWidth: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    labelMap: Mapping[Any, str | list[str]] | None = None,
    steps: int = 200,
    trim: bool = False,
    bandwidth: float | None = None,
    yTitle: str | list[str] | None | _UnsetType = _UNSET,
    xTitle: str | list[str] | None | _UnsetType = _UNSET,
) -> alt.LayerChart:
    """
    Build an Altair layer combining a violin plot with an inner statistic display.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``ds.stats.comparisons``).

    The returned ``LayerChart`` is safe to place in ``alt.hconcat()`` alongside
    ``mark_strip()`` or any other chart - the violin uses absolute ``x:Q``
    coordinates internally rather than ``xOffset``, so Vega-Lite's xOffset
    scale resolution never squishes the violin shape.

    Parameters
    ----------
    data:
        Polars or pandas DataFrame containing the data.
    x:
        Column name for the grouping variable (x-axis).
    y:
        Column name for the value variable (y-axis).
    categories:
        Ordered list of all x-axis categories, used for positioning and axis labels. It must
        contain each observed value exactly once and no unobserved values. Tuple/list order and
        numeric category values are supported; pass an ordered sequence, not a raw string.
    inner:
        Inner statistic display: ``"quartiles"`` (default) draws Prism-style
        horizontal lines - a solid median (at twice the outline ``strokeWidth``,
        clipped to the violin border) and dashed quartiles (at the outline
        ``strokeWidth``) - each spanning the violin's width at that value;
        ``"median"`` draws only the median line; ``"box"`` embeds a boxplot;
        ``None`` draws the violin outline only.
    innerColor:
        Color of the median/quartile lines (``"quartiles"``/``"median"``).
        ``None`` (default) means ``"black"`` in both light and dark mode - the
        lines sit inside the mark fill, not on the background, so they are
        deliberately not darkmode-sensitive.
    boxplotWidth:
        Width of the boxplot box in pixels (``inner="box"`` only).
    boxplotColor:
        Fill color of the boxplot (``inner="box"`` only).
    boxplotMedianColor:
        Fill color of the boxplot median line (``inner="box"`` only). Defaults to
        ``"white"`` so it reads against the default black box; overrides the
        theme's ``markMedianFill``.
    palette:
        Named dysonsphere palette or explicit list of category colors. When ``None``, each
        group inherits its color from the theme's active category palette. Cannot be combined
        with ``fill``.
    fill:
        Fixed literal fill color for the violin silhouette. Suppresses the category-color
        legend when set and does not affect the inner statistic marks. Cannot be combined with
        ``palette``.
    fillOpacity:
        Fill opacity of the violin. Inherits ``markFillOpacity`` from theme
        when ``None``.
    stroke:
        Outline color of the violin. ``True`` (default) uses the theme's
        ``markStroke`` (black - kept black in dark mode too, outlining the light
        palette fills like ``mark_strip``'s points); ``False`` or ``None``
        disables the outline; a string sets the color directly.
    strokeWidth:
        Width of the violin outline. Inherits ``markStrokeWidth`` from theme
        when ``None``.
    xLabelAngle:
        X-axis label rotation in degrees. Negative tilts left (e.g. ``-45``),
        positive tilts right; ``labelAlign`` is derived automatically from the
        sign. ``None`` inherits from ``theme(xLabelAngle)``.
    labelMap:
        ``{raw_value: label}`` mapping applied to the x-axis tick labels at render
        time via :func:`label_expr` - the data keeps the raw values. A label may be
        a list of strings for a multi-line label. Unmapped values show as-is.
    steps:
        Number of y grid points used for KDE estimation (per group).
    trim:
        When ``True``, evaluate the KDE only on the group's data range so the
        violin ends sharply at the observed min/max. When ``False`` (default),
        the tails extend 2 KDE bandwidths beyond the data extremes.
    bandwidth:
        KDE bandwidth (``scipy.stats.gaussian_kde`` ``bw_method``). ``None``
        (default) uses Scott's rule; smaller values give a tighter, less
        smoothed outline.
    yTitle:
        Y-axis title. Defaults to ``y``. Pass ``None`` to suppress.
    xTitle:
        X-axis title. Defaults to ``x``. Pass ``None`` to suppress.

    Raises
    ------
    TypeError
        If ``data`` is not a Polars or pandas DataFrame.
    ValueError
        If a required column is missing, an observed group has no finite numeric values, or a
        group has fewer than two distinct observations or cannot produce a finite KDE.

    Examples
    --------
    ::

        ds.theme(width=250)
        chart = ds.mark_violin(data, "group", "value", CATEGORIES)
        ds.save(chart, "violin")

        # safe in hconcat with mark_strip
        left = ds.mark_strip(data, "group", "value", CATEGORIES)
        right = ds.mark_violin(data, "group", "value", CATEGORIES)
        ds.save(alt.hconcat(left, right), "comparison")

        # Prism-style look with sharp tips at the data extremes
        chart = ds.mark_violin(data, "group", "value", CATEGORIES, trim=True)

        # bare silhouette: remove the default outline
        chart = ds.mark_violin(data, "group", "value", CATEGORIES, stroke=None)

        # classic embedded boxplot with custom colors
        chart = ds.mark_violin(
            data, "group", "value", CATEGORIES,
            inner="box",
            boxplotWidth=10,
            fill="#AAAAAA",
        )
    """
    yCol = y
    if inner not in ("box", "quartiles", "median", None):
        raise ValueError(f"inner must be 'box', 'quartiles', 'median', or None, got {inner!r}")

    s = _MarkScaffold(
        data,
        x,
        yCol,
        categories,
        palette=palette,
        fill=fill,
        legend=legend,
        xLabelAngle=xLabelAngle,
        labelMap=labelMap,
        xTitle=xTitle,
        yTitle=yTitle,
    )
    data = s.df
    group_values: list[tuple[Any, np.ndarray]] = []
    for group in categories:
        group_data = data.filter(pl.col(x) == group)
        if group_data.is_empty():
            raise ValueError(f"violin KDE column {yCol!r} has no observations in group {group!r}.")
        values = _validate_observations(group_data[yCol].to_list(), yCol, group, kind="violin KDE column")
        if values.size < 2 or np.all(values == values[0]):
            raise ValueError(f"violin KDE column {yCol!r} has an unusable group {group!r}.")
        if not math.isfinite(float(values.max()) - float(values.min())):
            raise ValueError(f"violin KDE column {yCol!r} has an unrepresentable range in group {group!r}.")
        group_values.append((group, values))
    if fillOpacity is None:
        fillOpacity = _opt("markFillOpacity")
    if strokeWidth is None:
        strokeWidth = _opt("markStrokeWidth")
    if stroke is True:
        # The house mark outline: the theme's markStroke, kept black in darkmode
        # too - it outlines the light palette fills, like mark_strip's points.
        stroke = "black" if _opt("dark") else _opt("markStroke")
    elif stroke is False:
        stroke = None
    if innerColor is None:
        # Deliberately NOT darkmode-sensitive: the lines sit inside the mark fill,
        # not on the background, so black reads in both modes.
        innerColor = "black"
    mark_size = _opt("markSize")
    chart_width = _opt("width")  # x:Q domain of the violin layer
    # Vega-Lite routes "rect and other marks" - boxplot included - through rectPadding,
    # NOT barPadding (scale="rect"), and not the xOffset/mark_circle variant ("offset").
    geo = _band_geometry(len(categories), scale="rect")
    rect_padding = float(_opt("rectPadding"))
    outer_padding = float(_opt("outerPadding"))
    # Pin the nominal scaffold to the same rect-band geometry used for the absolute-pixel
    # silhouette. Explicit scale padding also prevents a later figure-wide bandPaddingInner
    # config from moving the scaffold or boxplot away from the already-constructed shape.
    violin_x = s.x(padding_inner=rect_padding, padding_outer=outer_padding)
    half_width = mark_size * 0.75

    # Precompute absolute x positions for each violin point so the violin
    # layer uses x:Q (not xOffset), avoiding Vega-Lite's shared xOffset
    # scale resolution that squishes the violin when hconcated with any
    # chart that also uses xOffset (e.g. mark_strip).
    violin_rows = []
    group_kde = []
    for i, (group, vals) in enumerate(group_values):
        x_center = geo.centers[i]
        kde, bw = _fit_kde(
            vals,
            bandwidth=bandwidth,
            column=yCol,
            group=group,
            kind="violin KDE column",
        )
        # KDE bandwidth in data units - the tail extension scales with it so the
        # untrimmed overshoot is proportionate on any data scale.
        if trim:
            y_min = float(vals.min())
            y_max = float(vals.max())
        else:
            y_min = float(vals.min()) - 2 * bw
            y_max = float(vals.max()) + 2 * bw
        y_grid = np.linspace(y_min, y_max, steps)
        if not np.all(np.isfinite(y_grid)):
            raise ValueError(f"violin KDE column {yCol!r} produced a non-finite grid in group {group!r}.")
        density_norm = _normalised_kde_density(
            kde,
            y_grid,
            column=yCol,
            group=group,
            kind="violin KDE column",
        )
        group_kde.append((group, x_center, vals, y_grid, density_norm))

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
        # Close the outline: repeat the first point so the bottom edge gets a stroked
        # cap like the top (where the two sides already meet). Matters under trim=True,
        # where the end density is far from zero and the gap is visible.
        violin_rows.append(
            {
                "__group": group,
                "__y": float(y_grid[0]),
                "__x": x_center + float(density_norm[0]) * half_width,
                "__order": 2 * steps,
            }
        )

    median_rows: list[dict[str, Any]] = []
    quartile_rows: list[dict[str, Any]] = []
    if inner in ("quartiles", "median"):
        # Pixel->data conversion for the median's stroke thickness. The rendered y
        # domain is Vega-Lite's nice-rounded union of the violin grids and zero
        # (zero=True is the y-channel default; verified empirically) - utils'
        # _nice_domain is the same d3 algorithm, so the estimate tracks it closely.
        grid_lo = min(g[3][0] for g in group_kde)
        grid_hi = max(g[3][-1] for g in group_kde)
        dom_lo, dom_hi = _nice_domain(min(grid_lo, 0.0), max(grid_hi, 0.0))
        data_per_px = (dom_hi - dom_lo) / _opt("height")
        h_med = strokeWidth * data_per_px  # half the median band's 2*strokeWidth thickness

        for group, x_center, vals, y_grid, density_norm in group_kde:
            q1, q2, q3 = (float(q) for q in np.quantile(vals, [0.25, 0.5, 0.75]))
            if inner == "quartiles":
                for q in (q1, q3):
                    # Clip the line to the violin outline: half-width = the KDE
                    # density at the quantile's y, in the same normalized units
                    # as the outline.
                    d = float(np.interp(q, y_grid, density_norm))
                    quartile_rows.append(
                        {
                            "__group": group,
                            "__y": q,
                            "__x": x_center - d * half_width,
                            "__x2": x_center + d * half_width,
                        }
                    )
            # The median is TRUE-CLIPPED to the violin border: a straight stroked
            # line is a rectangle, and on a squat violin the outline sweeps inward
            # by whole pixels across the line's own thickness, so its corners jut
            # past the border no matter where it ends. Instead the median is a thin
            # polygon spanning q2 +/- half its thickness whose left/right edges
            # FOLLOW the outline - every grid point in the band plus interpolated
            # band edges, rendered as a mark_area.
            band_lo = max(q2 - h_med, float(y_grid[0]))
            band_hi = min(q2 + h_med, float(y_grid[-1]))
            band_ys = sorted({band_lo, *(float(y) for y in y_grid if band_lo < y < band_hi), q2, band_hi})
            for band_y in band_ys:
                d = float(np.interp(band_y, y_grid, density_norm))
                median_rows.append(
                    {
                        "__group": group,
                        "__y": band_y,
                        "__x": x_center - d * half_width,
                        "__x2": x_center + d * half_width,
                    }
                )

    violin_df = pl.DataFrame(violin_rows)

    mark_kwargs = {
        "filled": True,
        "strokeWidth": strokeWidth,
        "fillOpacity": fillOpacity,
        "strokeOpacity": 0 if stroke is None else 1,
    }
    if stroke is not None:
        mark_kwargs["stroke"] = stroke
    if s.fill is not None:
        mark_kwargs["fill"] = s.fill

    violin_encoding: dict[str, Any] = {
        # padding=0: the precomputed pixel coordinates assume the full panel width
        # range - theme(viewPadding=...) must not compress this internal scale
        "x": alt.X("__x:Q", scale=alt.Scale(domain=[0, chart_width], padding=0), axis=None),
        "y": s.y("__y:Q"),
        "order": alt.Order("__order:Q"),
    }
    if s.fill is None:
        violin_encoding["color"] = s.color(field="__group:N", title=None, symbolType="circle")
    else:
        violin_encoding["detail"] = alt.Detail("__group:N")

    violin = alt.Chart(_internal_data(violin_df)).mark_line(**mark_kwargs).encode(**violin_encoding)

    if inner == "box":
        boxplot = (
            alt.Chart(data)
            .mark_boxplot(
                color=boxplotColor,
                ticks=False,
                rule={"stroke": boxplotColor},
                median={"fill": boxplotMedianColor},
                **({"size": boxplotWidth} if boxplotWidth is not None else {}),
            )
            .encode(
                x=violin_x,
                y=s.y(),
            )
        )
        return cast(alt.LayerChart, alt.layer(violin, boxplot).resolve_axis(x="independent"))

    # Without the boxplot no layer carries the nominal x axis, so an invisible
    # zero-row layer on the user's df hosts it (the add_log_ticks trick: the pinned
    # category domain drives the axis, transform_filter("false") renders nothing,
    # and sharing df means no phantom dataset for read(what="data")). It must be a
    # BAR mark: a point mark makes Vega-Lite type the x:N scale as a POINT scale. The explicit
    # rect padding makes this band scale match the pixel-computed silhouette and boxplot exactly.
    axis_host = alt.Chart(data).transform_filter("false").mark_bar(opacity=0).encode(x=violin_x)
    layers: list[Any] = [violin]

    if inner in ("quartiles", "median"):
        # Same pinned pixel x scale as the violin layer so the shared-scale merge
        # can't shift the marks. Quartiles = dashed rules (strokeDash pinned -
        # config.rule is dashed under the theme's dashedRule default); the median =
        # a solid outline-clipped area band at double weight. Each quartile line is
        # its OWN layer because its dash pattern is SCALED TO FIT its length (an
        # integer number of cycles plus one dash), so every line both starts AND
        # ends with a full dash touching the outline - a fixed pattern ends
        # wherever the length lands in the cycle, up to a whole gap of blank before
        # the endpoint (the ink visibly stops short of the outline), and strokeDash
        # is a mark property, per layer not per datum.
        pixel_x_scale = alt.Scale(domain=[0, chart_width], padding=0)

        dash_len, gap_len = _opt("dashedWidth")[:2]
        cycle = dash_len + gap_len
        for row in quartile_rows:
            length = row["__x2"] - row["__x"]
            # Fit n full cycles + one closing dash into the length; a line shorter
            # than one dash degenerates to a single full-length dash (solid).
            n = max(0, round((length - dash_len) / cycle)) if cycle else 0
            scale_factor = length / (n * cycle + dash_len) if length > 0 else 1
            fitted = [dash_len * scale_factor, gap_len * scale_factor]
            layers.append(
                alt.Chart(_internal_data([row]))
                # strokeCap="butt": config.rule's round caps would paint
                # strokeWidth/2 of ink beyond each endpoint, past the outline.
                .mark_rule(color=innerColor, strokeCap="butt", strokeWidth=strokeWidth, strokeDash=fitted)
                .encode(
                    x=alt.X("__x:Q", scale=pixel_x_scale, axis=None),
                    x2=alt.X2("__x2:Q"),
                    y=s.y("__y:Q"),
                )
            )
        # The median band polygon (see the row builder above). Fill/stroke pinned to
        # dodge the config.area grey-fill/stroke leak; detail= splits the single
        # layer into one polygon per group without touching a colour scale.
        layers.append(
            alt.Chart(_internal_data(median_rows))
            .mark_area(fill=innerColor, opacity=1, fillOpacity=1, stroke=None, strokeWidth=0)
            .encode(
                x=alt.X("__x:Q", scale=pixel_x_scale, axis=None),
                x2=alt.X2("__x2:Q"),
                y=s.y("__y:Q"),
                detail=alt.Detail("__group:N"),
            )
        )

    layers.append(axis_host)
    return cast(alt.LayerChart, alt.layer(*layers).resolve_axis(x="independent"))


def mark_strip(
    data: "pl.DataFrame | pd.DataFrame",
    x: str,
    y: str,
    categories: list[Any],
    *,
    scatter: str = "jitter",
    palette: str | list[str] | None = None,
    fill: str | None = None,
    markSize: float | None = None,
    markOpacity: float | None = None,
    spread: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    labelMap: Mapping[Any, str | list[str]] | None = None,
    errorbars: bool = True,
    errorbarExtent: str = "sem",
    yTitle: str | list[str] | None | _UnsetType = _UNSET,
    xTitle: str | list[str] | None | _UnsetType = _UNSET,
) -> alt.LayerChart:
    """
    Build an Altair layer combining jittered or beeswarm points with a centre statistic.

    With ``errorbars=True`` (default) the centre tick marks the group MEAN - the same
    statistic the error bars are computed from, so the tick is always centred between
    the caps. With ``errorbars=False`` the tick marks the median instead.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``ds.stats.comparisons``).

    Parameters
    ----------
    data:
        Polars or pandas DataFrame containing the data.
    x:
        Column name for the grouping variable (x-axis).
    y:
        Column name for the value variable (y-axis).
    categories:
        Ordered list of all x-axis categories. It must contain each observed value exactly once
        and no unobserved values; tuple/list order and numeric category values are supported, but
        a raw string is rejected.
    scatter:
        Point distribution method: ``'jitter'`` (faster, random Gaussian offset)
        or ``'beeswarm'`` (collision-avoidance, better for smaller n).
    palette:
        Named dysonsphere palette or explicit list of category colors. When ``None``, colors
        inherit the active theme category palette. Cannot be combined with ``fill``.
    fill:
        Fixed literal fill color for the points. Suppresses the category-color legend when set
        and does not affect summary marks. Cannot be combined with ``palette``.
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
    labelMap:
        ``{raw_value: label}`` mapping applied to the x-axis tick labels at render
        time via :func:`label_expr` - the data keeps the raw values. A label may be
        a list of strings for a multi-line label. Unmapped values show as-is.
    errorbars:
        Whether to show error bars around the group mean. When ``True``,
        the mean is shown as a tick with error bars. When ``False``, the
        median is shown instead.
    errorbarExtent:
        Statistic to use for error bars: ``'sem'`` (standard error of the
        mean, default) or ``'sd'`` (standard deviation).
    yTitle:
        Y-axis title. Defaults to ``y``. Pass ``None`` to suppress.
    xTitle:
        X-axis title. Defaults to ``x``. Pass ``None`` to suppress.

    Examples
    --------
    ::

        ds.theme()
        chart = ds.mark_strip(data, "group", "value", CATEGORIES)
        ds.save(chart, "strip")

        # beeswarm variant
        chart = ds.mark_strip(data, "group", "value", CATEGORIES, scatter="beeswarm")
    """
    xCol = x
    s = _MarkScaffold(
        data,
        xCol,
        y,
        categories,
        palette=palette,
        fill=fill,
        legend=legend,
        xLabelAngle=xLabelAngle,
        labelMap=labelMap,
        xTitle=xTitle,
        yTitle=yTitle,
    )
    data = s.df
    if markSize is None:
        markSize = _opt("markSize")
    if markOpacity is None:
        markOpacity = _opt("markFillOpacity")

    if scatter == "jitter":
        data = jitter(data, spread=spread)
        offset_col = "jitter_x"
    elif scatter == "beeswarm":
        data = beeswarm(data, column=y, groupBy=[xCol], spread=spread)
        offset_col = "beeswarm_x"
    else:
        raise ValueError(f"scatter must be 'jitter' or 'beeswarm', got {scatter!r}")

    band_padding = _opt("outerPadding")  # the offset variant's padding - see _band_geometry
    step = _band_geometry(len(categories)).step
    # NOT a band centre: the xOffset scale positions relative to the band start, so this
    # is the in-band midpoint expressed in xOffset range coordinates.
    band_center = step * (0.5 - band_padding)
    max_offset = cast(float, data[offset_col].abs().cast(pl.Float64).max() or 0.0)
    offset_scale = alt.Scale(
        domain=[-max_offset, max_offset],
        range=[band_center - max_offset, band_center + max_offset],
    )

    x_encoding = s.x()

    point_mark_kwargs: dict[str, Any] = {
        "size": markSize,
        "opacity": markOpacity,
        "stroke": "black" if _opt("dark") else _opt("markStroke"),
        "strokeWidth": _opt("markStrokeWidth"),
        "strokeOpacity": _opt("markStrokeOpacity"),
    }
    point_encoding: dict[str, Any] = {
        "x": x_encoding,
        "y": s.y(),
        "xOffset": alt.XOffset(f"{offset_col}:Q", scale=offset_scale),
    }
    if s.fill is None:
        point_encoding["color"] = s.color()
    else:
        point_mark_kwargs["fill"] = s.fill

    points = (
        alt.Chart(data)
        # Stroke pinned here, NOT inherited: the theme's config.circle has stroke=None
        # (bare overlay dots are stroke-less), but strip/beeswarm points keep the house
        # outlined-dot look. Black in darkmode too (outlines light palette fills).
        .mark_circle(**point_mark_kwargs)
        .encode(**point_encoding)
    )

    if not errorbars:
        # Median indicator: a boxplot with everything but the median tick hidden, so the
        # tick inherits the theme's median styling and band placement exactly.
        median = (
            alt.Chart(data)
            .mark_boxplot(
                ticks=False,
                box={"fillOpacity": 0, "strokeOpacity": 0},
                rule={"strokeOpacity": 0},
                outliers={"opacity": 0},
            )
            .encode(
                x=x_encoding,
                y=s.y(),
            )
        )
        return cast(alt.LayerChart, alt.layer(points, median))

    if errorbarExtent == "sem":
        error_expr = (pl.col(y).std() / pl.col(y).count().sqrt()).alias("__error")
    elif errorbarExtent == "sd":
        error_expr = pl.col(y).std().alias("__error")
    else:
        raise ValueError(f"errorbarExtent must be 'sem' or 'sd', got {errorbarExtent!r}")

    # maintain_order: group_by is otherwise order-nondeterministic, which changed the
    # inlined summary dataset (and so the spec checksum + mark z-order) run to run.
    summary = _internal_data(
        data.group_by(xCol, maintain_order=True).agg([pl.col(y).mean().alias("__mean"), error_expr])
    )

    errorbar_layer = (
        alt.Chart(summary)
        .mark_errorbar()
        .encode(
            x=x_encoding,
            y=s.y("__mean:Q"),
            yError=alt.YError("__error:Q"),
        )
    )

    # The centre tick draws the MEAN - the statistic the error bars are computed from -
    # so it always sits centred between the caps (a median tick drifts off-centre on
    # skewed data). All styling inherits config.tick (the crossbar defaults: errorbar-cap
    # colour/round caps, boxplot-median span), which also resolves darkmode at render
    # time - no callable needed for correct tick colour across save() backgrounds.
    mean_tick = (
        alt.Chart(summary)
        .mark_tick()
        .encode(
            x=x_encoding,
            y=s.y("__mean:Q"),
        )
    )

    return cast(alt.LayerChart, alt.layer(points, errorbar_layer, mean_tick))

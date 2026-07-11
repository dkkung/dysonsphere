from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

import altair as alt
import numpy as np
import polars as pl

from .labels import label_expr
from .theme import _opt
from .transforms import add_beeswarm, add_jitter
from .utils import _internal_data, band_geometry, ensure_polars

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

    df: pl.DataFrame
    xCol: str
    yCol: str
    categories: list[str]
    palette: str | list[str] | None = None
    legend: bool = False
    xLabelAngle: float | None = None
    labelMap: Mapping[Any, str | list[str]] | None = None
    xTitle: str | None | _UnsetType = _UNSET
    yTitle: str | None | _UnsetType = _UNSET

    def __post_init__(self) -> None:
        self.df = ensure_polars(self.df)
        if self.xLabelAngle is None:
            self.xLabelAngle = _opt("xLabelAngle")
        self.x_title: str | None = self.xCol if isinstance(self.xTitle, _UnsetType) else self.xTitle
        self.y_title: str | None = self.yCol if isinstance(self.yTitle, _UnsetType) else self.yTitle

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

    def x(self) -> alt.X:
        return alt.X(f"{self.xCol}:N", sort=self.categories, title=self.x_title, axis=self.x_axis())

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
        scale = alt.Undefined if pal is None else alt.Scale(range=pal if isinstance(pal, list) else [pal])
        return alt.Color(
            field if field is not None else f"{self.xCol}:N",
            sort=self.categories,
            title=title,
            legend=alt.Legend(**legend_kwargs) if self.legend else None,
            scale=scale,
        )


def mark_violin(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    categories: list[str],
    *,
    boxplotSize: int | None = None,
    boxplotColor: str = "black",
    medianColor: str = "white",
    palette: str | list[str] | None = None,
    fillOpacity: float | None = None,
    stroke: str | None = None,
    strokeWidth: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    labelMap: Mapping[Any, str | list[str]] | None = None,
    steps: int = 200,
    yTitle: str | None | _UnsetType = _UNSET,
    xTitle: str | None | _UnsetType = _UNSET,
) -> alt.LayerChart:
    """
    Build an Altair layer combining a violin plot behind a boxplot.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``ds.add_comparisons``).

    The returned ``LayerChart`` is safe to place in ``alt.hconcat()`` alongside
    ``mark_strip()`` or any other chart - the violin uses absolute ``x:Q``
    coordinates internally rather than ``xOffset``, so Vega-Lite's xOffset
    scale resolution never squishes the violin shape.

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
    medianColor:
        Fill color of the boxplot median line. Defaults to ``"white"`` so it reads
        against the default black box; overrides the theme's ``markMedianFill``.
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
    labelMap:
        ``{raw_value: label}`` mapping applied to the x-axis tick labels at render
        time via :func:`label_expr` - the data keeps the raw values. A label may be
        a list of strings for a multi-line label. Unmapped values show as-is.
    steps:
        Number of y grid points used for KDE estimation (per group).
    yTitle:
        Y-axis title. Defaults to ``yCol``. Pass ``None`` to suppress.
    xTitle:
        X-axis title. Defaults to ``xCol``. Pass ``None`` to suppress.

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

    s = _MarkScaffold(
        df,
        xCol,
        yCol,
        categories,
        palette=palette,
        legend=legend,
        xLabelAngle=xLabelAngle,
        labelMap=labelMap,
        xTitle=xTitle,
        yTitle=yTitle,
    )
    df = s.df
    if fillOpacity is None:
        fillOpacity = _opt("markFillOpacity")
    if strokeWidth is None:
        strokeWidth = _opt("markStrokeWidth")
    mark_size = _opt("markSize")
    chart_width = _opt("chartWidth")  # x:Q domain of the violin layer
    # mark_boxplot lowers to a band scale with paddingInner=paddingOuter=bandPadding
    # (scale="band"), which is NOT the xOffset/mark_circle variant (scale="offset").
    geo = band_geometry(len(categories), scale="band")
    half_width = mark_size * 0.75

    # Precompute absolute x positions for each violin point so the violin
    # layer uses x:Q (not xOffset), avoiding Vega-Lite's shared xOffset
    # scale resolution that squishes the violin when hconcated with any
    # chart that also uses xOffset (e.g. mark_strip).
    violin_rows = []
    for i, group in enumerate(categories):
        x_center = geo.centers[i]
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

    mark_kwargs = {
        "filled": True,
        "strokeWidth": strokeWidth,
        "fillOpacity": fillOpacity,
        "strokeOpacity": 0 if stroke is None else 1,
    }
    if stroke is not None:
        mark_kwargs["stroke"] = stroke

    violin = (
        alt.Chart(_internal_data(violin_df))
        .mark_line(**mark_kwargs)
        .encode(
            x=alt.X("__x:Q", scale=alt.Scale(domain=[0, chart_width]), axis=None),
            y=s.y("__y:Q"),
            order=alt.Order("__order:Q"),
            color=s.color(field="__group:N", title=None, symbolType="circle"),
        )
    )

    boxplot = (
        alt.Chart(df)
        .mark_boxplot(
            color=boxplotColor,
            ticks=False,
            rule={"stroke": boxplotColor},
            median={"fill": medianColor},
            **({"size": boxplotSize} if boxplotSize is not None else {}),
        )
        .encode(
            x=s.x(),
            y=s.y(),
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
    labelMap: Mapping[Any, str | list[str]] | None = None,
    errorbars: bool = True,
    errorbarExtent: str = "sem",
    yTitle: str | None | _UnsetType = _UNSET,
    xTitle: str | None | _UnsetType = _UNSET,
) -> alt.LayerChart:
    """
    Build an Altair layer combining jittered or beeswarm points with a centre statistic.

    With ``errorbars=True`` (default) the centre tick marks the group MEAN - the same
    statistic the error bars are computed from, so the tick is always centred between
    the caps. With ``errorbars=False`` the tick marks the median instead.

    Returns a ``LayerChart`` that can be saved directly or composed with other
    layers (e.g. ``ds.add_comparisons``).

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
    s = _MarkScaffold(
        df,
        xCol,
        yCol,
        categories,
        palette=palette,
        legend=legend,
        xLabelAngle=xLabelAngle,
        labelMap=labelMap,
        xTitle=xTitle,
        yTitle=yTitle,
    )
    df = s.df
    if markSize is None:
        markSize = _opt("markSize")
    if markOpacity is None:
        markOpacity = _opt("markFillOpacity")

    if scatter == "jitter":
        df = add_jitter(df, spread=spread)
        offset_col = "jitter_x"
    elif scatter == "beeswarm":
        df = add_beeswarm(df, yCol=yCol, groupBy=[xCol], spread=spread)
        offset_col = "beeswarm_x"
    else:
        raise ValueError(f"scatter must be 'jitter' or 'beeswarm', got {scatter!r}")

    band_padding = _opt("bandPadding")
    step = band_geometry(len(categories)).step
    # NOT a band centre: the xOffset scale positions relative to the band start, so this
    # is the in-band midpoint expressed in xOffset range coordinates.
    band_center = step * (0.5 - band_padding)
    max_offset = cast(float, df[offset_col].abs().cast(pl.Float64).max() or 0.0)
    offset_scale = alt.Scale(
        domain=[-max_offset, max_offset],
        range=[band_center - max_offset, band_center + max_offset],
    )

    x = s.x()

    points = (
        alt.Chart(df)
        # Stroke pinned here, NOT inherited: the theme's config.circle has stroke=None
        # (bare overlay dots are stroke-less), but strip/beeswarm points keep the house
        # outlined-dot look. Black in darkmode too (outlines light palette fills).
        .mark_circle(
            size=markSize,
            opacity=markOpacity,
            stroke="black" if _opt("darkmode") else _opt("markStroke"),
            strokeWidth=_opt("markStrokeWidth"),
            strokeOpacity=_opt("markStrokeOpacity"),
        )
        .encode(
            x=x,
            y=s.y(),
            xOffset=alt.XOffset(f"{offset_col}:Q", scale=offset_scale),
            color=s.color(),
        )
    )

    if not errorbars:
        # Median indicator: a boxplot with everything but the median tick hidden, so the
        # tick inherits the theme's median styling and band placement exactly.
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
                y=s.y(),
            )
        )
        return cast(alt.LayerChart, alt.layer(points, median))

    if errorbarExtent == "sem":
        error_expr = (pl.col(yCol).std() / pl.col(yCol).count().sqrt()).alias("__error")
    elif errorbarExtent == "sd":
        error_expr = pl.col(yCol).std().alias("__error")
    else:
        raise ValueError(f"errorbarExtent must be 'sem' or 'sd', got {errorbarExtent!r}")

    # maintain_order: group_by is otherwise order-nondeterministic, which changed the
    # inlined summary dataset (and so the spec checksum + mark z-order) run to run.
    summary = _internal_data(
        df.group_by(xCol, maintain_order=True).agg([pl.col(yCol).mean().alias("__mean"), error_expr])
    )

    errorbar_layer = (
        alt.Chart(summary)
        .mark_errorbar()
        .encode(
            x=x,
            y=s.y("__mean:Q"),
            yError=alt.YError("__error:Q"),
        )
    )

    # The centre tick draws the MEAN - the statistic the error bars are computed from -
    # so it always sits centred between the caps (a median tick drifts off-centre on
    # skewed data). Tick and error bars form one glyph, so the colour follows the
    # errorbar-caps darkmode convention, not markMedianFill (whose fixed black left
    # the old median tick invisible on dark renders); there is no config.tick block
    # to inherit from, so every property is pinned here.
    mean_tick = (
        alt.Chart(summary)
        .mark_tick(
            color="white" if _opt("darkmode") else "black",
            cornerRadius=_opt("markStrokeWidth") / 2,  # round caps, like the errorbar ticks
            size=_opt("markSize") * 0.9,  # span the boxplot box width
            thickness=_opt("markStrokeWidth"),
            opacity=_opt("markFillOpacity"),
        )
        .encode(
            x=x,
            y=s.y("__mean:Q"),
        )
    )

    return cast(alt.LayerChart, alt.layer(points, errorbar_layer, mean_tick))

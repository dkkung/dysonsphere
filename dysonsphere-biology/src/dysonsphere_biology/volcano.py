"""Volcano plot for differential-expression results.

Uses dysonsphere's public core and extension APIs. This coordinated first-party package
may use shared core helpers internally; third-party extensions should use ``dysonsphere.ext`` for
extension primitives rather than shared private helpers.
"""

from __future__ import annotations

import math
import sys
from typing import TYPE_CHECKING, Any, cast

import altair as alt
import polars as pl

if TYPE_CHECKING:
    import pandas as pd

import dysonsphere as ds
from dysonsphere import ext
from dysonsphere.utils import _ensure_polars

# Distinguish an omitted title from an explicit None title.
_UNSET: Any = object()

# Clamp underflowed p-values before -log10 so y remains finite.
_P_FLOOR = sys.float_info.min

# Derived columns included in saved chart data.
_NEGLOG_COL = "neglog10p"
_SIG_COL = "significance"

# These values are also the legend labels. "Non-differential" describes the classification, not
# statistical significance: a point can pass the p-value cutoff but miss the fold-change cutoff.
_GAINED = "Gained"
_LOST = "Lost"
_NONDIFF = "Non-differential"


def volcano(
    data: "pl.DataFrame | pd.DataFrame",
    *,
    log2fc: str = "log2fc",
    pvalue: str = "pvalue",
    labels: str | None = None,
    fcThreshold: float = 1.0,
    pThreshold: float = 0.05,
    subset: str | int | list[str] | None = None,
    thresholdLines: bool = True,
    palette: str | list[str] | tuple[str, str] | None = None,
    nonDifferentialColor: str | None = None,
    markOpacity: float | None = None,
    legend: bool = True,
    xTitle: str | list[str] | None = _UNSET,
    yTitle: str | list[str] | None = _UNSET,
) -> alt.LayerChart:
    """Build a volcano plot (log2 fold change vs -log10 p) as a layered Altair chart.

    Points are classified ``"Gained"`` / ``"Lost"`` / ``"Non-differential"`` by the fold-change
    and p-value thresholds and colored accordingly; optional dashed threshold guides and gene
    labels are layered on. Returns an ``alt.LayerChart`` to compose or pass to ``ds.save()``.
    (The third label describes the analytical call, not significance - a point can be significant
    yet miss the fold-change threshold, so ``"ns"`` would be wrong for it.)

    Gained/lost colors inherit the active theme's diverging range when ``palette`` is omitted.
    The neutral remains a separate darkmode-aware grey, so build inside a
    ``ds.save(lambda: volcano(...))`` callable for correct light/dark export.

    Parameters
    ----------
    data:
        A polars or pandas DataFrame with per-gene results.
    log2fc, pvalue:
        Column names for the effect size (x) and the p-value (y is ``-log10`` of it).
    labels:
        Column of gene names; required only when ``subset`` is set.
    fcThreshold:
        ``|log2fc|`` significance cutoff (default ``1.0``). Vertical guides at ``+-`` this.
    pThreshold:
        P-value significance cutoff (default ``0.05``). Horizontal guide at ``-log10`` of it.
    subset:
        Which points to label (default ``None`` - no labels). ``int`` -> the top-N most
        significant, ranked by combined score ``|log2fc| * -log10(p)``; ``"significant"`` ->
        every significant point; ``list[str]`` -> the named genes. Any non-None value requires
        ``labels``.
    thresholdLines:
        Draw the fold-change / p-value guide lines (default ``True``).
    palette:
        A registered palette name, an explicit low-to-high color list, or the existing
        ``(gained, lost)`` endpoint tuple. Omission inherits the active theme's diverging range.
    nonDifferentialColor:
        Color for the non-differential points. Defaults to a faint theme grey (darkmode-aware).
    markOpacity:
        Point opacity. Inherits ``markFillOpacity`` from the active theme when ``None``.
    legend:
        Show the significance color legend (default ``True``).
    xTitle, yTitle:
        Axis titles. Omitted -> ``"log2 fold change"`` / ``"-log10 P"``; ``None`` -> no title.

    Raises
    ------
    ValueError
        If ``subset`` is set without ``labels``, or ``subset`` is an unrecognized string.
    """
    df = data
    data = _ensure_polars(df)

    data = data.with_columns((-pl.col(pvalue).clip(lower_bound=_P_FLOOR).log10()).alias(_NEGLOG_COL))
    gained = (pl.col(log2fc) >= fcThreshold) & (pl.col(pvalue) <= pThreshold)
    lost = (pl.col(log2fc) <= -fcThreshold) & (pl.col(pvalue) <= pThreshold)
    data = data.with_columns(
        pl.when(gained).then(pl.lit(_GAINED)).when(lost).then(pl.lit(_LOST)).otherwise(pl.lit(_NONDIFF)).alias(_SIG_COL)
    )
    # Draw non-differential points first so called points remain visible.
    data = data.sort(pl.col(_SIG_COL) != _NONDIFF)

    darkmode = bool(ext.opt("darkmode"))
    ns_color = (
        nonDifferentialColor
        if nonDifferentialColor is not None
        else (ds.palettes.colors["greys"][10] if darkmode else ds.palettes.colors["greys"][1])
    )
    scale_range = None
    if isinstance(palette, tuple):
        if len(palette) != 2 or any(not isinstance(color, str) or not color.strip() for color in palette):
            raise ValueError("palette tuple must contain exactly two non-empty (gained, lost) color strings")
        scale_range = [palette[1], palette[0]]
    elif isinstance(palette, str):
        if palette not in ds.palettes.colors:
            raise ValueError(f"unknown palette name {palette!r}")
        scale_range = ds.palettes.colors[palette]
    elif isinstance(palette, list):
        if not palette or any(not isinstance(color, str) or not color.strip() for color in palette):
            raise ValueError("palette must be a non-empty list of non-empty color strings")
        scale_range = palette
    elif palette is not None:
        raise ValueError("palette must be a registered name, color list, (gained, lost) tuple, or None")

    score_col = "__dysonsphere_volcano_significance_score"
    while score_col in data.columns:
        score_col += "_"

    x_title = "log2 fold change" if xTitle is _UNSET else xTitle
    y_title = "-log10 P" if yTitle is _UNSET else yTitle

    point_opacity = alt.Undefined if markOpacity is None else markOpacity
    points = (
        alt.Chart(data)
        .transform_calculate(
            **{score_col: f"datum.{_SIG_COL} === '{_GAINED}' ? 1 : datum.{_SIG_COL} === '{_LOST}' ? -1 : 0"}
        )
        .mark_point(opacity=point_opacity)
        .encode(
            x=alt.X(f"{log2fc}:Q", title=x_title),
            y=alt.Y(f"{_NEGLOG_COL}:Q", title=y_title),
            color=alt.Color(
                f"{score_col}:Q",
                scale=alt.Scale(domain=[-1, 1], domainMid=0, **({"range": scale_range} if scale_range else {})),
                legend=(
                    alt.Legend(
                        title=None,
                        type="symbol",
                        values=[1, -1],
                        labelExpr="datum.value === 1 ? 'Gained' : 'Lost'",
                    )
                    if legend
                    else None
                ),
                condition={"test": f"datum.{_SIG_COL} === '{_NONDIFF}'", "value": ns_color},
            ),
        )
    )

    layers: list[ext.AltairChart] = [points]
    if legend:
        # Keep the neutral entry independent of the diverging scale without exporting helper data.
        neutral_legend = (
            alt.Chart(data)
            .transform_filter("false")
            .mark_point()
            .encode(
                color=alt.Color(
                    f"{_SIG_COL}:N",
                    scale=alt.Scale(domain=[_NONDIFF], range=[ns_color]),
                    legend=alt.Legend(title=None, values=[_NONDIFF]),
                )
            )
        )
        layers.append(neutral_legend)

    if thresholdLines:
        # Datum-positioned rules preserve the base chart's axis titles.
        layers.append(ds.rule(x=-fcThreshold))
        layers.append(ds.rule(x=fcThreshold))
        layers.append(ds.rule(y=-math.log10(pThreshold)))

    chart: ext.AltairChart = alt.layer(*layers).resolve_scale(color="independent")
    if subset is not None:
        # labels returns a layer and pins the x/y scales.
        chart = chart + _label_layer(data, subset, log2fc, labels)
    # Record the extension version in export provenance.
    return cast(alt.LayerChart, ext.tag_extension(chart, "biology"))


def _label_layer(data: pl.DataFrame, label: str | int | list[str], log2fc_col: str, gene_col: str | None):
    """Select which genes to label (significance-aware) and delegate placement to ``ds.labels``.

    The volcano picks the rows itself - top-N by combined score, all significant, or an explicit
    list - because that ranking is domain-specific (``ds.labels``'s own ``subset=n`` is spatial
    even-spread, which isn't what a volcano wants). Row-based modes pass a positional mask so
    duplicate display labels cannot expand the selection. The FULL frame still goes to ``labels``,
    so force-repel placement, obstacles, connectors, and scale self-pinning all come for free.
    """
    if gene_col is None:
        raise ValueError("volcano(subset=...) requires labels to name the label column")

    if isinstance(label, bool):  # bool is an int subclass - reject before the int branch
        raise ValueError("volcano(subset=...) does not accept a bool")
    elif isinstance(label, int):
        # Preserve row identity so duplicate display names cannot expand top-N selection.
        row_index = "__dysonsphere_volcano_row"
        while row_index in data.columns:
            row_index += "_"
        score = (pl.col(log2fc_col).abs() * pl.col(_NEGLOG_COL)).alias("_score")
        chosen_rows = set(
            data.with_row_index(row_index)
            .filter(pl.col(_SIG_COL) != _NONDIFF)
            .with_columns(score)
            .sort("_score", descending=True)
            .head(label)[row_index]
            .to_list()
        )
        selected: list[bool] | list[str] = [i in chosen_rows for i in range(data.height)]
    elif isinstance(label, str):
        if label != "significant":
            raise ValueError(f"volcano(subset={label!r}) is not recognized; use 'significant', an int, or a list")
        selected = (data[_SIG_COL] != _NONDIFF).to_list()
    else:
        # Lists retain ds.labels' value-matching semantics.
        selected = [str(v) for v in data.filter(pl.col(gene_col).is_in(label))[gene_col].to_list()]

    # ds.labels derives connectorGap from the theme's point radius.
    return ds.labels(data, log2fc_col, _NEGLOG_COL, gene_col, subset=selected)

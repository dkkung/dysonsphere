"""Volcano plot for differential-expression results.

Built entirely on dysonsphere's public surfaces - core (``ds.theme`` / ``ds.add_rule`` /
``ds.colors`` / ``ds.ensure_polars``) plus the extension-author primitive surface
(``dysonsphere.ext``: ``opt`` / ``internal_data`` / ``AltairChart``). It doubles as the
reference for how an extension composes a first-class dysonsphere chart without reaching into
core internals.
"""

from __future__ import annotations

import math
import sys
from typing import Any

import altair as alt
import polars as pl

import dysonsphere as ds
from dysonsphere import ext

# Sentinel so "caller passed None (no title)" is distinct from "caller passed nothing (default
# title)" - the same _UNSET pattern the core marks use for yTitle/xTitle.
_UNSET: Any = object()

# Tools can underflow a p-value to exactly 0, which -log10 sends to +inf (an unplottable y).
# Clamp to the smallest positive float so the point plots at a finite, very high y.
_P_FLOOR = sys.float_info.min

# Derived columns added to the frame (the "data of record", like add_jitter's jitter_x).
_NEGLOG_COL = "neglog10p"
_SIG_COL = "significance"


def volcano(
    df: pl.DataFrame | Any,
    *,
    log2fcCol: str = "log2fc",
    pvalueCol: str = "pvalue",
    geneCol: str | None = None,
    fcThreshold: float = 1.0,
    pThreshold: float = 0.05,
    label: str | int | list[str] | None = None,
    thresholdLines: bool = True,
    palette: tuple[str, str] | None = None,
    nsColor: str | None = None,
    markOpacity: float = 0.85,
    legend: bool = True,
    xTitle: str | None = _UNSET,
    yTitle: str | None = _UNSET,
) -> ext.AltairChart:
    """Build a volcano plot (log2 fold change vs -log10 p) as a layered Altair chart.

    Points are classified ``"up"`` / ``"down"`` / ``"ns"`` by the fold-change and p-value
    thresholds and colored accordingly; optional dashed threshold guides and gene labels are
    layered on. Returns an ``alt.LayerChart`` to compose or pass to ``ds.save()``.

    Colors are resolved from the active theme at call time (darkmode-aware ``ns`` grey), so
    build inside a ``ds.save(lambda: volcano(...))`` callable for correct light/dark export.

    Parameters
    ----------
    df:
        A polars or pandas DataFrame with per-gene results.
    log2fcCol, pvalueCol:
        Column names for the effect size (x) and the p-value (y is ``-log10`` of it).
    geneCol:
        Column of gene names; required only when ``label`` is set.
    fcThreshold:
        ``|log2fc|`` significance cutoff (default ``1.0``). Vertical guides at ``+-`` this.
    pThreshold:
        P-value significance cutoff (default ``0.05``). Horizontal guide at ``-log10`` of it.
    label:
        Which points to label (default ``None`` - no labels). ``int`` -> the top-N most
        significant, ranked by combined score ``|log2fc| * -log10(p)``; ``"significant"`` ->
        every significant point; ``list[str]`` -> the named genes. Any non-None value requires
        ``geneCol``.
    thresholdLines:
        Draw the fold-change / p-value guide lines (default ``True``).
    palette:
        ``(up, down)`` hex colors. Defaults to the ``pinksblues`` diverging endpoints
        (pink = up, blue = down).
    nsColor:
        Color for non-significant points. Defaults to a faint theme grey (darkmode-aware).
    markOpacity:
        Point opacity (default ``0.85``). All other point styling (fill, size, stroke) comes
        from the active theme's ``mark_point`` config.
    legend:
        Show the significance color legend (default ``True``).
    xTitle, yTitle:
        Axis titles. Omitted -> ``"log2 fold change"`` / ``"-log10 P"``; ``None`` -> no title.

    Raises
    ------
    ValueError
        If ``label`` is set without ``geneCol``, or ``label`` is an unrecognized string.
    """
    data = ds.ensure_polars(df)

    data = data.with_columns((-pl.col(pvalueCol).clip(lower_bound=_P_FLOOR).log10()).alias(_NEGLOG_COL))
    up = (pl.col(log2fcCol) >= fcThreshold) & (pl.col(pvalueCol) <= pThreshold)
    down = (pl.col(log2fcCol) <= -fcThreshold) & (pl.col(pvalueCol) <= pThreshold)
    data = data.with_columns(
        pl.when(up).then(pl.lit("up")).when(down).then(pl.lit("down")).otherwise(pl.lit("ns")).alias(_SIG_COL)
    )
    # Draw ns first (behind) so significant points sit on top.
    data = data.sort(pl.col(_SIG_COL) != "ns")

    darkmode = bool(ext.opt("darkmode"))
    up_color, down_color = palette if palette is not None else (ds.colors["pinksblues"][0], ds.colors["pinksblues"][-1])
    ns_color = nsColor if nsColor is not None else (ds.colors["greys"][10] if darkmode else ds.colors["greys"][1])

    x_title = "log2 fold change" if xTitle is _UNSET else xTitle
    y_title = "-log10 P" if yTitle is _UNSET else yTitle

    # Plain mark_point() inherits the theme's config.point (filled, size, subtle stroke); only
    # opacity is overridden.
    points = (
        alt.Chart(data)
        .mark_point(opacity=markOpacity)
        .encode(
            x=alt.X(f"{log2fcCol}:Q", title=x_title),
            y=alt.Y(f"{_NEGLOG_COL}:Q", title=y_title),
            color=alt.Color(
                f"{_SIG_COL}:N",
                scale=alt.Scale(domain=["up", "down", "ns"], range=[up_color, down_color, ns_color]),
                legend=alt.Legend(title=None) if legend else None,
            ),
        )
    )

    layers: list[ext.AltairChart] = [points]

    if thresholdLines:
        # Dashed theme-styled reference guides at the +-fold-change and p-value cutoffs. add_rule
        # positions by alt.datum, so it composes here without nulling the axis titles.
        layers.append(ds.add_rule(-fcThreshold, axis="x"))
        layers.append(ds.add_rule(fcThreshold, axis="x"))
        layers.append(ds.add_rule(-math.log10(pThreshold), axis="y"))

    chart: ext.AltairChart = alt.layer(*layers)
    if label is not None:
        # add_labels returns a LayerChart; compose with + (it also self-pins the x/y scale).
        chart = chart + _label_layer(data, label, log2fcCol, geneCol)
    return chart


def _label_layer(data: pl.DataFrame, label: str | int | list[str], log2fcCol: str, geneCol: str | None):
    """Select which genes to label (significance-aware) and delegate placement to ``ds.add_labels``.

    The volcano picks the genes itself - top-N by combined score, all significant, or an explicit
    list - because that ranking is domain-specific (``add_labels``'s own ``labels=n`` is spatial
    even-spread, which isn't what a volcano wants). It then hands the chosen names to ``add_labels``
    as ``labels=[...]`` on the FULL frame, so the force-repel placement, connectors, and scale
    self-pinning all come for free.
    """
    if geneCol is None:
        raise ValueError("volcano(label=...) requires geneCol to name the label column")

    significant = data.filter(pl.col(_SIG_COL) != "ns")
    if isinstance(label, bool):  # bool is an int subclass - reject before the int branch
        raise ValueError("volcano(label=...) does not accept a bool")
    elif isinstance(label, int):
        score = (pl.col(log2fcCol).abs() * pl.col(_NEGLOG_COL)).alias("_score")
        chosen = significant.with_columns(score).sort("_score", descending=True).head(label)
    elif isinstance(label, str):
        if label != "significant":
            raise ValueError(f"volcano(label={label!r}) is not recognized; use 'significant', an int, or a list")
        chosen = significant
    else:
        chosen = data.filter(pl.col(geneCol).is_in(label))

    names = [str(v) for v in chosen[geneCol].to_list()]
    # Size the connector gap to clear the volcano's mark_point dots: radius = sqrt(config.point.size
    # / pi) = sqrt((markSize/2)/pi), plus the marker stroke - so the line stops at the dot edge, not
    # inside it (add_labels' default markSize/10 is tuned for tiny overlay dots and is too small).
    mark_size = ext.opt("markSize")
    gap = math.sqrt((mark_size / 2) / math.pi) + ext.opt("markStrokeWidth")
    return ds.add_labels(data, log2fcCol, _NEGLOG_COL, geneCol, labels=names, connectorGap=gap)

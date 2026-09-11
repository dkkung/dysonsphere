"""Composable chart annotations - reference lines, text, shading, and auto-placed point labels.

Every constructor returns an Altair chart/layer to compose onto a base chart with ``+``:
``rule`` (reference lines), ``text`` (positioned text), ``shade`` (background
shading), and ``labels`` (auto-placed point labels with connectors; the pixel placement
engine lives in ``_placement.py``). Statistical annotations (``comparisons``,
``correlation``) live in ``stats.py``.
"""

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import altair as alt
import polars as pl

if TYPE_CHECKING:
    import pandas as pd

from ._statistics import _validate_observations
from .theme import _opt
from .utils import _SHADE_PREFIX, _band_geometry, _empty_layer, _ensure_polars, _internal_data, _resolve_dash

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["rule", "text", "shade", "labels"]

# Reference lines


def _rule_number(name: str, value: Any) -> float:
    """Return one finite rule coordinate, rejecting booleans as non-numeric API inputs."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return result


def _rule_mark_kwargs(
    color: str | None,
    strokeWidth: float | None,
    strokeDash: bool | list[int | float] | None,
    opacity: float,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"opacity": opacity}
    if color is not None:
        kwargs["color"] = color
    if strokeWidth is not None:
        kwargs["strokeWidth"] = strokeWidth
    if strokeDash is not None:
        kwargs["strokeDash"] = _resolve_dash(strokeDash)
    return kwargs


def _resolve_rule_span(
    span: "tuple[Any, Any]",
    run_ch: str,
    categories: list[str] | None,
    flush: bool | None,
) -> tuple[str, float, float]:
    """Resolve a rule's ``span=(start, end)`` to a triple on the line's running axis (``run_ch``).

    Returns ``("q", a, b)`` for a numeric span (data coordinates, shares the base scale via
    ``alt.datum``) or ``("px", lo, hi)`` for a category-name span (resolved to pixels through
    ``_band_geometry`` like ``shade``, so it never merges into the base scale). Both bounds
    must be the same kind; a string span needs ``categories``.
    """
    if len(span) != 2:
        raise ValueError(f"span must be a (start, end) tuple, got {span!r}")
    start, end = span
    start_str, end_str = isinstance(start, str), isinstance(end, str)
    if start_str != end_str:
        raise ValueError(f"span bounds must both be numbers or both be category names, got {span!r}")
    if start_str:
        if categories is None:
            raise ValueError("categories is required when span uses category names.")
        cat_index = {cat: i for i, cat in enumerate(categories)}
        if start not in cat_index or end not in cat_index:
            missing = [c for c in (start, end) if c not in cat_index]
            raise ValueError(f"span category names not in categories: {missing}")
        n = len(categories)
        span_len = _opt("chartWidth") if run_ch == "x" else _opt("chartHeight")
        geo = _band_geometry(n, span_len)
        f = _default_flush() if flush is None else flush
        si, ei = cat_index[start], cat_index[end]
        lo = 0.0 if (f and si == 0) else geo.starts[si]
        hi = span_len if (f and ei == n - 1) else geo.ends[ei]
        return ("px", lo, hi)
    return ("q", _rule_number("span start", start), _rule_number("span end", end))


def _span_enc(triple: tuple[str, float, float] | None, run_ch: str) -> dict[str, Any]:
    """Encoding dict placing a resolved span triple on the rule's running channel + its ``2`` pair.

    Numeric (``"q"``) → ``alt.datum`` (shares the base scale); pixel (``"px"``) → ``alt.value``.
    """
    if triple is None:
        return {}
    kind, a, b = triple
    wrap = alt.value if kind == "px" else alt.datum
    return {run_ch: wrap(a), run_ch + "2": wrap(b)}


def _span_label_anchor(la: str, triple: tuple[str, float, float], axis: str) -> Any:
    """A label's running-axis anchor derived from the span, wrapped for the channel's coord space.

    Anchors to the span's ends by visual position so a sliced line's label sits on the line:
    ``axis="y"`` (perp x) left→low / right→high; ``axis="x"`` (perp y) top→up / bottom→down -
    which is the *high* data value but the *low* pixel value (the data/pixel y-flip), so the
    numeric and pixel branches invert. ``alt.datum`` for a data span, ``alt.value`` for pixels.
    """
    kind, a, b = triple
    lo, hi = (a, b) if a <= b else (b, a)
    mid = (lo + hi) / 2
    wrap = alt.value if kind == "px" else alt.datum
    if axis == "y":
        pick = {"left": lo, "center": mid, "right": hi}[la]
    elif kind == "q":  # data-y: larger value is visually up → top
        pick = {"top": hi, "center": mid, "bottom": lo}[la]
    else:  # pixel-y: smaller pixel is visually up → top
        pick = {"top": lo, "center": mid, "bottom": hi}[la]
    return wrap(pick)


# Pixel inset for text anchored at a flush plot edge - shared by rule's edge labels and
# text's corner presets, which both sit against the spine when the axis is not detached.
_EDGE_OFFSET = 2


def _default_flush() -> bool:
    """Extend outermost shade/span rects to the plot edge when the spine is flush.

    A detached axis puts a gap there already; a flush spine (closed, or axisOffset 0 - the
    default) would leave a sliver of unshaded plot between the band and the axis."""
    return bool(_opt("closed") or not _opt("axisOffset"))


def _rule_label_geometry(
    axis: str,
    labelAlign: str | None,
    labelPosition: str | None,
    labelOffsetX: float,
    labelOffsetY: float,
    fontSize: float,
    color: str | None,
    span_triple: tuple[str, float, float] | None = None,
) -> tuple[str, Any, dict[str, Any]]:
    """Resolve a reference-line label's placement to ``(perp_channel, perp_anchor, text_kwargs)``.

    ``perp_channel`` is the channel along which the line runs (``"x"`` for a horizontal
    ``axis="y"`` rule, ``"y"`` for a vertical ``axis="x"`` rule); ``perp_anchor`` is the built
    ``alt.value``/``alt.datum`` position on it; ``text_kwargs`` are the ``mark_text`` properties.
    With no ``span_triple`` the anchor is a pixel edge of the plot (``alt.value``); with a span it
    anchors to the slice's ends (via ``_span_label_anchor``) so the label stays on the line.
    Shared by the data-backed and datum (facet-safe) paths so their placement can't drift apart.
    """
    if axis == "y":
        la = labelAlign if labelAlign is not None else "left"
        lp = labelPosition if labelPosition is not None else "top"
        if la not in ("left", "center", "right"):
            raise ValueError(f"labelAlign must be 'left', 'center', or 'right' for axis='y', got {la!r}")
        if lp not in ("top", "bottom"):
            raise ValueError(f"labelPosition must be 'top' or 'bottom' for axis='y', got {lp!r}")
        perp_ch = "x"
        if span_triple is None:
            chart_width = _opt("chartWidth")
            # A flush spine sits at the content edge, so a left/right-anchored label would hug it;
            # inset by the same amount text uses. A detached axis already clears it. (Center is far
            # from either edge, so it is left alone.)
            edge_offset = _EDGE_OFFSET if (_opt("closed") or not _opt("axisOffset")) else 0
            perp_anchor = alt.value(
                {"left": edge_offset, "center": chart_width / 2, "right": chart_width - edge_offset}[la]
            )
        else:
            perp_anchor = _span_label_anchor(la, span_triple, "y")
        align, dx = la, labelOffsetX
        dy = (-3 if lp == "top" else 3) + labelOffsetY
        baseline = "bottom" if lp == "top" else "top"
    else:
        la = labelAlign if labelAlign is not None else "top"
        lp = labelPosition if labelPosition is not None else "right"
        if la not in ("top", "center", "bottom"):
            raise ValueError(f"labelAlign must be 'top', 'center', or 'bottom' for axis='x', got {la!r}")
        if lp not in ("left", "right"):
            raise ValueError(f"labelPosition must be 'left' or 'right' for axis='x', got {lp!r}")
        perp_ch = "y"
        baseline = {"top": "top", "center": "middle", "bottom": "bottom"}[la]
        if span_triple is None:
            chart_height = _opt("chartHeight")
            # See the axis="y" branch.
            edge_offset = _EDGE_OFFSET if (_opt("closed") or not _opt("axisOffset")) else 0
            perp_anchor = alt.value(
                {"top": edge_offset, "center": chart_height / 2, "bottom": chart_height - edge_offset}[la]
            )
        else:
            perp_anchor = _span_label_anchor(la, span_triple, "x")
        align = "left" if lp == "right" else "right"
        dx = (3 if lp == "right" else -3) + labelOffsetX
        dy = labelOffsetY
    text_kwargs: dict[str, Any] = {"align": align, "dx": dx, "dy": dy, "baseline": baseline, "fontSize": fontSize}
    if color is not None:
        text_kwargs["color"] = color
    return perp_ch, perp_anchor, text_kwargs


_DATUM_AGG = "__dsagg"


def _datum_base(src: Any) -> alt.Chart:
    """Facet-safe datum base: a chart on the shared frame ``src``, collapsed to a single row.

    The foundation of every facet-safe annotation ``data=`` path (``rule`` / ``text`` /
    ``shade``).  It shares ``src`` so a faceted composition partitions correctly — Altair
    requires all layers of a facet to share one data variable — and the dummy ``transform_aggregate``
    collapses N rows to one so constant ``alt.datum`` / ``alt.value`` marks don't overplot N times.
    Build the mark + a datum/value-only encoding on the result; **never reference a data field**
    (that would reintroduce a sidecar dataset and break faceting).  See the facet-safe datum-mode
    discipline in AGENTS.md.
    """
    # Altair's transform_aggregate **kwds form isn't stubbed, hence the ty ignore.
    return alt.Chart(src).transform_aggregate(**{_DATUM_AGG: "count()"})  # ty: ignore[invalid-argument-type]


def _datum_ref_layers(
    base_factory: "Callable[[], alt.Chart]",
    pos_ch: str,
    vals: list[float],
    mark_kwargs: dict[str, Any],
    *,
    labels: list[str] | None = None,
    text_kwargs: dict[str, Any] | None = None,
    perp_ch: str | None = None,
    perp_anchor: Any = None,
    span_enc: dict[str, Any] | None = None,
) -> list[alt.Chart]:
    """Datum-positioned rule layers: one rule layer per value, plus (when ``labels`` given) one
    text layer per value, each built on a fresh base from ``base_factory``.

    Positions come from a constant ``alt.datum`` (never a data field). This is what keeps the
    base chart's axis title intact: a field on the shared position channel participates in
    Vega-Lite's layer axis-title merge (an explicit ``title=None`` nulls the base title; a
    derived field title concatenates into it), whereas a constant datum contributes no title.
    ``span_enc`` (from ``_span_enc``) optionally slices each rule to a portion of its running axis;
    it too uses only ``alt.datum``/``alt.value`` so the base title survives. ``base_factory``
    decides faceting: ``_datum_base(src)`` (shared frame) is facet-safe; a fresh internal sidecar
    is the non-facet-safe default. One layer per value, so multiple values yield multiple layers."""
    span_enc = span_enc or {}
    layers = [base_factory().mark_rule(**mark_kwargs).encode(**{pos_ch: alt.datum(v), **span_enc}) for v in vals]
    if labels is not None:
        assert text_kwargs is not None and perp_ch is not None
        layers += [
            base_factory()
            .mark_text(**text_kwargs)
            .encode(**{pos_ch: alt.datum(v), perp_ch: perp_anchor, "text": alt.value(lbl)})
            for v, lbl in zip(vals, labels)
        ]
    return layers


def rule(
    *,
    x: float | list[float] | None = None,
    y: float | list[float] | None = None,
    x2: float | None = None,
    y2: float | None = None,
    slope: float | None = None,
    intercept: float = 0,
    span: "tuple[float, float] | tuple[str, str] | None" = None,
    categories: list[str] | None = None,
    flush: bool | None = None,
    label: str | list[str] | None = None,
    labelPosition: str | None = None,
    labelAlign: str | None = None,
    labelOffsetX: float = 0,
    labelOffsetY: float = 0,
    color: str | None = None,
    strokeWidth: float | None = None,
    strokeDash: bool | list[int | float] | None = None,
    opacity: float = 1.0,
    fontSize: float | None = None,
    data: "pl.DataFrame | pd.DataFrame | None" = None,
) -> alt.Chart | alt.LayerChart:
    """
    Add a horizontal, vertical, diagonal, or equation reference line to a chart.

    Returns a layer that the caller composes with ``+``.

    Parameters
    ----------
    x, y:
        Primary data coordinates. Supply only ``y`` for horizontal rules or only ``x`` for
        vertical rules; either may be a list in those modes. Supply both for a bounded or diagonal
        rule, completed by ``x2`` and/or ``y2`` as described below. Lists also remain supported for
        the fixed coordinate of bounded horizontal or vertical rules; diagonal endpoints are scalar.
    x2, y2:
        Secondary endpoint coordinates. ``x, x2, y`` makes a bounded horizontal rule;
        ``x, y, y2`` makes a bounded vertical rule; all four coordinates make a diagonal segment.
        Secondary endpoints cannot be combined with ``span``.
    slope, intercept:
        Equation mode. ``slope`` draws ``y = slope*x + intercept`` over the numeric x extent given
        by the required ``span``. ``intercept`` defaults to ``0``. This computes an ordinary endpoint
        segment and therefore represents the equation only on linear quantitative axes.
    span:
        Required x extent in equation mode, or optionally slice an axis-aligned line to a portion
        of its *running* axis, given as a ``(start, end)`` tuple. ``None`` (default) spans the full
        plot. A horizontal line runs along x and a vertical line runs along y. Two forms, mirroring
        ``shade``:

        - **Numeric** ``(start, end)`` — data coordinates on the running axis; shares the base
          chart's scale (positioned by ``alt.datum``).
        - **Category names** ``(start, end)`` — resolved to pixels via the band scale (needs
          ``categories``), so the slice does not merge into the base scale.

        A single ``span`` applies to every fixed coordinate when it is a list. When ``span`` is set,
        a ``label`` anchors to the slice's ends instead of the plot edge.
    categories:
        Ordered list of the running axis's categories, required only when ``span`` uses category
        names (for the band-scale index lookup).
    flush:
        For a category-name ``span``, extend an outermost-category endpoint to the axis domain
        edge. ``None`` (default) inherits the theme's ``closed`` setting. No effect on a numeric
        ``span``.
    label:
        Optional text label(s). One string per fixed coordinate; diagonal/equation rules accept one.
    labelAlign:
        Where *along* the line the label is anchored.
        Horizontal: ``"left"`` (default), ``"center"``, or ``"right"``.
        Vertical: ``"top"`` (default), ``"center"``, or ``"bottom"``.
        Diagonal/equation: ``"left"`` (default), ``"center"``, or ``"right"``. Left and right
        select the smaller and larger x coordinates, respectively; center uses the data-coordinate
        midpoint. These definitions do not inspect or change the composed chart's scales.
    labelPosition:
        Which *side* of the line the label sits on.
        Horizontal: ``"top"`` (default) or ``"bottom"``.
        Vertical: ``"right"`` (default) or ``"left"``.
        Diagonal/equation labels remain horizontal and use ``"top"`` (default) or ``"bottom"``.
    labelOffsetX:
        Additional horizontal pixel offset applied to the label. Default ``0``.
        Positive shifts right, negative shifts left.
    labelOffsetY:
        Additional vertical pixel offset applied to the label. Default ``0``.
        Positive shifts down, negative shifts up.
    color:
        Line and label color. ``None`` inherits from the active theme.
    strokeWidth:
        Line width in pixels. ``None`` inherits from the active theme.
    strokeDash:
        ``None`` (default) inherits the theme's ``dashedRule`` setting.
        ``False`` forces a solid line. ``True`` uses the theme's
        ``dashedWidth`` pattern. A list (e.g. ``[4, 2]``) uses that
        pattern directly.
    opacity:
        Line opacity. Defaults to ``1.0``.
    fontSize:
        Label font size. ``None`` inherits from the active theme.
    data:
        Facet-safe (datum) mode. ``None`` (default) builds the rule from its own small internal
        dataset — the normal behavior, but **incompatible with faceting** (Altair requires every
        layer of a faceted chart to share one data variable). Pass the **same DataFrame you gave
        the base chart** to switch to datum mode: the rule then shares that data and is positioned
        by a constant ``alt.datum`` instead of a sidecar dataset, so ``(base + rule(..., data=df))``
        can be faceted and the line repeats in every panel. Accepts a polars or pandas DataFrame.

    Examples
    --------
    ::

        # Horizontal line at y=0
        chart = base + ds.rule(y=0)

        # Facet-safe: pass the same df as the base, then facet
        df_chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        faceted = (df_chart + ds.rule(y=5.0, label="Threshold", data=df)).facet("group:N")

        # Labeled horizontal line, label above-left by default
        chart = base + ds.rule(y=5.0, label="Threshold", color="#c0392b")

        # Two horizontal lines, labels at the right end
        chart = base + ds.rule(
            y=[4.0, 8.0],
            label=["Lower limit", "Upper limit"],
            labelAlign="right",
            color="#c0392b",
        )

        # Vertical line, label at top-right by default
        chart = base + ds.rule(x=10, label="Intervention", color="#c0392b")

        # Vertical line, label nudged right and down
        chart = base + ds.rule(
            x=10, label="t₀", labelOffsetX=4, labelOffsetY=4
        )

        # Horizontal line sliced to x ∈ [2, 8] (data coords)
        chart = base + ds.rule(y=5.0, span=(2.0, 8.0))

        # Horizontal line sliced across a range of x categories
        chart = base + ds.rule(
            y=5.0, span=("Control", "Group B"), categories=CATEGORIES
        )

        # Straight segment and equation over an explicit x extent
        diagonal = base + ds.rule(x=2, y=3, x2=8, y2=9)
        equation = base + ds.rule(slope=2, intercept=1, span=(0, 5))
    """
    # Validate equation coefficients before dispatch or arithmetic. In particular, bool is not a
    # numeric coordinate, including `intercept=False` despite its equality to zero in Python.
    intercept_value = _rule_number("intercept", intercept)
    slope_value = _rule_number("slope", slope) if slope is not None else None
    coords_given = any(v is not None for v in (x, y, x2, y2))
    if slope is not None:
        if coords_given:
            raise ValueError("slope equation mode cannot be combined with x, y, x2, or y2.")
        if span is None:
            raise ValueError("span=(x_start, x_end) is required when slope is provided.")
        if categories is not None or flush is not None:
            raise ValueError("categories and flush do not apply to slope equation mode.")
        triple = _resolve_rule_span(span, "x", None, None)
        if triple[0] != "q":
            raise ValueError("equation span bounds must be numeric.")
        xa, xb = triple[1], triple[2]
        assert slope_value is not None
        x, y, x2, y2 = xa, slope_value * xa + intercept_value, xb, slope_value * xb + intercept_value
    elif not coords_given:
        raise ValueError("provide x or y coordinates, or slope with an explicit span.")
    elif intercept_value != 0:
        raise ValueError("intercept is only valid when slope is provided.")

    secondary = x2 is not None or y2 is not None
    if secondary and span is not None and slope is None:
        raise ValueError("x2/y2 and span are mutually exclusive.")

    mark_kwargs = _rule_mark_kwargs(color, strokeWidth, strokeDash, opacity)
    fs = fontSize if fontSize is not None else _opt("fontSize")

    # Reduce axis-aligned endpoint forms to the established axis-rule implementation. This preserves
    # category spans, labels, facet sharing, and datum/value positioning exactly.
    axis: str | None = None
    value: float | list[float] | None = None
    effective_span = span
    if y is not None and x is None and x2 is None and y2 is None:
        axis, value = "y", y
    elif x is not None and y is None and x2 is None and y2 is None:
        axis, value = "x", x
    elif x is not None and x2 is not None and y is not None and y2 is None:
        axis, value, effective_span = "y", y, (x, x2)
    elif x is not None and y is not None and y2 is not None and x2 is None:
        axis, value, effective_span = "x", x, (y, y2)

    if axis is None:
        if not all(v is not None for v in (x, y, x2, y2)):
            raise ValueError("invalid rule geometry: use x, y, x/x2/y, x/y/y2, x/y/x2/y2, or slope with span.")
        if any(isinstance(v, list) for v in (x, y)):
            raise ValueError("diagonal and equation rules require scalar endpoint coordinates.")
        if categories is not None or flush is not None:
            raise ValueError("categories and flush apply only to axis-aligned spans.")
        labels = None if label is None else ([label] if isinstance(label, str) else list(label))
        if labels is not None and len(labels) != 1:
            raise ValueError("diagonal and equation rules accept one label.")
        points = [_rule_number(name, v) for name, v in zip(("x", "y", "x2", "y2"), (x, y, x2, y2))]
        base_factory = (
            (lambda: _datum_base(_ensure_polars(data)))
            if data is not None
            else (lambda: alt.Chart(_internal_data([{}])))
        )
        enc = {
            "x": alt.datum(points[0]),
            "y": alt.datum(points[1]),
            "x2": alt.datum(points[2]),
            "y2": alt.datum(points[3]),
        }
        layers = [base_factory().mark_rule(**mark_kwargs).encode(**enc)]
        if labels is not None:
            la = labelAlign or "left"
            lp = labelPosition or "top"
            if la not in ("left", "center", "right"):
                raise ValueError("labelAlign must be 'left', 'center', or 'right' for a diagonal rule.")
            if lp not in ("top", "bottom"):
                raise ValueError("labelPosition must be 'top' or 'bottom' for a diagonal rule.")
            ordered = sorted(((points[0], points[1]), (points[2], points[3])))
            anchor = {
                "left": ordered[0],
                "center": ((points[0] + points[2]) / 2, (points[1] + points[3]) / 2),
                "right": ordered[1],
            }[la]
            text_kwargs: dict[str, Any] = {
                "align": la,
                "baseline": "bottom" if lp == "top" else "top",
                "dx": labelOffsetX,
                "dy": (-3 if lp == "top" else 3) + labelOffsetY,
                "fontSize": fs,
            }
            if color is not None:
                text_kwargs["color"] = color
            layers.append(
                base_factory()
                .mark_text(**text_kwargs)
                .encode(x=alt.datum(anchor[0]), y=alt.datum(anchor[1]), text=alt.value(labels[0]))
            )
        return layers[0] if len(layers) == 1 else cast(alt.LayerChart, alt.layer(*layers))

    assert value is not None
    raw_vals = value if isinstance(value, list) else [value]
    if not raw_vals:
        raise ValueError(f"{axis} coordinates must not be empty.")
    vals = [_rule_number(axis, v) for v in raw_vals]

    # A rule runs along the axis opposite to the one it is pinned on. `span` slices that running
    # axis; `_resolve_rule_span` returns a data (`"q"`) or pixel (`"px"`) triple (see shade).
    run_ch = "x" if axis == "y" else "y"
    span_triple = _resolve_rule_span(effective_span, run_ch, categories, flush) if effective_span is not None else None
    span_enc = _span_enc(span_triple, run_ch)

    labels: list[str] | None = None
    if label is not None:
        labels = [label] if isinstance(label, str) else list(label)
        if len(labels) != len(vals):
            raise ValueError(f"label has {len(labels)} items but value has {len(vals)}")
    # Label geometry is resolved once and shared by both paths (axis="y": horizontal rule,
    # labelAlign along x / labelPosition top|bottom; axis="x": vertical rule, labelAlign along y /
    # labelPosition right|left).
    geom = (
        _rule_label_geometry(axis, labelAlign, labelPosition, labelOffsetX, labelOffsetY, fs, color, span_triple)
        if labels is not None
        else None
    )

    # Both modes position by a constant `alt.datum` (never a data field), so the base chart's axis
    # title survives the Vega-Lite layer merge - see _datum_ref_layers.  They differ only in the
    # per-layer base: datum (facet-safe) mode shares `data` (via _datum_base) so
    # `(base + rule(..., data=df))` can be faceted; the default builds a fresh internal sidecar
    # (filtered by read(what="data"), and deliberately NOT facet-safe).
    if data is not None:
        src = _ensure_polars(data)

        def base_factory() -> alt.Chart:
            return _datum_base(src)
    else:

        def base_factory() -> alt.Chart:
            return alt.Chart(_internal_data([{}]))

    if geom is None:
        layers = _datum_ref_layers(base_factory, axis, vals, mark_kwargs, span_enc=span_enc)
    else:
        perp_ch, perp_anchor, text_kwargs = geom
        layers = _datum_ref_layers(
            base_factory,
            axis,
            vals,
            mark_kwargs,
            labels=labels,
            text_kwargs=text_kwargs,
            perp_ch=perp_ch,
            perp_anchor=perp_anchor,
            span_enc=span_enc,
        )
    return layers[0] if len(layers) == 1 else cast(alt.LayerChart, alt.layer(*layers))


_TEXT_PRESETS: dict[str, dict[str, Any]] = {
    "topLeft": {"x_frac": 0, "y_frac": 0, "align": "left", "baseline": "top"},
    "topCenter": {"x_frac": 0.5, "y_frac": 0, "align": "center", "baseline": "top"},
    "topRight": {"x_frac": 1, "y_frac": 0, "align": "right", "baseline": "top"},
    "middleLeft": {"x_frac": 0, "y_frac": 0.5, "align": "left", "baseline": "middle"},
    "middleCenter": {
        "x_frac": 0.5,
        "y_frac": 0.5,
        "align": "center",
        "baseline": "middle",
    },
    "middleRight": {"x_frac": 1, "y_frac": 0.5, "align": "right", "baseline": "middle"},
    "bottomLeft": {"x_frac": 0, "y_frac": 1, "align": "left", "baseline": "alphabetic"},
    "bottomCenter": {
        "x_frac": 0.5,
        "y_frac": 1,
        "align": "center",
        "baseline": "alphabetic",
    },
    "bottomRight": {
        "x_frac": 1,
        "y_frac": 1,
        "align": "right",
        "baseline": "alphabetic",
    },
}


def _is_alt_value(v) -> bool:
    return isinstance(v, dict) and "value" in v


def _resolve_text_bg(fill: "str | bool", stroke: "str | bool") -> "tuple[str | None, str | None]":
    """Resolve the text-background fill/stroke to concrete colours (or ``None`` -> not drawn).

    ``fill``/``stroke`` follow the ``bool | str`` pattern: ``False`` -> off; ``True`` -> a
    darkmode-aware default (fill: ``greys[0]`` light / ``greys[11]`` dark; stroke: ``black`` light /
    ``white`` dark); a string -> that colour. Read ``darkmode`` at build time (like ``shade``),
    so a ``save()`` across backgrounds needs a callable to re-resolve it.
    """
    from .palettes import colors

    dark = _opt("darkmode")
    fill_c = colors["greys"][11 if dark else 0] if fill is True else (fill if isinstance(fill, str) else None)
    stroke_c = ("white" if dark else "black") if stroke is True else (stroke if isinstance(stroke, str) else None)
    return fill_c, stroke_c


def _text_bg_props(
    text: str,
    fs: float,
    align: str,
    baseline: str,
    dx: float,
    dy: float,
    fill_c: "str | None",
    stroke_c: "str | None",
    fillOpacity: float,
    cornerRadius: "float | bool",
) -> "tuple[dict[str, Any], float, float]":
    """Background-rect ``mark_rect`` kwargs + pixel (xOffset, yOffset) for one text.

    The box is sized from a rough text estimate (``len*fs*0.6`` wide, proportional fonts vary so
    it is not exact) plus padding, and the offsets recentre the pixel-sized rect from the datum
    onto the text per its ``align``/``baseline`` (and any ``dx``/``dy``), so it sits behind the
    glyphs without needing the scale - works for both datum (data) and value (pixel) positions.
    ``cornerRadius`` follows the ``float | bool`` pattern: ``True`` -> ``fs * 0.25`` (the default
    rounding), ``False`` -> ``0`` (square), an explicit float -> that radius in px.
    """
    tw = len(text) * fs * 0.6  # text width estimate (no padding)
    w = tw + fs * 0.7  # chip width = text estimate + horizontal padding
    h = fs * 1.4
    # Recentre the chip on the TEXT via the text half-width, NOT the padded chip half-width: a
    # left/right-anchored label then sits centred in its chip with equal padding on both sides
    # (shifting by w/2 hugged the text to the near edge, piling all the padding on the far side).
    x_shift = {"left": tw / 2, "right": -tw / 2}.get(align, 0.0) + dx
    y_shift = {"top": h / 2, "bottom": -h / 2, "alphabetic": -h / 2}.get(baseline, 0.0) + dy
    cr = fs * 0.25 if cornerRadius is True else (0.0 if cornerRadius is False else cornerRadius)
    rk: dict[str, Any] = {"width": round(w, 2), "height": round(h, 2), "cornerRadius": round(cr, 2)}
    rk["fill"] = fill_c  # None -> transparent fill (stroke-only)
    if fill_c is not None:
        rk["fillOpacity"] = fillOpacity
    if stroke_c is not None:
        rk["stroke"] = stroke_c
        rk["strokeWidth"] = _opt("markStrokeWidth")
    else:
        # The theme styles config.rect with a black stroke, which a mark_rect inherits (same
        # config-leak as config.bar.fill); pin it off so stroke=False means no border.
        rk["stroke"] = None
        rk["strokeWidth"] = 0
    return rk, round(x_shift, 2), round(y_shift, 2)


def _text_datum_layers(
    base_factory: "Callable[[], alt.Chart]",
    texts: list[str],
    xs: list[Any],
    ys: list[Any],
    mark_kwargs: dict[str, Any],
    bg: "tuple[str | None, str | None, float, float | bool] | None" = None,
) -> list[alt.Chart]:
    """Datum/value-positioned text layers: one per annotation, each on a fresh ``base_factory``
    base. Positions come from ``alt.datum`` (data coords) or ``alt.value`` (pixels) - never a data
    field - so the base chart's axis titles survive the layer merge (a ``title=None`` field would
    null them; a derived field title would concatenate into them). ``base_factory`` decides
    faceting: ``_datum_base(src)`` (shared frame) is facet-safe; a fresh internal sidecar is the
    non-facet-safe default."""

    def _pos(v) -> Any:
        if _is_alt_value(v):
            return alt.value(v["value"])
        return alt.datum(float(v) if isinstance(v, (int, float)) else str(v))

    fs = mark_kwargs.get("fontSize") or _opt("fontSize")
    layers: list[alt.Chart] = []
    for t, xv, yv in zip(texts, xs, ys):
        if bg is not None:  # background rect BEHIND the text (drawn first)
            rk, xsh, ysh = _text_bg_props(
                t, fs, mark_kwargs["align"], mark_kwargs["baseline"], mark_kwargs["dx"], mark_kwargs["dy"], *bg
            )
            layers.append(
                base_factory()
                .mark_rect(**rk)
                .encode(x=_pos(xv), y=_pos(yv), xOffset=alt.value(xsh), yOffset=alt.value(ysh))
            )
        layers.append(base_factory().mark_text(**mark_kwargs).encode(text=alt.value(t), x=_pos(xv), y=_pos(yv)))
    return layers


def text(
    text: str | list[str],
    x=None,
    y=None,
    *,
    position: str | None = None,
    angle: float = 0,
    align: str | None = None,
    baseline: str | None = None,
    offsetX: float = 0,
    offsetY: float = 0,
    color: str | None = None,
    fontSize: float | None = None,
    fontWeight: str | None = None,
    fontStyle: str | None = None,
    font: str | None = None,
    opacity: float = 1.0,
    fill: str | bool = False,
    fillOpacity: float = 1.0,
    stroke: str | bool = True,
    cornerRadius: float | bool = True,
    data: "pl.DataFrame | pd.DataFrame | None" = None,
) -> alt.Chart | alt.LayerChart:
    """
    Add one or more text annotations to a chart.

    Returns a layer that the caller composes with ``+``.

    Parameters
    ----------
    text:
        Annotation string(s). Pass a list to place multiple annotations in one
        call — ``x`` and ``y`` must then also be lists of equal length.
    x:
        Horizontal coordinate(s). Three forms are accepted:

        - ``float`` / ``int`` — data coordinate on a quantitative x axis.
          Shares the main chart's x scale automatically.
        - ``str`` — category name on a nominal x axis. Shares the main chart's
          band scale, placing the text at the band center.
        - ``alt.value(n)`` — fixed pixel position, ``n`` pixels from the left
          edge of the plot area. Use this (or ``position``) for annotations that
          should not move with the data.

        Required when ``position`` is not set.
    y:
        Vertical coordinate(s). Same three forms as ``x``, measured from the
        top of the plot area for ``alt.value()``.
        Required when ``position`` is not set.
    position:
        Named position within the plot area, flush with the axis domain edges.
        Sets ``x``, ``y``, ``align``, and ``baseline`` automatically using
        ``alt.value()`` pixel coordinates derived from ``chartWidth`` /
        ``chartHeight`` in the active theme. Explicit ``x``, ``y``, ``align``,
        or ``baseline`` arguments override the position value for that parameter.

        Valid positions (3 × 3 grid):

        +------------------+--------------------+-------------------+
        | ``"topLeft"``    | ``"topCenter"``    | ``"topRight"``    |
        +------------------+--------------------+-------------------+
        | ``"middleLeft"`` | ``"middleCenter"`` | ``"middleRight"`` |
        +------------------+--------------------+-------------------+
        | ``"bottomLeft"`` | ``"bottomCenter"`` | ``"bottomRight"`` |
        +------------------+--------------------+-------------------+

        When ``closed=True`` or ``axisOffset=0`` in the active theme, a fixed
        1 px inset is applied automatically to edge positions so text clears
        the border or flush axis line. ``offsetX`` / ``offsetY`` add on top of
        this for further fine-tuning::

            chart + ds.text("p = 0.003", position="topRight", offsetX=-4, offsetY=4)

    angle:
        Rotation in degrees, clockwise. Vega-Lite requires values in [0, 360];
        negative values are wrapped automatically. Defaults to ``0``.
    align:
        Horizontal text anchor: ``"left"`` (default), ``"center"``, or
        ``"right"``. Overrides the position value when both are set.
    baseline:
        Vertical text anchor: ``"top"``, ``"middle"`` (default), ``"bottom"``,
        or ``"alphabetic"``. ``"middle"`` centers the text body on the y
        coordinate — best for annotations near symbols or rules.
        ``"alphabetic"`` sits the reading baseline on y — best when text sits
        alongside other typeset text. Overrides the position value when both are
        set.
    offsetX:
        Horizontal pixel nudge applied after positioning. Positive shifts right.
        Useful for inset when using ``position``.
    offsetY:
        Vertical pixel nudge applied after positioning. Positive shifts down.
        Useful for inset when using ``position``.
    color:
        Text color. ``None`` inherits from the active theme's ``mark_text``
        config.
    fontSize:
        Font size in points. ``None`` inherits from the active theme.
    fontWeight:
        ``"normal"``, ``"bold"``, or a numeric CSS weight (``100``–``900``).
        ``None`` inherits from the active theme.
    fontStyle:
        ``"normal"`` or ``"italic"``. ``None`` inherits from the active theme.
    font:
        Font family name (e.g. ``"sans-serif"``, ``"Georgia"``). ``None``
        inherits from the active theme.
    opacity:
        Text opacity. Defaults to ``1.0``.
    fill:
        Background fill behind the text (a rect chip). ``False`` (default) -> none; ``True`` -> a
        darkmode-aware default (``greys[0]`` light / ``greys[11]`` dark); a string -> that color.
        Read at build time (like ``shade``), so a ``save()`` across backgrounds needs a callable
        to re-resolve it. The chip is sized from a rough text estimate (proportional fonts vary, so
        it is approximate) plus padding.
    fillOpacity:
        Opacity of the background fill (``0``-``1``). Defaults to ``1.0``. Ignored when ``fill`` is off.
    stroke:
        Border of the background chip. ``True`` (default) -> a darkmode-aware default (``"black"``
        light / ``"white"`` dark); ``False`` -> no border; a string -> that color. Only takes effect
        when a chip is drawn (i.e. when ``fill`` is set) - it borders the fill, it does not create a
        chip on its own.
    cornerRadius:
        Corner rounding of the background chip. ``True`` (default) -> ``fontSize * 0.25``; ``False``
        -> ``0`` (square); an explicit float -> that radius in px. Ignored when no chip is drawn.
    data:
        Facet-safe (datum) mode. ``None`` (default) builds the annotation from its own internal
        dataset — the normal behavior, but **incompatible with faceting**. Pass the **same
        DataFrame you gave the base chart** to share its data and position the text by ``alt.datum``
        (data coordinates) / ``alt.value`` (pixels), so ``(base + text(..., data=df))`` can be
        faceted and the text repeats in every panel. Accepts a polars or pandas DataFrame.

    Examples
    --------
    ::

        # Annotation at a data coordinate (quantitative x, quantitative y)
        chart + ds.text("Peak", x=10.5, y=2.3)

        # Annotation at a group center (nominal x, quantitative y)
        chart + ds.text("n=20", x="Control", y=8.5, baseline="bottom")

        # Multiple annotations at data coordinates
        chart + ds.text(
            ["Low", "High"], x=[1.0, 9.0], y=[0.5, 0.5], align="center"
        )

        # Corner position — top-right, inset 4 px from boundary
        chart + ds.text("ANOVA p < 0.001", position="topRight", offsetX=-4, offsetY=4)

        # Bottom-left with explicit font overrides
        chart + ds.text(
            "FDR < 0.05", position="bottomLeft", offsetX=4, offsetY=-4,
            fontSize=6, fontStyle="italic", color="#888888",
        )

        # Fixed pixel position via alt.value() passthrough
        chart + ds.text("†", x=alt.value(60), y=alt.value(10))

        # Facet-safe: pass the same df as the base, then facet
        chart + ds.text("★", x="B", y=18.0, data=df)
    """
    if position is not None and position not in _TEXT_PRESETS:
        raise ValueError(f"position must be one of {sorted(_TEXT_PRESETS)}, got {position!r}")

    # Resolve position — fills x/y/align/baseline only where not already provided
    if position is not None:
        p = _TEXT_PRESETS[position]
        cw = _opt("chartWidth")
        ch = _opt("chartHeight")
        # Auto-inset when text would touch the border or flush axis line.
        # Triggers when the plot has a closed box (closed=True) or the axis
        # sits flush with the plot edge (axisOffset=0). Center positions
        # (x_frac=0.5, y_frac=0.5) are unaffected.
        _closed = _opt("closed")
        _axis_offset = _opt("axisOffset")
        _pad = _EDGE_OFFSET if (_closed or _axis_offset == 0) else 0
        if x is None:
            x_px = p["x_frac"] * cw
            if p["x_frac"] == 0:
                x_px += _pad
            elif p["x_frac"] == 1:
                x_px -= _pad
            x = {"value": x_px}
        if y is None:
            y_px = p["y_frac"] * ch
            if p["y_frac"] == 0:
                y_px += _pad
            elif p["y_frac"] == 1:
                y_px -= _pad
            y = {"value": y_px}
        if align is None:
            align = p["align"]
        if baseline is None:
            baseline = p["baseline"]

    if x is None or y is None:
        raise ValueError("x and y are required when position is not set.")

    if align is None:
        align = "left"
    if baseline is None:
        baseline = "middle"

    # Normalise to lists
    texts = [text] if isinstance(text, str) else list(text)
    n = len(texts)
    xs = x if isinstance(x, list) else [x] * n
    ys = y if isinstance(y, list) else [y] * n

    if len(xs) != n or len(ys) != n:
        raise ValueError(f"text, x, and y must have the same length; got text={n}, x={len(xs)}, y={len(ys)}.")

    mark_kwargs: dict[str, Any] = {
        "align": align,
        "baseline": baseline,
        "angle": angle % 360,
        "dx": offsetX,
        "dy": offsetY,
        "opacity": opacity,
    }
    if color is not None:
        mark_kwargs["color"] = color
    if fontSize is not None:
        mark_kwargs["fontSize"] = fontSize
    if fontWeight is not None:
        mark_kwargs["fontWeight"] = fontWeight
    if fontStyle is not None:
        mark_kwargs["fontStyle"] = fontStyle
    if font is not None:
        mark_kwargs["font"] = font

    # Both modes position each annotation by a constant `alt.datum` (data coords) or `alt.value`
    # (pixels), never a data field, so the base chart's axis titles survive the layer merge - see
    # _text_datum_layers.  They differ only in the per-layer base: datum (facet-safe) mode shares
    # `data` (via _datum_base) so `(base + text(..., data=df))` can be faceted; the default
    # builds a fresh internal sidecar (filtered by read(what="data"), and deliberately NOT
    # facet-safe).
    if data is not None:
        src = _ensure_polars(data)

        def base_factory() -> alt.Chart:
            return _datum_base(src)
    else:

        def base_factory() -> alt.Chart:
            return alt.Chart(_internal_data([{}]))

    fill_c, stroke_c = _resolve_text_bg(fill, stroke)
    bg = (fill_c, stroke_c, fillOpacity, cornerRadius) if fill_c is not None else None  # chip gated on fill

    layers = _text_datum_layers(base_factory, texts, xs, ys, mark_kwargs, bg)
    return layers[0] if len(layers) == 1 else cast(alt.LayerChart, alt.layer(*layers))


# Auto-placed point labels (force-repel)


def _bool_mask(labels: Any, n_rows: int) -> "list[bool] | None":
    """Return ``labels`` as a ``list[bool]`` if it is a boolean mask matching ``n_rows``, else ``None``.

    Accepts a pandas/polars ``Series``, a NumPy array, or a plain list - anything array-like whose
    length equals ``n_rows`` and whose every element is a boolean (native ``bool``, or a NumPy/Arrow
    boolean that ``to_list``/``tolist`` normalizes to native ``bool``). Anything else - a list of
    label VALUES (strings/ints), a wrong-length sequence, a non-iterable - returns ``None`` so the
    caller falls back to matching by the ``labels`` column. This lets ``labels(subset=...)`` select
    rows positionally (decoupled from the display column), so a non-unique ``labels`` column can still pick
    exactly the intended rows.
    """
    if hasattr(labels, "to_list"):  # pandas / polars Series -> native bools
        seq = list(labels.to_list())
    elif hasattr(labels, "tolist"):  # NumPy array -> native bools
        seq = list(labels.tolist())
    elif isinstance(labels, (list, tuple)):
        seq = list(labels)
    else:
        return None
    if len(seq) != n_rows or not seq or not all(isinstance(v, bool) for v in seq):
        return None
    return [bool(v) for v in seq]


def labels(
    data: "pl.DataFrame | pd.DataFrame",
    x: str,
    y: str,
    labels: str,
    *,
    subset: "int | list[Any] | Any | None" = None,
    xDomain: tuple[float, float] | None = None,
    yDomain: tuple[float, float] | None = None,
    fontSize: float | None = None,
    fontStyle: str | None = None,
    color: str | None = None,
    fill: str | bool = False,
    fillOpacity: float = 1.0,
    stroke: str | bool = True,
    cornerRadius: float | bool = True,
    connector: bool = True,
    connectorColor: str | None = None,
    connectorOpacity: float | None = None,
    connectorStrokeDash: bool | list[int | float] = False,
    connectorGap: float | None = None,
    alwaysShowConnectors: bool = False,
) -> alt.LayerChart:
    """Auto-place non-overlapping text labels for a set of points, with connector lines.

    Force-directed placement (deterministic - reproducible figures) nudges each label off its
    point and away from the others, drawing a thin leader line from each point to its label. Every
    requested label is shown (never dropped); in an impossibly dense region labels settle at their
    least-overlapping positions. Returns a layer to compose onto the base chart with ``+``.

    Placement is solved in pixels before Vega renders, but each label is emitted as a pixel offset
    from its own marker, so it lands correctly on whatever scale the base chart uses and the base's
    axes are left alone. Just compose ``base + ds.labels(data, ...)``.

    Parameters
    ----------
    data:
        The plotted data (polars or pandas) - pass the same frame as the base chart.
    x, y:
        Quantitative coordinate columns (must match the base chart's x / y encodings).
    labels:
        Column holding the label text.
    subset:
        Which rows to label. ``None`` (default) labels every row; an **int `n`** auto-selects `n`
        rows spread evenly across the plot (unbiased - no cherry-picking, deterministic); a **boolean
        mask** (a pandas/polars ``Series``, NumPy array, or list of bools with one entry per row of
        ``data``) selects rows **positionally** - decoupled from ``labels``, so a non-unique label
        column still picks exactly the intended rows (e.g. ``subset=data["is_hit"]``); any other
        **list** labels the rows whose ``labels`` value is in it (e.g. ``subset=["TP53", "EGFR"]``,
        which needs a unique ``labels``). Pass the full plotted ``data`` and let ``subset`` do the
        selecting: obstacles and the axis domain both span all of ``data``, so the labels dodge EVERY
        plotted point (not just the labelled subset) and selecting a subset never clips the axes.
    xDomain, yDomain:
        ``(min, max)`` the placement solver assumes the base chart will render. Default: the
        extent of ``data``'s ``x`` / ``y``. A mismatch only degrades collision avoidance -
        labels stay attached to their markers either way. Pass explicitly when the base chart's
        domain differs from ``data``'s extent (a zoomed axis, or derived positions like centroids).
    fontSize:
        Label font size. ``None`` -> the theme's ``fontSize`` (the primary chart font size).
    fontStyle:
        Label font style, e.g. ``"italic"`` (gene / species names) or ``"bold"``. ``None`` (default)
        inherits the theme's ``mark_text`` (upright). Applies to every label.
    color:
        Label text color. ``None`` -> inherits the theme's ``mark_text`` color (darkmode-aware
        black/white).
    fill:
        Background fill behind each label (a rect chip - useful over a dense scatter). ``False``
        (default) -> none; ``True`` -> a darkmode-aware default (``greys[0]`` light / ``greys[11]``
        dark); a string -> that color. Read at build time (like ``shade``), so a ``save()``
        across backgrounds needs a callable. The connector meets the chip's edge, and the text is
        centred inside the chip (overriding the side justification a bare label would use).
    fillOpacity:
        Opacity of the background fill (``0``-``1``). Defaults to ``1.0``. Ignored when ``fill`` is off.
    stroke:
        Border of the background chip. ``True`` (default) -> a darkmode-aware default (``"black"``
        light / ``"white"`` dark); ``False`` -> no border; a string -> that color. Only takes effect
        when a chip is drawn (i.e. when ``fill`` is set).
    cornerRadius:
        Corner rounding of the background chip. ``True`` (default) -> ``fontSize * 0.25``; ``False``
        -> ``0`` (square); an explicit float -> that radius in px. Ignored when no chip is drawn.
    connector:
        Whether to draw the line connecting each point to its label (default ``True``).
    connectorColor:
        Connector line color. ``None`` -> inherits the theme's ``mark_rule`` color (darkmode-aware).
        Connectors otherwise inherit the theme's rule style (rounded caps, ``axisWidth`` stroke,
        opaque).
    connectorOpacity:
        Connector line opacity, ``0``-``1``. ``None`` (default) -> inherits the theme's ``mark_rule``
        opacity (opaque). Sets only the mark opacity, leaving the (darkmode-aware) color intact, so a
        faded leader - e.g. ``connectorOpacity=0.5`` to quiet the leaders relative to the labels -
        stays legible in both light and dark mode.
    connectorStrokeDash:
        Connector dash pattern. ``False`` (default) -> solid; ``True`` -> the theme's ``dashedWidth``
        pattern; a list (e.g. ``[4, 2]``) -> that pattern directly.
    connectorGap:
        Pixel gap left at the MARKER end of the connector so it points at the dot rather than
        piercing it. ``None`` (default) -> the theme's ``mark_point`` edge radius plus two
        connector stroke widths of whitespace
        (``sqrt(markSize/2/pi) + markStrokeWidth + 2*axisWidth``), which clears the default point
        mark (and the smaller ``mark_circle``) with a visible sliver of daylight at any theme
        scale; ``0`` -> no marker gap; a float -> that many pixels (set this for unusually large
        or heavily stroked markers, which the gap can't measure since the base chart isn't visible
        here). The TEXT end always keeps just the whitespace term (``2*axisWidth`` - there is no
        marker to clear there, so a symmetric gap would open a hole between line and label). Both
        gaps are uniform - they never shrink, so every drawn connector sits the same distance off
        its dot and its label; a connector too short to keep the full gaps is dropped instead (see
        ``alwaysShowConnectors``).
    alwaysShowConnectors:
        By default (``False``) a connector is omitted when the full end gaps would leave less than
        four connector stroke widths of visible line (length < ``connectorGap + 6*axisWidth``,
        i.e. < 1 px of line at the default theme) - the stub is just noise and the adjacent label
        is unambiguous. This threshold is font-independent (tied to the marker gap), so changing
        the label font never drops real leaders. ``True`` draws every one (sub-threshold stubs
        shrink their gaps to fit).

    Raises
    ------
    TypeError
        If ``data`` is not a Polars or pandas DataFrame.
    ValueError
        If a required column is missing, ``subset`` is invalid, or any row in either coordinate
        column contains a missing, non-numeric, or non-finite value. Coordinate validation covers
        rows outside the selected subset because they still define the plot domain and obstacles.
    """
    df, xCol, yCol = data, x, y
    from ._placement import _repel_labels, _sample_spread
    from .utils import _ensure_polars, _nice_domain

    data = _ensure_polars(df)
    missing = [column for column in (xCol, yCol, labels) if column not in data.columns]
    if missing:
        raise ValueError(f"labels data column(s) not found: {missing}.")
    # Domain and obstacles both span the FULL data (so labeling a subset via subset= never clips the
    # axes AND the labels dodge every plotted point, not just the labelled ones); the label positions
    # come from the selected rows. subset=None labels every row; an int auto-selects that many evenly
    # spread across the plot (unbiased, no cherry-picking); a BOOLEAN MASK selects rows positionally -
    # decoupling selection from the display column, so a non-unique labels column selects exactly the
    # intended rows; any other list selects the rows whose labels-column value is in it.
    if data.height:
        all_x = _validate_observations(data[xCol].to_list(), xCol, kind="label coordinate").tolist()
        all_y = _validate_observations(data[yCol].to_list(), yCol, kind="label coordinate").tolist()
    else:
        all_x, all_y = [], []
    if isinstance(subset, bool):  # bool is an int subclass - reject before the int branch
        raise ValueError("subset must be None, an int, a boolean mask, or a list of values - not a bool")
    if isinstance(subset, int):
        data = data[_sample_spread(all_x, all_y, subset)]
    elif subset is not None:
        mask = _bool_mask(subset, len(all_x))
        if mask is not None:
            data = data.filter(pl.Series(mask))
        else:
            data = data.filter(pl.col(labels).is_in(subset))
    xs = [float(v) for v in data[xCol].to_list()]
    ys = [float(v) for v in data[yCol].to_list()]
    label_texts = [str(v) for v in data[labels].to_list()]
    n = len(label_texts)

    width, height = _opt("chartWidth"), _opt("chartHeight")
    fs = fontSize if fontSize is not None else _opt("fontSize")
    # Text and connectors INHERIT the theme's mark_text / mark_rule config (darkmode-aware color,
    # rounded caps, axisWidth stroke, opaque) - resolved per render, so they track darkmode without
    # a callable. We only force the connector dash solid (never the theme's dashedRule) and apply an
    # explicit color when the caller passes one. (align is set per-label below, by side.)
    text_kwargs: dict[str, Any] = {"fontSize": fs, "baseline": "middle"}
    if color is not None:
        text_kwargs["color"] = color
    if fontStyle is not None:
        text_kwargs["fontStyle"] = fontStyle
    # connectorStrokeDash: False -> solid ([0, 0]); True -> the theme's dashedWidth; a list -> as given.
    rule_kwargs: dict[str, Any] = {"strokeDash": _resolve_dash(connectorStrokeDash)}
    if connectorColor is not None:
        rule_kwargs["color"] = connectorColor
    # connectorOpacity only sets the mark's opacity, leaving color to the (darkmode-aware) default or
    # connectorColor - so a faded leader stays legible in both light and dark mode, unlike baking the
    # alpha into an rgba color. None -> inherit the theme's mark_rule opacity (opaque).
    if connectorOpacity is not None:
        rule_kwargs["opacity"] = connectorOpacity

    if n == 0:
        return cast(alt.LayerChart, alt.layer(_empty_layer()))

    # Default domain: the full df's extent rounded OUTWARD to nice tick multiples (d3's nice(), via
    # _nice_domain) - so the pinned axes read like Vega's own nice:true (round bounds, edge markers
    # clear of the border) even though the scale spec says nice=False (the bounds ARE nice; pinning
    # makes our rounding self-fulfilling, no need to match Vega bit-for-bit). An explicit
    # xDomain/yDomain is used exactly as given (no nicing - the caller asked for those bounds).
    x0, x1 = xDomain if xDomain is not None else _nice_domain(min(all_x), max(all_x))
    y0, y1 = yDomain if yDomain is not None else _nice_domain(min(all_y), max(all_y))
    xspan = x1 - x0 or 1.0
    yspan = y1 - y0 or 1.0

    def to_px(x: float, y: float) -> tuple[float, float]:
        # Match Vega's linear map with a pinned domain: x -> [0, width], y inverted -> [height, 0].
        return ((x - x0) / xspan * width, height - (y - y0) / yspan * height)

    def px_to_x(px: float) -> float:
        return x0 + px / width * xspan

    def px_to_y(py: float) -> float:
        return y0 + (height - py) / height * yspan

    anchors = [to_px(x, y) for x, y in zip(xs, ys)]
    obstacles = [to_px(x, y) for x, y in zip(all_x, all_y)]  # ALL plotted points, so labels avoid them
    sizes = [(len(t) * fs * 0.6, fs * 1.2) for t in label_texts]  # rough text-box estimate
    label_pos = _repel_labels(anchors, sizes, width=width, height=height, obstacles=obstacles)

    # Positions are data coordinates: contained in the panel on any scale. The stated domain
    # matches the base's, kept only to suppress Vega-Lite's default nice:true.
    raw_x = alt.Scale(domain=[min(all_x), max(all_x)] if xDomain is None else list(xDomain))
    raw_y = alt.Scale(domain=[min(all_y), max(all_y)] if yDomain is None else list(yDomain))

    def datum_xy(px: float, py: float) -> dict[str, Any]:
        return {"x": alt.XDatum(px_to_x(px), scale=raw_x), "y": alt.YDatum(px_to_y(py), scale=raw_y)}

    fill_c, stroke_c = _resolve_text_bg(fill, stroke)
    bg = (fill_c, stroke_c, fillOpacity, cornerRadius) if fill_c is not None else None  # chip gated on fill

    layers: list[alt.Chart] = []
    for (ax, ay), (lx, ly), (w, h), text in zip(anchors, label_pos, sizes, label_texts):
        hw, hh = w / 2, h / 2
        dx, dy = ax - lx, ay - ly  # label centre -> point
        # Attach the connector on the box side facing the point (aspect-aware: which edge a straight
        # line to the point would cross). A left/right edge -> justify the text AWAY from the point,
        # anchored at that edge, so it reads as flowing out of the connector and edits grow outward.
        # A top/bottom edge (near-vertical connector, e.g. a label directly above its point) ->
        # CENTRE-justify, connector to the middle of that edge - so the connector stays vertical and
        # a center-justified edit keeps it aligned. The connector endpoint (ex, ey) is the box edge.
        if hw > 0 and hh > 0 and abs(dx) / hw >= abs(dy) / hh:
            align = "left" if dx <= 0 else "right"
            text_x = ex = lx - hw if dx <= 0 else lx + hw
            ey = ly
        else:
            align = "center"
            text_x = ex = lx
            ey = ly - hh if dy <= 0 else ly + hh
        if bg is not None:
            # With a chip, CENTRE the text inside it rather than anchoring it at the box edge: pin the
            # text AND the chip at the box centre (lx) so they are concentric, and the text is exactly
            # centred no matter how far the len*fs*0.6 width estimate is from the true glyph run. (An
            # edge-anchored label drifts to one side of its chip when the estimate misjudges the run -
            # e.g. wide all-caps like "NK" render wider than estimated and hug the far edge.) The
            # connector endpoint (ex, ey) stays on the box edge, so it still meets the chip's edge.
            align = "center"
            text_x = lx
        if connector:
            # Small gap at each end so the line points at the marker/label rather than piercing the
            # dot or touching the glyphs. connectorGap (px) defaults to the theme's mark_point EDGE
            # radius - sqrt(config.point.size/pi) = sqrt((markSize/2)/pi) plus the marker stroke -
            # ASYMMETRIC end gaps, same daylight at both ends. Marker end: the mark_point edge
            # radius (sqrt(config.point.size/pi) = sqrt((markSize/2)/pi)) + the marker stroke
            # + 2*axisWidth of whitespace. Text end: just the 2*axisWidth whitespace - there is no
            # marker to clear there, so a symmetric gap read as a hole between line and label.
            # Every term scales with its visual referent: marker radius (markSize, itself
            # chart-dimension-derived), marker stroke (markStrokeWidth), and daylight sized against
            # the connector's OWN stroke (the connector inherits the theme mark_rule config, drawn
            # at axisWidth). No fixed px constants. TWO axisWidths of daylight, not one: the rule's
            # round cap paints axisWidth/2 beyond each endpoint (and the marker stroke
            # markStrokeWidth/2 beyond its radius), so one axisWidth left only ~0.25px of true
            # painted daylight at the default theme - sub-device-pixel in PNG exports, visible or
            # not depending on the connector's angle (nonuniform-LOOKING gaps from uniform
            # geometry, verified 2026-07-05). Two leaves ~0.5px painted daylight.
            daylight = 2.0 * _opt("axisWidth")
            gap_cap = (
                connectorGap
                if connectorGap is not None
                else math.sqrt(_opt("markSize") / (2 * math.pi)) + _opt("markStrokeWidth") + daylight
            )
            seg = math.hypot(ex - ax, ey - ay)  # point -> label box edge (the connector length)
            # The gaps are UNIFORM - they never shrink, so every drawn connector sits the same
            # visible distance off its dot and its label. (The old min(gap_cap, seg*0.25) shrink
            # let short connectors - the nearest-clear-spot norm - start INSIDE the marker:
            # nonuniform touching-vs-gapped dots across one chart.) A connector whose full gaps
            # would leave less than 4 connector-stroke-widths of visible line (1px at the default
            # theme) is dropped instead: the stub is noise and the adjacent label is unambiguous.
            # All thresholds are FONT-INDEPENDENT (tied to marker/stroke geometry, not fontSize) so
            # changing the label font never silently drops real leaders. alwaysShowConnectors
            # forces every connector; forced sub-threshold stubs fall back to proportionally
            # shrunken gaps so some line remains.
            if seg >= gap_cap + daylight + 4.0 * _opt("axisWidth"):
                g_mark: float | None = gap_cap
                g_text = daylight
            elif alwaysShowConnectors:
                g_mark = min(gap_cap, seg * 0.25)
                g_text = min(daylight, seg * 0.25)
            else:
                g_mark = None
                g_text = 0.0
            if g_mark is not None:
                if seg > 0:
                    ux, uy = (ex - ax) / seg, (ey - ay) / seg
                    sx, sy = ax + ux * g_mark, ay + uy * g_mark
                    tx, ty = ex - ux * g_text, ey - uy * g_text
                else:
                    sx, sy, tx, ty = ax, ay, ex, ey
                layers.append(
                    alt.Chart(_internal_data([{}]))
                    .mark_rule(**rule_kwargs)
                    .encode(**datum_xy(sx, sy), x2=alt.X2Datum(px_to_x(tx)), y2=alt.Y2Datum(px_to_y(ty)))
                )
        if bg is not None:  # background rect behind the label (drawn after its connector, under the text)
            rk, xsh, ysh = _text_bg_props(text, fs, align, "middle", 0, 0, *bg)
            layers.append(
                alt.Chart(_internal_data([{}]))
                .mark_rect(**rk)
                .encode(**datum_xy(text_x, ly), xOffset=alt.value(xsh), yOffset=alt.value(ysh))
            )
        layers.append(
            alt.Chart(_internal_data([{}]))
            .mark_text(align=align, **text_kwargs)
            .encode(**datum_xy(text_x, ly), text=alt.value(text))
        )
    return cast(alt.LayerChart, alt.layer(*layers))


# Background shading


# Shade rects are BACKGROUND; `export._layer_axes_below_marks` sinks them behind the grid and axes
# by the view-`name` marker Vega copies into the SVG group class.
_shade_counter = 0


def _tag_shade(chart: alt.Chart) -> alt.Chart:
    """Name a shade layer so the SVG fixer can sink it. Names must be unique - Vega compiles a
    view name into a dataset name and rejects collisions."""
    global _shade_counter
    _shade_counter += 1
    return chart.properties(name=f"{_SHADE_PREFIX}{_shade_counter}")


def shade(
    categories: list[str] | None = None,
    *,
    positions: list[tuple[Any, ...]] | None = None,
    axis: str = "x",
    palette: list[str] | None = None,
    nShades: int = 2,
    repeat: int = 1,
    opacity: float = 1.0,
    stroke: bool = False,
    strokeWidth: float | None = None,
    strokeDash: list[float] | bool | None = None,
    flush: bool | None = None,
    data: "pl.DataFrame | pd.DataFrame | None" = None,
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
        shade = ds.shade(CATEGORIES)
        chart = shade + main_chart

        # positions mode — shade two category spans on x
        shade = ds.shade(
            positions=[("Control", "Group B"), ("Group D", "Group E")],
            categories=CATEGORIES,
        )

        # positions mode — reference band on y (quantitative)
        shade = ds.shade(
            positions=[(5.0, 10.0)], axis='y', palette=["#E8F4F8"]
        )

        # positions mode — intersection rect, nominal x + quantitative y
        shade = ds.shade(
            positions=[(("Control", "Group B"), (8.0, 12.0))],
            axis='both',
            categories=CATEGORIES,
        )

    Parameters
    ----------
    categories:
        Ordered list of axis categories. Required for band mode. Also
        required in positions mode when any tuple values are strings.
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
        List of hex color strings to cycle through in light mode. Defaults
        to ``"greys"`` when ``None``. In dark mode this parameter is always
        ignored — the darkest ``nShades`` stops of ``"greys"`` are used
        regardless. Resolved at call time; pass a callable to ``ds.save()``
        for correct darkmode rendering.
    nShades:
        Number of colors to use. In light mode, slices the first
        ``nShades`` stops from ``palette`` (or ``"greys"``). In dark mode,
        slices the last ``nShades`` stops of ``"greys"``. Defaults to
        ``2``.
    repeat:
        Number of consecutive ticks sharing the same color before advancing
        (band mode only). Defaults to ``1``.
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
    data:
        Facet-safe (datum) mode, **positions mode only**. ``None`` (default) builds each rect from
        its own internal dataset — the normal behavior, but **incompatible with faceting**. Pass
        the **same DataFrame you gave the base chart** to share its data and position numeric ranges
        by ``alt.datum`` (string/pixel ranges already use ``alt.value``), so
        ``(base + shade(positions=..., data=df))`` can be faceted and the shading repeats in
        every panel. Accepts polars or pandas. **Band mode** (``positions`` omitted) does not
        support ``data=`` and raises.

    Raises
    ------
    TypeError
        If facet-safe ``data`` is not a Polars or pandas DataFrame.
    ValueError
        If the requested mode, axis, categories, positions, or palette is invalid.
    """
    from .palettes import colors as _colors

    darkmode = _opt("darkmode")
    if darkmode:
        palette = _colors["greys"][-nShades:]
    else:
        if palette is None:
            palette = _colors["greys"]
        palette = palette[:nShades]

    n_colors = len(palette)
    # None means solid here (shade's documented default), so only True needs resolving.
    resolved_dash = _resolve_dash(strokeDash) if strokeDash is not None else None
    resolved_stroke_width = (strokeWidth if strokeWidth is not None else _opt("axisWidth")) if stroke else 0
    axis_stroke_color = "white" if _opt("darkmode") else "black"
    mark_kwargs: dict[str, Any] = {
        "opacity": opacity,
        "stroke": axis_stroke_color if stroke else None,
        "strokeWidth": resolved_stroke_width,
        "strokeOpacity": 1 if stroke else 0,
        # Shade rects are chart annotations, not data marks, so they pin square corners
        # regardless of theme(cornerRadius=...) - which styles config.rect and would
        # otherwise round these background bands as an unintended side effect.
        "cornerRadius": 0,
    }
    if resolved_dash is not None:
        mark_kwargs["strokeDash"] = resolved_dash

    dummy_df = pl.DataFrame({"__dummy": [0]})

    datum_mode = data is not None
    src = None
    if datum_mode:
        if positions is None:
            raise ValueError("shade(data=...) is a facet-safe positions mode only; band mode does not support it.")
        src = _ensure_polars(data)

    def _shade_rect(color, *, x=None, y=None) -> alt.Chart:
        """One ``mark_rect`` layer. ``x`` / ``y`` are each ``None``, a pixel range ``("px", lo,
        hi)``, or a data range ``("q", start, end)``. Pixel ranges use ``alt.value``; data ranges
        use ``alt.datum`` - NEVER a data field, whose ``title=None`` would null the base chart's
        axis title (a field on the shared channel joins Vega-Lite's layer axis-title merge). Datum
        mode shares ``src`` (faceteable); the default builds a fresh internal sidecar
        (read-filtered, deliberately NOT faceteable). Both share the base chart's scale, so the
        datum lands at the right data coordinate."""
        enc: dict[str, Any] = {}
        for ch, spec in (("x", x), ("y", y)):
            if spec is None:
                continue
            kind, a, b = spec
            c2 = ch + "2"
            if kind == "px":
                enc[ch], enc[c2] = alt.value(a), alt.value(b)
            else:  # ("q", ...) data range - datum keeps the base axis title (a field would clobber it)
                enc[ch], enc[c2] = alt.datum(float(a)), alt.datum(float(b))
        base = _datum_base(src) if datum_mode else alt.Chart(_internal_data(dummy_df))
        return _tag_shade(base.mark_rect(**mark_kwargs, color=color).encode(**enc))

    # ── positions mode ────────────────────────────────────────────────────────
    if positions is not None:
        layers: list[alt.Chart] = []

        if axis == "both":
            # Nested tuples: ((x_start, x_end), (y_start, y_end)).
            # Each half is resolved independently — string → pixel value via
            # band scale; numeric → Q field that shares the main chart's scale.
            chart_width = _opt("chartWidth")
            chart_height = _opt("chartHeight")
            n = len(categories) if categories else 0
            cat_index = {cat: i for i, cat in enumerate(categories)} if categories else {}
            x_geo = _band_geometry(n, chart_width) if n else None
            y_geo = _band_geometry(n, chart_height) if n else None
            if flush is None:
                flush = _default_flush()

            def _half(ch: str, start, end, geo, span) -> tuple[Any, ...]:
                # A string range → pixel span via the band scale; a numeric range → data span.
                if isinstance(start, str):
                    if categories is None:
                        raise ValueError(f"categories is required when positions contains string {ch}-ranges.")
                    si, ei = cat_index[start], cat_index[end]
                    lo = 0 if (flush and si == 0) else geo.starts[si]
                    hi = span if (flush and ei == n - 1) else geo.ends[ei]
                    return ("px", lo, hi)
                return ("q", start, end)

            for k, (x_range, y_range) in enumerate(positions):
                color = palette[k % n_colors]
                x_spec = _half("x", x_range[0], x_range[1], x_geo, chart_width)
                y_spec = _half("y", y_range[0], y_range[1], y_geo, chart_height)
                layers.append(_shade_rect(color, x=x_spec, y=y_spec))

        elif len(positions) > 0 and isinstance(positions[0][0], str):
            # String tuples: category names on a nominal axis.
            # Convert to pixel coordinates using the band scale formula so the
            # shade layer does not participate in scale merging.
            if categories is None:
                raise ValueError("categories is required when positions contains string tuples.")
            n = len(categories)
            span = _opt("chartHeight") if axis == "y" else _opt("chartWidth")
            geo = _band_geometry(n, span)
            cat_index = {cat: i for i, cat in enumerate(categories)}

            if flush is None:
                flush = _default_flush()

            for k, (start, end) in enumerate(positions):
                si, ei = cat_index[start], cat_index[end]
                lo = 0 if (flush and si == 0) else geo.starts[si]
                hi = span if (flush and ei == n - 1) else geo.ends[ei]
                color = palette[k % n_colors]
                spec = ("px", lo, hi)
                layers.append(_shade_rect(color, **({"y": spec} if axis == "y" else {"x": spec})))

        else:
            # Numeric tuples: data-space coordinates on a quantitative axis. Default → Q fields that
            # share the main chart's scale; datum mode → alt.datum on the same channel.
            for k, (start, end) in enumerate(positions):
                color = palette[k % n_colors]
                spec = ("q", start, end)
                layers.append(_shade_rect(color, **({"y": spec} if axis == "y" else {"x": spec})))

        return cast(alt.LayerChart, alt.layer(*layers))

    # ── band mode ─────────────────────────────────────────────────────────────
    if categories is None:
        raise ValueError(
            "categories is required for band mode. Pass positions= to shade explicit coordinate ranges instead."
        )

    n = len(categories)
    color_map = [palette[(i // repeat) % n_colors] for i in range(n)]

    chart_width = _opt("chartWidth")
    geo = _band_geometry(n, chart_width)

    if flush is None:
        flush = _default_flush()

    # Merge consecutive same-color categories so there is no coincident edge
    # between two rects of the same fill — that edge would show as a faint seam
    # in rasterized PNG output regardless of opacity.
    run_layers: list[alt.Chart] = []
    i = 0
    while i < n:
        j = i
        while j < n and color_map[j] == color_map[i]:
            j += 1
        left = 0 if (flush and i == 0) else geo.starts[i]
        right = chart_width if (flush and j == n) else geo.ends[j - 1]
        run_layers.append(
            _tag_shade(
                alt.Chart(_internal_data(dummy_df))
                .mark_rect(**mark_kwargs, color=color_map[i])
                .encode(x=alt.value(left), x2=alt.value(right))
            )
        )
        i = j

    return cast(alt.LayerChart, alt.layer(*run_layers))

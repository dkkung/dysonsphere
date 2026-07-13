"""Composable chart annotations - reference lines, text, shading, and auto-placed point labels.

Every constructor returns an Altair chart/layer to compose onto a base chart with ``+``:
``add_rule`` (reference lines), ``add_text`` (positioned text), ``add_shade`` (background
shading), and ``add_labels`` (auto-placed point labels with connectors; the pixel placement
engine lives in ``_placement.py``). Statistical annotations (``add_comparisons``,
``add_correlation``) live in ``inference.py``.
"""

import math
from collections.abc import Callable
from typing import Any, cast

import altair as alt
import polars as pl

from .theme import _opt
from .utils import _empty_layer, _internal_data, _resolve_dash, band_geometry

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["add_rule", "add_text", "add_shade", "add_labels"]

# Reference lines


def _rule_mark_kwargs(
    color: str | None,
    strokeWidth: float | None,
    strokeDash: bool | list[int] | None,
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


def _rule_label_geometry(
    axis: str,
    labelAlign: str | None,
    labelPosition: str | None,
    labelOffsetX: int,
    labelOffsetY: int,
    fontSize: float,
    color: str | None,
) -> tuple[str, float, dict[str, Any]]:
    """Resolve a reference-line label's placement to ``(perp_channel, perp_anchor, text_kwargs)``.

    ``perp_channel`` is the pixel-anchored channel perpendicular to the line (``"x"`` for a
    horizontal ``axis="y"`` rule, ``"y"`` for a vertical ``axis="x"`` rule); ``perp_anchor`` is
    its ``alt.value`` position; ``text_kwargs`` are the ``mark_text`` properties.  Shared by the
    data-backed and datum (facet-safe) paths so their label placement can't drift apart.
    """
    if axis == "y":
        la = labelAlign if labelAlign is not None else "left"
        lp = labelPosition if labelPosition is not None else "top"
        if la not in ("left", "center", "right"):
            raise ValueError(f"labelAlign must be 'left', 'center', or 'right' for axis='y', got {la!r}")
        if lp not in ("top", "bottom"):
            raise ValueError(f"labelPosition must be 'top' or 'bottom' for axis='y', got {lp!r}")
        chart_width = _opt("chartWidth")
        # A closed plot's spine sits flush at the content edge, so a left/right-anchored label
        # hugs the border; inset it by axisOffset to match the gap an open plot gets for free
        # from its detached axis, so opened and closed look the same. (Center is far from either
        # edge, so it is left alone.)
        edge_inset = _opt("axisOffset") if _opt("closed") else 0
        perp_ch = "x"
        perp_val = {"left": edge_inset, "center": chart_width / 2, "right": chart_width - edge_inset}[la]
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
        chart_height = _opt("chartHeight")
        # See the axis="y" branch: inset a top/bottom-anchored label off the flush closed spine
        # by axisOffset so opened and closed match.
        edge_inset = _opt("axisOffset") if _opt("closed") else 0
        perp_val, baseline = {
            "top": (edge_inset, "top"),
            "center": (chart_height / 2, "middle"),
            "bottom": (chart_height - edge_inset, "bottom"),
        }[la]
        perp_ch = "y"
        align = "left" if lp == "right" else "right"
        dx = (3 if lp == "right" else -3) + labelOffsetX
        dy = labelOffsetY
    text_kwargs: dict[str, Any] = {"align": align, "dx": dx, "dy": dy, "baseline": baseline, "fontSize": fontSize}
    if color is not None:
        text_kwargs["color"] = color
    return perp_ch, perp_val, text_kwargs


_DATUM_AGG = "__dsagg"


def _datum_base(src: Any) -> alt.Chart:
    """Facet-safe datum base: a chart on the shared frame ``src``, collapsed to a single row.

    The foundation of every facet-safe annotation ``data=`` path (``add_rule`` / ``add_text`` /
    ``add_shade``).  It shares ``src`` so a faceted composition partitions correctly — Altair
    requires all layers of a facet to share one data variable — and the dummy ``transform_aggregate``
    collapses N rows to one so constant ``alt.datum`` / ``alt.value`` marks don't overplot N times.
    Build the mark + a datum/value-only encoding on the result; **never reference a data field**
    (that would reintroduce a sidecar dataset and break faceting).  See the facet-safe datum-mode
    discipline in CLAUDE.md.
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
    perp_val: float | None = None,
) -> list[alt.Chart]:
    """Datum-positioned rule layers: one rule layer per value, plus (when ``labels`` given) one
    text layer per value, each built on a fresh base from ``base_factory``.

    Positions come from a constant ``alt.datum`` (never a data field). This is what keeps the
    base chart's axis title intact: a field on the shared position channel participates in
    Vega-Lite's layer axis-title merge (an explicit ``title=None`` nulls the base title; a
    derived field title concatenates into it), whereas a constant datum contributes no title.
    ``base_factory`` decides faceting: ``_datum_base(src)`` (shared frame) is facet-safe; a
    fresh internal sidecar is the non-facet-safe default. One layer per value, so multiple
    values yield multiple layers."""
    layers = [base_factory().mark_rule(**mark_kwargs).encode(**{pos_ch: alt.datum(v)}) for v in vals]
    if labels is not None:
        assert text_kwargs is not None and perp_ch is not None
        layers += [
            base_factory()
            .mark_text(**text_kwargs)
            .encode(**{pos_ch: alt.datum(v), perp_ch: alt.value(perp_val), "text": alt.value(lbl)})
            for v, lbl in zip(vals, labels)
        ]
    return layers


def add_rule(
    value: float | list[float],
    *,
    axis: str = "y",
    label: str | list[str] | None = None,
    labelPosition: str | None = None,
    labelAlign: str | None = None,
    labelOffsetX: int = 0,
    labelOffsetY: int = 0,
    color: str | None = None,
    strokeWidth: float | None = None,
    strokeDash: bool | list[int] | None = None,
    opacity: float = 1.0,
    fontSize: float | None = None,
    data: "pl.DataFrame | Any | None" = None,
) -> alt.Chart | alt.LayerChart:
    """
    Add one or more horizontal or vertical reference lines to a chart.

    Returns a layer that the caller composes with ``+``.

    Parameters
    ----------
    value:
        Coordinate(s) on the specified axis. ``float`` or ``list[float]``.
    axis:
        ``"y"`` (default) — horizontal line(s) at fixed y value(s).
        ``"x"`` — vertical line(s) at fixed x value(s).
    label:
        Optional text label(s). One string per value.
    labelAlign:
        Where *along* the line the label is anchored.
        ``axis="y"``: ``"left"`` (default), ``"center"``, or ``"right"``.
        ``axis="x"``: ``"top"`` (default), ``"center"``, or ``"bottom"``.
    labelPosition:
        Which *side* of the line the label sits on.
        ``axis="y"``: ``"top"`` (default) or ``"bottom"``.
        ``axis="x"``: ``"right"`` (default) or ``"left"``.
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
        by a constant ``alt.datum`` instead of a sidecar dataset, so ``(base + add_rule(..., data=df))``
        can be faceted and the line repeats in every panel. Accepts a polars or pandas DataFrame.

    Examples
    --------
    ::

        # Horizontal line at y=0
        chart = base + ds.add_rule(0)

        # Facet-safe: pass the same df as the base, then facet
        df_chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        faceted = (df_chart + ds.add_rule(5.0, label="Threshold", data=df)).facet("group:N")

        # Labeled horizontal line, label above-left by default
        chart = base + ds.add_rule(5.0, label="Threshold", color="#c0392b")

        # Two horizontal lines, labels at the right end
        chart = base + ds.add_rule(
            [4.0, 8.0],
            label=["Lower limit", "Upper limit"],
            labelAlign="right",
            color="#c0392b",
        )

        # Vertical line, label at top-right by default
        chart = base + ds.add_rule(10, axis="x", label="Intervention", color="#c0392b")

        # Vertical line, label nudged right and down
        chart = base + ds.add_rule(
            10, axis="x", label="t₀", labelOffsetX=4, labelOffsetY=4
        )
    """
    if axis not in ("x", "y"):
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

    vals = [float(v) for v in (value if isinstance(value, list) else [value])]
    mark_kwargs = _rule_mark_kwargs(color, strokeWidth, strokeDash, opacity)
    fs = fontSize if fontSize is not None else _opt("fontSize")

    labels: list[str] | None = None
    if label is not None:
        labels = [label] if isinstance(label, str) else list(label)
        if len(labels) != len(vals):
            raise ValueError(f"label has {len(labels)} items but value has {len(vals)}")
    # Label geometry is resolved once and shared by both paths (axis="y": horizontal rule,
    # labelAlign along x / labelPosition top|bottom; axis="x": vertical rule, labelAlign along y /
    # labelPosition right|left).
    geom = (
        _rule_label_geometry(axis, labelAlign, labelPosition, labelOffsetX, labelOffsetY, fs, color)
        if labels is not None
        else None
    )

    # Both modes position by a constant `alt.datum` (never a data field), so the base chart's axis
    # title survives the Vega-Lite layer merge - see _datum_ref_layers.  They differ only in the
    # per-layer base: datum (facet-safe) mode shares `data` (via _datum_base) so
    # `(base + add_rule(..., data=df))` can be faceted; the default builds a fresh internal sidecar
    # (filtered by read(what="data"), and deliberately NOT facet-safe).
    if data is not None:
        from .utils import ensure_polars

        src = ensure_polars(data)

        def base_factory() -> alt.Chart:
            return _datum_base(src)
    else:

        def base_factory() -> alt.Chart:
            return alt.Chart(_internal_data([{}]))

    if geom is None:
        layers = _datum_ref_layers(base_factory, axis, vals, mark_kwargs)
    else:
        perp_ch, perp_val, text_kwargs = geom
        layers = _datum_ref_layers(
            base_factory,
            axis,
            vals,
            mark_kwargs,
            labels=labels,
            text_kwargs=text_kwargs,
            perp_ch=perp_ch,
            perp_val=perp_val,
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
    ``white`` dark); a string -> that colour. Read ``darkmode`` at build time (like ``add_shade``),
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
    w = len(text) * fs * 0.6 + fs * 0.7  # text width estimate + horizontal padding
    h = fs * 1.4
    x_shift = {"left": w / 2, "right": -w / 2}.get(align, 0.0) + dx
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


def add_text(
    text: str | list[str],
    x=None,
    y=None,
    *,
    position: str | None = None,
    angle: float = 0,
    align: str | None = None,
    baseline: str | None = None,
    offsetX: int = 0,
    offsetY: int = 0,
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
    data: "pl.DataFrame | Any | None" = None,
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

            chart + ds.add_text("p = 0.003", position="topRight", offsetX=-4, offsetY=4)

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
        Read at build time (like ``add_shade``), so a ``save()`` across backgrounds needs a callable
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
        (data coordinates) / ``alt.value`` (pixels), so ``(base + add_text(..., data=df))`` can be
        faceted and the text repeats in every panel. Accepts a polars or pandas DataFrame.

    Examples
    --------
    ::

        # Annotation at a data coordinate (quantitative x, quantitative y)
        chart + ds.add_text("Peak", x=10.5, y=2.3)

        # Annotation at a group center (nominal x, quantitative y)
        chart + ds.add_text("n=20", x="Control", y=8.5, baseline="bottom")

        # Multiple annotations at data coordinates
        chart + ds.add_text(
            ["Low", "High"], x=[1.0, 9.0], y=[0.5, 0.5], align="center"
        )

        # Corner position — top-right, inset 4 px from boundary
        chart + ds.add_text("ANOVA p < 0.001", position="topRight", offsetX=-4, offsetY=4)

        # Bottom-left with explicit font overrides
        chart + ds.add_text(
            "FDR < 0.05", position="bottomLeft", offsetX=4, offsetY=-4,
            fontSize=6, fontStyle="italic", color="#888888",
        )

        # Fixed pixel position via alt.value() passthrough
        chart + ds.add_text("†", x=alt.value(60), y=alt.value(10))

        # Facet-safe: pass the same df as the base, then facet
        chart + ds.add_text("★", x="B", y=18.0, data=df)
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
        _pad = 1 if (_closed or _axis_offset == 0) else 0
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
    # `data` (via _datum_base) so `(base + add_text(..., data=df))` can be faceted; the default
    # builds a fresh internal sidecar (filtered by read(what="data"), and deliberately NOT
    # facet-safe).
    if data is not None:
        from .utils import ensure_polars

        src = ensure_polars(data)

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
    caller falls back to matching by ``labelCol`` value. This lets ``add_labels(labels=...)`` select
    rows positionally (decoupled from the display column), so a non-unique ``labelCol`` can still pick
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


def add_labels(
    df: "pl.DataFrame | Any",
    xCol: str,
    yCol: str,
    labelCol: str,
    *,
    labels: "int | list[Any] | Any | None" = None,
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
    connectorStrokeDash: bool | list[int] = False,
    connectorGap: float | None = None,
    alwaysShowConnectors: bool = False,
) -> alt.LayerChart:
    """Auto-place non-overlapping text labels for a set of points, with connector lines.

    Force-directed placement (deterministic - reproducible figures) nudges each label off its
    point and away from the others, drawing a thin leader line from each point to its label. Every
    requested label is shown (never dropped); in an impossibly dense region labels settle at their
    least-overlapping positions. Returns a layer to compose onto the base chart with ``+``.

    Label placement is a pixel-space problem solved before Vega renders, so the connectors align
    with the points only if the shared scale matches. ``add_labels`` handles that itself: the label
    layers pin the x/y scale to the data extent rounded outward to nice tick bounds (``nice=False``,
    ``zero=False``, explicit nice domain), so you do NOT need to touch the base chart's scale - just
    compose ``base + ds.add_labels(df, ...)``. (This retightens the axes around the data - with
    round bounds, but without Vega's default ``zero`` - which is required for alignment.)

    Parameters
    ----------
    df:
        The plotted data (polars or pandas) - pass the same frame as the base chart. The axis
        domain is inferred from its full extent, so the connectors line up without you pinning the
        base scale (the label layers pin it themselves; see below).
    xCol, yCol:
        Quantitative coordinate columns (must match the base chart's x / y encodings).
    labelCol:
        Column holding the label text.
    labels:
        Which rows to label. ``None`` (default) labels every row; an **int `n`** auto-selects `n`
        rows spread evenly across the plot (unbiased - no cherry-picking, deterministic); a **boolean
        mask** (a pandas/polars ``Series``, NumPy array, or list of bools with one entry per row of
        ``df``) selects rows **positionally** - decoupled from ``labelCol``, so a non-unique label
        column still picks exactly the intended rows (e.g. ``labels=df["is_hit"]``); any other
        **list** labels the rows whose ``labelCol`` value is in it (e.g. ``labels=["TP53", "EGFR"]``,
        which needs a unique ``labelCol``). Pass the full plotted ``df`` and let ``labels`` do the
        selecting: obstacles and the axis domain both span all of ``df``, so the labels dodge EVERY
        plotted point (not just the labelled subset) and selecting a subset never clips the axes.
    xDomain, yDomain:
        ``(min, max)`` axis domains, forced onto the shared scale (``nice=False``, ``zero=False``).
        Default: the **extent of the passed ``df``'s ``xCol`` / ``yCol``, rounded outward to nice
        tick bounds** (d3-style nice, so the axes end on round numbers; filtering ``df`` just moves
        the axes with it - always inferred). An explicit value is used exactly as given (no
        rounding). Pass explicitly only when you want the axes to span a range the passed ``df``
        does not cover - i.e. the base chart plots more than you hand ``add_labels`` (a deliberate
        subset, or **derived positions** like cluster centroids whose extent is tighter than the
        scatter).
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
        dark); a string -> that color. Read at build time (like ``add_shade``), so a ``save()``
        across backgrounds needs a callable. The connector meets the chip's edge.
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
    """
    from ._placement import _repel_labels, _sample_spread
    from .utils import _nice_domain, ensure_polars

    data = ensure_polars(df)
    # Domain and obstacles both span the FULL df (so labeling a subset via labels= never clips the
    # axes AND the labels dodge every plotted point, not just the labelled ones); the label positions
    # come from the selected rows. labels=None labels every row; an int auto-selects that many evenly
    # spread across the plot (unbiased, no cherry-picking); a BOOLEAN MASK selects rows positionally -
    # decoupling selection from the display column, so a non-unique labelCol still selects exactly the
    # intended rows; any other list selects the rows whose labelCol value is in it.
    all_x = [float(v) for v in data[xCol].to_list()]
    all_y = [float(v) for v in data[yCol].to_list()]
    if isinstance(labels, bool):  # bool is an int subclass - reject before the int branch
        raise ValueError("labels must be None, an int, a boolean mask, or a list of values - not a bool")
    if isinstance(labels, int):
        data = data[_sample_spread(all_x, all_y, labels)]
    elif labels is not None:
        mask = _bool_mask(labels, len(all_x))
        if mask is not None:
            data = data.filter(pl.Series(mask))
        else:
            data = data.filter(pl.col(labelCol).is_in(labels))
    xs = [float(v) for v in data[xCol].to_list()]
    ys = [float(v) for v in data[yCol].to_list()]
    label_texts = [str(v) for v in data[labelCol].to_list()]
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

    # Self-pin: the FIRST label layer carries the scale pin (domain=..., nice=False, zero=False) on
    # its datum encodings, forcing the shared x/y scale to the assumed domain so the connectors
    # align with the points WITHOUT the caller pinning the base chart's scale - and without any
    # invisible sidecar mark (the pin rides on real label marks, so nothing extra lands in the SVG).
    # All label geometry is emitted in DATA coordinates via alt.datum (the exact inverse of the
    # pinned pixel map): a datum contributes no axis title and does not extend the scale domain, so
    # the base chart's axes survive intact and the explicit pin is the only domain influence. NOTE
    # the domain is the label df's (niced) extent or an explicit xDomain/yDomain - when labeling a
    # SUBSET of a larger scatter, pass xDomain/yDomain covering the full data or the axes will clip
    # to the labeled points.
    # padding=0: placement runs in pixel space assuming the domain spans the full
    # [0, chartWidth]/[0, chartHeight] range; the pin wins the shared scale, so a
    # theme(viewPadding=...) chart with labels renders unpadded rather than misaligned
    x_scale = alt.Scale(domain=[x0, x1], nice=False, zero=False, padding=0)
    y_scale = alt.Scale(domain=[y0, y1], nice=False, zero=False, padding=0)
    pinned = False

    def datum_xy(px: float, py: float) -> dict[str, Any]:
        # x/y datum encodings for a pixel position; the first call attaches the scale pin.
        nonlocal pinned
        if pinned:
            return {"x": alt.XDatum(px_to_x(px)), "y": alt.YDatum(px_to_y(py))}
        pinned = True
        return {"x": alt.XDatum(px_to_x(px), scale=x_scale), "y": alt.YDatum(px_to_y(py), scale=y_scale)}

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
        # a center-justified edit keeps it aligned. The connector endpoint coincides with the text
        # anchor either way.
        if hw > 0 and hh > 0 and abs(dx) / hw >= abs(dy) / hh:
            align = "left" if dx <= 0 else "right"
            text_x = ex = lx - hw if dx <= 0 else lx + hw
            ey = ly
        else:
            align = "center"
            text_x = ex = lx
            ey = ly - hh if dy <= 0 else ly + hh
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


def add_shade(
    categories: list[str] | None = None,
    xCol: str | None = None,
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
    data: "pl.DataFrame | Any | None" = None,
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
            positions=[("Control", "Group B"), ("Group D", "Group E")],
            categories=CATEGORIES,
        )

        # positions mode — reference band on y (quantitative)
        shade = ds.add_shade(
            positions=[(5.0, 10.0)], axis='y', palette=["#E8F4F8"]
        )

        # positions mode — intersection rect, nominal x + quantitative y
        shade = ds.add_shade(
            positions=[(("Control", "Group B"), (8.0, 12.0))],
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
        ``(base + add_shade(positions=..., data=df))`` can be faceted and the shading repeats in
        every panel. Accepts polars or pandas. **Band mode** (``positions`` omitted) does not
        support ``data=`` and raises.
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
    # None means solid here (add_shade's documented default), so only True needs resolving.
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
        from .utils import ensure_polars

        if positions is None:
            raise ValueError("add_shade(data=...) is a facet-safe positions mode only; band mode does not support it.")
        src = ensure_polars(data)

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
        return base.mark_rect(**mark_kwargs, color=color).encode(**enc)

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
            x_geo = band_geometry(n, chart_width) if n else None
            y_geo = band_geometry(n, chart_height) if n else None
            if flush is None:
                flush = _opt("closed")

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
            geo = band_geometry(n, span)
            cat_index = {cat: i for i, cat in enumerate(categories)}

            if flush is None:
                flush = _opt("closed")

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
    geo = band_geometry(n, chart_width)

    if flush is None:
        flush = _opt("closed")

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
            alt.Chart(_internal_data(dummy_df))
            .mark_rect(**mark_kwargs, color=color_map[i])
            .encode(x=alt.value(left), x2=alt.value(right))
        )
        i = j

    return cast(alt.LayerChart, alt.layer(*run_layers))

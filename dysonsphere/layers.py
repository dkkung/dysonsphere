import math

import altair as alt
import polars as pl

from .utils import count_n

# Reference lines


def _rule_mark_kwargs(
    color: str | None,
    strokeWidth: float | None,
    strokeDash: bool | list[int] | None,
    opacity: float,
) -> dict:
    kwargs: dict = {"opacity": opacity}
    if color is not None:
        kwargs["color"] = color
    if strokeWidth is not None:
        kwargs["strokeWidth"] = strokeWidth
    if strokeDash is False:
        kwargs["strokeDash"] = [0, 0]
    elif strokeDash is True:
        kwargs["strokeDash"] = alt.theme.options.get("dashedWidth", [2, 2])
    elif isinstance(strokeDash, list):
        kwargs["strokeDash"] = strokeDash
    return kwargs


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

    Examples
    --------
    ::

        # Horizontal line at y=0
        chart = base + ds.add_rule(0)

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

    vals = value if isinstance(value, list) else [value]
    mark_kwargs = _rule_mark_kwargs(color, strokeWidth, strokeDash, opacity)
    fs = fontSize if fontSize is not None else alt.theme.options.get("fontSize", 7)

    if axis == "y":
        # Horizontal rule: value is a y-coordinate.
        # labelAlign: where along the line (x-axis): "left", "center", "right".
        # labelPosition: which side of the line (y-axis): "top", "bottom".
        df = pl.DataFrame({"__v": [float(v) for v in vals]})
        rule = alt.Chart(df).mark_rule(**mark_kwargs).encode(y=alt.Y("__v:Q", title=None))
        if label is None:
            return rule

        labels = [label] if isinstance(label, str) else list(label)
        if len(labels) != len(vals):
            raise ValueError(f"label has {len(labels)} items but value has {len(vals)}")

        la = labelAlign if labelAlign is not None else "left"
        lp = labelPosition if labelPosition is not None else "top"
        if la not in ("left", "center", "right"):
            raise ValueError(
                f"labelAlign must be 'left', 'center', or 'right' for axis='y', got {la!r}"
            )
        if lp not in ("top", "bottom"):
            raise ValueError(f"labelPosition must be 'top' or 'bottom' for axis='y', got {lp!r}")

        chart_width = alt.theme.options.get("chartWidth", 100)
        x_anchor = {"left": 0, "center": chart_width / 2, "right": chart_width}[la]
        base_dy = -3 if lp == "top" else 3
        vl_baseline = "bottom" if lp == "top" else "top"

        ldf = pl.DataFrame({"__v": [float(v) for v in vals], "__label": labels})
        text_kwargs: dict = {
            "align": la,
            "dx": labelOffsetX,
            "dy": base_dy + labelOffsetY,
            "baseline": vl_baseline,
            "fontSize": fs,
        }
        if color is not None:
            text_kwargs["color"] = color
        text = (
            alt.Chart(ldf)
            .mark_text(**text_kwargs)
            .encode(
                y=alt.Y("__v:Q", title=None),
                text=alt.Text("__label:N"),
                x=alt.value(x_anchor),
            )
        )
        return alt.layer(rule, text)

    else:  # axis == "x"
        # Vertical rule: value is an x-coordinate.
        # labelAlign: where along the line (y-axis): "top", "center", "bottom".
        # labelPosition: which side of the line (x-axis): "right", "left".
        df = pl.DataFrame({"__v": [float(v) for v in vals]})
        rule = alt.Chart(df).mark_rule(**mark_kwargs).encode(x=alt.X("__v:Q", title=None))
        if label is None:
            return rule

        labels = [label] if isinstance(label, str) else list(label)
        if len(labels) != len(vals):
            raise ValueError(f"label has {len(labels)} items but value has {len(vals)}")

        la = labelAlign if labelAlign is not None else "top"
        lp = labelPosition if labelPosition is not None else "right"
        if la not in ("top", "center", "bottom"):
            raise ValueError(
                f"labelAlign must be 'top', 'center', or 'bottom' for axis='x', got {la!r}"
            )
        if lp not in ("left", "right"):
            raise ValueError(f"labelPosition must be 'left' or 'right' for axis='x', got {lp!r}")

        chart_height = alt.theme.options.get("chartHeight", 100)
        y_anchor, vl_baseline = {
            "top": (0, "top"),
            "center": (chart_height / 2, "middle"),
            "bottom": (chart_height, "bottom"),
        }[la]
        base_dx = 3 if lp == "right" else -3
        vl_align = "left" if lp == "right" else "right"

        ldf = pl.DataFrame({"__v": [float(v) for v in vals], "__label": labels})
        text_kwargs = {
            "align": vl_align,
            "dx": base_dx + labelOffsetX,
            "dy": labelOffsetY,
            "baseline": vl_baseline,
            "fontSize": fs,
        }
        if color is not None:
            text_kwargs["color"] = color
        text = (
            alt.Chart(ldf)
            .mark_text(**text_kwargs)
            .encode(
                x=alt.X("__v:Q", title=None),
                text=alt.Text("__label:N"),
                y=alt.value(y_anchor),
            )
        )
        return alt.layer(rule, text)


_TEXT_PRESETS: dict[str, dict] = {
    "topLeft": {"x_frac": 0, "y_frac": 0, "align": "left", "baseline": "top"},
    "topCenter": {"x_frac": 0.5, "y_frac": 0, "align": "center", "baseline": "top"},
    "topRight": {"x_frac": 1, "y_frac": 0, "align": "right", "baseline": "top"},
    "middleLeft": {"x_frac": 0, "y_frac": 0.5, "align": "left", "baseline": "middle"},
    "middleCenter": {"x_frac": 0.5, "y_frac": 0.5, "align": "center", "baseline": "middle"},
    "middleRight": {"x_frac": 1, "y_frac": 0.5, "align": "right", "baseline": "middle"},
    "bottomLeft": {"x_frac": 0, "y_frac": 1, "align": "left", "baseline": "alphabetic"},
    "bottomCenter": {"x_frac": 0.5, "y_frac": 1, "align": "center", "baseline": "alphabetic"},
    "bottomRight": {"x_frac": 1, "y_frac": 1, "align": "right", "baseline": "alphabetic"},
}


def _is_alt_value(v) -> bool:
    return isinstance(v, dict) and "value" in v


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
) -> alt.Chart:
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
    """
    if position is not None and position not in _TEXT_PRESETS:
        raise ValueError(f"position must be one of {sorted(_TEXT_PRESETS)}, got {position!r}")

    # Resolve position — fills x/y/align/baseline only where not already provided
    if position is not None:
        p = _TEXT_PRESETS[position]
        cw = alt.theme.options.get("chartWidth", 100)
        ch = alt.theme.options.get("chartHeight", 100)
        # Auto-inset when text would touch the border or flush axis line.
        # Triggers when the plot has a closed box (closed=True) or the axis
        # sits flush with the plot edge (axisOffset=0). Center positions
        # (x_frac=0.5, y_frac=0.5) are unaffected.
        _closed = alt.theme.options.get("closed", False)
        _axis_offset = alt.theme.options.get("axisOffset", None)
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
        raise ValueError(
            f"text, x, and y must have the same length; got text={n}, x={len(xs)}, y={len(ys)}."
        )

    x_pixel = _is_alt_value(xs[0])
    y_pixel = _is_alt_value(ys[0])

    data: dict = {"__text": texts}
    if not x_pixel:
        data["__x"] = [float(v) if isinstance(v, (int, float)) else str(v) for v in xs]
    if not y_pixel:
        data["__y"] = [float(v) if isinstance(v, (int, float)) else str(v) for v in ys]

    df = pl.DataFrame(data)

    mark_kwargs: dict = {
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

    enc: dict = {"text": alt.Text("__text:N")}

    if x_pixel:
        enc["x"] = alt.value(xs[0]["value"])
    elif isinstance(xs[0], (int, float)):
        enc["x"] = alt.X("__x:Q", title=None)
    else:
        enc["x"] = alt.X("__x:N", title=None)

    if y_pixel:
        enc["y"] = alt.value(ys[0]["value"])
    elif isinstance(ys[0], (int, float)):
        enc["y"] = alt.Y("__y:Q", title=None)
    else:
        enc["y"] = alt.Y("__y:N", title=None)

    return alt.Chart(df).mark_text(**mark_kwargs).encode(**enc)


# Background shading


def add_shade(
    categories: list[str] | None = None,
    xCol: str | None = None,
    *,
    positions: list[tuple] | None = None,
    axis: str = "x",
    palette: list[str] | None = None,
    nShades: int = 2,
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
    """
    from .palettes import colors as _colors

    darkmode = alt.theme.options.get("darkmode", False)
    if darkmode:
        palette = _colors["greys"][-nShades:]
    else:
        if palette is None:
            palette = _colors["greys"]
        palette = palette[:nShades]

    n_colors = len(palette)
    resolved_dash = (
        alt.theme.options.get("dashedWidth", [2, 2]) if strokeDash is True else strokeDash
    )
    resolved_stroke_width = (
        (strokeWidth if strokeWidth is not None else alt.theme.options.get("axisWidth", 0.25))
        if stroke
        else 0
    )
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

        if axis == "both":
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
                        chart_width if (flush and ei == n - 1) else x_step * (band_padding + ei + 1)
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
                        chart_height
                        if (flush and ei == n - 1)
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
                layers.append(alt.Chart(df).mark_rect(**mark_kwargs, color=color).encode(**enc))

        elif len(positions) > 0 and isinstance(positions[0][0], str):
            # String tuples: category names on a nominal axis.
            # Convert to pixel coordinates using the band scale formula so the
            # shade layer does not participate in scale merging.
            if categories is None:
                raise ValueError("categories is required when positions contains string tuples.")
            band_padding = alt.theme.options.get("bandPadding", 0.1)
            n = len(categories)
            span = (
                alt.theme.options.get("chartHeight", 100)
                if axis == "y"
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
                    if axis == "y"
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
                if axis == "y":
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
    # step = range/(n + 2*bandPadding); band i spans [step*(bp+i), step*(bp+i+1)].
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


# Multilabel annotations


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
    plusminus_rows = [r for r in row_order if row_styles[r] == "plusminus"]
    text_rows = [r for r in row_order if row_styles[r] == "text"]
    symbol_rows = [r for r in row_order if row_styles[r] == "symbol"]

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
        tight_height = fontSize * 0.6 * max_len * math.sin(angle_rad) + fontSize * math.cos(
            angle_rad
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
            return "+" if v else "−"
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
        axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None),
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
        axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None),
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
        pm_df = marks_df.filter(pl.col("__label").is_in(plusminus_rows))
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
            negative_fill = colors["greys"][11]
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
            pl.col("__label").is_in(symbol_rows) & (pl.col("__value") == "−")
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
                            line_rows.append(
                                {"__category": cat, "__label": row_order[run[0]], "__line_id": _id}
                            )
                            line_rows.append(
                                {"__category": cat, "__label": row_order[run[-1]], "__line_id": _id}
                            )
                        run = []
                if len(run) >= 2:
                    _id = f"{cat}_{run[0]}_{run[-1]}"
                    line_rows.append(
                        {"__category": cat, "__label": row_order[run[0]], "__line_id": _id}
                    )
                    line_rows.append(
                        {"__category": cat, "__label": row_order[run[-1]], "__line_id": _id}
                    )

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

    return alt.layer(*layers).properties(
        width=chartWidth, height=chart_h, view={"fill": None, "stroke": None}
    )


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

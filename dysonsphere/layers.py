from typing import cast

import altair as alt
import polars as pl

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
        return cast(alt.LayerChart, alt.layer(rule, text))

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
        return cast(alt.LayerChart, alt.layer(rule, text))


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

        return cast(alt.LayerChart, alt.layer(*layers))

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

    return cast(alt.LayerChart, alt.layer(*run_layers))


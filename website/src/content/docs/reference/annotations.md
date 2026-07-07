---
title: "Annotations"
description: "Composable annotation layers: reference lines, text, shading, point labels."
sidebar:
  order: 3
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Composable chart annotations - reference lines, text, shading, and auto-placed point labels.

Every constructor returns an Altair chart/layer to compose onto a base chart with ``+``:
``add_rule`` (reference lines), ``add_text`` (positioned text), ``add_shade`` (background
shading), and ``add_labels`` (auto-placed point labels with connectors; the pixel placement
engine lives in ``_placement.py``). Statistical annotations (``add_comparisons``,
``add_correlation``) live in ``inference.py``.

## `add_rule`

```python
def add_rule(
    value: float | list[float],
    *,
    axis: str = 'y',
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
    data: pl.DataFrame | Any | None = None,
) -> alt.Chart | alt.LayerChart: ...
```

Add one or more horizontal or vertical reference lines to a chart.

Returns a layer that the caller composes with ``+``.

**Parameters**

- **`value`** (`float | list[float]`) - Coordinate(s) on the specified axis. ``float`` or ``list[float]``.
- **`axis`** (`str`) - ``"y"`` (default) — horizontal line(s) at fixed y value(s). ``"x"`` — vertical line(s) at fixed x value(s).
- **`label`** (`str | list[str] | None`) - Optional text label(s). One string per value.
- **`labelAlign`** (`str | None`) - Where *along* the line the label is anchored. ``axis="y"``: ``"left"`` (default), ``"center"``, or ``"right"``. ``axis="x"``: ``"top"`` (default), ``"center"``, or ``"bottom"``.
- **`labelPosition`** (`str | None`) - Which *side* of the line the label sits on. ``axis="y"``: ``"top"`` (default) or ``"bottom"``. ``axis="x"``: ``"right"`` (default) or ``"left"``.
- **`labelOffsetX`** (`int`) - Additional horizontal pixel offset applied to the label. Default ``0``. Positive shifts right, negative shifts left.
- **`labelOffsetY`** (`int`) - Additional vertical pixel offset applied to the label. Default ``0``. Positive shifts down, negative shifts up.
- **`color`** (`str | None`) - Line and label color. ``None`` inherits from the active theme.
- **`strokeWidth`** (`float | None`) - Line width in pixels. ``None`` inherits from the active theme.
- **`strokeDash`** (`bool | list[int] | None`) - ``None`` (default) inherits the theme's ``dashedRule`` setting. ``False`` forces a solid line. ``True`` uses the theme's ``dashedWidth`` pattern. A list (e.g. ``[4, 2]``) uses that pattern directly.
- **`opacity`** (`float`) - Line opacity. Defaults to ``1.0``.
- **`fontSize`** (`float | None`) - Label font size. ``None`` inherits from the active theme.
- **`data`** (`pl.DataFrame | Any | None`) - Facet-safe (datum) mode. ``None`` (default) builds the rule from its own small internal dataset — the normal behavior, but **incompatible with faceting** (Altair requires every layer of a faceted chart to share one data variable). Pass the **same DataFrame you gave the base chart** to switch to datum mode: the rule then shares that data and is positioned by a constant ``alt.datum`` instead of a sidecar dataset, so ``(base + add_rule(..., data=df))`` can be faceted and the line repeats in every panel. Accepts a polars or pandas DataFrame.

**Examples**

```python
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
```

## `add_text`

```python
def add_text(
    text: str | list[str],
    x = None,
    y = None,
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
    data: pl.DataFrame | Any | None = None,
) -> alt.Chart | alt.LayerChart: ...
```

Add one or more text annotations to a chart.

Returns a layer that the caller composes with ``+``.

**Parameters**

- **`text`** (`str | list[str]`) - Annotation string(s). Pass a list to place multiple annotations in one call — ``x`` and ``y`` must then also be lists of equal length.
- **`x`** - Horizontal coordinate(s). Three forms are accepted: - ``float`` / ``int`` — data coordinate on a quantitative x axis. Shares the main chart's x scale automatically. - ``str`` — category name on a nominal x axis. Shares the main chart's band scale, placing the text at the band center. - ``alt.value(n)`` — fixed pixel position, ``n`` pixels from the left edge of the plot area. Use this (or ``position``) for annotations that should not move with the data. Required when ``position`` is not set.
- **`y`** - Vertical coordinate(s). Same three forms as ``x``, measured from the top of the plot area for ``alt.value()``. Required when ``position`` is not set.
- **`position`** (`str | None`) - Named position within the plot area, flush with the axis domain edges. Sets ``x``, ``y``, ``align``, and ``baseline`` automatically using ``alt.value()`` pixel coordinates derived from ``chartWidth`` / ``chartHeight`` in the active theme. Explicit ``x``, ``y``, ``align``, or ``baseline`` arguments override the position value for that parameter. Valid positions (3 × 3 grid): +------------------+--------------------+-------------------+ | ``"topLeft"`` | ``"topCenter"`` | ``"topRight"`` | +------------------+--------------------+-------------------+ | ``"middleLeft"`` | ``"middleCenter"`` | ``"middleRight"`` | +------------------+--------------------+-------------------+ | ``"bottomLeft"`` | ``"bottomCenter"`` | ``"bottomRight"`` | +------------------+--------------------+-------------------+ When ``closed=True`` or ``axisOffset=0`` in the active theme, a fixed 1 px inset is applied automatically to edge positions so text clears the border or flush axis line. ``offsetX`` / ``offsetY`` add on top of this for further fine-tuning:: chart + ds.add_text("p = 0.003", position="topRight", offsetX=-4, offsetY=4)
- **`angle`** (`float`) - Rotation in degrees, clockwise. Vega-Lite requires values in [0, 360]; negative values are wrapped automatically. Defaults to ``0``.
- **`align`** (`str | None`) - Horizontal text anchor: ``"left"`` (default), ``"center"``, or ``"right"``. Overrides the position value when both are set.
- **`baseline`** (`str | None`) - Vertical text anchor: ``"top"``, ``"middle"`` (default), ``"bottom"``, or ``"alphabetic"``. ``"middle"`` centers the text body on the y coordinate — best for annotations near symbols or rules. ``"alphabetic"`` sits the reading baseline on y — best when text sits alongside other typeset text. Overrides the position value when both are set.
- **`offsetX`** (`int`) - Horizontal pixel nudge applied after positioning. Positive shifts right. Useful for inset when using ``position``.
- **`offsetY`** (`int`) - Vertical pixel nudge applied after positioning. Positive shifts down. Useful for inset when using ``position``.
- **`color`** (`str | None`) - Text color. ``None`` inherits from the active theme's ``mark_text`` config.
- **`fontSize`** (`float | None`) - Font size in points. ``None`` inherits from the active theme.
- **`fontWeight`** (`str | None`) - ``"normal"``, ``"bold"``, or a numeric CSS weight (``100``–``900``). ``None`` inherits from the active theme.
- **`fontStyle`** (`str | None`) - ``"normal"`` or ``"italic"``. ``None`` inherits from the active theme.
- **`font`** (`str | None`) - Font family name (e.g. ``"sans-serif"``, ``"Georgia"``). ``None`` inherits from the active theme.
- **`opacity`** (`float`) - Text opacity. Defaults to ``1.0``.
- **`data`** (`pl.DataFrame | Any | None`) - Facet-safe (datum) mode. ``None`` (default) builds the annotation from its own internal dataset — the normal behavior, but **incompatible with faceting**. Pass the **same DataFrame you gave the base chart** to share its data and position the text by ``alt.datum`` (data coordinates) / ``alt.value`` (pixels), so ``(base + add_text(..., data=df))`` can be faceted and the text repeats in every panel. Accepts a polars or pandas DataFrame.

**Examples**

```python
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
```

## `add_labels`

```python
def add_labels(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    labelCol: str,
    *,
    labels: int | list | None = None,
    xDomain: tuple[float, float] | None = None,
    yDomain: tuple[float, float] | None = None,
    fontSize: float | None = None,
    color: str | None = None,
    connector: bool = True,
    connectorColor: str | None = None,
    connectorStrokeDash: bool | list[int] = False,
    connectorGap: float | None = None,
    alwaysShowConnectors: bool = False,
) -> alt.LayerChart: ...
```

Auto-place non-overlapping text labels for a set of points, with connector lines.

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

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - The plotted data (polars or pandas) - pass the same frame as the base chart. The axis domain is inferred from its full extent, so the connectors line up without you pinning the base scale (the label layers pin it themselves; see below).
- **`xCol`** (`str`) - Quantitative coordinate columns (must match the base chart's x / y encodings).
- **`yCol`** (`str`) - Quantitative coordinate columns (must match the base chart's x / y encodings).
- **`labelCol`** (`str`) - Column holding the label text.
- **`labels`** (`int | list | None`) - Which rows to label. ``None`` (default) labels every row; an **int `n`** auto-selects `n` rows spread evenly across the plot (unbiased - no cherry-picking, deterministic); a **list** labels only the rows whose ``labelCol`` value is in it (e.g. ``labels=["TP53", "EGFR"]``). Pass the full plotted ``df`` and let ``labels`` do the selecting - the domain is inferred from all of ``df``, so selecting a subset never clips the axes.
- **`xDomain`** (`tuple[float, float] | None`) - ``(min, max)`` axis domains, forced onto the shared scale (``nice=False``, ``zero=False``). Default: the **extent of the passed ``df``'s ``xCol`` / ``yCol``, rounded outward to nice tick bounds** (d3-style nice, so the axes end on round numbers; filtering ``df`` just moves the axes with it - always inferred). An explicit value is used exactly as given (no rounding). Pass explicitly only when you want the axes to span a range the passed ``df`` does not cover - i.e. the base chart plots more than you hand ``add_labels`` (a deliberate subset, or **derived positions** like cluster centroids whose extent is tighter than the scatter).
- **`yDomain`** (`tuple[float, float] | None`) - ``(min, max)`` axis domains, forced onto the shared scale (``nice=False``, ``zero=False``). Default: the **extent of the passed ``df``'s ``xCol`` / ``yCol``, rounded outward to nice tick bounds** (d3-style nice, so the axes end on round numbers; filtering ``df`` just moves the axes with it - always inferred). An explicit value is used exactly as given (no rounding). Pass explicitly only when you want the axes to span a range the passed ``df`` does not cover - i.e. the base chart plots more than you hand ``add_labels`` (a deliberate subset, or **derived positions** like cluster centroids whose extent is tighter than the scatter).
- **`fontSize`** (`float | None`) - Label font size. ``None`` -> the theme's ``fontSize`` (the primary chart font size).
- **`color`** (`str | None`) - Label text color. ``None`` -> inherits the theme's ``mark_text`` color (darkmode-aware black/white).
- **`connector`** (`bool`) - Whether to draw the line connecting each point to its label (default ``True``).
- **`connectorColor`** (`str | None`) - Connector line color. ``None`` -> inherits the theme's ``mark_rule`` color (darkmode-aware). Connectors otherwise inherit the theme's rule style (rounded caps, ``axisWidth`` stroke, opaque).
- **`connectorStrokeDash`** (`bool | list[int]`) - Connector dash pattern. ``False`` (default) -> solid; ``True`` -> the theme's ``dashedWidth`` pattern; a list (e.g. ``[4, 2]``) -> that pattern directly.
- **`connectorGap`** (`float | None`) - Pixel gap left at the MARKER end of the connector so it points at the dot rather than piercing it. ``None`` (default) -> the theme's ``mark_point`` edge radius plus two connector stroke widths of whitespace (``sqrt(markSize/2/pi) + markStrokeWidth + 2*axisWidth``), which clears the default point mark (and the smaller ``mark_circle``) with a visible sliver of daylight at any theme scale; ``0`` -> no marker gap; a float -> that many pixels (set this for unusually large or heavily stroked markers, which the gap can't measure since the base chart isn't visible here). The TEXT end always keeps just the whitespace term (``2*axisWidth`` - there is no marker to clear there, so a symmetric gap would open a hole between line and label). Both gaps are uniform - they never shrink, so every drawn connector sits the same distance off its dot and its label; a connector too short to keep the full gaps is dropped instead (see ``alwaysShowConnectors``).
- **`alwaysShowConnectors`** (`bool`) - By default (``False``) a connector is omitted when the full end gaps would leave less than four connector stroke widths of visible line (length < ``connectorGap + 6*axisWidth``, i.e. < 1 px of line at the default theme) - the stub is just noise and the adjacent label is unambiguous. This threshold is font-independent (tied to the marker gap), so changing the label font never drops real leaders. ``True`` draws every one (sub-threshold stubs shrink their gaps to fit).

## `add_shade`

```python
def add_shade(
    categories: list[str] | None = None,
    xCol: str | None = None,
    *,
    positions: list[tuple] | None = None,
    axis: str = 'x',
    palette: list[str] | None = None,
    nShades: int = 2,
    repeat: int = 1,
    opacity: float = 1.0,
    stroke: bool = False,
    strokeWidth: float | None = None,
    strokeDash: list[float] | bool | None = None,
    flush: bool | None = None,
    data: pl.DataFrame | Any | None = None,
) -> alt.LayerChart: ...
```

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

**Parameters**

- **`categories`** (`list[str] | None`) - Ordered list of axis categories. Required for band mode. Also required in positions mode when any tuple values are strings.
- **`xCol`** (`str | None`) - Column name for the x-axis grouping variable (band mode only; not used internally).
- **`positions`** (`list[tuple] | None`) - List of ``(start, end)`` tuples (single-axis) or ``((x_start, x_end), (y_start, y_end))`` tuples (``axis='both'``) defining explicit shade regions. Activates positions mode; ``repeat`` and ``flush`` are used only when tuple values are strings.
- **`axis`** (`str`) - ``'x'`` (default), ``'y'``, or ``'both'``. Controls which axis the shading runs along. ``'both'`` draws intersection rects spanning an explicit x-range and y-range simultaneously. Ignored in band mode (always ``'x'``).
- **`palette`** (`list[str] | None`) - List of hex color strings to cycle through in light mode. Defaults to ``"greys"`` when ``None``. In dark mode this parameter is always ignored — the darkest ``nShades`` stops of ``"greys"`` are used regardless. Resolved at call time; pass a callable to ``ds.save()`` for correct darkmode rendering.
- **`nShades`** (`int`) - Number of colors to use. In light mode, slices the first ``nShades`` stops from ``palette`` (or ``"greys"``). In dark mode, slices the last ``nShades`` stops of ``"greys"``. Defaults to ``2``.
- **`repeat`** (`int`) - Number of consecutive ticks sharing the same color before advancing (band mode only). Defaults to ``1``.
- **`opacity`** (`float`) - Fill opacity of the shade rects. Defaults to ``1.0``.
- **`stroke`** (`bool`) - Enable a border on the shade rects. ``False`` (default) → no stroke. ``True`` → axis-style stroke: color from theme darkmode state (black / white), width from ``axisWidth``.
- **`strokeWidth`** (`float | None`) - Explicit border width in pixels. Overrides ``axisWidth`` when ``stroke=True``. Has no effect when ``stroke=False``.
- **`strokeDash`** (`list[float] | bool | None`) - Dash pattern for the rect border. ``None`` (default) → solid. ``True`` → inherit ``dashedWidth`` from the active theme. A list (e.g. ``[4, 2]``) → use that pattern directly.
- **`flush`** (`bool | None`) - Extend the outermost rects to the axis domain edge (band mode and string positions only). ``None`` inherits from the theme's ``closed`` setting.
- **`data`** (`pl.DataFrame | Any | None`) - Facet-safe (datum) mode, **positions mode only**. ``None`` (default) builds each rect from its own internal dataset — the normal behavior, but **incompatible with faceting**. Pass the **same DataFrame you gave the base chart** to share its data and position numeric ranges by ``alt.datum`` (string/pixel ranges already use ``alt.value``), so ``(base + add_shade(positions=..., data=df))`` can be faceted and the shading repeats in every panel. Accepts polars or pandas. **Band mode** (``positions`` omitted) does not support ``data=`` and raises.

---
title: "Annotations"
description: "Composable annotation layers: reference lines, text, shading, point labels."
sidebar:
  order: 1
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Composable chart annotations - reference lines, text, shading, and auto-placed point labels.

Every constructor returns an Altair chart/layer to compose onto a base chart with ``+``:
``rule`` (reference lines), ``text`` (positioned text), ``shade`` (background
shading), and ``labels`` (auto-placed point labels with connectors; the pixel placement
engine lives in ``_placement.py``). Statistical annotations (``comparisons``,
``correlation``) live in ``stats.py``.

## `rule`

```python
def rule(
    *,
    x: float | list[float] | None = None,
    y: float | list[float] | None = None,
    x2: float | None = None,
    y2: float | None = None,
    slope: float | None = None,
    intercept: float = 0,
    span: tuple[float, float] | tuple[str, str] | None = None,
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
    startCap: Literal['arrow', 'circle', 'square'] | None = None,
    endCap: Literal['arrow', 'circle', 'square'] | None = None,
    startGap: float | None = None,
    endGap: float | None = None,
    data: pl.DataFrame | pd.DataFrame | None = None,
) -> alt.Chart | alt.LayerChart: ...
```

Add a horizontal, vertical, diagonal, or equation reference line to a chart.

Returns a layer that the caller composes with ``+``.

**Parameters**

- **`x`** (`float | list[float] | None`) - Primary data coordinates. Supply only ``y`` for horizontal rules or only ``x`` for vertical rules; either may be a list in those modes. Supply both for a bounded or diagonal rule, completed by ``x2`` and/or ``y2`` as described below. Lists also remain supported for the fixed coordinate of bounded horizontal or vertical rules; diagonal endpoints are scalar.
- **`y`** (`float | list[float] | None`) - Primary data coordinates. Supply only ``y`` for horizontal rules or only ``x`` for vertical rules; either may be a list in those modes. Supply both for a bounded or diagonal rule, completed by ``x2`` and/or ``y2`` as described below. Lists also remain supported for the fixed coordinate of bounded horizontal or vertical rules; diagonal endpoints are scalar.
- **`x2`** (`float | None`) - Secondary endpoint coordinates. ``x, x2, y`` makes a bounded horizontal rule; ``x, y, y2`` makes a bounded vertical rule; all four coordinates make a diagonal segment. Secondary endpoints cannot be combined with ``span``.
- **`y2`** (`float | None`) - Secondary endpoint coordinates. ``x, x2, y`` makes a bounded horizontal rule; ``x, y, y2`` makes a bounded vertical rule; all four coordinates make a diagonal segment. Secondary endpoints cannot be combined with ``span``.
- **`slope`** (`float | None`) - Equation mode. ``slope`` draws ``y = slope*x + intercept`` over the numeric x extent given by the required ``span``. ``intercept`` defaults to ``0``. This computes an ordinary endpoint segment and therefore represents the equation only on linear quantitative axes.
- **`intercept`** (`float | None`) - Equation mode. ``slope`` draws ``y = slope*x + intercept`` over the numeric x extent given by the required ``span``. ``intercept`` defaults to ``0``. This computes an ordinary endpoint segment and therefore represents the equation only on linear quantitative axes.
- **`span`** (`tuple[float, float] | tuple[str, str] | None`) - Required x extent in equation mode, or optionally slice an axis-aligned line to a portion of its *running* axis, given as a ``(start, end)`` tuple. ``None`` (default) spans the full plot. A horizontal line runs along x and a vertical line runs along y. Two forms, mirroring ``shade``: - **Numeric** ``(start, end)`` — data coordinates on the running axis; shares the base chart's scale (positioned by ``alt.datum``). - **Category names** ``(start, end)`` — resolved to pixels via the band scale (needs ``categories``), so the slice does not merge into the base scale. A single ``span`` applies to every fixed coordinate when it is a list. When ``span`` is set, a ``label`` anchors to the slice's ends instead of the plot edge.
- **`categories`** (`list[str] | None`) - Ordered list of the running axis's categories, required only when ``span`` uses category names (for the band-scale index lookup).
- **`flush`** (`bool | None`) - For a category-name ``span``, extend an outermost-category endpoint to the axis domain edge. ``None`` (default) inherits the theme's ``closed`` setting. No effect on a numeric ``span``.
- **`label`** (`str | list[str] | None`) - Optional text label(s). One string per fixed coordinate; diagonal/equation rules accept one.
- **`labelAlign`** (`str | None`) - Where *along* the line the label is anchored. Horizontal: ``"left"`` (default), ``"center"``, or ``"right"``. Vertical: ``"top"`` (default), ``"center"``, or ``"bottom"``. Diagonal/equation: ``"left"`` (default), ``"center"``, or ``"right"``. Left and right select the smaller and larger x coordinates, respectively; center uses the data-coordinate midpoint. These definitions do not inspect or change the composed chart's scales.
- **`labelPosition`** (`str | None`) - Which *side* of the line the label sits on. Horizontal: ``"top"`` (default) or ``"bottom"``. Vertical: ``"right"`` (default) or ``"left"``. Diagonal/equation labels remain horizontal and use ``"top"`` (default) or ``"bottom"``.
- **`labelOffsetX`** (`float`) - Additional horizontal pixel offset applied to the label. Default ``0``. Positive shifts right, negative shifts left.
- **`labelOffsetY`** (`float`) - Additional vertical pixel offset applied to the label. Default ``0``. Positive shifts down, negative shifts up.
- **`color`** (`str | None`) - Line and label color. ``None`` inherits from the active theme.
- **`strokeWidth`** (`float | None`) - Line width in pixels. ``None`` inherits from the active theme.
- **`strokeDash`** (`bool | list[int | float] | None`) - ``None`` (default) inherits the theme's ``dashedRule`` setting. ``False`` forces a solid line. ``True`` uses the theme's ``dashedWidth`` pattern. A list (e.g. ``[4, 2]``) uses that pattern directly.
- **`opacity`** (`float`) - Line opacity. Defaults to ``1.0``.
- **`fontSize`** (`float | None`) - Label font size. ``None`` inherits from the active theme.
- **`startCap`** (`Literal['arrow', 'circle', 'square'] | None`) - Optional endpoint decoration: ``"arrow"``, ``"circle"``, or ``"square"``. Start is the primary endpoint and end is the secondary endpoint, preserving explicit endpoint/span order even on reversed scales. For an implicit full-span horizontal rule start/end are the left/right plot edges; for a full-span vertical rule they are the top/bottom edges. Decorations are sized from the rendered rule width. Arrow depth is ``4 * sqrt(strokeWidth)`` pixels (2 px at the default 0.25 px stroke), while circles and squares have a 4 px minimum size.
- **`endCap`** (`Literal['arrow', 'circle', 'square'] | None`) - Optional endpoint decoration: ``"arrow"``, ``"circle"``, or ``"square"``. Start is the primary endpoint and end is the secondary endpoint, preserving explicit endpoint/span order even on reversed scales. For an implicit full-span horizontal rule start/end are the left/right plot edges; for a full-span vertical rule they are the top/bottom edges. Decorations are sized from the rendered rule width. Arrow depth is ``4 * sqrt(strokeWidth)`` pixels (2 px at the default 0.25 px stroke), while circles and squares have a 4 px minimum size.
- **`startGap`** (`float | None`) - Nonnegative finite pixel clearance between the target coordinate and the decoration's outermost tip/edge. ``None`` derives the same theme-aware marker clearance used by point-label connectors when that endpoint has a cap, and means 0 otherwise; explicit 0 is respected. Gaps also shorten capless rules. The resolved value is stored at construction, so use a callable with ``ds.save()`` when exporting across themes with different geometry. Caps and gaps are applied by the shared SVG pipeline (and therefore PNG export), not bare Altair display or interactive HTML. A screen-coincident or too-short segment is omitted rather than shrinking a requested gap or drawing decorations beyond the opposite target.
- **`endGap`** (`float | None`) - Nonnegative finite pixel clearance between the target coordinate and the decoration's outermost tip/edge. ``None`` derives the same theme-aware marker clearance used by point-label connectors when that endpoint has a cap, and means 0 otherwise; explicit 0 is respected. Gaps also shorten capless rules. The resolved value is stored at construction, so use a callable with ``ds.save()`` when exporting across themes with different geometry. Caps and gaps are applied by the shared SVG pipeline (and therefore PNG export), not bare Altair display or interactive HTML. A screen-coincident or too-short segment is omitted rather than shrinking a requested gap or drawing decorations beyond the opposite target.
- **`data`** (`pl.DataFrame | pd.DataFrame | None`) - Facet-safe (datum) mode. ``None`` (default) builds the rule from its own small internal dataset — the normal behavior, but **incompatible with faceting** (Altair requires every layer of a faceted chart to share one data variable). Pass the **same DataFrame you gave the base chart** to switch to datum mode: the rule then shares that data and is positioned by a constant ``alt.datum`` instead of a sidecar dataset, so ``(base + rule(..., data=df))`` can be faceted and the line repeats in every panel. Accepts a polars or pandas DataFrame.

**Examples**

```python
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
```

## `text`

```python
def text(
    text: str | list[str],
    x = None,
    y = None,
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
    data: pl.DataFrame | pd.DataFrame | None = None,
) -> alt.Chart | alt.LayerChart: ...
```

Add one or more text annotations to a chart.

Returns a layer that the caller composes with ``+``.

**Parameters**

- **`text`** (`str | list[str]`) - Annotation string(s). Pass a list to place multiple annotations in one call — ``x`` and ``y`` must then also be lists of equal length.
- **`x`** - Horizontal coordinate(s). Three forms are accepted: - ``float`` / ``int`` — data coordinate on a quantitative x axis. Shares the main chart's x scale automatically. - ``str`` — category name on a nominal x axis. Shares the main chart's band scale, placing the text at the band center. - ``alt.value(n)`` — fixed pixel position, ``n`` pixels from the left edge of the plot area. Use this (or ``position``) for annotations that should not move with the data. Required when ``position`` is not set.
- **`y`** - Vertical coordinate(s). Same three forms as ``x``, measured from the top of the plot area for ``alt.value()``. Required when ``position`` is not set.
- **`position`** (`str | None`) - Named position within the plot area, flush with the axis domain edges. Sets ``x``, ``y``, ``align``, and ``baseline`` automatically using ``alt.value()`` pixel coordinates derived from ``chartWidth`` / ``chartHeight`` in the active theme. Explicit ``x``, ``y``, ``align``, or ``baseline`` arguments override the position value for that parameter. Valid positions (3 × 3 grid): +------------------+--------------------+-------------------+ | ``"topLeft"`` | ``"topCenter"`` | ``"topRight"`` | +------------------+--------------------+-------------------+ | ``"middleLeft"`` | ``"middleCenter"`` | ``"middleRight"`` | +------------------+--------------------+-------------------+ | ``"bottomLeft"`` | ``"bottomCenter"`` | ``"bottomRight"`` | +------------------+--------------------+-------------------+ When ``closed=True`` or ``axisOffset=0`` in the active theme, a fixed 1 px inset is applied automatically to edge positions so text clears the border or flush axis line. ``offsetX`` / ``offsetY`` add on top of this for further fine-tuning:: chart + ds.text("p = 0.003", position="topRight", offsetX=-4, offsetY=4)
- **`angle`** (`float`) - Rotation in degrees, clockwise. Vega-Lite requires values in [0, 360]; negative values are wrapped automatically. Defaults to ``0``.
- **`align`** (`str | None`) - Horizontal text anchor: ``"left"`` (default), ``"center"``, or ``"right"``. Overrides the position value when both are set.
- **`baseline`** (`str | None`) - Vertical text anchor: ``"top"``, ``"middle"`` (default), ``"bottom"``, or ``"alphabetic"``. ``"middle"`` centers the text body on the y coordinate — best for annotations near symbols or rules. ``"alphabetic"`` sits the reading baseline on y — best when text sits alongside other typeset text. Overrides the position value when both are set.
- **`offsetX`** (`float`) - Horizontal pixel nudge applied after positioning. Positive shifts right. Useful for inset when using ``position``.
- **`offsetY`** (`float`) - Vertical pixel nudge applied after positioning. Positive shifts down. Useful for inset when using ``position``.
- **`color`** (`str | None`) - Text color. ``None`` inherits from the active theme's ``mark_text`` config.
- **`fontSize`** (`float | None`) - Font size in points. ``None`` inherits from the active theme.
- **`fontWeight`** (`str | None`) - ``"normal"``, ``"bold"``, or a numeric CSS weight (``100``–``900``). ``None`` inherits from the active theme.
- **`fontStyle`** (`str | None`) - ``"normal"`` or ``"italic"``. ``None`` inherits from the active theme.
- **`font`** (`str | None`) - Font family name (e.g. ``"sans-serif"``, ``"Georgia"``). ``None`` inherits from the active theme.
- **`opacity`** (`float`) - Text opacity. Defaults to ``1.0``.
- **`fill`** (`str | bool`) - Background fill behind the text (a rect chip). ``False`` (default) -> none; ``True`` -> a darkmode-aware default (``greys[0]`` light / ``greys[11]`` dark); a string -> that color. Read at build time (like ``shade``), so a ``save()`` across backgrounds needs a callable to re-resolve it. The chip is sized from a rough text estimate (proportional fonts vary, so it is approximate) plus padding.
- **`fillOpacity`** (`float`) - Opacity of the background fill (``0``-``1``). Defaults to ``1.0``. Ignored when ``fill`` is off.
- **`stroke`** (`str | bool`) - Border of the background chip. ``True`` (default) -> a darkmode-aware default (``"black"`` light / ``"white"`` dark); ``False`` -> no border; a string -> that color. Only takes effect when a chip is drawn (i.e. when ``fill`` is set) - it borders the fill, it does not create a chip on its own.
- **`cornerRadius`** (`float | bool`) - Corner rounding of the background chip. ``True`` (default) -> ``fontSize * 0.25``; ``False`` -> ``0`` (square); an explicit float -> that radius in px. Ignored when no chip is drawn.
- **`data`** (`pl.DataFrame | pd.DataFrame | None`) - Facet-safe (datum) mode. ``None`` (default) builds the annotation from its own internal dataset — the normal behavior, but **incompatible with faceting**. Pass the **same DataFrame you gave the base chart** to share its data and position the text by ``alt.datum`` (data coordinates) / ``alt.value`` (pixels), so ``(base + text(..., data=df))`` can be faceted and the text repeats in every panel. Accepts a polars or pandas DataFrame.

**Examples**

```python
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
```

## `labels`

```python
def labels(
    data: pl.DataFrame | pd.DataFrame,
    x: str,
    y: str,
    labels: str,
    *,
    subset: int | list[Any] | Any | None = None,
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
    connectorCap: Literal['arrow'] | None = None,
    connectorColor: str | None = None,
    connectorOpacity: float | None = None,
    connectorStrokeDash: bool | list[int | float] = False,
    connectorGap: float | None = None,
    alwaysShowConnectors: bool = False,
) -> alt.LayerChart: ...
```

Auto-place non-overlapping text labels for a set of points, with connector lines.

Force-directed placement (deterministic - reproducible figures) nudges each label off its
point and away from the others, drawing a thin leader line from each point to its label. Every
requested label is shown (never dropped); in an impossibly dense region labels settle at their
least-overlapping positions. Returns a layer to compose onto the base chart with ``+``.

Placement is solved in pixels before Vega renders, but each label is emitted as a pixel offset
from its own marker, so it lands correctly on whatever scale the base chart uses and the base's
axes are left alone. Just compose ``base + ds.labels(data, ...)``.

**Parameters**

- **`data`** (`pl.DataFrame | pd.DataFrame`) - The plotted data (polars or pandas) - pass the same frame as the base chart.
- **`x`** (`str`) - Quantitative coordinate columns (must match the base chart's x / y encodings).
- **`y`** (`str`) - Quantitative coordinate columns (must match the base chart's x / y encodings).
- **`labels`** (`str`) - Column holding the label text.
- **`subset`** (`int | list[Any] | Any | None`) - Which rows to label. ``None`` (default) labels every row; an **int `n`** auto-selects `n` rows spread evenly across the plot (unbiased - no cherry-picking, deterministic); a **boolean mask** (a pandas/polars ``Series``, NumPy array, or list of bools with one entry per row of ``data``) selects rows **positionally** - decoupled from ``labels``, so a non-unique label column still picks exactly the intended rows (e.g. ``subset=data["is_hit"]``); any other **list** labels the rows whose ``labels`` value is in it (e.g. ``subset=["TP53", "EGFR"]``, which needs a unique ``labels``). Pass the full plotted ``data`` and let ``subset`` do the selecting: obstacles and the axis domain both span all of ``data``, so the labels dodge EVERY plotted point (not just the labelled subset) and selecting a subset never clips the axes.
- **`xDomain`** (`tuple[float, float] | None`) - ``(min, max)`` the placement solver assumes the base chart will render. Default: the extent of ``data``'s ``x`` / ``y``. A mismatch only degrades collision avoidance - labels stay attached to their markers either way. Pass explicitly when the base chart's domain differs from ``data``'s extent (a zoomed axis, or derived positions like centroids).
- **`yDomain`** (`tuple[float, float] | None`) - ``(min, max)`` the placement solver assumes the base chart will render. Default: the extent of ``data``'s ``x`` / ``y``. A mismatch only degrades collision avoidance - labels stay attached to their markers either way. Pass explicitly when the base chart's domain differs from ``data``'s extent (a zoomed axis, or derived positions like centroids).
- **`fontSize`** (`float | None`) - Label font size. ``None`` -> the theme's ``fontSize`` (the primary chart font size).
- **`fontStyle`** (`str | None`) - Label font style, e.g. ``"italic"`` (gene / species names) or ``"bold"``. ``None`` (default) inherits the theme's ``mark_text`` (upright). Applies to every label.
- **`color`** (`str | None`) - Label text color. ``None`` -> inherits the theme's ``mark_text`` color (darkmode-aware black/white).
- **`fill`** (`str | bool`) - Background fill behind each label (a rect chip - useful over a dense scatter). ``False`` (default) -> none; ``True`` -> a darkmode-aware default (``greys[0]`` light / ``greys[11]`` dark); a string -> that color. Read at build time (like ``shade``), so a ``save()`` across backgrounds needs a callable. The connector meets the chip's edge, and the text is centred inside the chip (overriding the side justification a bare label would use).
- **`fillOpacity`** (`float`) - Opacity of the background fill (``0``-``1``). Defaults to ``1.0``. Ignored when ``fill`` is off.
- **`stroke`** (`str | bool`) - Border of the background chip. ``True`` (default) -> a darkmode-aware default (``"black"`` light / ``"white"`` dark); ``False`` -> no border; a string -> that color. Only takes effect when a chip is drawn (i.e. when ``fill`` is set).
- **`cornerRadius`** (`float | bool`) - Corner rounding of the background chip. ``True`` (default) -> ``fontSize * 0.25``; ``False`` -> ``0`` (square); an explicit float -> that radius in px. Ignored when no chip is drawn.
- **`connector`** (`bool`) - Whether to draw the line connecting each point to its label (default ``True``).
- **`connectorCap`** (`Literal['arrow'] | None`) - Optional ``"arrow"`` at the point-facing end of each connector. The arrow points toward the target point and uses the existing ``connectorGap`` exactly once; no additional cap gap is added. ``None`` (default) leaves connector specs and rendering unchanged. A valid cap is a harmless inactive setting when ``connector=False``. Caps are applied in ``ds.save()`` SVG/PNG and ``ds.show()``, not bare Altair or interactive HTML. If the post-gap rendered connector is too short for the fixed arrow geometry, that connector is omitted rather than shrinking the arrow or moving the label; all requested labels remain shown. This also applies when ``alwaysShowConnectors=True``.
- **`connectorColor`** (`str | None`) - Connector line color. ``None`` -> inherits the theme's ``mark_rule`` color (darkmode-aware). Connectors otherwise inherit the theme's rule style (rounded caps, ``axisWidth`` stroke, opaque).
- **`connectorOpacity`** (`float | None`) - Connector line opacity, ``0``-``1``. ``None`` (default) -> inherits the theme's ``mark_rule`` opacity (opaque). Sets only the mark opacity, leaving the (darkmode-aware) color intact, so a faded leader - e.g. ``connectorOpacity=0.5`` to quiet the leaders relative to the labels - stays legible in both light and dark mode.
- **`connectorStrokeDash`** (`bool | list[int | float]`) - Connector dash pattern. ``False`` (default) -> solid; ``True`` -> the theme's ``dashedWidth`` pattern; a list (e.g. ``[4, 2]``) -> that pattern directly.
- **`connectorGap`** (`float | None`) - Pixel gap left at the MARKER end of the connector so it points at the dot rather than piercing it. ``None`` (default) -> the theme's ``mark_point`` edge radius plus two connector stroke widths of whitespace (``sqrt(markSize/2/pi) + markStrokeWidth + 2*axisWidth``), which clears the default point mark (and the smaller ``mark_circle``) with a visible sliver of daylight at any theme scale; ``0`` -> no marker gap; a float -> that many pixels (set this for unusually large or heavily stroked markers, which the gap can't measure since the base chart isn't visible here). The TEXT end always keeps just the whitespace term (``2*axisWidth`` - there is no marker to clear there, so a symmetric gap would open a hole between line and label). Both gaps are uniform - they never shrink, so every drawn connector sits the same distance off its dot and its label; a connector too short to keep the full gaps is dropped instead (see ``alwaysShowConnectors``).
- **`alwaysShowConnectors`** (`bool`) - By default (``False``) a connector is omitted when the full end gaps would leave less than four connector stroke widths of visible line (length < ``connectorGap + 6*axisWidth``, i.e. < 1 px of line at the default theme) - the stub is just noise and the adjacent label is unambiguous. This threshold is font-independent (tied to the marker gap), so changing the label font never drops real leaders. ``True`` draws every one (sub-threshold stubs shrink their gaps to fit).

## `shade`

```python
def shade(
    categories: list[str] | None = None,
    *,
    positions: list[tuple[Any, ...]] | None = None,
    axis: str = 'x',
    palette: list[str] | None = None,
    nShades: int = 2,
    repeat: int = 1,
    opacity: float = 1.0,
    stroke: bool = False,
    strokeWidth: float | None = None,
    strokeDash: list[float] | bool | None = None,
    flush: bool | None = None,
    data: pl.DataFrame | pd.DataFrame | None = None,
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

**Parameters**

- **`categories`** (`list[str] | None`) - Ordered list of axis categories. Required for band mode. Also required in positions mode when any tuple values are strings.
- **`positions`** (`list[tuple[Any, ...]] | None`) - List of ``(start, end)`` tuples (single-axis) or ``((x_start, x_end), (y_start, y_end))`` tuples (``axis='both'``) defining explicit shade regions. Activates positions mode; ``repeat`` and ``flush`` are used only when tuple values are strings.
- **`axis`** (`str`) - ``'x'`` (default), ``'y'``, or ``'both'``. Controls which axis the shading runs along. ``'both'`` draws intersection rects spanning an explicit x-range and y-range simultaneously. Ignored in band mode (always ``'x'``).
- **`palette`** (`list[str] | None`) - List of hex color strings to cycle through in light mode. Defaults to ``"greys"`` when ``None``. In dark mode this parameter is always ignored — the darkest ``nShades`` stops of ``"greys"`` are used regardless. Resolved at call time; pass a callable to ``ds.save()`` for correct darkmode rendering.
- **`nShades`** (`int`) - Number of colors to use. In light mode, slices the first ``nShades`` stops from ``palette`` (or ``"greys"``). In dark mode, slices the last ``nShades`` stops of ``"greys"``. Defaults to ``2``.
- **`repeat`** (`int`) - Number of consecutive ticks sharing the same color before advancing (band mode only). Defaults to ``1``.
- **`opacity`** (`float`) - Fill opacity of the shade rects. Defaults to ``1.0``.
- **`stroke`** (`bool`) - Enable a border on the shade rects. ``False`` (default) → no stroke. ``True`` → axis-style stroke: color from theme darkmode state (black / white), width from ``axisWidth``.
- **`strokeWidth`** (`float | None`) - Explicit border width in pixels. Overrides ``axisWidth`` when ``stroke=True``. Has no effect when ``stroke=False``.
- **`strokeDash`** (`list[float] | bool | None`) - Dash pattern for the rect border. ``None`` (default) → solid. ``True`` → inherit ``dashedWidth`` from the active theme. A list (e.g. ``[4, 2]``) → use that pattern directly.
- **`flush`** (`bool | None`) - Extend the outermost rects to the axis domain edge (band mode and string positions only). ``None`` inherits from the theme's ``closed`` setting.
- **`data`** (`pl.DataFrame | pd.DataFrame | None`) - Facet-safe (datum) mode, **positions mode only**. ``None`` (default) builds each rect from its own internal dataset — the normal behavior, but **incompatible with faceting**. Pass the **same DataFrame you gave the base chart** to share its data and position numeric ranges by ``alt.datum`` (string/pixel ranges already use ``alt.value``), so ``(base + shade(positions=..., data=df))`` can be faceted and the shading repeats in every panel. Accepts polars or pandas. **Band mode** (``positions`` omitted) does not support ``data=`` and raises.

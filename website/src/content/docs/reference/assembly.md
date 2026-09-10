---
title: "Assembling figures"
description: "Compose several charts into one figure, each at its own size."
sidebar:
  order: 6
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `assemble`

```python
def assemble(
    members: list[_Member],
    *,
    spacing: _Spacing = None,
    labelFontSize: float = 8,
    labelFontWeight: int = 700,
    labelColor: str | None = None,
    labelOffset: float | tuple[float, float] = (-5, 0),
) -> _AltairChart: ...
```

Compose several charts into one figure, each built at its own size.

Charts in one figure share a single ``config.view``, so :func:`theme` alone cannot give
them different sizes - the last call wins. Sizing with ``.properties()`` instead leaves
``markSize``, the corner and arc radii, and the pixel geometry of every annotation
(``shade`` spans, comparison brackets, ``labels`` placement) computed for the
theme's size rather than the one the chart renders at. ``assemble`` builds each member
while the theme genuinely says its size, so those all land correctly, then stamps the
size on the chart so the shared config cannot override it.

Size only: Vega-Lite's ``config`` is spec-level, so palettes, fonts and axis styling
cannot differ between charts in one figure. Set those on the encoding instead - e.g.
``alt.Color(..., scale=alt.Scale(range=ds.palette("cat3", 3)))`` - which is per-view
and survives. Scales are not shared: concat resolves them independently already.

**Parameters**

- **`members`** (`list[_Member]`) - The charts, in layout order. Each is a ``(builder, width, height)`` tuple, a bare zero-argument builder (built at the theme's current size), or an already-built chart (used as-is, so a ``assemble`` result can nest inside another). Nest lists to make rows: ``[[a, b], [c, d]]`` is two rows of two, a flat list is a single row. Add a fourth element to carry a figure label: ``(time_course, 190, 110, "a")`` puts an ``a`` at that chart's top-left. The text is used verbatim, and members without a fourth element get no label, so a figure can label some charts and not others. A member may also be a dict, for callers who prefer the keys spelled out: ``{"chart": time_course, "width": 190, "height": 110, "label": "a"}``. Only ``chart`` is required, and it takes a builder or an already-built chart. ``None`` as the chart reserves an empty slot of that size - ``(None, 190, 110, "a")`` holds space to fill in later, labelled so the lettering stays in sequence. A blank carries no axis chrome, so it occupies exactly its width, where a real chart of the same width occupies that plus its axis margin.
- **`spacing`** (`_Spacing`) - Gap between charts in pixels - a number for both directions, or ``{"row": 40, "column": 10}`` to set them independently. ``None`` uses Vega-Lite's default.
- **`labelFontSize`** (`float`) - Figure-label styling. Weight is numeric (700, bold, by default). ``labelColor`` defaults to the theme's title ink, which follows ``darkmode`` at render, so a ``save()`` across both backgrounds gets the right color without a callable. ``labelOffset`` offsets the label from the corner - one number for both axes, or ``(x, y)``. It defaults to ``(-5, 0)``, holding the label off the chart the way ``axisOffset`` detaches the axes. The label already sits at the figure's leftmost point, so a negative x cannot move it further left - it widens the canvas and indents the chart instead, which reads the same and costs those pixels of width.
- **`labelFontWeight`** (`float`) - Figure-label styling. Weight is numeric (700, bold, by default). ``labelColor`` defaults to the theme's title ink, which follows ``darkmode`` at render, so a ``save()`` across both backgrounds gets the right color without a callable. ``labelOffset`` offsets the label from the corner - one number for both axes, or ``(x, y)``. It defaults to ``(-5, 0)``, holding the label off the chart the way ``axisOffset`` detaches the axes. The label already sits at the figure's leftmost point, so a negative x cannot move it further left - it widens the canvas and indents the chart instead, which reads the same and costs those pixels of width.
- **`labelColor`** (`float`) - Figure-label styling. Weight is numeric (700, bold, by default). ``labelColor`` defaults to the theme's title ink, which follows ``darkmode`` at render, so a ``save()`` across both backgrounds gets the right color without a callable. ``labelOffset`` offsets the label from the corner - one number for both axes, or ``(x, y)``. It defaults to ``(-5, 0)``, holding the label off the chart the way ``axisOffset`` detaches the axes. The label already sits at the figure's leftmost point, so a negative x cannot move it further left - it widens the canvas and indents the chart instead, which reads the same and costs those pixels of width.
- **`labelOffset`** (`float`) - Figure-label styling. Weight is numeric (700, bold, by default). ``labelColor`` defaults to the theme's title ink, which follows ``darkmode`` at render, so a ``save()`` across both backgrounds gets the right color without a callable. ``labelOffset`` offsets the label from the corner - one number for both axes, or ``(x, y)``. It defaults to ``(-5, 0)``, holding the label off the chart the way ``axisOffset`` detaches the axes. The label already sits at the figure's leftmost point, so a negative x cannot move it further left - it widens the canvas and indents the chart instead, which reads the same and costs those pixels of width.

**Returns**

- `An Altair concat chart, so ``.resolve_scale()``, ``.properties()`` and further nesting` - 
- `all work on the result.` - 

**Examples**

```python
A wide time course beside a narrow endpoint comparison::

    figure = ds.assemble(
        [(time_course, 210, 130), (endpoint_quant, 95, 130)],
        spacing=34,
    )

Two rows, with more room between the rows than within them::

    figure = ds.assemble(
        [
            [(time_course, 190, 110), (endpoint_quant, 90, 110)],
            [(heatmap, 130, 110), (activity_fit, 150, 110)],
        ],
        spacing={"row": 40, "column": 10},
    )
```

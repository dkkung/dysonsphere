---
title: "Theming"
description: "Register the dysonsphere Altair theme and scaffold config files."
sidebar:
  order: 15
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `theme`

```python
def theme(
    style: str | None = None,
    *,
    axisOffset: int | float | bool = _UNSET,
    axisWidth: int | float = _UNSET,
    boxplotOutliers: int | float | bool = _UNSET,
    chartFill: str | None = _UNSET,
    closed: bool | None = _UNSET,
    cornerRadius: int | float | bool = _UNSET,
    dark: bool = _UNSET,
    dashedGrid: bool = _UNSET,
    dashedLine: bool = _UNSET,
    dashedRule: bool = _UNSET,
    dashedWidth: Sequence[int | float] = _UNSET,
    font: str = _UNSET,
    fontSize: int | float = _UNSET,
    fontStyle: str = _UNSET,
    fontWeight: str | int | float = _UNSET,
    grid: bool = _UNSET,
    gridColor: str = _UNSET,
    height: int | float = _UNSET,
    legend: bool = _UNSET,
    legendColumnPadding: int | float = _UNSET,
    legendGradientLength: int | float | None = _UNSET,
    legendGradientThickness: int | float = _UNSET,
    legendOffset: int | float | None = _UNSET,
    legendRowPadding: int | float = _UNSET,
    legendStroke: bool = _UNSET,
    markFill: str = _UNSET,
    markFillOpacity: int | float = _UNSET,
    markMedianFill: str = _UNSET,
    markSize: int | float | None = _UNSET,
    markStroke: str = _UNSET,
    markStrokeOpacity: int | float = _UNSET,
    markStrokeWidth: int | float | None = _UNSET,
    barPadding: int | float = _UNSET,
    groupPadding: int | float = _UNSET,
    outerPadding: int | float = _UNSET,
    rectPadding: int | float = _UNSET,
    subgroupPadding: int | float = _UNSET,
    tickPadding: int | float = _UNSET,
    palette: str | list[str] | None = _UNSET,
    categoryPalette: str | list[str] | None = _UNSET,
    divergingPalette: str | list[str] | None = _UNSET,
    heatmapPalette: str | list[str] | None = _UNSET,
    ordinalPalette: str | list[str] | None = _UNSET,
    rampPalette: str | list[str] | None = _UNSET,
    saveBackground: str | Sequence[str] = _UNSET,
    saveFormat: str | Sequence[str] = _UNSET,
    sigFigs: int = _UNSET,
    strokeCap: str = _UNSET,
    tickDirection: Literal['in', 'out'] = _UNSET,
    ticks: bool = _UNSET,
    tickSize: int | float = _UNSET,
    transparent: bool = _UNSET,
    viewFill: str | None = _UNSET,
    viewPadding: int | float | bool = _UNSET,
    width: int | float = _UNSET,
    xAxis: bool = _UNSET,
    xDomain: bool = _UNSET,
    xLabelAngle: int | float = _UNSET,
    xLabels: bool = _UNSET,
    xTicks: bool = _UNSET,
    yAxis: bool = _UNSET,
    yDomain: bool = _UNSET,
    yLabelAngle: int | float = _UNSET,
    yLabels: bool = _UNSET,
    yTicks: bool = _UNSET,
) -> None: ...
```

Configure and register the dysonsphere Altair theme.

Every styling option is keyword-only. Omitted options inherit the applicable TOML/default/style value;
a successful call replaces, rather than updates, the active theme. Explicit ``None`` retains its
documented meaning for auto-derived fills, frame state, offsets, and mark dimensions.
``style`` remains an optional positional primary input; every styling option is keyword-only.
Runtime introspection displays ``<omitted>`` for omitted styling defaults; generated source
signatures may show the private ``_UNSET`` marker. Neither is a value callers pass.

By family, canvas dimensions default to 100 x 100 pixels. ``fontSize=6`` is a positive, fractional nominal
publication point size; SVG markup exposes the same number as a renderer user-unit value, and raster
export scales from 72 intrinsic units per inch. Axis, tick, legend, radius, and linear composite
dimensions are pixels. ``legendGradientLength=None`` allocates half the panel height to a
vertical title-plus-gradient span and the full panel width to a horizontal gradient. A positive
number is instead a dimensionless factor applied to either orientation at spec-resolution time;
``legendGradientThickness`` is a positive pixel width independent of marks and chart dimensions.
Continuous legends require ``ds.save()`` or ``ds.show()`` to resolve their sizing marker; bare
Altair/notebook rendering may fail. Signed axis/legend offsets and label angles are supported.
``markSize=None`` derives one tenth of
the smaller canvas dimension and is the common basis for symbol areas and composite dimensions;
``markStrokeWidth=None`` derives from ``axisWidth``. An omitted and unconfigured ``markFill``
follows the render mode (``greys[1]`` light, ``greys[4]`` dark); an explicit or configured value
stays fixed across modes. Circle marks keep their separate black/white fill.
``dark`` is a boolean selecting the logical light/dark theme. It defaults to ``False`` in the
built-in theme and to ``True`` in the ``notebook`` style, independently of ``transparent`` and
export background selection. The removed ``darkmode`` keyword and TOML key are not aliases.

Boolean axis switches gate domains/ticks but not labels. ``tickDirection`` is ``"out"`` or ``"in"``;
``closed=None`` derives from inward ticks or a view fill. ``viewPadding=True``, ``cornerRadius=True``,
and ``boxplotOutliers=True`` derive
size-dependent values; False disables them and a nonnegative number is explicit. Inner band
paddings are dimensionless values in [0, 1]; ``outerPadding`` is any nonnegative value. Opacities
are in [0, 1], and dash sequences contain finite nonnegative pixel lengths, including empty and
odd-length sequences.

Palette options accept a nonblank registered name, renderer scheme name, nonempty color-string
list, or None. The master ``palette`` overrides every per-type palette after source precedence is
resolved. ``saveFormat`` accepts svg/png/json/html and ``saveBackground`` accepts light/dark as a
string or nonempty sequence. See the [configuration guide](/guides/configuration/) for the complete
per-option defaults and scopes.

A TOML config file can provide persistent per-project or per-user
overrides. See the README for the config file format and search path.
Named styles in the config file are selected with ``style=``.

## `create_config`

```python
def create_config(
    directory: str | Path | None = None,
    *,
    persist: bool = False,
) -> None: ...
```

Write a dysonsphere.toml template to *directory* (default: current working directory).

Pass persist=True to write to the platform user config directory instead
(~/.config/dysonsphere/ on macOS/Linux, %APPDATA%/dysonsphere/ on Windows).
This file applies across all your projects.

The file is not overwritten if it already exists. Edit the values in each
section, rename [my_style] to your own style name, and load it with
ds.theme(style="name").

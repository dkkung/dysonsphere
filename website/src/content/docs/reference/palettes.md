---
title: "Palettes"
description: "Perceptually uniform palettes and Adobe Illustrator swatch export."
sidebar:
  order: 8
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `categorical`

```python
def categorical(
    members: int = 1,
    palette: str = _DEFAULT_QUALITATIVE,
) -> list[str]: ...
```

Qualitative color palette built from a family of base hues.

Every color is drawn from an existing base palette at fixed stops - nothing is
generated de novo, so retuning a base hue regenerates this palette automatically.

**Parameters**

- **`members`** (`int`) - Colors per associated group. - ``1`` (default): a flat palette for *unrelated* groups, ordered **tier-major** (cycle the hues at the light tier, then mid, then dark) so adjacent categories differ in hue. Returns ``3 * len(hues)`` colors. The default palette's flat form is what ``config.range.category`` uses. - ``2`` or more: a **grouped** palette for paired data (``A1``/``A2`` …), ordered **hue-major** - each consecutive block of ``members`` categories is one hue climbing through ``members`` lightness levels. Returns ``len(hues) * members`` colors. Sort your categories so a group's members are adjacent, then pass this as the color scale range. Up to ``4`` members the lightness stops are the classic tier stops (``1, 4, 7, 10`` - three ramp steps apart, matching the flat palette's tiers); beyond ``4`` the stops spread evenly across the usable ramp (``1``-``10``), which **shrinks the within-hue contrast** with every extra member - fine at normal mark sizes for ``5``-``6``, increasingly ambiguous past that, and capped at ``10`` where distinct stops run out. If your "members" are actually ordinal (a dose series, timepoints), a sequential slice per group - ``palette("cat_azures", n=5)`` - usually communicates that better than a categorical palette pretending they're unordered.
- **`palette`** (`str`) - Which qualitative palette to build. ``"ds_cat_1"`` (default) is the muted, australis-harmonious five-hue set (also stored as ``colors["ds_cat_1"]`` and wired to ``config.range.category``); ``"ds_cat_2"`` is the legacy four-hue pastel set (``colors["ds_cat_2"]``).

**Examples**

```python
Flat categorical (the default; also automatic via ``config.range.category``)::

    alt.Color("g:N")                                       # picks it up automatically
    alt.Color("g:N", scale=alt.Scale(range=categorical()))  # explicit
    alt.Color("g:N", scale=alt.Scale(range=categorical(palette="ds_cat_2")))  # pastel

Paired data, members adjacent within each group::

    groups = ["A1", "A2", "B1", "B2"]
    alt.Color("g:N", sort=groups, scale=alt.Scale(range=categorical(2)))
    # -> A1=azure-light, A2=azure-dark, B1=blue-light, B2=blue-dark, ...
```

## `palette`

```python
def palette(
    name: str,
    n: int | None = None,
    start: int = 0,
    end: int | None = None,
    step: int = 1,
    reverse: bool = False,
) -> list[str]: ...
```

Sample colors from a named palette with control over start, stop, and spacing.

When ``n`` is provided, evenly samples ``n`` colors between ``start`` and
``stop`` (linspace). Otherwise, returns every ``step``-th color from
``start`` to ``stop`` — with default ``step=1`` this returns the full slice.

**Parameters**

- **`name`** (`str`) - Key in the ``colors`` dict (e.g. ``"mpl_YlGnBu"``).
- **`n`** (`int | None`) - Number of colors to return (evenly spaced). Takes priority over ``step``.
- **`start`** (`int`) - Index of the first color to include. Defaults to 0.
- **`end`** (`int | None`) - Index of the last color to include (inclusive). Defaults to the last index in the palette.
- **`step`** (`int`) - Step between color indices. Defaults to 1 (every color).
- **`reverse`** (`bool`) - If True, reverse the returned list.

**Examples**

```python
All colors in the palette:

    palette("mpl_YlGnBu")

Last 4 colors:

    palette("mpl_YlGnBu", start=5)

Four evenly-spaced colors across the full palette:

    palette("mpl_YlGnBu", n=4)

Every second color from index 0 to 6 (returns indices 0, 2, 4, 6):

    palette("mpl_YlGnBu", end=6, step=2)

Four evenly-spaced colors, reversed:

    palette("mpl_YlGnBu", n=4, reverse=True)
```

## `export_swatches`

```python
def export_swatches(
    directory: str | Path | None = None,
    palettes: list[str] | None = None,
    name: str = 'dysonsphere',
) -> None: ...
```

Write a JSX script and an ASE swatch library for Adobe Illustrator to *directory*
(default: current working directory).

Produces two files (``name`` defaults to ``"dysonsphere"``):

- ``import_{name}_palettes_to_illustrator.jsx`` — run via
  File > Scripts > Other Script... to load the selected palettes into the active
  document's Swatches panel as named groups.
- ``{name}.ase`` — Adobe Swatch Exchange file containing the selected palettes as
  named groups. Automatically copied to the Illustrator User Defined Swatches
  folder if it can be detected; otherwise copy it there manually. After restarting
  Illustrator it appears under Open Swatch Library > User Defined > {name}.

**Parameters**

- **`directory`** (`str | Path | None`) - Output directory for the two files. Defaults to the current working directory.
- **`palettes`** (`list[str] | None`) - Names of the palettes to export (keys of ``dysonsphere.colors``). ``None`` (default) exports every palette. Pass a non-empty list to export only a subset, e.g. ``["reds", "blues", "redsblues"]``. Unknown names raise ``ValueError``.
- **`name`** (`str`) - Base name for the generated files and the Illustrator swatch library. Defaults to ``"dysonsphere"``.

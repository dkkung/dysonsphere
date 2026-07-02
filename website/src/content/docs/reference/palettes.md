---
title: "Palettes"
description: "Perceptually uniform palettes and Adobe Illustrator swatch export."
sidebar:
  order: 2
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `palette`

```python
palette(name: str, n: int | None = None, start: int = 0, end: int | None = None, step: int = 1, reverse: bool = False)
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
export_swatches(directory: str | Path | None = None, palettes: list[str] | None = None, name: str = 'dysonsphere')
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

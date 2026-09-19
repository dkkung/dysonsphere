---
title: "Palettes"
description: "Perceptually uniform palettes and Adobe Illustrator swatch export."
sidebar:
  order: 9
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Use `ds.palette(...)` to select colors. This ordinary root function is implemented in
`palettes.py`; the catalogue and other helpers live at `ds.palettes.colors`,
`ds.palettes.categorical(...)`, and `ds.palettes.export_swatches(...)`.
`ds.palettes.accents` is a read-only mapping of named emphasis colors resolved from the
active light/dark theme at lookup time; it is not part of the palette catalogue.

## `categorical`

Call as `ds.palettes.categorical(...)`.

```python
def categorical(
    members: int = 1,
    *,
    palette: str = _DEFAULT_QUALITATIVE_PALETTE,
) -> list[str]: ...
```

Qualitative color palette built from a family of base hues.

Every color is drawn from an existing base palette at fixed stops - nothing is
generated de novo, so retuning a base hue regenerates this palette automatically.

**Parameters**

- **`members`** (`int`) - Colors per associated group. - ``1`` (default): a flat palette for *unrelated* groups, ordered **tier-major** so adjacent categories differ in hue. Canonical families cycle light, mid, then dark and return ``3 * len(hues)`` colors. ``cat2`` uses a curated 10-color sequence; ``cat1`` instead places five dark accent anchors before five lighter companions. The default ``cat1`` flat form is what ``config.range.category`` uses in light mode; the dark-mode default is ``cat2``. - ``2`` or more: a **grouped** palette for paired data (``A1``/``A2`` …), ordered **hue-major** - each consecutive block of ``members`` categories is one hue climbing through ``members`` lightness levels. Returns ``len(hues) * members`` colors. Sort your categories so a group's members are adjacent, then pass this as the color scale range. For the canonical ``cat3`` and ``cat4`` families, up to ``4`` members use the classic tier stops (``1, 4, 7, 10``); beyond ``4``, stops spread evenly across ``1``-``10``. ``cat1`` and ``cat2`` instead spread every grouped selection across their per-hue usable windows. In either path, adding members shrinks within-hue contrast; ``5``-``6`` are reasonable at normal mark sizes but larger groups become increasingly ambiguous. If your "members" are actually ordinal (a dose series, timepoints), a sequential slice per group - ``palette("cat1_blues", n=5)`` - usually communicates that better than a categorical palette pretending they're unordered.
- **`palette`** (`str`) - Which qualitative palette to build. ``"cat1"`` (default) is the static two-tier accent set - grey, blue, green, purple, and teal - with five light-theme accents followed by lighter companions (also stored as ``colors["cat1"]`` and used by the light-mode ``config.range.category`` default). ``"cat2"`` is the saturated cool set, ``"cat3"`` is the legacy four-hue pastel set, and ``"cat4"`` is the muted australis-harmonious set. ``cat2`` differs from the canonical-stop palettes in how its stops are chosen: its flat palette uses explicit stops (not the canonical ``(1, 4, 7)``), and in grouped mode each family spreads across its own usable window rather than a shared ``1``-``10``. That caps it at ``members=6``, set by ``cat2_greens``. ``cat1`` likewise uses per-family stops ``1``-``10`` and is capped at ``members=10``; its flat form remains ten colors.

**Examples**

```python
Flat categorical (the default; also automatic via ``config.range.category``)::

    alt.Color("g:N")                                       # picks it up automatically
    alt.Color("g:N", scale=alt.Scale(range=categorical()))  # explicit
    alt.Color("g:N", scale=alt.Scale(range=categorical(palette="cat3")))  # pastel

Paired data, members adjacent within each group::

    groups = ["A1", "A2", "B1", "B2"]
    alt.Color("g:N", sort=groups, scale=alt.Scale(range=categorical(2)))
    # -> A1=grey-light, A2=grey-dark, B1=blue-light, B2=blue-dark, ...
```

## `palette`

Call as `ds.palette(...)`.

```python
def palette(
    name: str,
    n: int | None = None,
    *,
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

- **`name`** (`str`) - Case-sensitive key in the ``colors`` dict (e.g. ``"YlGnBu"``). Native palette names containing ``"greys"`` also accept ``"grays"`` (for example, ``"warmgrays"`` and ``"graysblues2"``); imported ``"gray"`` and ``"Greys"`` remain distinct.
- **`n`** (`int | None`) - Number of colors to return (evenly spaced). Takes priority over ``step``.
- **`start`** (`int`) - Index of the first color to include. Defaults to 0.
- **`end`** (`int | None`) - Index of the last color to include (inclusive). Defaults to the last index in the palette.
- **`step`** (`int`) - Step between color indices. Defaults to 1 (every color).
- **`reverse`** (`bool`) - If True, reverse the returned list.

**Examples**

```python
All colors in the palette:

    palette("YlGnBu")

Last 4 colors:

    palette("YlGnBu", start=5)

Four evenly-spaced colors across the full palette:

    palette("YlGnBu", n=4)

Every second color from index 0 to 6 (returns indices 0, 2, 4, 6):

    palette("YlGnBu", end=6, step=2)

Four evenly-spaced colors, reversed:

    palette("YlGnBu", n=4, reverse=True)
```

## `export_swatches`

Call as `ds.palettes.export_swatches(...)`.

```python
def export_swatches(
    directory: str | Path | None = None,
    *,
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
- **`palettes`** (`list[str] | None`) - Names of the palettes to export (keys of ``dysonsphere.palettes.colors``). ``None`` (default) exports every palette. Pass a non-empty list to export only a subset, e.g. ``["reds", "blues", "redsblues"]``. Unknown names raise ``ValueError``.
- **`name`** (`str`) - Base name for the generated files and the Illustrator swatch library. Defaults to ``"dysonsphere"``.

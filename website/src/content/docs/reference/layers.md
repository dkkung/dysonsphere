---
title: "Annotations"
description: "Composable annotation layers: rules, text, shading, comparisons, correlation."
sidebar:
  order: 4
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `add_rule`

```python
add_rule(value: float | list[float], *, axis: str = 'y', label: str | list[str] | None = None, labelPosition: str | None = None, labelAlign: str | None = None, labelOffsetX: int = 0, labelOffsetY: int = 0, color: str | None = None, strokeWidth: float | None = None, strokeDash: bool | list[int] | None = None, opacity: float = 1.0, fontSize: float | None = None)
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

**Examples**

```python
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
```

## `add_text`

```python
add_text(text: str | list[str], x = None, y = None, *, position: str | None = None, angle: float = 0, align: str | None = None, baseline: str | None = None, offsetX: int = 0, offsetY: int = 0, color: str | None = None, fontSize: float | None = None, fontWeight: str | None = None, fontStyle: str | None = None, font: str | None = None, opacity: float = 1.0)
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
```

## `add_shade`

```python
add_shade(categories: list[str] | None = None, xCol: str | None = None, *, positions: list[tuple] | None = None, axis: str = 'x', palette: list[str] | None = None, nShades: int = 2, repeat: int = 1, opacity: float = 1.0, stroke: bool = False, strokeWidth: float | None = None, strokeDash: list[float] | bool | None = None, flush: bool | None = None)
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

## `add_comparisons`

```python
add_comparisons(df: pl.DataFrame | Any, xCol: str, yCol: str, pairs: list[tuple[str, str]] | None = None, *, test: str = 'mannwhitneyu', postHoc: str | None = None, pvalues: list[float] | None = None, correction: str | None = None, nComparisons: int | None = None, yPositions: list[float] | None = None, yStart: float | None = None, yStep: float | None = None, yPad: float | None = None, categories: list | None = None, chartWidth: int | None = None, bracketStyle: str | dict = 'bracket', labelStyle: str = 'p', tickHeight: float | None = None, strokeWidth: float | None = None, fontSize: int | None = None, reverse: list[tuple[str, str]] | None = None, sigFigs: int | None = None, notation: str | dict | None = None, testLabelPosition: str | None = 'auto', testLabel: str | None = None, omnibusVerbose: bool = False, testLabelOffsetX: int = 0, testLabelOffsetY: int = 0, testLabelX = None, testLabelY = None, report: bool = False, save: bool | str = False)
```

Build p-value annotation layers for one or more group comparisons.

Two modes, selected by ``test``:

- **Pairwise** (``'mannwhitneyu'``, ``'ttest_ind'``, ``'ttest_rel'``,
  ``'wilcoxon'``, ``'tukey_hsd'``) — draws a bracket per pair in ``pairs``,
  stacked automatically so they don't overlap (shorter-span pairs sit lower;
  overlapping spans are bumped up a level).
- **Omnibus** (``'anova'``, ``'kruskal'``, ``'friedman'``,
  ``'alexandergovern'``) — runs one "are *any* groups different?" test and
  places its result as a corner label via ``add_text`` (see
  ``testLabelPosition``). If ``pairs`` is also given, a post-hoc test (see
  ``postHoc``) fills the brackets.

A descriptive + effect-size report is generated on every call and queued for
the export metadata written by ``ds.save()`` (see ``report``/``save``).

Combine with your chart using ``+``:  ``chart + add_comparisons(...)``.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - Polars DataFrame containing the data.
- **`xCol`** (`str`) - Column name for the grouping variable (x-axis).
- **`yCol`** (`str`) - Column name for the value variable (y-axis). Used to run tests and to auto-place the first bracket.
- **`pairs`** (`list[tuple[str, str]] | None`) - List of ``(group1, group2)`` tuples identifying the comparisons to annotate with brackets. Required for pairwise ``test`` values. Optional for omnibus tests — pass ``None`` for an omnibus-only corner label, or a list to also draw post-hoc brackets.
- **`test`** (`str`) - Statistical test. **Pairwise:** ``'mannwhitneyu'`` (default), ``'ttest_ind'``, ``'ttest_rel'``, ``'wilcoxon'`` (run per pair), or ``'tukey_hsd'`` (one omnibus run, per-pair p-values from the matrix). **Omnibus:** ``'anova'`` (``f_oneway``), ``'kruskal'``, ``'friedman'``, ``'alexandergovern'``. Ignored when ``pvalues`` is provided.
- **`postHoc`** (`str | None`) - Post-hoc test that fills the brackets when ``test`` is omnibus and ``pairs`` is given. ``None`` (default) picks a sensible default per omnibus test: ``anova → 'tukey_hsd'``, ``alexandergovern → 'games_howell'``, ``kruskal → 'dunn'``, ``friedman → 'nemenyi'``. May also be set to any pairwise test name. Dunn, Nemenyi, and Games-Howell are computed in-house (validated against scikit-posthocs / pingouin); ``correction`` adjusts them over all unique pairs. Ignored for pairwise ``test``.
- **`pvalues`** (`list[float] | None`) - Pre-computed p-values, one per pair in the same order. Skips all statistical tests for the brackets when provided.
- **`correction`** (`str | None`) - Multiple comparison correction: ``'bonferroni'``, ``'holm'``, or ``None``. For pairwise/post-hoc bracket p-values; ignored for ``tukey_hsd`` (correction is built in) and when ``pvalues`` is provided.
- **`nComparisons`** (`int | None`) - Total number of comparisons for Bonferroni correction. Defaults to ``len(pairs)`` when ``correction='bonferroni'`` and not set explicitly.
- **`yPositions`** (`list[float] | None`) - Explicit y positions (data units) for each bracket, one per pair in the same order. When provided, overrides all auto-stacking logic (``yStart``, ``yStep``, ``yPad`` are ignored).
- **`yStart`** (`float | None`) - Y position (data units) of the lowest bracket. Defaults to ``max(y values for all annotated groups) + yPad``.
- **`yStep`** (`float | None`) - Vertical distance (data units) between stacking levels. Defaults to ``yPad * 2``.
- **`yPad`** (`float | None`) - Padding above the data maximum when ``yStart`` is auto-placed. Defaults to a fixed visual gap of ~8 px (``bracketStyle='line'``) or ~10 px (``bracketStyle='bracket'``), expressed in data units via ``chartHeight`` so the gap stays visually consistent regardless of chart height.
- **`categories`** (`list | None`) - Ordered list of all x-axis categories. Inferred from ``df`` (sorted alphabetically) when not provided.
- **`chartWidth`** (`int | None`) - Width of the chart in pixels, used to compute text x positions. Auto-detected from ``ds.theme()`` when not set.
- **`bracketStyle`** (`str | dict`) - ``'bracket'`` (default; bar + end ticks) or ``'line'`` (horizontal bar only) applied to every bracket. Or a ``dict`` mapping a pair to its style for per-pair control, e.g. ``{("A", "B"): "line", ("A", "C"): "bracket"}`` — keys match either pair order; pairs absent from the dict fall back to ``'bracket'``.
- **`labelStyle`** (`str`) - ``'p'`` (default) renders ``P = 0.012`` / ``P < 0.001``. ``'asterisks'`` renders ``*`` / ``**`` / ``***`` / ``ns``.
- **`tickHeight`** (`float | None`) - Height of bracket end ticks in data units. Defaults to the theme's ``tickSize`` (converted from px to data units), so bracket ticks match the axis ticks. Always positive, so it works with reverse (negative-``yStep``) brackets without an explicit override. Only used when ``bracketStyle='bracket'``.
- **`strokeWidth`** (`float | None`) - Stroke width of bracket lines. Inherits ``axisWidth`` from ``ds.theme()`` when not set.
- **`fontSize`** (`int | None`) - Font size of the p-value / corner labels. Defaults to the theme's ``secondaryFontSize`` (``fontSize - 1``, i.e. ``6`` at the default ``fontSize=7``).
- **`reverse`** (`list[tuple[str, str]] | None`) - List of ``(group1, group2)`` tuples identifying brackets to flip — text moves below the bar and ticks point upward.
- **`sigFigs`** (`int | None`) - Significant figures for p-value labels (and the correlation readout). Gives consistent visual precision across magnitudes — e.g. ``sigFigs=2`` renders both ``P = 4.3×10⁻¹⁴`` and ``P = 0.68`` at two figures. Trailing zeros are stripped. ``None`` (default) reads the theme's ``sigFigs`` (default ``3``). Plain notation floors at a fixed ``P < 0.001``; ``'power'`` is unaffected (integer exponent).
- **`notation`** (`str | dict | None`) - Format style for p-value labels when ``labelStyle='p'``. ``None`` (default) uses ``P = 0.012`` / ``P < 0.001`` style. ``'scientific'`` uses ``P = 1.23×10⁻²``. ``'e'`` uses ``P = 1.23e-02``. ``'power'`` rounds to the nearest power of 10 giving ``P ≈ 10⁻²`` — note that values within the same decade (e.g. 0.04 and 0.06) map to the same label; best for p-values spanning multiple orders of magnitude. A single value applies to every label; or pass a ``dict`` for per-pair notation, e.g. ``{("A", "B"): "scientific", "test": "power"}`` — tuple keys are pairs (matched either order, unlisted → plain), and the special ``"test"`` key sets the omnibus label's notation.
- **`testLabelPosition`** (`str | None`) - Corner preset (an ``add_text`` position, e.g. ``'topLeft'``, ``'bottomRight'``) for the single test label. Its content adapts: the omnibus **result** (``ANOVA P = 0.003``) for an omnibus ``test``, or the pairwise **test name** (``Mann-Whitney U``) for a pairwise ``test``. Default ``'auto'`` → shown at ``'topLeft'`` for omnibus, hidden for pairwise (opt-in). A preset draws it there; ``None`` hides it (the result is still computed for the report/metadata).
- **`testLabel`** (`str | None`) - Override string for the test label. ``None`` (default) builds it from the test result / name.
- **`omnibusVerbose`** (`bool`) - Applies to the omnibus label content: ``False`` (default) → terse ``ANOVA P = 0.003``; ``True`` → ``ANOVA F(2, 57) = 6.34, P = 0.003, η² = 0.18`` (statistic, df, p, and effect size).
- **`testLabelOffsetX`** (`int`) - Pixel nudges for the test label, forwarded to ``add_text``.
- **`testLabelOffsetY`** (`int`) - Pixel nudges for the test label, forwarded to ``add_text``.
- **`testLabelX`** - Explicit coordinates for the test label (data values, category names, or ``alt.value(px)``), forwarded to ``add_text`` where they override the preset. ``None`` (default) uses ``testLabelPosition``.
- **`testLabelY`** - Explicit coordinates for the test label (data values, category names, or ``alt.value(px)``), forwarded to ``add_text`` where they override the preset. ``None`` (default) uses ``testLabelPosition``.
- **`report`** (`bool`) - ``True`` prints the full descriptive + effect-size report (per-group n/mean/sd/median/IQR/range, the omnibus result, and the post-hoc comparisons) to stdout. Default ``False``. For an omnibus ``test`` the report lists **all** pairwise post-hoc comparisons — the full table, not just the pairs you bracket (and even when ``pairs=None``). For a pairwise ``test`` it lists exactly the requested ``pairs``. The report is queued for the export metadata regardless of this flag (when ``ds.save(..., saveMetadata=True)``); it lands in the next ``ds.save()``.
- **`save`** (`bool | str`) - ``True`` writes the report to ``dysonsphere_report_<timestamp>.txt`` in the current directory; a string writes it to that directory. Default ``False``.

**Examples**

```python
Single comparison::

    CATEGORIES = ["A", "B", "C"]
    chart = ds.mark_strip(df, "group", "value", CATEGORIES)
    chart + ds.add_comparisons(
        df, "group", "value",
        pairs=[("A", "B")],
        categories=CATEGORIES,
    )

Multiple comparisons — brackets stacked automatically::

    chart + ds.add_comparisons(
        df, "group", "value",
        pairs=[("A", "B"), ("A", "C"), ("B", "C")],
        test="mannwhitneyu",
        categories=CATEGORIES,
    )

Omnibus ANOVA in the corner + Tukey post-hoc brackets::

    chart + ds.add_comparisons(
        df, "group", "value",
        pairs=[("A", "B"), ("A", "C")],
        test="anova",
        omnibusVerbose=True,
        categories=CATEGORIES,
    )

Omnibus-only (no brackets), report printed::

    chart + ds.add_comparisons(
        df, "group", "value",
        test="kruskal",
        categories=CATEGORIES,
        report=True,
    )

From pre-computed p-values::

    chart + ds.add_comparisons(
        df, "group", "value",
        pairs=[("A", "B"), ("A", "C")],
        pvalues=[0.012, 0.341],
        categories=CATEGORIES,
    )
```

## `add_correlation`

```python
add_correlation(df: pl.DataFrame | Any, xCol: str, yCol: str, *, method: str = 'pearson', line: bool = True, position: str | None = 'topLeft', label: str | None = None, coefficient: str = 'r', includePvalue: bool = False, includeEquation: bool = False, verbose: bool = False, offsetX: int = 0, offsetY: int = 0, fontSize: int | None = None, sigFigs: int | None = None, notation: str | None = None, color: str | None = None, strokeWidth: float | None = None, strokeDash: bool | list[int] | None = None, opacity: float | None = None, lineStyle: dict | None = None, report: bool = False, save: bool | str = False)
```

Annotate a scatter with a correlation coefficient (and an OLS fit line for Pearson).

Reports the coefficient as a corner label, and — for ``method="pearson"``
only — draws the ordinary-least-squares regression line. A structured record
(``kind="correlation"``) is queued for the export metadata (see ``ds.save``),
exactly like ``add_comparisons``.

Combine with your scatter using ``+``:  ``chart + add_correlation(...)``.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - DataFrame containing the data (polars or pandas).
- **`xCol`** (`str`) - Column names for the two **continuous** variables.
- **`yCol`** (`str`) - Column names for the two **continuous** variables.
- **`method`** (`str`) - ``'pearson'`` (default) — linear correlation ``r`` + ``r²`` + slope/intercept, with an OLS line. ``'spearman'`` — rank correlation ``ρ``. ``'kendall'`` — rank correlation ``τ``. The rank methods report the coefficient only (no ``r²``, no line — a straight line isn't their model). Matches pandas' ``DataFrame.corr``.
- **`line`** (`bool`) - Draw the OLS fit line. Default ``True``. Only applies to ``method="pearson"`` (a no-op for the rank methods). Set ``False`` to suppress it and, e.g., compose your own line from the returned/recorded slope and intercept.
- **`position`** (`str | None`) - Corner preset (an ``add_text`` position, e.g. ``'topLeft'``) for the readout. Default ``'topLeft'``. ``None`` computes the result for the report/metadata but draws no label.
- **`label`** (`str | None`) - Override string for the corner readout. ``None`` builds it from the parts below.
- **`coefficient`** (`str`) - Pearson only — which statistic the readout shows: ``'r'`` (default), ``'r2'`` (just ``r²``, Excel-trendline style), or ``'both'``. Ignored for the rank kinds (they always show ``ρ``/``τ``).
- **`includePvalue`** (`bool`) - Append the p-value to the readout. Default ``False``.
- **`includeEquation`** (`bool`) - Pearson only — append the fit equation ``, y = 0.84x + 0.27``. Default ``False``.
- **`verbose`** (`bool`) - Shortcut for the fullest readout: ``True`` is equivalent to ``coefficient="both", includePvalue=True, includeEquation=True`` (and overrides those three). Default ``False``. So the default readout is just ``r = 0.87`` (Pearson) / ``ρ = 0.81`` (rank); ``verbose=True`` gives ``r = 0.87, r² = 0.76, P < 0.001, y = 0.84x + 0.27``.
- **`offsetX`** (`int`) - Pixel nudges for the readout, forwarded to ``add_text``.
- **`offsetY`** (`int`) - Pixel nudges for the readout, forwarded to ``add_text``.
- **`fontSize`** (`int | None`) - Font size of the readout. Defaults to the theme's ``secondaryFontSize`` (``fontSize - 1``, i.e. ``6`` at the default ``fontSize=7``).
- **`sigFigs`** (`int | None`) - Significant figures / number format for the readout (coefficient, r², p-value, and fit equation), as in ``add_comparisons``. ``sigFigs=None`` reads the theme.
- **`notation`** (`int | None`) - Significant figures / number format for the readout (coefficient, r², p-value, and fit equation), as in ``add_comparisons``. ``sigFigs=None`` reads the theme.
- **`color`** (`str | None`) - Curated style overrides for the fit line (same four knobs as ``add_rule``). Each defaults to ``None`` → the line inherits the theme's ``mark_line`` config; set one to override just that property.
- **`strokeWidth`** (`str | None`) - Curated style overrides for the fit line (same four knobs as ``add_rule``). Each defaults to ``None`` → the line inherits the theme's ``mark_line`` config; set one to override just that property.
- **`strokeDash`** (`str | None`) - Curated style overrides for the fit line (same four knobs as ``add_rule``). Each defaults to ``None`` → the line inherits the theme's ``mark_line`` config; set one to override just that property.
- **`opacity`** (`str | None`) - Curated style overrides for the fit line (same four knobs as ``add_rule``). Each defaults to ``None`` → the line inherits the theme's ``mark_line`` config; set one to override just that property.
- **`lineStyle`** (`dict | None`) - A dict of raw ``mark_line`` properties merged in last, so any Vega-Lite line property is reachable (e.g. ``{"interpolate": "monotone", "strokeCap": "round"}``). Keys here **override** the curated ``color``/``strokeWidth``/etc. above.
- **`report`** (`bool`) - ``True`` prints the report (coefficient, r², p, fit, n) to stdout. Default ``False``. The record is queued for export metadata regardless.
- **`save`** (`bool | str`) - ``True`` writes the report to ``dysonsphere_report_<timestamp>.txt`` in the cwd; a string writes it to that directory.

**Examples**

```python
::

    scatter = alt.Chart(df).mark_point().encode(x="height:Q", y="weight:Q")
    scatter + ds.add_correlation(df, "height", "weight")                 # r + r² + OLS line
    scatter + ds.add_correlation(df, "height", "weight", method="spearman")  # ρ, no line
    scatter + ds.add_correlation(
        df, "height", "weight",
        color="#c0392b", lineStyle={"strokeDash": [4, 2]},
    )
```

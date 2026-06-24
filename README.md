# dysonsphere

An Altair configuration wrapper with perceptually uniform palettes and chart utilities for publication-ready figures.

*This is a personal project under active development, so there may be breaking changes between minor versions.*

![thumbnail](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/thumbnail_light.png)

## Installation

```sh
# uv
uv pip install dysonsphere

# pip
pip install dysonsphere
```

Requires Python 3.11+. Dependencies: `altair`, `numpy`, `polars`, `scipy`.

---

## Quick start

```python
import altair as alt
import polars as pl
import dysonsphere as ds  # or: import dysonsphere

ds.theme(chartWidth=300, chartHeight=200)

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("x:Q"),
        y=alt.Y("y:Q"),
        color=alt.Color("y:Q", scale=alt.Scale(range=ds.palette("blues"))),
    )
)

ds.save(chart, "plots/myplot")
# writes: plots/myplot_light.png, plots/myplot_light.svg
#         plots/myplot_dark.png,  plots/myplot_dark.svg
#         plots/myplot_vegalite.json
```

---

## dysonsphere.theme()

**Call before building any Altair charts to configure global theme defaults.**

```python
ds.theme()  # apply defaults

ds.theme(   # custom configuration
    chartWidth=400,
    chartHeight=250,
    fontSize=8,
    grid=True,
    palette="blues",
)
```

| Parameter | Default | Description |
|---|---|---|
| `angledX` | `False` | Angle x-axis labels 45° |
| `axisOffset` | `tickSize` | Distance between axis line and data area |
| `axisWidth` | `0.25` | Stroke width of axes, ticks, and rules |
| `bandPadding` | `0.1` | Inner and outer padding for ordinal bands |
| `chartFill` | `"white"` | Background fill of the entire chart |
| `chartHeight` | `100` | Default chart height in pixels |
| `chartWidth` | `100` | Default chart width in pixels |
| `closed` | auto | Draw a border around the plot area. Auto-enabled when `viewFill` is set |
| `darkmode` | `False` | Invert text and axis colors for dark backgrounds |
| `dashedLine` | `False` | Render line marks dashed |
| `dashedRule` | `True` | Render rule marks dashed |
| `dashedWidth` | `[2, 2]` | Dash/gap pattern `[dash, gap]` in pixels |
| `font` | `"HelveticaNeue"` | Font family for all labels and titles |
| `fontSize` | `7` | Font size in points |
| `fontWeight` | `400` | Font weight: 300 = light, 400 = normal, 700 = bold |
| `grid` | `False` | Show axis grid lines |
| `gridColor` | `"darkGray"` | Grid line color |
| `legend` | `True` | Show legends |
| `legendOffset` | `tickSize` | Distance between legend and chart edge |
| `legendStroke` | `False` | Draw a border around the legend box |
| `markFill` | `"black"` | Default fill color for marks |
| `markFillOpacity` | `1.0` | Default mark fill opacity |
| `markSize` | `min(W, H) × 0.1` | Mark size; for points, this is area in sq px |
| `markStroke` | `"black"` | Default stroke color for marks |
| `markStrokeOpacity` | `1` | Default mark stroke opacity |
| `palette` | `None` | Default color scheme applied to category, diverging, heatmap, and ramp scales. Accepts a key from `colors` or a raw list |
| `strokeCap` | `"round"` | Stroke end cap: `"butt"`, `"round"`, or `"square"` |
| `ticks` | `True` | Show axis ticks |
| `tickSize` | `5` | Tick length in pixels |
| `transparentBackground` | `False` | Transparent chart background (overrides `chartFill`) |
| `verticalY` | `False` | Rotate y-axis labels 90° |
| `viewFill` | `None` | Fill color of the plot area only. Setting this auto-enables `closed` |
| `xTicks` | `True` | Show ticks on the x-axis |
| `yTicks` | `True` | Show ticks on the y-axis |

---

## Palettes

All custom palettes are built in [Oklab](https://bottosson.github.io/posts/oklab/) (Ottosson, *A perceptual color space for image processing*, 2020) for perceptual uniformity. They are stored in `dysonsphere.colors`, a plain `dict[str, list[str]]` mapping palette names to 12-stop hex lists (13 stops for diverging palettes).

### Accessing palettes

```python
from dysonsphere.palettes import colors

blues = colors["blues"]   # list of 12 hex strings, light → dark
```

### dysonsphere.palette()

Samples a slice or subset from any named palette.

```python
ds.palette("blues")                     # all 12 stops
ds.palette("blues", n=5)                # 5 evenly-spaced stops
ds.palette("blues", start=3)            # stops 3–11
ds.palette("blues", end=6, step=2)      # indices 0, 2, 4, 6
ds.palette("blues", n=4, reverse=True)  # reversed
```

| Parameter | Default | Description |
|---|---|---|
| `name` | required | Key in `colors` |
| `n` | `None` | Return `n` evenly-spaced stops (overrides `step`) |
| `start` | `0` | Index of the first stop to include |
| `end` | last | Index of the last stop to include (inclusive) |
| `step` | `1` | Step between indices (used when `n` is not set) |
| `reverse` | `False` | Reverse the returned list |

### Theme defaults

When no explicit `scale=` is set on a color encoding, Vega-Lite falls back to the theme's range defaults:

| Range type | Default palette | Used for |
|---|---|---|
| `category` | `blues` (even indices: 0, 2, 4, 6, 8, 10) | Nominal/unordered groups |
| `ordinal` | `blues` | Ordered discrete values |
| `ramp` | `blues` | Sequential continuous (legend ramps) |
| `heatmap` | `blues` | Rect/heatmap marks |
| `diverging` | `redsblues` | Diverging scales |

Setting `ds.theme(palette="mypalette")` overrides all five types simultaneously.

### Available palettes

See the [palette gallery](https://dkkung.github.io/dysonsphere/) for a visual overview of all palettes, or open `docs/index.html` locally.

**Sequential — Single-hue** (12 stops, light → dark):
`blues`, `greens`, `purples`, `lavenders`, `violets`, `greys`, `reds`, `rose`, `oranges`, `browns`, `yellows`, `cyans`, `magentas`, `neongreens`

**Sequential — Single-hue 2** (12 stops, deeper saturation built with Oklab arc-length resampling):
`blues2`, `greens2`, `purples2`, `lavenders2`, `violets2`, `greys2`, `reds2`, `roses2`, `oranges2`, `browns2`, `yellows2`, `cyans2`, `magentas2`, `neongreens2`

**Sequential — Multi-hue** (12 stops, two or more hues blended in Oklab):
`yellowgreen`, `ember`, `dusk`, `shoal`, `moss`, `GnBu`, `YlGnBu`, `candy`, `lagoon`, `bluestlagoon`, `bluerlagoon`, `bluelagoon`

**Diverging** (13 stops, exact-white pivot at stop 6):
`RdBu`, `RdYlBu`, `PuGn`, `MgGn`, `PkTe`, `GdBu`, `BrTe`, `BrGn`

**Diverging — Sequential pairs** (13 stops, one sequential hue per arm):
`greensblues`, `redsblues`, `redsgreens`, `redscyans`, `redslavenders`, `redsviolets`, `redsneongreens`, `rosesblues`, `rosescyans`, `rosesgreens`, `rosesneongreens`, `orangesblues`, `orangescyans`, `orangespurples`, `orangeslavenders`, `orangesviolets`, `orangesneongreens`, `yellowsblues`, `yellowspurples`, `yellowslavenders`, `brownsblues`, `brownsgreens`, `brownscyans`, `brownsneongreens`, `magentasneongreens`, `magentasgreens`, `magentasblues`, `magentascyans`, `violetsoranges`, `violetsyellows`, `purplesgreens`, `purplesblues`, `purplesneongreens`, `lavendersgreens`, `lavendersblues`, `lavendersneongreens`, `cyanspurples`, `cyanslavenders`, `cyansviolets`, `greysblues`, `greysreds`, `greysgreens`, `greyscyans`, `greysyellows`, `greysoranges`, `greysmagentas`, `greysviolets`, `greysneongreens`, `greyspurples`, `greyslavender`, `greysrose`

**Discrete:**
`nucleotides` (5 colors: A, T, G, C, U), `proteins` (8 biochemical groups: hydrophobic, aromatic, positive, negative, polar, proline, glycine, cysteine)

**Matplotlib ported** (prefixed with `mpl_`):
`mpl_viridis`, `mpl_plasma`, `mpl_inferno`, `mpl_magma`, `mpl_cividis`, `mpl_turbo`, `mpl_Blues`, `mpl_Greens`, `mpl_Greys`, `mpl_Oranges`, `mpl_Purples`, `mpl_Reds`, `mpl_YlGnBu`, `mpl_YlOrBr`, `mpl_YlOrRd`, and more.

**cmocean ported** (prefixed with `cmocean_`):
`cmocean_algae`, `cmocean_amp`, `cmocean_balance`, `cmocean_curl`, `cmocean_deep`, `cmocean_delta`, `cmocean_dense`, `cmocean_diff`, `cmocean_gray`, `cmocean_haline`, `cmocean_ice`, `cmocean_matter`, `cmocean_oxy`, `cmocean_phase`, `cmocean_rain`, `cmocean_solar`, `cmocean_speed`, `cmocean_tarn`, `cmocean_tempo`, `cmocean_thermal`, `cmocean_topo`, `cmocean_turbid`

---

## Saving charts

```python
ds.save(chart, "plots/myplot")
# writes: plots/myplot_light.png, plots/myplot_light.svg
#         plots/myplot_dark.png,  plots/myplot_dark.svg
#         plots/myplot_vegalite.json
```

Produces light and dark PNG and SVG files from a single call. SVG output is post-processed to flatten Vega's redundant `<g>` wrappers, making it easier to navigate in Illustrator. A Vega-Lite JSON spec is also saved by default for full reproducibility.

```python
ds.save(chart, "myplot", ppi=1200)               # default PPI; reduce for faster exports
ds.save(chart, "myplot", save_vega_spec=False)    # skip the JSON spec
ds.save(chart, "myplot", description="Figure 1")  # embed a description in the SVG
```

---

## Data transforms

### dysonsphere.add_jitter()

Adds random Gaussian x-offsets to each row. Each offset is drawn independently from N(0, spread²) — ~68% of points fall within ±spread of centre, ~95% within ±2·spread. Points can overlap; use `add_beeswarm()` for small n where overlap is undesirable.

```python
df = ds.add_jitter(df, spread=5)

alt.Chart(df).mark_circle().encode(
    x=alt.X("group:N"),
    y=alt.Y("value:Q"),
    xOffset=alt.XOffset("jitter_x:Q"),
)
```

| Parameter | Default | Description |
|---|---|---|
| `spread` | `2.0` | Standard deviation of jitter in pixels. Pass `None` to use `2.0` |
| `out_col` | `"jitter_x"` | Output column name |
| `seed` | `20220701` | Random seed |

### dysonsphere.add_beeswarm()

Computes collision-avoiding x-offsets per group using an analytic method. Points are sorted by y position and placed greedily from the centre outward: for each point, the forbidden x intervals imposed by already-placed neighbours are computed exactly as `px ± √((2·spread)² − dy²)`, and the candidate closest to 0 outside all intervals is chosen. Better than jitter for small n; total width grows with n.

```python
df = ds.add_beeswarm(df, y_col="value", group_by=["group"], spread=2.0)

alt.Chart(df).mark_circle().encode(
    x=alt.X("group:N"),
    y=alt.Y("value:Q"),
    xOffset=alt.XOffset("beeswarm_x:Q"),
)
```

| Parameter | Default | Description |
|---|---|---|
| `y_col` | required | Value column |
| `group_by` | required | Column(s) defining each beeswarm group |
| `spread` | `√(markSize/π)` | Collision radius in pixels — defaults to the rendered point radius from the active theme |
| `height_px` | theme `chartHeight` | Chart height in pixels |
| `out_col` | `"beeswarm_x"` | Output column name |

---

## Statistical annotations

`add_pvalue()` annotates one or more group comparisons with p-value brackets, stacking them automatically so they don't overlap. Combine with any chart using `+`.

```python
CATEGORIES = ["Control", "Group A", "Group B"]

# single comparison
chart + ds.add_pvalue(
    df, "group", "value",
    pairs=[("Control", "Group A")],
    categories=CATEGORIES, chartWidth=300,
)

# multiple comparisons — brackets stacked automatically
chart + ds.add_pvalue(
    df, "group", "value",
    pairs=[("Control", "Group A"), ("Control", "Group B"), ("Group A", "Group B")],
    categories=CATEGORIES, chartWidth=300,
)
```

From pre-computed p-values:

```python
ds.add_pvalue(..., pvalues=[0.023], y_positions=[210])

# batch
ds.add_pvalue(..., pvalues=[0.002, 0.031])
```

**Parameters**

| Parameter | Default | Description |
|---|---|---|
| `df` | required | Polars DataFrame |
| `x_col`, `y_col` | required | Column names for groups and values |
| `pairs` | required | List of `(group1, group2)` tuples to annotate |
| `test` | `"mannwhitneyu"` | Statistical test: `"mannwhitneyu"`, `"ttest_ind"`, `"ttest_rel"`, `"wilcoxon"`, `"tukey_hsd"` |
| `pvalues` | `None` | Pre-computed p-values, one per pair (skips all tests) |
| `correction` | `None` | `"bonferroni"` or `None`. Ignored for `tukey_hsd` |
| `n_comparisons` | `len(pairs)` | Number of comparisons for Bonferroni correction |
| `y_positions` | `None` | Explicit y positions per bracket (overrides auto-stacking) |
| `y_start` | auto | Y position of the lowest bracket |
| `y_step` | `y_pad × 2` | Vertical distance between stacking levels |
| `y_pad` | `5` | Padding above data max when y_start is auto-placed |
| `style` | `"line"` | `"line"` (bar only) or `"bracket"` (bar + end ticks) |
| `tick_height` | `0.5` | End tick height in data units (only for `style="bracket"`) |
| `reverse` | `None` | List of `(group1, group2)` tuples identifying brackets to flip below the bar |
| `categories` | inferred | Ordered list of all x-axis categories |
| `chartWidth` | theme default | Chart width used to compute text x position |
| `decimals` | `3` | Decimal places in the p-value label |

---

## Multilabels

`add_multilabel()` attaches a condition table directly below a chart, replacing its x-axis labels. `add_multilabel_detached()` returns the table as a standalone layer for manual composition with `alt.vconcat`.

```python
CONDITIONS = {
    "Condition 1": [True,  False, True,  True],
    "Condition 2": [False, False, True,  False],
    "Condition 3": [False, False, False, True],
}

# attached — x-axis labels replaced by the table
ds.add_multilabel(chart, CONDITIONS, categories=CATEGORIES, style="plusminus")

# detached — compose manually
alt.vconcat(
    chart,
    ds.add_multilabel_detached(CONDITIONS, categories=CATEGORIES, style="symbol"),
).resolve_scale(x="shared")
```

`groups` values should be booleans: `True` for a positive mark, `False` for a negative mark. If any value is a non-bool (`str`, `int`, `float`), the style is automatically set to `"text"` and values are rendered verbatim — useful for numeric scores or arbitrary labels.

Three `style` options are available: `"plusminus"` renders `True` as `+` and `False` as `−`, `"symbol"` renders `True` as a filled mark and `False` as an unfilled mark (shape set by the `symbol` parameter, default `"circle"`) with an optional connecting rule, and `"text"` renders raw values as strings centered under each category.

![Multilabel example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/multilabel_example_light.png)

| Parameter | Default | Description |
|---|---|---|
| `groups` | required | `{row_label: [bool, ...]}` — one `True`/`False` per category; non-bool values force `style="text"` |
| `categories` | required | Ordered list of x-axis categories matching the main chart |
| `style` | `"plusminus"` | `"plusminus"`, `"symbol"`, or `"text"` (auto-set when values are non-bool) |
| `label_align` | `"left"` | `"left"` places row labels left of the multilabel grid; `"right"` places them right |
| `label_padding` | `0` | Gap in pixels between the plot boundary and the label text |
| `order` | insertion order | Top-to-bottom row order |
| `row_height` | `14` | Height in pixels per row |
| `symbol` | `"circle"` | Vega-Lite shape name (`"square"`, `"diamond"`, `"triangle-up"`, etc.) (`"symbol"` style only) |
| `symbol_size` | `markSize × 4` | Symbol area in square pixels (`"symbol"` style only) |
| `connecting_line` | `True` | Draw a rule spanning each consecutive run of `True` values per row (`"symbol"` style only) |
| `strokeWidth` | `markStrokeWidth` | Stroke width for dots and connecting rule |
| `y_padding` | `0.1` | Inner padding between rows as a fraction of band step |
| `chartWidth` | theme default | Width of the annotation chart in pixels |
| `fontSize` | theme default | Font size for symbols and row labels |

> **Dark mode:** `"symbol"` style resolves fill colours from `ds.theme()` at construction time. Pass a callable to `ds.save()` so the chart rebuilds after each darkmode toggle:
> ```python
> ds.save(
>     lambda: ds.add_multilabel(chart, CONDITIONS, style="symbol", ...),
>     "my_plot",
> )
> ```

---

## Custom marks

### dysonsphere.mark_violin()

Violin plot with an embedded boxplot.

```python
ds.theme(chartWidth=300)
palette = ds.palette("lavenders", n=len(CATEGORIES))

chart = ds.mark_violin(df, "group", "value", CATEGORIES, palette=palette)
ds.save(chart, "violin")
```

| Parameter | Default | Description |
|---|---|---|
| `df` | required | Polars DataFrame |
| `x_col` | required | Grouping column name |
| `y_col` | required | Value column name |
| `categories` | required | Ordered list of group labels |
| `palette` | `None` | Single color or list of colors for violin fills |
| `boxplot_size` | `markSize × 0.8` | Boxplot box width in pixels |
| `boxplot_color` | `"black"` | Boxplot fill color |
| `fillOpacity` | theme default | Violin fill opacity |
| `stroke` | `None` | Violin outline color (`None` = no outline) |
| `strokeWidth` | theme default | Violin outline width |
| `legend` | `False` | Show a color legend |
| `angledX` | theme default | Angle x-axis labels |
| `steps` | `200` | KDE grid resolution per group |

### dysonsphere.mark_strip()

Jittered or beeswarm points with a median tick and optional mean ± error bars.

```python
chart = ds.mark_strip(df, "group", "value", CATEGORIES)
chart = ds.mark_strip(df, "group", "value", CATEGORIES, scatter="beeswarm")
```

| Parameter | Default | Description |
|---|---|---|
| `scatter` | `"jitter"` | `"jitter"` (fast, random Gaussian) or `"beeswarm"` (collision-avoidance) |
| `palette` | `None` | List of colors for points |
| `point_size` | theme `markSize` | Point size in sq px |
| `spread` | `None` | Point spread in pixels. For jitter: std dev (defaults to 2.0). For beeswarm: collision radius (defaults to `√(markSize/π)`) |
| `errorbars` | `True` | Show mean ± error bars |
| `errorbar_extent` | `"sem"` | `"sem"` or `"sd"` |

---

## Development

### Building palettes

`scripts/build/build_palettes.py` documents the Oklab recipes for all custom palette families and prints updated hex literals to stdout. Use this to calibrate or extend palettes.

```sh
# uv
uv run python scripts/build/build_palettes.py

# pip
python scripts/build/build_palettes.py
```

The four recipes are:

1. **Sequential single-hue** — fix hue; sweep L from light to dark with C = `frac × Cmax(L, hue)`; arc-length resample to 12 stops.
2. **Sequential multi-hue** — interpolate `(L, hue)` between keyframes; same chroma and arc-length logic.
3. **Diverging** — two arms meeting at an exact-white pivot; 13 stops so the white center lands exactly on the V-corner.
4. **Chroma-scaling** — preserve L, scale `(a, b)` by a constant to derive lighter variants.

Palette hex values live in `dysonsphere/palettes.py` as plain lists — no color math runs at import time.

### Building the gallery

```sh
# uv
uv run python scripts/build/build_gallery.py

# pip
python scripts/build/build_gallery.py
```

Writes `docs/index.html`. Open in a browser to browse all palettes across 11 chart types.

### Exporting swatches for Adobe Illustrator

```sh
# uv
uv run python scripts/build/build_swatches_for_illustrator.py

# pip
python scripts/build/build_swatches_for_illustrator.py
```

Generates `scripts/import_palettes_to_illustrator.jsx`. To import into Illustrator:

1. Open or create a document in Adobe Illustrator.
2. Go to **File > Scripts > Other Script...**
3. Select `scripts/import_palettes_to_illustrator.jsx`.
4. All palettes are added as named swatch groups in the Swatches panel.

Re-run this script after adding or modifying palettes in `dysonsphere/palettes.py`.

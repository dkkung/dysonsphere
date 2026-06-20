# dkkung-altair-theme

Custom Altair/Vega-Lite themes, perceptually uniform palettes, and chart utilities for publication-ready scientific figures.

*This is a personal project under active development, so there may be breaking changes between minor versions.*

![thumbnail](docs/thumbnail_light.png)

## Installation

```sh
# uv
uv pip install -e .

# pip
pip install -e .
```

Requires Python 3.11+. Dependencies: `altair`, `numpy`, `polars`, `scipy`.

---

## Quick start

```python
import altair as alt
import polars as pl
import theme

theme.options(chartWidth=300, chartHeight=200)

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("x:Q"),
        y=alt.Y("y:Q"),
        color=alt.Color("y:Q", scale=alt.Scale(range=theme.palette_range("blues"))),
    )
)

theme.save(chart, "plots/myplot")
# writes: plots/myplot_light.png, plots/myplot_light.svg
#         plots/myplot_dark.png,  plots/myplot_dark.svg
#         plots/myplot_vegalite.json
```

---

## theme.options()

**Call before building any Altair charts to configure global theme defaults.**

```python
theme.options()  # apply defaults

theme.options(   # custom configuration
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

All custom palettes are built in [Oklab](https://bottosson.github.io/posts/oklab/) (Ottosson, *A perceptual color space for image processing*, 2020) for perceptual uniformity. They are stored in `theme.colors`, a plain `dict[str, list[str]]` mapping palette names to 12-stop hex lists (13 stops for diverging palettes).

### Accessing palettes

```python
from theme.palettes import colors

blues = colors["blues"]   # list of 12 hex strings, light → dark
```

### theme.palette_range()

Samples a slice or subset from any named palette.

```python
theme.palette_range("blues")                     # all 12 stops
theme.palette_range("blues", n=5)                # 5 evenly-spaced stops
theme.palette_range("blues", start=3)            # stops 3–11
theme.palette_range("blues", stop=6, step=2)     # indices 0, 2, 4, 6
theme.palette_range("blues", n=4, reverse=True)  # reversed
```

| Parameter | Default | Description |
|---|---|---|
| `name` | required | Key in `colors` |
| `n` | `None` | Return `n` evenly-spaced stops (overrides `step`) |
| `start` | `0` | Index of the first stop to include |
| `stop` | last | Index of the last stop to include (inclusive) |
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

Setting `theme.options(palette="mypalette")` overrides all five types simultaneously.

### Available palettes

See the [palette gallery](https://dkkung.github.io/theme/) for a visual overview of all palettes, or open `docs/index.html` locally.

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

**Matplotlib ported** (prefixed `mpl_`):
`mpl_viridis`, `mpl_plasma`, `mpl_inferno`, `mpl_magma`, `mpl_cividis`, `mpl_turbo`, `mpl_Blues`, `mpl_Greens`, `mpl_Greys`, `mpl_Oranges`, `mpl_Purples`, `mpl_Reds`, `mpl_YlGnBu`, `mpl_YlOrBr`, `mpl_YlOrRd`, and more.

---

## Saving charts

```python
theme.save(chart, "plots/myplot")
# writes: plots/myplot_light.png, plots/myplot_light.svg
#         plots/myplot_dark.png,  plots/myplot_dark.svg
#         plots/myplot_vegalite.json
```

Produces light and dark PNG and SVG files from a single call. SVG output is post-processed to flatten Vega's redundant `<g>` wrappers, making it easier to navigate in Illustrator. A Vega-Lite JSON spec is also saved by default for full reproducibility.

```python
theme.save(chart, "myplot", ppi=1200)               # default PPI; reduce for faster exports
theme.save(chart, "myplot", save_vega_spec=False)    # skip the JSON spec
theme.save(chart, "myplot", description="Figure 1")  # embed a description in the SVG
```

---

## Custom marks

### theme.mark_violin()

Violin plot with an embedded boxplot.

```python
theme.options(chartWidth=300)
palette = theme.palette_range("lavenders", n=len(CATEGORIES))

chart = theme.mark_violin(df, "group", "value", CATEGORIES, palette=palette)
theme.save(chart, "violin")
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

### theme.mark_strip()

Jittered or beeswarm points with a median tick and optional mean ± error bars.

```python
chart = theme.mark_strip(df, "group", "value", CATEGORIES)
chart = theme.mark_strip(df, "group", "value", CATEGORIES, scatter="beeswarm")
```

| Parameter | Default | Description |
|---|---|---|
| `scatter` | `"jitter"` | `"jitter"` (fast, random Gaussian) or `"beeswarm"` (collision-avoidance) |
| `palette` | `None` | List of colors for points |
| `point_size` | theme `markSize` | Point size in sq px |
| `jitter_scale` | `4.0` | Jitter standard deviation in pixels |
| `errorbars` | `True` | Show mean ± error bars |
| `errorbar_extent` | `"sem"` | `"sem"` or `"sd"` |

---

## Statistical annotations

Add a p-value bracket between two groups using `theme.pvalue_layer()`. Combine with any chart using `+`.

```python
ann = theme.pvalue_layer(
    df, "group", "value", "Control", "Drug A",
    test="mannwhitneyu",
    categories=["Control", "Drug A", "Drug B"],
    chartWidth=300,
    y=210,
)
chart + ann
```

From a pre-computed p-value:

```python
ann = theme.pvalue_layer(
    group1="Control", group2="Drug A",
    pvalue=0.023, y=210,
    categories=CATEGORIES,
    chartWidth=300,
)
```

| Parameter | Default | Description |
|---|---|---|
| `df` | `None` | Polars DataFrame (required unless `pvalue` and `y` are both provided) |
| `x_col`, `y_col` | `None` | Column names for groups and values |
| `group1`, `group2` | required | Group labels to compare |
| `test` | `"mannwhitneyu"` | Statistical test: `"mannwhitneyu"`, `"ttest_ind"`, `"ttest_rel"`, `"wilcoxon"`, `"tukey_hsd"` |
| `pvalue` | `None` | Pre-computed p-value (skips the test) |
| `correction` | `None` | `"bonferroni"` or `None` |
| `n_comparisons` | `1` | Number of comparisons for Bonferroni correction |
| `y` | auto | Y position of the bracket in data units |
| `y_pad` | `5` | Padding above the group max when `y` is auto-placed |
| `style` | `"line"` | `"line"` (bar only) or `"bracket"` (bar + end ticks) |
| `categories` | inferred | Ordered list of all x-axis categories |
| `chartWidth` | theme default | Chart width used to compute text x position |
| `reverse` | `False` | Flip the annotation below the bar |
| `decimals` | `3` | Decimal places in the p-value label |

---

## Data transforms

### Jitter

Adds random Gaussian x-offsets to each row, useful for strip plots.

```python
df = theme.add_jitter_offsets(df, scale=5)

alt.Chart(df).mark_circle().encode(
    x=alt.X("group:N"),
    y=alt.Y("value:Q"),
    xOffset=alt.XOffset("jitter_x:Q"),
)
```

| Parameter | Default | Description |
|---|---|---|
| `scale` | `5.0` | Standard deviation of jitter in pixels |
| `out_col` | `"jitter_x"` | Output column name |
| `seed` | `20220701` | Random seed |

### Beeswarm

Computes collision-avoiding x-offsets per group. Better than jitter for small n, but slower.

```python
df = theme.add_beeswarm_offsets(
    df,
    y_col="value",
    group_by=["group"],
    height_px=200,
    markSize=10,
)
```

| Parameter | Default | Description |
|---|---|---|
| `y_col` | required | Value column |
| `group_by` | required | Column(s) defining each beeswarm group |
| `height_px` | theme `chartHeight` | Chart height in pixels |
| `markSize` | `10` | Point size (area in sq px) |
| `out_col` | `"beeswarm_x"` | Output column name |

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

Palette hex values live in `theme/palettes.py` as plain lists — no color math runs at import time.

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

Re-run this script after adding or modifying palettes in `theme/palettes.py`.

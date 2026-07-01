# dysonsphere

An Altair configuration wrapper with perceptually uniform palettes and chart utilities for publication-ready figures.

![thumbnail](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/thumbnail_light.png)

## Installation

```sh
# uv: add as a dependency
uv add dysonsphere

# uv: pip install
uv pip install dysonsphere

# pip
pip install dysonsphere
```

Requires Python 3.11+. Dependencies: `altair`, `numpy`, `polars[pyarrow]`, `scipy`.

All functions that accept a `DataFrame` support both **`polars`** and **`pandas`** dataframes. A `pandas` `DataFrame` is automatically converted to `polars` for internal processing via `ds.ensure_polars()`.

---

## Quick start

```python
import altair as alt
import polars as pl
import dysonsphere as ds  # or: import dysonsphere

ds.theme()  # apply the default dysonsphere theme

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

## Contents

- **[Installation](#installation)**
- **[Quick start](#quick-start)**
- **[dysonsphere.theme()](#dysonspheretheme)**
  - [Config file](#config-file)
    - [`notebook` style](#notebook-style)
- **[Palettes](#palettes)**
  - [Accessing palettes](#accessing-palettes)
  - [dysonsphere.palette()](#dysonspherepalette)
  - [Default palettes](#default-palettes)
  - [Available palettes](#available-palettes)
  - [Exporting palettes as swatches for Adobe Illustrator](#exporting-palettes-as-swatches-for-adobe-illustrator)
- **[Saving charts](#saving-charts)**
  - [Metadata](#metadata)
- **[Chart utilities](#chart-utilities)**
  - [Data transforms](#data-transforms)
    - [Beeswarm](#beeswarm)
    - [Jitter](#jitter)
  - [Custom marks](#custom-marks)
    - [Strip plots (`mark_strip`)](#strip-plots-mark_strip)
    - [Violin](#violin)
  - [Statistical annotations](#statistical-annotations)
    - [Adding p-value annotations](#adding-p-value-annotations)
    - [Correlation](#correlation)
  - [Multilabels](#multilabels)
    - [Sample sizes](#sample-sizes)
    - [Category labels](#category-labels)
    - [Spans](#spans)
  - [Chart annotations](#chart-annotations)
    - [Background shading](#background-shading)
    - [Reference lines](#reference-lines)
    - [Text annotations](#text-annotations)
  - [Non-linear axes](#non-linear-axes)
    - [Axis label reformatting](#axis-label-reformatting)
    - [Minor ticks](#minor-ticks)
- **[Development](#development)**
  - [Building palettes](#building-palettes)
  - [Building docs](#building-docs)

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
| `axisOffset` | `tickSize` | Distance between axis line and data area |
| `axisWidth` | `0.25` | Stroke width of axes, ticks, and rules |
| `bandPadding` | `0.1` | Inner and outer padding for ordinal bands |
| `chartFill` | `"white"` | Background fill of the entire chart |
| `chartHeight` | `100` | Default chart height in pixels |
| `chartWidth` | `100` | Default chart width in pixels |
| `closed` | auto | Draw a border around the plot area. Auto-enabled when `viewFill` is set |
| `cornerRadius` | `False` | Corner rounding for rect, bar, boxplot box, and arc marks. `False` = none; `True` = `min(chartWidth, chartHeight) / 100` (1 px at default 100×100); explicit `float` = pixels. Bars use `cornerRadiusEnd` (tip only); all others use `cornerRadius` (all corners) |
| `darkmode` | `False` | Invert text and axis colors for dark backgrounds |
| `dashedGrid` | `False` | Render axis grid lines dashed (uses `dashedWidth` pattern); off by default so grids are solid |
| `dashedLine` | `False` | Render line marks dashed |
| `dashedRule` | `True` | Render rule marks dashed |
| `dashedWidth` | `[2, 2]` | Dash/gap pattern `[dash, gap]` in pixels |
| `font` | `"HelveticaNeue"` | Font family for all labels and titles |
| `fontSize` | `7` | Font size in points (titles, axis labels — the primary tier) |
| `secondaryFontSize` | `fontSize - 1` | An auxiliary smaller font size, auto-derived from `fontSize` (never below `smallestFontSize`, unless you set `fontSize` below it) unless set explicitly. Available for your own annotations; not consumed by the built-in defaults |
| `smallestFontSize` | `5` | A fixed small font size (points) that also floors `secondaryFontSize`. Accepts an `int` or a `bool`: `True` minimizes the plot by setting `fontSize` to it; an `int` overrides the value; `False` / omitted leaves it simply retrievable. To go below it, pass a smaller `fontSize` directly |
| `fontWeight` | `400` | Font weight: 300 = light, 400 = normal, 700 = bold |
| `sigFigs` | `3` | Significant figures for on-plot statistical labels (`add_comparisons` p-values, `add_correlation` readout). Consistent precision across magnitudes; per-call `sigFigs=` overrides it. (The saved report/metadata uses its own fixed 3 sig figs.) |
| `grid` | `False` | Show axis grid lines |
| `gridColor` | `colors["greys"][0]` | Grid line color |
| `legend` | `True` | Show legends |
| `legendOffset` | `tickSize` | Distance between legend and chart edge |
| `legendStroke` | `False` | Draw a border around the legend box |
| `markFill` | `"black"` | Default fill color for marks |
| `markFillOpacity` | `1.0` | Default mark fill opacity |
| `markSize` | `min(chartWidth, chartHeight) * 0.1` | Mark size; for points, this is area in px<sup>2</sup> |
| `markStroke` | `"black"` | Default stroke color for marks |
| `markStrokeOpacity` | `1` | Default mark stroke opacity |
| `palette` | `None` | **Master** color scheme applied to *all* scale types (category, diverging, heatmap, ordinal, ramp). Accepts a key from `colors`, a custom palette name, a raw hex list, or a Vega scheme name. When set, it overrides the per-type keys below |
| `categoryPalette` | `None` | Override the scheme for **categorical** scales only. Same accepted values as `palette`. Ignored when `palette` is set |
| `divergingPalette` | `None` | Override the scheme for **diverging** scales only |
| `heatmapPalette` | `None` | Override the scheme for **heatmap** scales only |
| `ordinalPalette` | `None` | Override the scheme for **ordinal** scales only |
| `rampPalette` | `None` | Override the scheme for **ramp** (continuous) scales only |
| `strokeCap` | `"round"` | Stroke end cap: `"butt"`, `"round"`, or `"square"` |
| `ticks` | `True` | Show axis ticks |
| `tickSize` | `3` | Tick length in pixels |
| `transparentBackground` | `False` | Transparent chart background (overrides `chartFill`) |
| `viewFill` | `None` | Fill color of the plot area only. Setting this auto-enables `closed` |
| `xAxis` | `True` | Toggle for the x-axis — disabling hides the axis domain and axis ticks, but not axis labels |
| `xDomain` | `True` | Show the x-axis domain line (overridden to `False` when `xAxis=False`) |
| `xLabelAngle` | `0` | X-axis label rotation in degrees (e.g. `-45`); negative = tilt left, positive = tilt right |
| `xLabels` | `True` | Show tick labels on the x-axis |
| `xTicks` | `True` | Show ticks on the x-axis (overridden to `False` when `xAxis=False`) |
| `yAxis` | `True` | Toggle for the y-axis — disabling hides the axis domain and axis ticks, but not axis labels |
| `yDomain` | `True` | Show the y-axis domain line (overridden to `False` when `yAxis=False`) |
| `yLabelAngle` | `0` | Y-axis label rotation in degrees (e.g. `-90`); `labelAlign` is auto-derived from the angle |
| `yLabels` | `True` | Show tick labels on the y-axis |
| `yTicks` | `True` | Show ticks on the y-axis (overridden to `False` when `yAxis=False`) |

### Config file

Persistent per-project or per-user overrides can be stored in a TOML config file. Generate a template with all built-in presets at their defaults:

```python
ds.create_config()                 # writes dysonsphere.toml in the current directory
ds.create_config("/my/dir")        # writes to a specific directory
ds.create_config(persist=True)     # writes to ~/.config/dysonsphere/ or %APPDATA%\dysonsphere\
```

dysonsphere looks for config files in this order (later files take precedence):

1. `~/.config/dysonsphere/dysonsphere.toml` — user-wide; respects `$XDG_CONFIG_HOME`
2. `./dysonsphere.toml` — project-level; found by walking up from the current working directory to the filesystem root (like git locating `.git`)

Each file contains named style sections. Load a style with `ds.theme(style="name")`. Calling `ds.theme()` again with a different `style=` (or none) replaces the theme entirely — styles do not accumulate.

```toml
# dysonsphere.toml
# Theme configuration for dysonsphere.
# Load a style with ds.theme(style="name").

# Only the keys present in a section are applied - everything else uses
# dysonsphere's built-in defaults. Unknown keys raise a ValueError immediately.

# [default] applies to every ds.theme() call regardless of style.
# Leave it empty or omit to use dysonsphere's built-in defaults unchanged,
# or add keys to override the defaults.

[default]

# Built-in styles - edit values or remove sections you don't need.

[notebook]
chartWidth = 900
chartHeight = 900
darkmode = true
fontSize = 18
transparentBackground = true

[presentation]
fontSize = 12
darkmode = true
transparentBackground = true

# Custom styles - add your own style sections below

[my_style]  # Rename to your desired style name

# Custom palettes — lists of hex strings, available via ds.palette("name")
# or ds.theme(palette="name"). dysonsphere palettes are typically 12 stops
# for sequential palettes, and 13 stops for diverging palettes.

[palettes]
# my_palette = ["#DFE9F7", "#C6D9F1", "#ADC8EC", "#94B8E6", "#7AA8E0", "#6097DA", "#4D87CA", "#4177B1", "#386898", "#2F597F", "#264A69", "#1D3A58"]
```

```python
ds.theme(style="notebook")             # load notebook style
ds.theme(style="notebook", grid=True)  # style + per-call override
ds.theme()                             # back to dysonsphere built-in defaults
```

Only the keys present in a style section are applied — everything else uses the dysonsphere built-in defaults. Explicit kwargs always take precedence over the config file. Unknown section keys raise a `ValueError` immediately. Custom palettes in `[palettes]` are loaded globally on every `ds.theme()` call and are reset when `ds.theme()` is called without a config file present.

#### `notebook` style

The `notebook` style is useful for plotting in interactive notebooks, and defaults to using `darkmode=True` plots with a transparent background (*white axes and text, larger `Chart` areas, and larger font sizes*).

---

## Palettes

All palettes are built in [Oklab](https://bottosson.github.io/posts/oklab/) (Ottosson, *A perceptual color space for image processing*, 2020) for perceptual uniformity. They are stored in `dysonsphere.colors`, a plain `dict[str, list[str]]` mapping palette names to 12-stop hex lists (13 stops for diverging palettes).

#### Accessing palettes

```python
from dysonsphere.palettes import colors

blues = colors["blues"]  # list of 12 hex strings, light → dark
```

Custom palettes defined in a `[palettes]` block in `dysonsphere.toml` are merged into `colors` on each `ds.theme()` call and can be accessed the same way:

```python
ds.theme()  # loads custom palettes from dysonsphere.toml if present

my_pal = colors["my_palette"]       # access directly
ds.palette("my_palette", n=5)       # slice with palette()
ds.theme(palette="my_palette")      # set as the default color scheme
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

### Default palettes

When no explicit `scale=` is set on a color encoding, Vega-Lite falls back to the theme's range defaults:

| Range type | Default palette | Override with | Used for |
|---|---|---|---|
| `category` | `blues` (even indices: 0, 2, 4, 6, 8, 10) | `categoryPalette` | Nominal/unordered groups |
| `ordinal` | `blues` | `ordinalPalette` | Ordered discrete values |
| `ramp` | `blues` | `rampPalette` | Sequential continuous (legend ramps) |
| `heatmap` | `blues` | `heatmapPalette` | Rect/heatmap marks |
| `diverging` | `redsblues` | `divergingPalette` | Diverging scales |

Setting `ds.theme(palette="mypalette")` overrides all five types simultaneously. To override an individual type, set its **Override with** key from the table above — each accepts a palette name, a custom palette, a raw hex list, or a Vega scheme name:

```python
ds.theme(divergingPalette="redsblues2", heatmapPalette="greens")   # only those two types change
```

Or in `dysonsphere.toml`:

```toml
[default]
divergingPalette = "redsblues2"

[my_style]
categoryPalette = "reds2"
heatmapPalette  = ["#ffffff", "#000000"]
```

> **Note:** The gallery and examples in this README use `palette="blues2"` rather than the shipped default `blues`. `blues2` is a more saturated variant of `blues`.

### Available palettes

See the [palette gallery](https://dkkung.github.io/dysonsphere/) for a visual overview of all palettes, or open `docs/index.html` locally.

**Sequential — Single-hue** (12 stops, light → dark):
`blues`, `greens`, `purples`, `lavenders`, `violets`, `greys`, `reds`, `rose`, `oranges`, `browns`, `yellows`, `cyans`, `magentas`, `neongreens`

**Sequential — Single-hue 2** (12 stops, deeper saturation built with Oklab arc-length resampling):
`blues2`, `greens2`, `purples2`, `lavenders2`, `violets2`, `greys2`, `reds2`, `pinks2`, `oranges2`, `browns2`, `yellows2`, `cyans2`, `magentas2`, `neongreens2`

**Sequential — Multi-hue** (12 stops, two or more hues blended in Oklab):
`yellowgreen`, `ember`, `dusk`, `shoal`, `moss`, `GnBu`, `YlGnBu`, `candy`, `lagoon`, `bluestlagoon`, `bluerlagoon`, `bluelagoon`

**Diverging** (13 stops, exact-white pivot at stop 6):
`RdBu`, `RdYlBu`, `PuGn`, `MgGn`, `PkTe`, `GdBu`, `BrTe`, `BrGn`

**Diverging — Sequential pairs** (13 stops, one sequential hue per arm):
`greensblues`, `redsblues`, `redsgreens`, `redscyans`, `redslavenders`, `redsviolets`, `redsneongreens`, `pinksblues`, `pinkscyans`, `pinksgreens`, `pinksneongreens`, `orangesblues`, `orangescyans`, `orangespurples`, `orangeslavenders`, `orangesviolets`, `orangesneongreens`, `yellowsblues`, `yellowspurples`, `yellowslavenders`, `brownsblues`, `brownsgreens`, `brownscyans`, `brownsneongreens`, `magentasneongreens`, `magentasgreens`, `magentasblues`, `magentascyans`, `violetsoranges`, `violetsyellows`, `purplesgreens`, `purplesblues`, `purplesneongreens`, `lavendersgreens`, `lavendersblues`, `lavendersneongreens`, `cyanspurples`, `cyanslavenders`, `cyansviolets`, `greysblues`, `greysreds`, `greysgreens`, `greyscyans`, `greysyellows`, `greysoranges`, `greysmagentas`, `greysviolets`, `greysneongreens`, `greyspurples`, `greyslavender`, `greyspinks`

**Diverging — Sequential pairs 2** (13 stops, one deeper-saturation `2` sequential hue per arm):
`greensblues2`, `redsblues2`, `redsgreens2`, `redscyans2`, `redslavenders2`, `redsviolets2`, `redsneongreens2`, `pinksblues2`, `pinkscyans2`, `pinksgreens2`, `pinksneongreens2`, `orangesblues2`, `orangescyans2`, `orangespurples2`, `orangeslavenders2`, `orangesviolets2`, `orangesneongreens2`, `yellowsblues2`, `yellowspurples2`, `yellowslavenders2`, `brownsblues2`, `brownsgreens2`, `brownscyans2`, `brownsneongreens2`, `magentasneongreens2`, `magentasgreens2`, `magentasblues2`, `magentascyans2`, `violetsoranges2`, `violetsyellows2`, `purplesgreens2`, `purplesblues2`, `purplesneongreens2`, `lavendersgreens2`, `lavendersblues2`, `lavendersneongreens2`, `cyanspurples2`, `cyanslavenders2`, `cyansviolets2`, `greysblues2`, `greysreds2`, `greysgreens2`, `greyscyans2`, `greysyellows2`, `greysoranges2`, `greysmagentas2`, `greysviolets2`, `greysneongreens2`, `greyspurples2`, `greyslavenders2`, `greyspinks2`

**Discrete:**
`nucleotides` (5 colors: A, T, G, C, U), `proteins` (8 biochemical groups: hydrophobic, aromatic, positive, negative, polar, proline, glycine, cysteine)

**Matplotlib ported** (prefixed with `mpl_`):
`mpl_viridis`, `mpl_plasma`, `mpl_inferno`, `mpl_magma`, `mpl_cividis`, `mpl_turbo`, `mpl_Blues`, `mpl_Greens`, `mpl_Greys`, `mpl_Oranges`, `mpl_Purples`, `mpl_Reds`, `mpl_YlGnBu`, `mpl_YlOrBr`, `mpl_YlOrRd`, and more.

**cmocean ported** (prefixed with `cmocean_`):
`cmocean_algae`, `cmocean_amp`, `cmocean_balance`, `cmocean_curl`, `cmocean_deep`, `cmocean_delta`, `cmocean_dense`, `cmocean_diff`, `cmocean_gray`, `cmocean_haline`, `cmocean_ice`, `cmocean_matter`, `cmocean_oxy`, `cmocean_phase`, `cmocean_rain`, `cmocean_solar`, `cmocean_speed`, `cmocean_tarn`, `cmocean_tempo`, `cmocean_thermal`, `cmocean_topo`, `cmocean_turbid`

### Exporting palettes as swatches for Adobe Illustrator

```python
ds.export_swatches()           # writes to the current directory
ds.export_swatches("/my/dir")  # writes to a specific directory
```

This writes two files:

- `import_dysonsphere_palettes_to_illustrator.jsx` — loads all palettes into the active document's Swatches panel as named groups.
- `dysonsphere.ase` — an ASE (Adobe Swatch Exchange) library containing all palettes. Automatically copied to your Illustrator User Defined Swatches folder if it can be found; otherwise copy it there manually.

**One-time setup (persistent library):** If the ASE was installed automatically, restart Illustrator and open the library via **Open Swatch Library > User Defined > dysonsphere**. It will now be available in all documents without re-running any script.

**Per-document import (active document only):**
1. Open or create a document in Adobe Illustrator.
2. Go to **File > Scripts > Other Script...**
3. Select `import_dysonsphere_palettes_to_illustrator.jsx`.

All palettes are added to the Swatches panel as named groups (e.g. `blues`, `reds`).

---

## Saving charts

```python
ds.save(chart, "plots/myplot")
# writes: plots/myplot_light.png, plots/myplot_light.svg
#         plots/myplot_dark.png,  plots/myplot_dark.svg
#         plots/myplot_vegalite.json
```

**Always use `ds.save()` instead of `chart.save()`.** `ds.save()` is a wrapper around Altair's built-in save that runs several post-processing steps essential for correct rendering in dysonsphere-themed charts:

- **Tick alignment** — Vega floors axis tick positions to integers for screen rendering; at 1200 PPI this becomes a visible gap between ticks and their marks. `ds.save()` corrects tick transforms to exact float positions.
- **Minor tick correction** — corrects sub-pixel rounding on log-scale and power-scale minor ticks so spacing is visually uniform at high DPI.
- **Axis layering** — moves axis elements to the front so they render above chart marks (relevant for `viewFill`-filled charts).
- **SVG simplification** — flattens Vega's redundant `<g>` wrappers for cleaner Illustrator imports.
- **Light/dark variants** — renders both background modes in a single call by toggling `darkmode` in the active theme.

Calling `chart.save()` directly skips all of the above and will produce misaligned ticks and incorrect minor tick spacing in dysonsphere charts.

`ds.save()` produces light and dark PNG and SVG files from a single call. A Vega-Lite JSON spec is also saved by default for full reproducibility. It accepts any Altair chart type — `Chart`, `LayerChart`, `FacetChart`, `HConcatChart`, `VConcatChart`, or `ConcatChart` — as well as a zero-argument callable that returns one.

```python
ds.save(chart, "myplot", ppi=1200)                 # default PPI; reduce for faster exports
ds.save(chart, "myplot", saveVegaSpec=False)       # skip the JSON spec
ds.save(chart, "myplot", description="Figure 1")   # your own description, in SVG <desc>, PNG iTXt, and the JSON spec
ds.save(chart, "myplot", saveMetadata=False)       # suppress the structured metadata block
ds.save(chart, "myplot", background=["light"])     # light variant only
ds.save(chart, "myplot", background=["dark"])      # dark variant only
```

#### Metadata

By default, `ds.save()` embeds a machine-readable JSON block — `{"provenance": {...}, "statistics": [...]}` — in **all three** outputs, so each file is self-contained and records exactly what produced it:

- **Vega-Lite JSON** — under `usermeta.dysonsphere` (merged into any `usermeta` you set yourself).
- **SVG** — in a `<metadata id="dysonsphere">` element (CDATA).
- **PNG** — in an `iTXt dysonsphere` chunk (read with e.g. `exiftool myplot_light.png`).

The block has these keys:

- `provenance` — the generation facts as structured fields: `user`, `script`, `timestamp` (ISO-8601), `python`, `altair`, `dysonsphere`. (In a Jupyter notebook `script` is `<jupyter-notebook>`; if the OS exposes no username, `user` is `unknown_user`.)
- `statistics` — the structured records from any [`add_comparisons()`](#adding-p-value-annotations) / `add_correlation()` calls (per-group descriptives, the omnibus result, the comparison test + correction method, and every comparison with exact p-values and effect sizes). Read it back with `json.load(open("myplot_vegalite.json"))["usermeta"]["dysonsphere"]["statistics"]` — no text parsing, and trivial to turn into CSV/TSV.
- `report` — the same statistics rendered as a **human-readable table** (the descriptive + effect-size text), so you can read it straight out of the file. On by default (`embedReport=True`); set `embedReport=False` to keep just the structured block. In the SVG and PNG it's carried in its own readable channel (`<metadata id="dysonsphere-report">` / `iTXt dysonsphere-report`, real newlines) rather than escaped inside the JSON blob.

None of this touches `description` — that stays your `description=` text only. (The report is also available standalone via `ds.add_comparisons(..., report=True)` to stdout or `save="dir"` to a `.txt`.)

The `description=` field is entirely yours: whatever you pass is stored verbatim (nothing appended) in the SVG `<desc>`, the PNG `Description` chunk, and the JSON `description` key — so it stays a clean chart label / aria-label.

```python
ds.save(chart, "myplot", description="Figure 1")   # description field: "Figure 1"
```

Pass `saveMetadata=False` to suppress the structured block; your `description` (if any) is still written.

---

## Chart utilities

### Data transforms

#### Beeswarm

`add_beeswarm()` computes collision-avoiding x-offsets per group using an analytic method. Points are sorted by y position and placed greedily from the centre outward: for each point, the forbidden x intervals imposed by already-placed neighbours are computed exactly as `px ± √((2·spread)² − dy²)`, and the candidate closest to 0 outside all intervals is chosen. Better than jitter for small n; total width grows with n.

```python
df = ds.add_beeswarm(df, yCol="value", groupBy=["group"], spread=2.0)

alt.Chart(df).mark_circle().encode(
    x=alt.X("group:N"),
    y=alt.Y("value:Q"),
    xOffset=alt.XOffset("beeswarm_x:Q"),
)
```

| Parameter | Default | Description |
|---|---|---|
| `yCol` | required | Value column |
| `groupBy` | required | Column(s) defining each beeswarm group |
| `spread` | `theme(markSize)` | Collision radius in pixels, derived as `√(markSize/π)` to match the rendered point radius |
| `heightPx` | `theme(chartHeight)` | Chart height in pixels |
| `outCol` | `"beeswarm_x"` | Output column name |

#### Jitter

`add_jitter()` adds random Gaussian x-offsets to each row. Each offset is drawn independently from N(0, spread²) — ~68% of points fall within ±spread of centre, ~95% within ±2·spread. Points can overlap; use `add_beeswarm()` for small n where overlap is undesirable.

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
| `spread` | `min(chartWidth, chartHeight) / 50` | Standard deviation of jitter in pixels. Auto-scaled from theme dimensions (2.0 at default 100×100 px<sup>2</sup>) |
| `outCol` | `"jitter_x"` | Output column name |
| `seed` | `20220701` | Random seed |

![transforms example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/transforms_example_light.png)

### Custom marks

#### Strip plots (`mark_strip`)

Create a `Chart` with jittered or beeswarm points with a median tick and optional mean ± error bars using `mark_strip()`.

```python
chart = ds.mark_strip(df, "group", "value", CATEGORIES)
chart = ds.mark_strip(df, "group", "value", CATEGORIES, scatter="beeswarm")
```

| Parameter | Default | Description |
|---|---|---|
| `scatter` | `"jitter"` | `"jitter"` (fast, random Gaussian) or `"beeswarm"` (collision-avoidance) |
| `palette` | `None` | List of colors for points |
| `markSize` | `theme(markSize)` | Point size in sq px |
| `markOpacity` | `theme(markFillOpacity)` | Point opacity |
| `spread` | `None` | Point spread in pixels. For jitter: std dev (defaults to `min(chartWidth, chartHeight) / 50`). For beeswarm: collision radius (defaults to `√(markSize/π)` from theme) |
| `legend` | `False` | Show a color legend |
| `xLabelAngle` | `theme(xLabelAngle)` | X-axis label rotation in degrees |
| `errorbars` | `True` | Show mean ± error bars |
| `errorbarExtent` | `"sem"` | `"sem"` or `"sd"` |
| `yTitle` | `yCol` | Y-axis title; `None` suppresses it |
| `xTitle` | `xCol` | X-axis title; `None` suppresses it |

#### Violin

Create a violin plot with an embedded boxplot with `mark_violin()`. The returned chart is safe to place in `alt.hconcat()` alongside `mark_strip()` or any other chart — no extra `.resolve_scale()` calls needed.

```python
ds.theme(chartWidth=300)
palette = ds.palette("lavenders", n=len(CATEGORIES))

chart = ds.mark_violin(df, "group", "value", CATEGORIES, palette=palette)
ds.save(chart, "violin")

# side-by-side with mark_strip — works without special resolution
left = ds.mark_strip(df, "group", "value", CATEGORIES)
right = ds.mark_violin(df, "group", "value", CATEGORIES)
ds.save(alt.hconcat(left, right), "comparison")
```

| Parameter | Default | Description |
|---|---|---|
| `df` | required | Polars or pandas DataFrame |
| `xCol` | required | Grouping column name |
| `yCol` | required | Value column name |
| `categories` | required | Ordered list of group labels |
| `palette` | `None` | Single color or list of colors for violin fills |
| `boxplotSize` | `theme(markSize) * 0.8` | Boxplot box width in pixels |
| `boxplotColor` | `"black"` | Boxplot fill color |
| `fillOpacity` | `theme(markFillOpacity)` | Violin fill opacity |
| `stroke` | `None` | Violin outline color (`None` = no outline) |
| `strokeWidth` | `theme(markStrokeWidth)` | Violin outline width |
| `legend` | `False` | Show a color legend |
| `xLabelAngle` | `theme(xLabelAngle)` | X-axis label rotation in degrees |
| `steps` | `200` | KDE grid resolution per group |
| `yTitle` | `yCol` | Y-axis title; `None` suppresses it |
| `xTitle` | `xCol` | X-axis title; `None` suppresses it |

![marks example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/marks_example_light.png)

### Statistical annotations

`add_comparisons()` annotates group comparisons. It has two modes, selected by `test`:

- **Pairwise** (`"mannwhitneyu"`, `"ttest_ind"`, `"ttest_rel"`, `"wilcoxon"`, `"tukey_hsd"`) - draws a bracket per pair in `pairs`, stacked automatically so they don't overlap.
- **Omnibus** (`"anova"`, `"kruskal"`, `"friedman"`, `"alexandergovern"`) - places the omnibus result as a corner label (via `add_text`), and, if `pairs` is given, fills the brackets with a post-hoc test.

> **Renamed in v1.1:** this function was `add_pvalue()` in v1.0. `add_pvalue()` still works as a deprecated alias (it emits a `DeprecationWarning`) and will be removed in v2.0 - switch to `add_comparisons()`.

Combine with any chart using `+`.

#### Pairwise tests

```python
CATEGORIES = ["Group A", "Group B", "Group C"]

# single comparison
chart + ds.add_comparisons(
    df,
    "group",
    "value",
    pairs=[("Group A", "Group B")],
    categories=CATEGORIES,
)

# multiple comparisons — brackets stacked automatically
chart + ds.add_comparisons(
    df,
    "group",
    "value",
    pairs=[("Group A", "Group B"), ("Group A", "Group C"), ("Group B", "Group C")],
    categories=CATEGORIES,
)
```

From pre-computed p-values, with explicit bracket positions:

```python
ds.add_comparisons(..., pvalues=[0.002, 0.031], yPositions=[4.5, 5.2])
```

Brackets below the marks using `reverse` - requires negative `yStep` so levels stack downward, and an explicit `tickHeight` (positive) since auto-compute would produce a negative value:

```python
ds.add_comparisons(
    df,
    "group",
    "value",
    pairs=[("A", "B")],
    categories=["A", "B"],
    bracketStyle="bracket",
    yStart=data_min - yPad,
    yStep=-yStep,
    tickHeight=0.15,
    reverse=[("A", "B")],
)
```

Style or format brackets **per pair** by passing a `dict` (instead of a string) to `bracketStyle` or `notation` — keys match either pair order, and unlisted pairs fall back to the default:

```python
ds.add_comparisons(
    df, "group", "value", pairs=[("A", "B"), ("A", "C")], categories=["A", "B", "C"],
    bracketStyle={("A", "C"): "line"},      # A-C as a plain line, the rest as brackets
    notation={("A", "C"): "scientific"},    # A-C in scientific, the rest plain
)
```

For `notation`, a special `"test"` key sets the omnibus label's format (e.g. `notation={"test": "power"}`).

![p-value example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/pairwise_example_light.png)

#### Omnibus tests

Omnibus ANOVA in the corner + Tukey post-hoc brackets (`omnibusVerbose=True` adds the statistic, df, and effect size to the label):

```python
chart + ds.add_comparisons(
    df,
    "group",
    "value",
    pairs=[("Group A", "Group C"), ("Group B", "Group C")],
    test="anova",                # corner: "ANOVA F(2, 57) = 6.34, P = 0.003, η² = 0.18"
    omnibusVerbose=True,
    testLabelPosition="topLeft",
    categories=CATEGORIES,        # post-hoc defaults to Tukey HSD
)

# omnibus-only (no brackets), print the full descriptive + effect-size report
chart + ds.add_comparisons(df, "group", "value", test="kruskal", categories=CATEGORIES, report=True)
```

The supported post-hocs are Tukey HSD and Dunnett (via `scipy`) plus **Dunn, Nemenyi, and Games-Howell**, which `dysonsphere` computes *in-house* (validated against `scikit-posthocs` and `pingouin`). Every `add_comparisons()` call also generates a descriptive + effect-size report that is appended to the metadata of files written by `ds.save()` (see `report`/`save`). For an omnibus test the report lists **all** pairwise post-hoc comparisons (the full table), not just the pairs you draw brackets for. Report p-values carry the **real computed value at a fixed 3 significant figures** (e.g. `P = 1.22e-11`) — never the floored `P < 0.001` used for on-plot labels, and independent of the on-plot `sigFigs` — so the metadata stays precise regardless of how you style the plot.

![p-value omnibus example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/omnibus_example_light.png)

| Parameter | Default | Description |
|---|---|---|
| `df` | required | Polars or pandas DataFrame |
| `xCol`, `yCol` | required | Column names for groups and values |
| `pairs` | `None` | List of `(group1, group2)` tuples to bracket. Required for pairwise tests; optional for omnibus (omit for a corner label only) |
| `test` | `"mannwhitneyu"` | Pairwise: `"mannwhitneyu"`, `"ttest_ind"`, `"ttest_rel"`, `"wilcoxon"`, `"tukey_hsd"`. Omnibus: `"anova"`, `"kruskal"`, `"friedman"`, `"alexandergovern"` |
| `postHoc` | auto | Post-hoc filling the brackets for omnibus tests. Default per test: `anova→"tukey_hsd"`, `alexandergovern→"games_howell"`, `kruskal→"dunn"`, `friedman→"nemenyi"`. Accepts any pairwise test too |
| `pvalues` | `None` | Pre-computed p-values, one per pair (skips all tests) |
| `correction` | `None` | `"bonferroni"`, `"holm"`, or `None`. Ignored for `tukey_hsd`. For post-hoc matrices, adjusts over all unique pairs |
| `nComparisons` | `len(pairs)` | Number of comparisons for Bonferroni correction |
| `yPositions` | `None` | Explicit y positions per bracket (overrides auto-stacking) |
| `yStart` | auto | Y position of the lowest bracket |
| `yStep` | `yPad * 2` | Vertical distance between stacking levels |
| `yPad` | auto | Padding above data max when `yStart` is auto-placed. Defaults to a fixed ~8 px visual gap (`bracketStyle="line"`) or ~10 px (`bracketStyle="bracket"`), scaled to data units via `chartHeight` |
| `bracketStyle` | `"bracket"` | `"bracket"` (bar + end ticks) or `"line"` (bar only) for all brackets; or a `dict` mapping a pair to its style for per-pair control, e.g. `{("A","B"): "line", ("A","C"): "bracket"}` (keys match either order; unlisted pairs default to `"bracket"`) |
| `labelStyle` | `"p"` | `"p"` renders `P = 0.012` / `P < 0.001`; `"asterisks"` renders `*` / `**` / `***` / `ns` (brackets only — the omnibus label always shows the p-value) |
| `tickHeight` | `tickSize` | End tick height, defaulting to the theme's `tickSize` (px → data units) so bracket ticks match the axis ticks. Only for `bracketStyle="bracket"` |
| `reverse` | `None` | List of `(group1, group2)` tuples identifying brackets to flip below the bar |
| `categories` | inferred | Ordered list of all x-axis categories |
| `chartWidth` | `theme(chartWidth)` | Chart width for computing text x position; auto-read from the active theme, rarely needs to be set explicitly |
| `fontSize` | `theme(fontSize)` | Font size of the p-value / corner labels; defaults to the theme's `fontSize` |
| `sigFigs` | `theme(sigFigs)` | Significant figures for the p-value label (and mantissa in scientific/`e`). Gives consistent precision across magnitudes — e.g. `sigFigs=2` renders both `P = 4.3×10⁻¹⁴` and `P = 0.68`. Trailing zeros stripped. `None` reads the theme (default 3). Plain notation floors at a fixed `P < 0.001` |
| `notation` | `None` | Number format for `labelStyle="p"`. `None` uses `P = 0.012` / `P < 0.001` style. `"scientific"` → `P = 1.23×10⁻⁵`. `"e"` → `P = 1.23e-05`. `"power"` → `P ≈ 10⁻⁵` (rounds to nearest power of 10 — values within the same order of magnitude get the same label, so best for widely spread p-values). `"si"` raises `ValueError`. Or a `dict` for per-pair notation, e.g. `{("A","B"): "scientific", "test": "power"}` — tuple keys are pairs (either order; unlisted → plain), and the special `"test"` key sets the omnibus label's notation |
| `testLabelPosition` | `"auto"` | Corner preset for the single **test label**, whose content adapts: the omnibus **result** (`ANOVA P = 0.003`) for omnibus tests, or the pairwise **test name** (`Mann-Whitney U`) for pairwise tests. `"auto"` shows it at `"topLeft"` for omnibus and hides it for pairwise (opt-in); a preset draws it there; `None` hides it (result still computed for the report/metadata) |
| `testLabel` | `None` | Override string for the test label |
| `omnibusVerbose` | `False` | Omnibus label content: `False` → `ANOVA P = 0.003`; `True` → `ANOVA F(2, 57) = 6.34, P = 0.003, η² = 0.18` |
| `testLabelOffsetX`, `testLabelOffsetY` | `0` | Pixel nudges for the test label |
| `testLabelX`, `testLabelY` | `None` | Explicit coordinates for the test label (data values, category names, or `alt.value(px)`), overriding the preset |
| `report` | `False` | `True` prints the full descriptive + effect-size report to stdout. The report is queued for `ds.save()` metadata regardless |
| `save` | `False` | `True` writes the report to `dysonsphere_report_<timestamp>.txt` in the cwd; a string writes to that directory |

#### Correlation

`add_correlation()` annotates a **scatter** (two continuous variables) with a correlation coefficient, and — for `method="pearson"` only — draws the OLS regression line. `method` matches pandas' `DataFrame.corr` (`"pearson"` / `"spearman"` / `"kendall"`). Like `add_comparisons()`, it reports its result as a corner label and queues a structured record for `ds.save()` metadata. Compose it with `+`.

```python
import altair as alt
import numpy as np
import polars as pl
import dysonsphere as ds

ds.theme()

rng = np.random.default_rng(0)
x = rng.uniform(0, 10, 100)
df = pl.DataFrame({"height": x, "weight": 0.9 * x + rng.normal(0, 1, 100)})

scatter = alt.Chart(df).mark_point().encode(x="height:Q", y="weight:Q")

# Pearson: draws the OLS fit line; the readout is just "r = 0.90" by default
chart = scatter + ds.add_correlation(df, "height", "weight")
ds.save(chart, "plots/correlation")

# other options
scatter + ds.add_correlation(df, "height", "weight", method="spearman")            # ρ, no line
scatter + ds.add_correlation(df, "height", "weight", includePvalue=True)           # r = 0.90, P < 0.001
scatter + ds.add_correlation(df, "height", "weight", coefficient="both")           # r + r²
scatter + ds.add_correlation(df, "height", "weight", verbose=True)                 # r, r², P, and the equation
scatter + ds.add_correlation(
    df, "height", "weight",
    color="#c0392b", strokeWidth=1.2,                                              # curated line style
    lineStyle={"strokeDash": [4, 2]},                                              # raw mark_line passthrough
)
```

![correlation example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/correlation_example_light.png)

The three `method`s report different coefficients; only Pearson has a straight-line model, so `line=` is a no-op for the rank methods:

| `method` | coefficient | line |
|---|---|---|
| `"pearson"` *(default)* | `r` (and `r²`, slope/intercept) | OLS line |
| `"spearman"` | `ρ` | none |
| `"kendall"` | `τ` | none |

The readout is composed from independent parts — by default it shows just the coefficient (`r = 0.90` / `ρ = 0.81`); switch on more with the parameters below. `verbose=True` is the shortcut for the fullest readout.

| Parameter | Default | Description |
|---|---|---|
| `df` | required | Polars or pandas DataFrame |
| `xCol`, `yCol` | required | Column names for the two continuous variables |
| `method` | `"pearson"` | `"pearson"`, `"spearman"`, or `"kendall"` (matches pandas' `DataFrame.corr`) |
| `line` | `True` | Draw the OLS fit line (Pearson only; no-op for rank methods). `False` to suppress and, e.g., compose your own from the recorded slope/intercept |
| `position` | `"topLeft"` | Corner preset (an `add_text` position) for the readout. `None` computes the result for the metadata but draws no label |
| `label` | `None` | Override string for the corner readout |
| `coefficient` | `"r"` | Pearson only — `"r"`, `"r2"` (just r², Excel-trendline style), or `"both"`. Ignored for rank methods |
| `includePvalue` | `False` | Append the p-value to the readout |
| `includeEquation` | `False` | Pearson only — append the fit equation `, y = 0.84x + 0.27` |
| `verbose` | `False` | Shortcut: `True` = `coefficient="both", includePvalue=True, includeEquation=True` (overrides those three) |
| `offsetX`, `offsetY` | `0` | Pixel nudges for the readout |
| `fontSize` | `theme(fontSize)` | Font size of the readout; defaults to the theme's `fontSize` |
| `sigFigs`, `notation` | `theme(sigFigs)`, `None` | Significant figures / number format for the readout — coefficient, r², p-value, and fit equation (as in `add_comparisons`). `sigFigs=None` reads the theme |
| `color`, `strokeWidth`, `strokeDash`, `opacity` | `None` (inherit) | Curated style overrides for the fit line (the same four knobs as `add_rule`). Each defaults to `None`, so the line inherits the theme's `mark_line` config; set one to override just that property |
| `lineStyle` | `None` | A dict of raw `mark_line` properties merged in last, so any Vega-Lite line property is reachable. Keys here **override** the curated `color`/`strokeWidth`/etc. above |
| `report` | `False` | `True` prints the report (coefficient, r², P, fit, n) to stdout; queued for `ds.save()` metadata regardless |
| `save` | `False` | `True` writes the report to a `.txt` in the cwd; a string writes to that directory |

### Multilabels

`add_multilabel()` attaches a condition table directly below a chart, replacing its x-axis labels. Both `groups` and `categories` are optional — you can call it with only sample sizes or category labels if that's all you need.

```python
CONDITIONS = {
    "Condition 1": [True, False, True, True],
    "Condition 2": [False, False, True, False],
    "Condition 3": [False, False, False, True],
}

ds.add_multilabel(chart, CONDITIONS, categories=CATEGORIES, style="plusminus")
```

`groups` values should be booleans: `True` for a positive mark, `False` for a negative mark. If any value in a row is a non-bool (`str`, `int`, `float`), that row is automatically rendered as `"text"` regardless of `style` or `rowStyles`.

Rows can mix styles: set a global `style` and override individual rows with `rowStyles`. Connecting rules only span between `"symbol"` rows — rows of other styles between symbol rows are skipped in run detection without raising an error.

Three `style` options are available: `"plusminus"` renders `True` as `+` and `False` as `−`, `"symbol"` renders `True` as a filled mark and `False` as an unfilled mark (shape set by the `symbol` parameter, default `"circle"`) with an optional connecting rule whose direction is controlled by `orientation`, and `"text"` renders raw values as strings centered under each category.

#### Sample sizes

Pass `showSampleSize=True` to `add_multilabel()` to automatically inject a per-category sample size row. Requires `df` and `xCol`; counts are computed via `ds.count_n()`.

```python
ds.add_multilabel(
    chart,
    CONDITIONS,
    categories=CATEGORIES,
    style="symbol",
    showSampleSize=True,
    df=df,
    xCol="group",           # column used for x-axis grouping
    sampleSizeIndex=0,      # insertion position among rows (default 0 = first)
    sampleSizeLabel="n =",  # row label (default "n =")
)
```

The `n =` row always renders as `"text"` regardless of the global `style` setting. `sampleSizeIndex` follows `list.insert()` semantics: `0` = first, `len(groups)` = last, negative indices count from the end (note: `-1` is second-to-last, not last).

`ds.count_n(df, xCol, categories)` is also available as a standalone helper returning a `list[int]` of per-category row counts — useful for building custom annotation rows or reporting sample sizes elsewhere.

Since `groups` defaults to `{}`, you can show only sample sizes with no other rows:

```python
ds.add_multilabel(chart, categories=CATEGORIES, showSampleSize=True, df=df, xCol="group")
```

#### Category labels

Pass `categoryLabel=True` to `add_multilabel()` to render the x-axis category names as angled text in a dedicated row, replacing the stripped axis labels. This row lives outside the data band scale and is always placed at the top or bottom.

```python
ds.add_multilabel(
    chart,
    CONDITIONS,
    categories=CATEGORIES,
    style="symbol",
    categoryLabel=True,
    categoryLabelPosition="bottom",  # "top" or "bottom" (default "bottom")
    categoryLabelAngle=-45,          # degrees; default -45
    categoryLabelHeight=None,        # auto-computed when None
)
```

`categoryLabelHeight` is auto-computed as `ceil(fontSize × 0.6 × max_len × |sin(angle)| + fontSize × |cos(angle)|)` — the rotated bounding box of the longest label. Pass an explicit value to adjust the space between the category label text and the adjacent data rows.

![Multilabel example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/multilabel_example_light.png)

#### Spans

Pass `span=` to `add_multilabel()` to group x-axis categories under a shared rule or bracket with an optional label. The span extends from the lowest to the highest index of the listed categories, so passing only the first and last members is equivalent to listing all of them.

```python
ds.add_multilabel(
    chart,
    CONDITIONS,
    categories=CATEGORIES,
    span=[
        {"Span 1": ["A", "B", "C"]},
        {"Span 2": ["D", "E", "F"]},
    ],
    spanBracketStyle="line",   # "line" (default) or "bracket"
)
```

Use a list of single-entry dicts instead of a plain dict when you need multiple unlabeled spans (plain dict keys must be unique; `None` or `""` as a key suppresses the label):

```python
span=[{None: ["A", "B", "C"]}, {None: ["D", "E", "F"]}]
```

The span section is always placed below all annotation rows. When `categoryLabel=True` and `categoryLabelPosition="bottom"`, the category label row is deferred to below the spans so the visual order is always: rows → spans → category labels.

![Multilabel span example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/multilabel_span_example_light.png)

| Parameter | Default | Description |
|---|---|---|
| `groups` | `{}` | `{row_label: [bool, ...]}` — one `True`/`False` per category; non-bool values force `style="text"` for that row |
| `categories` | `None` | Ordered list of x-axis categories matching the main chart |
| `style` | `"plusminus"` | Global default style: `"plusminus"`, `"symbol"`, or `"text"` (auto-set per row when values are non-bool) |
| `rowStyles` | `None` | Per-row style overrides as `{row_label: style_string}` or a list of style strings in `row_order`; accepts the same values as `style` |
| `labelAlign` | `"left"` | `"left"` places row labels left of the multilabel grid; `"right"` places them right |
| `labelPadding` | `0` | Gap in pixels between the plot boundary and the label text |
| `order` | insertion order | Top-to-bottom row order |
| `rowHeight` | `10` | Height in pixels per row |
| `symbol` | `"circle"` | Vega-Lite shape name (`"square"`, `"diamond"`, `"triangle-up"`, etc.) (`"symbol"` style only) |
| `symbolSize` | `theme(markSize) * 4` | Symbol area in square pixels (`"symbol"` style only) |
| `connectingLine` | `True` | Draw a connecting rule between consecutive `True` values (`"symbol"` rows only); direction set by `orientation` |
| `orientation` | `"vertical"` | `"vertical"` connects consecutive `True` rows within each column; `"horizontal"` connects consecutive `True` columns within each row (`"symbol"` style only) |
| `strokeWidth` | `theme(markStrokeWidth)` | Stroke width for dots and connecting rule |
| `yPadding` | `0.1` | Inner padding between rows as a fraction of band step |
| `chartWidth` | `theme(chartWidth)` | Width of the annotation chart in pixels |
| `fontSize` | `theme(fontSize)` | Font size for symbols and row labels |
| `showSampleSize` | `False` | Inject a per-category sample size row; requires `df` and `xCol` |
| `df` | `None` | Source DataFrame (Polars or Pandas) for counting samples; used with `showSampleSize=True` |
| `xCol` | `None` | Grouping column in `df`; used with `showSampleSize=True` |
| `sampleSizeIndex` | `0` | Insertion position of the n-row among `groups` rows, using `list.insert()` semantics |
| `sampleSizeLabel` | `"n ="` | Row label for the sample size row |
| `categoryLabel` | `False` | Render x-axis category names as angled text in a dedicated row |
| `categoryLabelPosition` | `"bottom"` | `"bottom"` places the category label row below all data rows; `"top"` places it above |
| `categoryLabelAngle` | `-45` | Rotation angle of the category name text in degrees |
| `categoryLabelHeight` | auto | Height in pixels reserved for the category label row; auto-computed from font size, angle, and longest label when `None` |
| `span` | `None` | Dict or list of single-entry dicts mapping span label → list of categories; `None` or `""` key suppresses the label |
| `spanBracketStyle` | `"line"` | `"line"` draws a plain horizontal rule; `"bracket"` adds vertical end ticks |
| `spanLabelPosition` | `"bottom"` | Where to place the span label relative to the rule: `"bottom"` or `"top"` |
| `spanBracketReverse` | `True` | When `True`, bracket end ticks point toward the annotation rows; when `False`, they point away |
| `spanTickHeight` | `theme(tickSize)` | Height in pixels of the bracket end ticks; only used when `spanBracketStyle="bracket"` |
| `spanGap` | `rowHeight × 0.3` | Vertical gap in pixels between the last annotation row and the span rule |

**Dark mode:** `"symbol"` style resolves fill colours from `ds.theme()` at construction time — positive marks are white, unfilled marks use `greys[11]`. Pass a callable to `ds.save()` so the chart rebuilds after each darkmode toggle:
```python
ds.save(
    lambda: ds.add_multilabel(chart, CONDITIONS, style="symbol", ...),
    "my_plot",
)
```

### Chart annotations

#### Background shading

`add_shade()` builds a background `mark_rect` layer. Compose it behind the main chart with `+`.

**Band mode** (`categories` provided, `positions` omitted): shades every x-axis band, cycling colors through `palette` with `repeat` consecutive ticks per color.

**Positions mode** (`positions` provided): shades explicit coordinate ranges as `(start, end)` tuples. String tuples reference category names on a nominal axis; numeric tuples reference data-space coordinates on a quantitative axis and auto-share the main chart's scale. Set `axis='both'` to draw intersection rects using nested pairs `((x_start, x_end), (y_start, y_end))` — each half is resolved independently, so mixed types (e.g. nominal x + quantitative y) work in the same rect.

```python
# band mode — alternating shades for every x-axis category
shade = ds.add_shade(CATEGORIES, "group")
chart = shade + main_chart

# positions mode — y-axis region (quantitative)
shade = ds.add_shade(
    positions=[(7.5, 10.0)],
    axis="y",
    palette=[ds.palette("blues")[0]],
)

# positions mode — x-y intersection rect
shade = ds.add_shade(
    positions=[((7.5, 10.0), (7.5, 10.0))],
    axis="both",
    palette=[ds.palette("blues")[0]],
    stroke=True,
    strokeDash=True,
)
chart = shade + main_chart

# positions mode — category spans on nominal x
shade = ds.add_shade(
    positions=[("Group A", "Group C"), ("Group E", "Group F")],
    categories=CATEGORIES,
)
```

![shade example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/shade_example_light.png)

| Parameter | Default | Description |
|---|---|---|
| `categories` | `None` | Ordered category list. Required for band mode and string-valued positions |
| `xCol` | `None` | x-axis column name (band mode only; not used internally) |
| `positions` | `None` | List of `(start, end)` tuples (single-axis) or `((x_start, x_end), (y_start, y_end))` tuples (`axis='both'`). Activates positions mode |
| `axis` | `'x'` | `'x'`, `'y'`, or `'both'`. Ignored in band mode (always `'x'`) |
| `palette` | `greys[:nShades]` | List of hex colors to cycle through in light mode. Ignored in dark mode — darkest `nShades` greys are always used. Resolved at call time — pass a callable to `ds.save()` for correct darkmode rendering |
| `nShades` | `2` | Number of colors to use. Slices the first `nShades` stops from `palette` in light mode, or the last `nShades` stops from `"greys"` in dark mode |
| `repeat` | `1` | Number of consecutive ticks covered by each rect before advancing to the next color (band mode only) |
| `opacity` | `1.0` | Fill opacity |
| `stroke` | `False` | `True` → axis-style border: black/white per dark mode, `axisWidth` wide |
| `strokeWidth` | `None` | Explicit border width in pixels. Overrides `axisWidth` when `stroke=True` |
| `strokeDash` | `None` | `None` → solid; `True` → inherit `dashedWidth` from theme; list (e.g. `[4, 2]`) → explicit pattern |
| `flush` | `None` | Extend outermost rects to the axis domain edge. `None` inherits from `theme(closed=...)` |

#### Reference lines

`add_rule()` builds a horizontal or vertical `mark_rule` layer. Compose it with the main chart using `+`.

```python
# Horizontal line at y=0
chart = base + ds.add_rule(0)

# Labeled horizontal line — label above-left by default
chart = base + ds.add_rule(5.0, label="Threshold", color="#c0392b")

# Two horizontal lines, labels at the right end of each line
chart = base + ds.add_rule(
    [4.0, 8.0],
    label=["Lower limit", "Upper limit"],
    labelAlign="right",
    color="#c0392b",
)

# Vertical line, label at top-right by default
chart = base + ds.add_rule(10, axis="x", label="Intervention", color="#c0392b")

# Vertical line, label to the left of the line
chart = base + ds.add_rule(10, axis="x", label="t₀", labelPosition="left")
```

`labelAlign` controls where **along** the line the label is anchored; `labelPosition` controls which **side** of the line it sits on.

![reference line example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/reference_line_example_light.png)

| Parameter | Default | Description |
|---|---|---|
| `value` | required | Coordinate(s) on the axis; `float` or `list[float]` |
| `axis` | `"y"` | `"y"` = horizontal line(s); `"x"` = vertical line(s) |
| `label` | `None` | Text label(s); one string per value |
| `labelAlign` | `"left"` / `"top"` | Where along the line to anchor the label. `axis="y"`: `"left"`, `"center"`, or `"right"`. `axis="x"`: `"top"`, `"center"`, or `"bottom"` |
| `labelPosition` | `"top"` / `"right"` | Which side of the line the label sits on. `axis="y"`: `"top"` or `"bottom"`. `axis="x"`: `"right"` or `"left"` |
| `labelOffsetX` | `0` | Additional horizontal pixel offset on the label. Positive = right, negative = left |
| `labelOffsetY` | `0` | Additional vertical pixel offset on the label. Positive = down, negative = up |
| `color` | `None` | Line and label color; `None` inherits from theme |
| `strokeWidth` | `None` | Line width in pixels; `None` inherits from theme |
| `strokeDash` | `None` | `None` = theme `dashedRule`; `False` = solid; `True` = `dashedWidth`; list = explicit pattern |
| `opacity` | `1.0` | Line opacity |
| `fontSize` | `None` | Label font size; `None` inherits from theme |

#### Text annotations

`add_text()` places one or more text annotations at arbitrary positions within a chart. Compose it with the main chart using `+`.

```python
# Annotation at a data coordinate (nominal x + quantitative y)
chart = base + ds.add_text("n = 20", x="Control", y=1.0, align="center", baseline="bottom")

# Named position preset — flush with the top-left axis domain edge
chart = base + ds.add_text("ANOVA p < 0.001", position="topLeft")

# Named position preset — bottom-right corner, nudged inward
chart = base + ds.add_text("Threshold = 5.0", position="bottomRight", offsetX=-4)
```

The `x` and `y` parameters accept three forms: a `float`/`int` for quantitative data coordinates (shares the main chart's scale automatically), a `str` for nominal band centers, or `alt.value(n)` to pin to a fixed pixel position independent of the data. The `position` preset sets `x`, `y`, `align`, and `baseline` automatically from `chartWidth` / `chartHeight` in the active theme; explicit arguments override any preset value.

![text annotation example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/text_example_light.png)

| Parameter | Default | Description |
|---|---|---|
| `text` | required | Annotation string(s); pass a list with matching-length `x`/`y` lists for multiple annotations in one call |
| `x` | `None` | Horizontal coordinate: `float`/`int` (quantitative), `str` (nominal band center), or `alt.value(n)` (fixed pixel); required if `position` not set |
| `y` | `None` | Vertical coordinate; same three forms as `x`; required if `position` not set |
| `position` | `None` | Named position preset on a 3×3 grid: `"topLeft"`, `"topCenter"`, `"topRight"`, `"middleLeft"`, `"middleCenter"`, `"middleRight"`, `"bottomLeft"`, `"bottomCenter"`, `"bottomRight"` |
| `angle` | `0` | Rotation in degrees, clockwise; negative values wrapped automatically to [0, 360] |
| `align` | `"left"` | Horizontal text anchor: `"left"`, `"center"`, or `"right"`; overrides `position` |
| `baseline` | `"middle"` | Vertical text anchor: `"top"`, `"middle"`, `"bottom"`, or `"alphabetic"`; overrides `position` |
| `offsetX` | `0` | Horizontal pixel nudge after positioning; positive = right |
| `offsetY` | `0` | Vertical pixel nudge after positioning; positive = down |
| `color` | `None` | Text color; `None` inherits from theme |
| `fontSize` | `None` | Font size in points; `None` inherits from theme |
| `fontWeight` | `None` | `"normal"`, `"bold"`, or numeric CSS weight (100–900); `None` inherits from theme |
| `fontStyle` | `None` | `"normal"` or `"italic"`; `None` inherits from theme |
| `font` | `None` | Font family name (e.g. `"sans-serif"`, `"Georgia"`); `None` inherits from theme |
| `opacity` | `1.0` | Text opacity |

### Non-linear axes

`add_log_ticks()` and `add_pow_ticks()` add unlabeled minor ticks to log- and power-scaled axes respectively. Both wrap your chart in a layer with an invisible second axis — your chart's data, scale domain, and axis labels are unaffected. Both work with `alt.Chart`, `alt.LayerChart`, and any chart type composable with `alt.layer()`, including `hconcat` and `vconcat` layouts.

> **Note:** Always use `ds.save()` rather than `chart.save()`. `ds.save()` runs an SVG post-processing step that corrects the sub-pixel rounding Vega applies to tick transforms, ensuring consistent minor tick spacing at high DPI.

![Nonlinear scale example](https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/nonlinear_example_light.png)

#### Axis label reformatting

`log_label_expr()` returns a Vega `labelExpr` string for log-scale axis labels. Four notations are available, although `e` and `si` are also supplied with base `altair` via Vega-Lite's d3 `format()`.:

```python
# Power notation — 10⁴, 10⁵, 10⁶, … (any integer base)
axis = alt.Axis(
    values=[10**e for e in range(exp_min, exp_max + 1)],
    labelExpr=ds.log_label_expr(),
)

# Power notation — log2 axis: 2⁰, 2¹, …, 2²⁰
axis = alt.Axis(
    values=[2**e for e in range(0, 21)],
    labelExpr=ds.log_label_expr(base=2),
)

# Scientific notation — 1×10⁴, 1×10⁵, 1×10⁶, … (base-10 only)
axis = alt.Axis(
    values=[10**e for e in range(exp_min, exp_max + 1)],
    labelExpr=ds.log_label_expr(notation="scientific"),
)

# E-notation — 1e+4, 1e+5, 1e+6, … (base-10 only)
axis = alt.Axis(
    values=[10**e for e in range(exp_min, exp_max + 1)],
    labelExpr=ds.log_label_expr(notation="e"),
)

# SI prefix notation — 10k, 100k, 1M, … (base-10 only)
axis = alt.Axis(
    values=[10**e for e in range(exp_min, exp_max + 1)],
    labelExpr=ds.log_label_expr(notation="si"),
)
```

| Parameter | Default | Description |
|---|---|---|
| `base` | `10` | Logarithm base matching the axis scale |
| `notation` | `"power"` | `"power"` (e.g. `10⁴`, any integer base), `"scientific"` (e.g. `1×10⁴`), `"e"` (e.g. `1e+4`), or `"si"` (e.g. `10k`, `1M`). All notations except `"power"` require `base=10`. Power and scientific support exponents up to ±99 |

#### Minor ticks

**`add_log_ticks()`** — **Base 10** places ticks at the conventional 2×–9× integer multiples within each decade (8 minor ticks per decade, fixed). **Base 2** places `nMinor` equally-spaced ticks per octave in log space — default `nMinor=1` gives one tick at the geometric midpoint (√2 × 2ⁿ). Other integer bases also work using the same equal-spacing rule.

```python
# log10 y-axis — exp range auto-derived from data
chart = (
    alt.Chart(df)
    .mark_line(point=True)
    .encode(
        y=alt.Y(
            "value:Q",
            scale=alt.Scale(type="log", base=10),
            axis=alt.Axis(values=[10**e for e in range(exp_min, exp_max + 1)]),
        ),
    )
)
chart = ds.add_log_ticks(chart, df, "value")

# log2 x-axis — fold change on a volcano plot
exp_min, exp_max = -4, 4
chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X(
            "fc:Q",
            scale=alt.Scale(type="log", base=2, domain=[2**exp_min, 2**exp_max]),
            axis=alt.Axis(values=[2**e for e in range(exp_min, exp_max + 1)]),
        ),
    )
)
chart = ds.add_log_ticks(chart, df, "fc", axis="x", base=2, expMin=exp_min, expMax=exp_max)

# log2 with 3 minor ticks per octave
chart = ds.add_log_ticks(chart, df, "fc", axis="x", base=2, nMinor=3)

# both axes log-scaled
chart = ds.add_log_ticks(chart, df, axis="both", xField="fc", yField="pvalue")
```

The `expMin` / `expMax` parameters are auto-derived from `df[field].min()` / `.max()` when omitted. When specifying an explicit `domain=` on the main chart's scale, pass matching `expMin` / `expMax` to `add_log_ticks()` so the minor tick layer's internal domain aligns correctly.

| Parameter | Default | Description |
|---|---|---|
| `Chart` | required | Chart to add minor ticks to |
| `df` | required | Polars or pandas DataFrame |
| `field` | `None` | Log-scaled column name. Required for single-axis mode; omit when `axis='both'` |
| `axis` | `'y'` | `'x'`, `'y'`, or `'both'`. When `'both'`, provide `xField` and `yField` instead of `field` |
| `base` | `10` | Logarithm base matching the axis scale (`10` or `2` are the common choices) |
| `nMinor` | `1` | Minor ticks per interval for non-base-10 axes. Ignored when `base=10` |
| `expMin` | auto | Lowest exponent (in the given `base`). Auto-derived from data when `None` |
| `expMax` | auto | Highest exponent. Auto-derived from data when `None` |
| `xField` | `None` | Log-scaled x column (`axis='both'` only) |
| `yField` | `None` | Log-scaled y column (`axis='both'` only) |
| `xExpMin`, `xExpMax` | auto | Exponent overrides for x axis (`axis='both'` only) |
| `yExpMin`, `yExpMax` | auto | Exponent overrides for y axis (`axis='both'` only) |
| `minorTickSize` | `tickSize / 2` | Minor tick length in pixels; defaults to half the active theme's `tickSize` (typically `1.5` at the default `tickSize=3`) |

**`add_pow_ticks()`** adds minor ticks to a power- or sqrt-scale axis. Unlike `add_log_ticks()`, `majorValues` is required — it must match the `values=` passed to the main chart's `alt.Axis` so the minor tick layer can compute interval boundaries. Minor ticks are placed at positions equally spaced in the power-transformed (visual) space: tick `k` of `nMinor` between major ticks `a` and `b` falls at `(a**exp + k/(nMinor+1) * (b**exp − a**exp))**(1/exp)`.

A useful convention for choosing major ticks on a sqrt axis: pick values whose square roots are evenly spaced. For example, `[0.25, 1.0, 2.25, 4.0]` gives `√L = 0.5, 1.0, 1.5, 2.0` — equal visual spacing.

```python
# sqrt y-axis — major ticks equally spaced in √y
major_values = [0, 1, 4, 9, 16, 25]
chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        y=alt.Y(
            "value:Q",
            scale=alt.Scale(type="pow", exponent=0.5),
            axis=alt.Axis(values=major_values),
        ),
    )
)
chart = ds.add_pow_ticks(chart, df, "value", majorValues=major_values)

# sqrt x-axis with 4 minor ticks per interval
chart = ds.add_pow_ticks(
    chart,
    df,
    "length",
    axis="x",
    exponent=0.5,
    majorValues=[0.25, 1.0, 2.25, 4.0],
    nMinor=4,
)

# both axes power-scaled
chart = ds.add_pow_ticks(
    chart,
    df,
    axis="both",
    xField="length",
    yField="value",
    xMajorValues=[0.25, 1.0, 2.25, 4.0],
    yMajorValues=[0, 1, 4, 9, 16, 25],
)
```

| Parameter | Default | Description |
|---|---|---|
| `Chart` | required | Chart to add minor ticks to |
| `df` | required | Polars or pandas DataFrame |
| `field` | `None` | Power-scaled column name. Required for single-axis mode; omit when `axis='both'` |
| `axis` | `'y'` | `'x'`, `'y'`, or `'both'`. When `'both'`, provide `xField`, `yField`, `xMajorValues`, and `yMajorValues` |
| `exponent` | `0.5` | Power exponent matching the axis scale (`0.5` = sqrt, `2` = quadratic) |
| `majorValues` | required | Ordered major tick data values. Must match `axis.values=` on the main chart |
| `nMinor` | `4` | Minor ticks between each pair of major ticks |
| `minorTickSize` | `tickSize / 2` | Minor tick length in pixels; defaults to half the active theme's `tickSize` (typically `1.5` at the default `tickSize=3`) |
| `xField` | `None` | Power-scaled x column (`axis='both'` only) |
| `yField` | `None` | Power-scaled y column (`axis='both'` only) |
| `xMajorValues` | `None` | Major tick values for x axis (`axis='both'` only) |
| `yMajorValues` | `None` | Major tick values for y axis (`axis='both'` only) |

---

## Development

### Building palettes

`scripts/build/print_palettes.py` documents the Oklab recipes for all custom palette families and prints updated hex literals to stdout. Use this to calibrate or extend palettes.

```sh
# uv
uv run scripts/build/print_palettes.py

# pip
python3 scripts/build/print_palettes.py
```

The four recipes are:

1. **Sequential single-hue** — fix hue; sweep L from light to dark with C = `frac × Cmax(L, hue)`; arc-length resample to 12 stops.
2. **Sequential multi-hue** — interpolate `(L, hue)` between keyframes; same chroma and arc-length logic.
3. **Diverging** — two arms meeting at an exact-white pivot; 13 stops so the white center lands exactly on the V-corner.
4. **Chroma-scaling** — preserve L, scale `(a, b)` by a constant to derive lighter variants.

Palette hex values live in `dysonsphere/palettes.py` as plain lists — no color math runs at import time.

### Building docs

Run all build scripts in one command:

```sh
# uv
uv run scripts/build_all.py

# pip
python3 scripts/build_all.py
```

This runs all scripts in `scripts/build/` in sorted order, rebuilding all assets in `docs/` used by the README and the palette gallery.


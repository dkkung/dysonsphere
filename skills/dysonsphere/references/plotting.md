# Plotting and composition

Read this for chart selection, styling, category alignment, labels, or size-dependent panels.
Examples target core Dysonsphere 4.0.0. Each Python block is standalone, uses synthetic data, and writes
to the current directory. Run examples in an empty directory; adapt their inputs and paths for real work.

## Choose a representation, not a wrapper

| Question | Starting point |
| --- | --- |
| Relationship between continuous variables | Native Altair points; add a fit only when justified |
| Ordered measurements or a time course | Native lines, with explicit series identity and order |
| Distribution across categories | Individual observations; `ds.mark_strip()` for points plus a summary |
| Distribution shape with sufficient observations | `ds.mark_violin()`; assess whether KDE is appropriate |
| Counts or supplied summaries | Native bars/points with explicitly defined intervals if available |
| Matrix of measured values | Native rects with a scale appropriate to the values and units |
| Tabular results or condition labels | `ds.mark_table()` or `ds.add_multilabel()` as appropriate |

Do not connect independent samples as a time series, treat repeated measurements as independent
replicates, or add an inferred interval to a supplied summary. For unequal sampling, retain counts
and the observational unit. Large scatterplots may need an explicitly agreed aggregation rather
than hidden subsampling or thousands of labels.

## Minimal native chart

The synthetic values below are independent observations. No test or trend line is requested.
No formats are specified, so saving uses the theme defaults: SVG + JSON under built-in settings.

```python
# example: scatter
import altair as alt
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({"input": [1, 2, 3, 4, 5, 6], "response": [1.3, 1.8, 3.4, 3.6, 5.2, 5.7]})
ds.theme(width=180, height=120)
chart = alt.Chart(data).mark_point().encode(
    x=alt.X("input:Q", title="Input (a.u.)"),
    y=alt.Y("response:Q", title="Response (a.u.)"),
)
ds.save(chart, "skill_scatter")
```

When editing, retain the user's mappings, filters, summaries, and justified scale settings.
Use the existing dataframe library rather than converting the whole project to Polars for this example.

## Validate only what the analysis needs

Check that required columns are present, not that they are the only columns. An unused notes column
may contain blanks without invalidating a scatterplot. Check missingness and numeric finiteness in
the plotted/tested columns; if explicit exclusion is authorized, record the removed counts and apply
the same analytical subset to the plot and test. Preserve the original frame rather than deleting
extra columns to make a strict schema check pass. Select columns separately when limiting export exposure.

## Theme and color decisions

- `ds.theme(width=180, height=120, fontSize=6)` controls the panel's intrinsic size and nominal
  publication font size. Width/height exclude surrounding axes and legends; inspect the full export
  before claiming it meets a physical figure-width requirement. Raster export scales from 72 intrinsic
  units per inch. A higher `ppi` adds pixels, not larger text relative to the panel.
- A second `ds.theme()` call replaces active settings. Set related options together and retain the
  intended style/configuration. Theme config is figure-wide, not independent for each subchart.
- `ds.palette("cat1", 3)` returns a list of colors; it does not change the theme. Palette names are
  case-sensitive. Use categorical colors for unordered groups, sequential ramps for ordered magnitude,
  and diverging ramps only when there is a meaningful center. Avoid claiming CVD safety for an
  arbitrary selection; use shape or direct labels when color alone would be ambiguous.
- For a native categorical encoding, set an explicit `alt.Scale(domain=categories, range=colors)`
  when consistent category-to-color correspondence matters. Sorting an axis alone does not pin color.
- The theme's master `palette` overrides its per-type palettes. Use `categoryPalette`, `rampPalette`,
  or an explicit native encoding range when only that use should change.
- `ds.palettes.accents["blue"]` is a single emphasis color, not a palette. It resolves the current
  light/dark mode at lookup time. Rebuild the lookup inside a callable for multi-background exports.

## Composite marks and annotations

- `ds.mark_strip(data, "group", "value", categories, ...)` requires each observed category exactly
  once. To show a subset, filter explicitly first; do not use `categories` to hide observations.
  The default shows mean +/- SEM. `errorbarExtent="sd"` changes the interval to SD;
  `errorbars=False` changes the center to the median. Choose deliberately, not as a cosmetic toggle.
  `scatter="beeswarm"` avoids random jitter, but its geometry depends on construction dimensions.
  Validate used values explicitly: strip plots do not enforce the same missing/non-finite checks
  as statistical annotations, and summaries may ignore nulls. Intentionally align plotted and tested rows.
- `ds.mark_violin()` needs adequate, nondegenerate observations for KDE. Do not invent observations
  or jitter measured values to bypass validation. A point plot may be more truthful for sparse groups.
- `palette` selects category colors; `fill` is a fixed color on strip/violin marks. Do not supply both.
  Fixed fill does not recolor every summary element. Parent `.encode()` supports axis/legend
  customizations, but it is not a recursive rewrite of child encodings. In particular, a strip
  chart's child y encodings can defeat a parent-only domain setting. Do not index internal layers
  to patch around it; for explicit matched domains use native layers whose encodings you own, below.
- Layer bare annotations with `+`: `ds.rule(y=threshold)`, `ds.rule(x=start, x2=end, y=low, y2=high)`,
  `ds.shade(...)`, `ds.text(...)`, and `ds.labels(...)`. Inspect signatures for coordinate conventions;
  do not guess whether an option is in pixels or data units. `add_*` functions instead take a chart.
- For `ds.labels(data, "x", "y", "name", subset=...)`, pass the full plotted dataframe so all points
  remain obstacles. `subset` selects labels, not plotted rows. `None` labels all rows; an integer
  selects spatially distributed observations, not the most significant ones. Lists of label values
  can match multiple rows; use a positional boolean mask to select specific duplicate names.
- Label placement models standard linear scales and cannot see arbitrary sibling marks. Match
  `xDomain`/`yDomain` to explicit base domains when needed; do not promise collision-free placement
  on nonlinear scales or overcrowded panels. Rebuild after changing font or geometry and inspect.
- Faceting a globally calculated annotation does not recalculate it within each panel. Compute
  panel-specific results from the correct subsets, or explicitly label a global result separately.

## Composition with matching quantitative scales

Use ordinary layering, concatenation, and faceting when they suffice. Use `ds.assemble()` builders
for panels whose marks or annotations resolve sizes during construction. Calling `.properties()`
on an already-built panel does not rescale its precomputed geometry.

Shared units and matching Python domain arguments do not guarantee matching rendered scales.
Concatenations normally have independent positional scales; labeled `ds.assemble()` panels also
introduce nested composition scopes. A root `.resolve_scale(y="shared")` is not a universal fix
for those scopes. Equal-height panels can instead use independent scales with the same explicit
domain, padding, and scale type, provided those settings reach every contributing unit encoding.

This synthetic example uses native layers for that explicit control. It shows independent specimens
at different loads and a 3 mN subset with mean +/- sample SD, not a confidence interval. A strip plot
is still convenient when its automatic domain is appropriate; do not rebuild every strip by hand.

```python
# example: panels
import altair as alt
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({
    "formulation": ["Reference"] * 8 + ["Modified"] * 8,
    "load_mN": [1, 1, 2, 2, 3, 3, 3, 3] * 2,
    "extension_mm": [1.0, 1.2, 1.8, 2.2, 2.7, 3.0, 3.3, 3.6, 0.5, 0.7, 1.0, 1.3, 1.4, 1.7, 2.0, 2.3],
})
endpoint = data.filter(pl.col("load_mN") == 3)
categories = ["Reference", "Modified"]
y_domain = [0, 4]
ds.theme()


def category_color():
    return alt.Color(
        "formulation:N",
        scale=alt.Scale(domain=categories, range=[ds.palettes.accents["grey"], ds.palettes.accents["blue"]]),
        legend=alt.Legend(title=None, orient="bottom"),
    )


def relationship():
    return alt.Chart(data).mark_point().encode(
        x=alt.X("load_mN:Q", title="Applied load (mN)"),
        y=alt.Y("extension_mm:Q", title="Extension (mm)", scale=alt.Scale(domain=y_domain)),
        color=category_color(),
    ).properties(
        title=alt.Title("All specimens", subtitle="n = 8 per formulation", anchor="start"),
    )


def endpoints():
    base = alt.Chart(endpoint).encode(
        x=alt.X("formulation:N", sort=categories, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("extension_mm:Q", title="Extension (mm)", scale=alt.Scale(domain=y_domain)),
        color=category_color().legend(None),
    )
    points = base.mark_point()
    errorbars = base.mark_errorbar(extent="stdev")
    means = base.mark_tick().encode(
        y=alt.Y("mean(extension_mm):Q", title="Extension (mm)", scale=alt.Scale(domain=y_domain)),
    )
    return (points + errorbars + means).properties(
        title=alt.Title("3 mN endpoint", subtitle="Mean ± SD; n = 4 each", anchor="start"),
    )


def build_figure():
    return ds.assemble([(relationship, 180, 130, "a"), (endpoints, 120, 130, "b")], spacing=24)


ds.save(build_figure, "skill_panels")
```

The explicit domain is retained on the points, the errorbar's input, and the mean's aggregate
encoding. Do not replace the mean's y encoding with shorthand that drops its scale. Keep the
builders at equal heights for aligned ticks; different heights do not give equal pixels per unit.
For different units or intended independent zooms, choose separate domains and make that clear instead.

Check that both zero and an upper common tick align in the rendered figure. When uncertain, inspect
the saved JSON compiled with `vl_convert.vegalite_to_vega()`; identical intended settings in source
are not evidence of identical effective scales. Merely passing schema/checksum validation is not enough.
Builders inherit `assemble()`'s panel size; do not reset it with `ds.theme()` inside them. The outer
save callable also rebuilds colors for requested background variants, as described in the export reference.

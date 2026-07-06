# Changelog

## [Unreleased]

### Breaking changes

- **`theme(transparentBackground=)` renamed to `theme(transparent=)`.** Shorter, and it pairs with the `save(transparent=)` parameter - the same question answered at the theme level (the chart's logical background: notebook display, JSON, HTML) and per export. The old name (keyword argument and `dysonsphere.toml` key) is removed. Note: files exported by v2.x bake the old key into their theme block, so `load(applyTheme=True)` on them raises - use `load(raw=True)` or re-export.
- **The `presentation` built-in style preset is removed.** `theme(style="presentation")` now raises the standard unknown-style `ValueError` unless you define a `[presentation]` section in your own `dysonsphere.toml` (config-file styles are unaffected; the old preset was three lines - `fontSize = 12`, `darkmode = true`, `transparent = true`). `notebook` remains the only shipped preset, and the `create_config()` template follows.
- **`dysonsphere.layers` is split into `dysonsphere.annotations` and `dysonsphere.inference`.** The catch-all module held three unrelated families; it is dissolved: `add_rule` / `add_text` / `add_shade` / `add_labels` now live in `annotations.py`, and `add_comparisons` / `add_correlation` in `inference.py` (statistical inference - the annotation wrappers around the pure `statistics.py` engine). The label-placement engine moved from `utils` to the private `_placement.py`. The public namespace is unchanged (`ds.add_rule` etc. work as before); only deep imports like `from dysonsphere.layers import add_rule` need updating.
- **The package namespace is tightened to the intended API.** Every module now defines `__all__`, so the ~31 public names are all the `dysonsphere` namespace exposes. Previously the star-imports leaked every module-level import onto it - `ds.np`, `ds.pl`, `ds.alt`, `ds.math`, `ds.json`, even `ds.field` (from `dataclasses`) were importable; code relying on those must import the real packages directly.
- **`beeswarm_offsets` is now private (`_beeswarm_offsets`).** It was the undocumented low-level engine behind `add_beeswarm`, which remains the public API (and covers the same use via `yCol`/grouping). Call the underscore name if you truly need raw pixel offsets.

### New features

- **The package ships a `py.typed` marker (PEP 561).** dysonsphere has been fully type-annotated all along, but without the marker downstream type checkers discarded the annotations; now `mypy`/`pyright`/`ty` users get real signatures for the whole API.

- **`label_expr()` and `labelMap=` - presentable labels without renaming data.** `ds.label_expr({"metadata_group1": "group 1"})` builds the Vega `labelExpr` that maps raw data values to display labels, usable on any axis, legend, or facet header; a list value renders as a multi-line label, unmapped values fall back to the raw value, and quoting/escaping is handled (the generated ternary chain also avoids the `{...}[datum.value] || datum.value` idiom's silent misfire on falsy labels). `mark_strip`/`mark_violin` accept the mapping directly via `labelMap=`, and `add_multilabel(labelMap=)` applies it to the category-label row. Presentation-only: the data, exported JSON, checksums, and statistics records keep the raw values.
- **`save(transparent=)`.** Exports have always rendered the SVG/PNG with a transparent background (so figures composite onto any page or slide); that is now a per-call choice instead of a force. `transparent=True` (default) is unchanged; `transparent=False` fills the background with the theme's `chartFill` (white in light mode, black in dark mode, unless set explicitly) - for images viewed on their own, e.g. a README. There is deliberately no global default for it, so a config file can never silently make exports opaque. Applies to the SVG/PNG render only; the JSON and HTML keep the chart's logical background.
- **`add_rule(data=)` / `add_text(data=)` / `add_shade(data=)` facet-safe mode.** Composable annotations couldn't be faceted: by default each carries its own small dataset, and Altair refuses to facet a layered chart whose layers don't all share one data variable (and the `facet(data=)` workaround silently fails to partition). Passing `data=` (the same DataFrame as the base chart) switches to datum mode - the annotation shares that frame and is positioned by a constant `alt.datum` / `alt.value`, so `(base + add_rule/add_text/add_shade(..., data=df)).facet(...)` works and the annotation repeats in every panel. `add_shade` supports it in positions mode (band mode raises). Accepts polars or pandas; the default (no `data=`) behavior is unchanged. Also fixes a latent bug where a numeric `add_shade` range could leak its internal field name into the axis title.

- **`save()` provenance `dataChecksum`.** The embedded provenance block gains a third identity field: `dataChecksum`, a `sha256:` fingerprint of the chart's input data. Unlike `vegaliteChecksum` (which changes with row order, since the inlined data is part of the spec it hashes), `dataChecksum` identifies the *data* independent of how it was drawn - two charts with different Vega-Lite specs (marks, encodings, themes) but the same data share it. It is order-independent (re-sorted rows still match) and excludes dysonsphere's own internal sidecar datasets, so adding an annotation layer never changes it. Multi-frame charts (e.g. `hconcat`) get a sorted list, one entry per input dataframe. The identity fields now lead in the order `dataChecksum`, `vegaliteChecksum`, `exportIdentifier`.
- **`save(description=)` embedded in the metadata block.** The description now also rides inside `usermeta.dysonsphere.description` - as the last member, and in every format's structured blob (JSON, and the JSON embedded in exported SVG/PNG) - so it is machine-readable via `read(what="metadata")`, alongside the existing native `description` / SVG `<desc>` / PNG `iTXt` channels.
- **Runtime versions grouped under `provenance.environment`.** `provenance` gains a nested `environment` dict — `{python, altair, dysonsphere, numpy, scipy, polars}` — the interpreter, the tool, and its declared runtime dependencies, in one place. `numpy`, `scipy`, and `polars` are new (the reported statistics/correlations and the inlined data are produced with them, so their versions are the pins needed to reproduce those numbers). The human-readable "Generated by …" sentence lists them all.
- **Statistics records tagged with a `dataChecksum`.** Each `add_comparisons()` / `add_correlation()` record now carries a `dataChecksum` - the order-independent fingerprint (same algorithm as the provenance `dataChecksum`) of the dataframe it was computed from. So two annotations from different dataframes are distinguishable in `usermeta.dysonsphere.statistics`, and ones from the same data match regardless of row order. It also feeds the record's content hash, so distinct-data annotations never collapse. When the annotation is on the chart's inlined frame, the record's `dataChecksum` equals the top-level `provenance.dataChecksum`.
- **`theme(boxplotOutliers=)`.** Show boxplot outlier points (hidden by default, since the house style overlays raw data via `mark_strip`/beeswarm where separate outlier glyphs would double-draw). `False` (default) hides them; `True` shows them at `markSize / 10`; a number sets an explicit point size. Per-chart `mark_boxplot(outliers={"size": n})` still overrides.
- **`categorical()` qualitative palette.** A four-hue qualitative palette (blue, pink, yellow, green) derived from the existing base palettes - nothing generated de novo. `ds.categorical(members=1)` (default) returns the flat categorical palette (tier-major, for unrelated groups); `members=2..4` returns a grouped palette (hue-major) for paired data (`A1`/`A2` …), where each group is one hue climbing through `members` lightness levels. Sort categories so a group's members are adjacent, then pass `scale=alt.Scale(range=ds.categorical(2))`. Colorblind-robust (deuteranopia-clean); green and yellow are kept non-adjacent. Also exposed as `colors["categorical"]`.
- **`theme(inwardTicks=)`.** Axis ticks point *into* the plot (the physics/astronomy convention) instead of outward. `False` (default) is unchanged; `True` also defaults `closed=True` (a boxed frame with `axisOffset=0`, since inward ticks need a closed axis - an explicit `closed=False` still wins). Applies to the primary x/y axes, any explicitly-enabled secondary (right/top) axis, and log/power minor ticks, with no mirroring on the opposite axes. Rendered through `ds.save()` as an SVG post-process (Altair's schema rejects the negative `tickSize` that would do it natively). Demo: `scripts/plots/inward_ticks.py`.
- **`ds.show(chart)`.** Render a chart through the full `ds.save()` post-processing pipeline and return it as an `IPython.display.SVG` for accurate inline display in a notebook, without writing a file. Altair's own inline renderer skips dysonsphere's SVG fixers, so its preview is approximate (un-typeset superscript labels, the axisOffset grid gap, and - most visibly - `inwardTicks` still pointing outward); `ds.show()` shows the same corrected SVG that `ds.save()` writes. Accepts the same chart types as `save()` (including a callable). Requires IPython (present in notebooks).
- **`save(format="html")`.** Write a self-contained interactive HTML file (the Vega JS runtime is bundled in, so it works offline): tooltips, pan, zoom. It's fully themed and carries the `dysonsphere` metadata block, but - because it renders live in the browser via Vega - it does NOT get dysonsphere's static SVG post-processors (inward ticks, superscript typesetting); it's the interactive tier, alongside the publication-accurate `svg`/`png`. Tick positions are exact in HTML too - that fix lives in the theme config. Combines with the other formats and `background` variants. Demo: `scripts/plots/html_export.py`.

### Changes

- **`add_shade(strokeDash=False)` now renders solid.** The undocumented `False` input used to leak a literal `False` into the mark's `strokeDash` property; it now resolves to `[0, 0]` (forced solid), matching the project-wide `strokeDash` convention (`None` solid-by-default, `True` themed dash, list passthrough).
- **Corrected the `ds.save()` rationale in the non-linear tick docs.** The README and `add_log_ticks`/`add_pow_ticks` notes still claimed `ds.save()` fixes sub-pixel tick rounding - that fixer was deleted when tick alignment moved into the theme config (ticks are exact in any renderer). The advice stands for the remaining SVG corrections and metadata embedding, and now says so.
- **`categorical(members=)` accepts up to 10 members** (was capped at 4). `members<=4` keep the exact classic tier stops (unchanged output); `5`-`10` spread the lightness stops evenly across the usable ramp, shrinking within-hue contrast with each extra member - documented, with a pointer to sequential per-group slices for ordinal series. Raises above 10, where distinct stops run out.
- **`mark_strip` specs are deterministic.** The mean/error summary used an order-nondeterministic `group_by`, so two builds of the identical chart could differ in inlined dataset order (changing the spec checksum and the error-bar z-order run to run). The summary now preserves input group order.
- **Custom marks share a `_MarkScaffold` (internal).** `mark_violin`/`mark_strip` now build their shared chrome (dataframe coercion, title sentinels, x-axis with label angle + mapping, x/y/color encodings with category sorting and palette handling) from one composition helper, so shared parameters land once for every mark. Output specs are unchanged (verified identical).
- **`mark_circle` dots have no outline.** The theme's circle config no longer applies `markStroke` - at the small overlay-dot default size a stroke swamps the fill. Set `stroke` per chart to restore one. `mark_strip`/beeswarm points are unaffected: they now pin the house outline explicitly instead of inheriting it from the circle config.
- **Theme options read through one accessor.** Modules used to read theme options as `alt.theme.options.get(key, hardcoded)` with the default re-hardcoded at ~60 call sites (several already stale). A single internal accessor now falls back to the derived built-in defaults, so a helper called before `ds.theme()` sees the same values a fresh `ds.theme()` would set, and defaults can no longer drift per call site.
- **Band-axis pixel math consolidated into `band_geometry()`.** The band-scale step/centre/edge formulas were hand-rolled at six sites (violin centres, strip offset scale, all three `add_shade` modes, the p-value bracket midpoint, multilabel spans), each re-deriving the padding arithmetic. One tested helper in `utils` now provides all three scale variants (offset / band / point); positions are unchanged.
- **SVG post-processor pipeline parses once.** `save()`/`show()` used to parse and rewrite the SVG file once per fixer (up to five round trips); the fixers now share one parsed tree and the corrected SVG is serialized once. Output is unchanged, except every saved SVG now consistently starts with the XML declaration (previously it was dropped when the superscript fixer was the last to touch the file).
- **`chartFill=None` (the default) is now darkmode-aware.** Auto resolves to white in light mode and **black in dark mode** (previously dark mode had no fill, which rendered as transparent-or-white depending on the viewer). The resolution now happens at render time, so `save(background=["light", "dark"], transparent=False)` fills each variant correctly. An explicit `chartFill` is used as-is in both modes.
- **Tick alignment fixed at the source; the SVG tick-position fixers are gone.** Vega rounds axis tick/grid positions to integer pixels while marks stay fractional, which at high DPI drifted ticks visibly off their marks; through v2.0 dysonsphere corrected this after rendering with ~400 lines of SVG surgery (`_fix_tick_alignment`, `_fix_log_minor_ticks`). The theme now renders with Vega's `tickRound: false` (`config.axis`) and `tickOffset: 0` (`config.axisBand`), so every tick lands on the exact fractional scale position - identical to its mark to the last digit - for band centres (boxplot/strip/violin), linear axes, heatmap bin edges, log/power minor ticks, and every hconcat/vconcat panel. Both fixers are deleted (the grid-line y-span extension they carried lives on as `_extend_grid_span`). Because the fix is theme config, it travels with the spec: `format="html"` and bare-chart notebook previews now get exact ticks too, not just `ds.save()`/`ds.show()` output.
- **Default `markFill` is now light grey** (`colors["greys"][1]`, `#DBDBDB`) instead of `"black"` - all filled marks (bars, boxplot boxes, arcs, points) default to a light grey that reads on both light and dark backgrounds. `markMedianFill` is now `"black"` (was `"white"`) to contrast the grey box.
- **Boxplot proportions tuned.** Box width `markSize * 0.8` → `* 0.9`, whisker end-cap ticks `markSize * 0.6` → `* 0.45` (half the box width), and the median renders as a single thin stroke.
- **Default `axisOffset` / `legendOffset` are now `tickSize * 1.5`** (was `tickSize`) - a slightly larger gap between the axis (and legend) and the plot, resolved once in `theme()`. Set either explicitly to override.
- **`add_comparisons()` bracket spacing tightened.** The auto `yStep` (the vertical gap between stacked p-value brackets) now defaults to `yPad * 1.5` instead of `yPad * 2.25` - multi-level brackets stack more compactly (~15 px per level instead of ~22 px). Pass `yStep=` to override.
- **Default categorical color range is now the multi-hue `categorical` palette** (blue/pink/yellow/green) instead of a monochromatic blue ramp (`blues[::2]`). Nominal (`:N`) color scales pick it up automatically via `config.range.category`, which is now a **bare array** so colors map positionally (category *i* → color *i*) - the tier-major hue cycling depends on it (the `{"scheme": [...]}` form samples/interpolates and is invalid for nominal). A Vega scheme *name* set via `categoryPalette` still passes through wrapped.
- **Default ordinal color range is now `greys`** (was `blues`) - ordered categorical (`:O`) scales default to a grey ramp.
- **Default diverging color range is now `pinksblues`** (was `redsblues`) - a pink↔blue diverging map whose extremes (`#C35082` / `#4177B1`) are the categorical palette's pink and blue, tying the defaults together. Near-identical to `redsblues` in appearance; `redsblues` remains available via `divergingPalette="redsblues"`.

## [2.0.0] - 2026-07-01

### Breaking changes

- **`add_pvalue()` removed.** It was renamed to `add_comparisons()` in v1.1 and kept as a `DeprecationWarning`-emitting alias; that alias is now gone. Use `add_comparisons()`.
- **`decimals` removed** (replaced by `sigFigs`, significant figures) on `theme()` / `add_comparisons()` / `add_correlation()` - see the `sigFigs` entry below.
- **`save()` defaults and output control.** `save()` now writes **SVG + JSON, light background only** by default (previously light+dark PNG+SVG+JSON). A new `format` param (`"svg"`/`"png"`/`"json"`, string or list) controls which files are written, and `background` (`"light"`/`"dark"`, string or list) which variants; both default to the new theme options `saveFormat` (`["svg", "json"]`) / `saveBackground` (`"light"`), so the export defaults are configurable globally or in `dysonsphere.toml`. The `saveVegaSpec` parameter is **removed** (use `format` with/without `"json"`). Filenames now get a `_light`/`_dark` suffix **only when more than one background** is rendered — a single-background export writes clean names (`fig.svg`, `fig.json`), and the JSON dropped its `_vegalite` infix (now `fig.json`). Invalid or empty `format`/`background` raises `ValueError`.

### New features

- **`export_swatches()` palette selection and custom name.** `ds.export_swatches(palettes=[...])` exports only the named palettes (keys of `ds.colors`) instead of all of them; `None` (default) still exports everything. `name=` (default `"dysonsphere"`) renames the generated `.jsx` / `.ase` files and the Illustrator swatch library. Both are additive, so the default call is unchanged.
- **`save()` `maxRows=` / `overrideMaxRows=`.** Every output format inlines the chart's data to render (and the JSON embeds it for `read(what="data")`), so `save()` now blocks data over `maxRows` (default `5000`, matching Altair) with a **clear error** instead of Altair's raw `MaxRowsError` or a silently huge file. Raise `maxRows=` to allow larger data, or pass `overrideMaxRows=True` to remove the cap entirely.
- **Robust statistics attribution + `clear_stats()`.** `save()` now embeds only the statistics whose annotations are actually in the chart being saved — a stats chart built but never saved can no longer contaminate a later `save()` of a different chart. Each `add_comparisons()`/`add_correlation()` tags its layer with an internal marker (stripped from the output); `save()` matches by it. `ds.clear_stats()` drops any pending records (useful in notebooks). Provenance also gains two identity fields: **`vegaliteChecksum`** (a `sha256:` of the chart's spec, for validation — same content ⇒ same checksum) and **`exportIdentifier`** (a `uuid4` shared by every file from one `save()` call).
- **`read()` and `load()`** - read a dysonsphere-exported file back in. `ds.read(path, what="report"|"statistics"|"metadata"|"data")` pulls the embedded metadata from a PNG/SVG/JSON — or, with `what="data"`, rebuilds the original data from the JSON spec (the whole frame, including columns the chart never plotted; dysonsphere's internal sidecar datasets are filtered out, so you get just your data — a chart layering two of your own frames raises, pass `dataset="all"`/`"<name>"`) in the form you choose via `output=` — `"polars"` (default), `"pandas"`, `"duckdb"` (a queryable relation), or `"records"` (raw `list[dict]`); pandas/duckdb are imported only on request, not added as dependencies — the report table (printed; re-rendered from the records if it wasn't embedded), the structured records (exact floats), or the whole block. `ds.load(path)` rebuilds a composable Altair object from the Vega-Lite JSON and re-applies the figure's saved theme (`raw=True` returns the untouched spec dict; `applyTheme=False` leaves the active theme alone). `save()` now also bakes the resolved `ds.theme()` arguments into `usermeta.dysonsphere.theme`, so styling is recorded and reconstructable.
- **`save()` `embedReport=`** - the human-readable report is now embedded in every output by default (`True`), so you can read it straight out of a saved file. `usermeta.dysonsphere.report` is a container keyed by section — `report.provenance` (a "Generated by …" sentence, always present) and `report.statistics` (the descriptive + effect-size table, when the chart has any) — leaving room for future renderings; in the SVG and PNG each section rides in its own readable channel (real newlines: `<metadata id="dysonsphere-report-<section>">` / `iTXt dysonsphere-report-<section>`). It never touches `description`. Set `embedReport=False` to keep only the structured block.
- **`theme()` `sigFigs=` (replaces `decimals`)** - statistical labels are now formatted to a number of **significant figures** rather than decimal places, so precision stays visually consistent across magnitudes (`sigFigs=2` renders both `P = 4.3×10⁻¹⁴` and `P = 0.68`). Set the default in `theme(sigFigs=3)` or per-call on `add_comparisons()`/`add_correlation()`; it also drives the correlation readout's `r`/`r²`/slope/intercept (previously fixed at 2 decimals). Trailing zeros are stripped, and plain notation floors at a fixed `P < 0.001`. The `decimals` parameter has been removed. The saved report/metadata uses its own fixed 3 significant figures, independent of the on-plot `sigFigs`.
- **`theme()` `secondaryFontSize=`** - an auxiliary smaller font size, auto-derived as `fontSize - 1` (never dropping below `smallestFontSize`) unless set explicitly. Exposed for your own annotations.
- **`theme()` `smallestFontSize=`** - a fixed small font size (`5` pt) that also floors `secondaryFontSize`. Accepts an `int` or a `bool`: `True` minimizes the plot by setting `fontSize` to it; an `int` overrides the value; otherwise it's simply retrievable via `alt.theme.options`. Pass a smaller `fontSize` directly to go below it.
- **`add_comparisons()` test label** - a single label whose content adapts to the test: the omnibus result for omnibus tests, or the pairwise **test name** (e.g. "Mann-Whitney U", "Tukey HSD") for pairwise tests. Controlled by `testLabelPosition` (`"auto"` shows it for omnibus, hides it for pairwise), `testLabel`, `testLabelOffsetX/Y`, and `testLabelX/testLabelY` for manual coordinates. Renames the previous `omnibus*` label params (`omnibusVerbose` stays). The multiple-comparison **correction method** is now recorded in the metadata (`comparisons.correction`) and shown in the text report.
- **`add_comparisons()` per-pair `bracketStyle` / `notation`** - both now also accept a `dict` mapping a pair to its value, e.g. `bracketStyle={("A","B"): "line", ("A","C"): "bracket"}` or `notation={("A","B"): "scientific", "test": "power"}`, for mixed styles/notations in one call (keys match either pair order; unlisted pairs fall back to the default). `notation` also supports a special `"test"` key for the omnibus label's notation. Plain string values still apply uniformly.
- **`add_comparisons()` defaults** - `bracketStyle` now defaults to `"bracket"` (bar + end ticks, the common significance-annotation style) instead of `"line"`; bracket end-tick height defaults to the theme's `tickSize` (so ticks match the axis ticks and reverse brackets no longer need an explicit `tickHeight`); and the omnibus/test label always shows the p-value (`labelStyle="asterisks"` now applies only to the pairwise brackets). Statistics labels default to the theme's primary `fontSize`, and `reverse=True` labels are no longer cramped against the bar.
- **`add_correlation()`** - annotate a scatter with a correlation coefficient. `method="pearson"` (default; matches pandas' `DataFrame.corr`) draws the OLS fit line; `"spearman"` / `"kendall"` report the rank coefficient with no line. The corner readout is composed from independent parts — `coefficient` (`"r"` / `"r2"` / `"both"`), `includePvalue`, `includeEquation`, with `verbose=True` as a "show everything" shortcut — and defaults to just the coefficient. The fit line inherits the theme's `mark_line` config, with curated overrides (`color`/`strokeWidth`/`strokeDash`/`opacity`), a raw `lineStyle` dict passthrough, and `line=False` to suppress. Feeds the same structured metadata as `add_comparisons()`.

## [1.0.0] - 2026-06-30

v1.0.0 marks the first stable release of dysonsphere.

## Breaking changes

- **All public API parameters renamed to camelCase** (`xCol`, `yCol`, `bracketStyle`, `labelStyle`, `yPad`, `yStep`, `markSize`, `markOpacity`, `xTitle`, `yTitle`, `xLabelAngle`, `yLabelAngle`, etc.) to align with Altair and Vega-Lite conventions. Any code using the old snake_case names will break.
- `mark_strip()`: `pointSize` / `pointOpacity` → `markSize` / `markOpacity`
- `theme()`: `angledX` / `verticalY` removed → replaced by `xLabelAngle` / `yLabelAngle` (accept any angle in degrees)
- `add_multilabel_detached()` removed - now private as `_multilabel_layer()`
- `adobe_greys` palette removed from `colors`

---

## New features

### Chart utilities

#### Multilabels
- **`add_multilabel()` `spans=`** - group contiguous x-axis categories under a labeled or unlabeled bracket.
- **`add_multilabel()` `showSampleSize=`** - injects a per-category count row; `sampleSizeIndex=` controls insertion position and `sampleSizeLabel=` sets the row label (default `"n ="`).
- **`add_multilabel()` `categoryLabel=`** - renders x-axis category names as angled text in a dedicated row; `categoryLabelAngle=` (default `-45`), `categoryLabelPosition=` (`"top"` / `"bottom"`), `categoryLabelHeight=` (auto-computed from label length and angle).
- **`add_multilabel()` empty `groups={}`** - `groups` and `categories` now default to empty/`None`, so `showSampleSize=True` or `categoryLabel=True` can be used without any condition rows.
- **`add_multilabel()` `rowStyles=`** - accepts a list (ordinal) or dict (by label) to set style per row.
- **`add_multilabel()` `orientation=`** - `"vertical"` (default) or `"horizontal"` connecting lines.

#### Chart annotations
- **`add_shade()`** - background rect shading with band mode (alternating per category), positions mode (quantitative/nominal ranges), `axis="both"` for x-y intersection rects, `flush`, `stroke`, `strokeDash`, `nShades`, `repeat`, `opacity`.
- **`add_rule()`** - horizontal and vertical reference lines with optional labels; `axis="y"` / `"x"`, `labelAlign`, `labelPosition`, `labelOffsetX/Y`, `strokeDash`.
- **`add_text()`** - text annotations at data coordinates (`:Q` or `:N`), pixel coordinates (`alt.value()`), or one of 9 named position presets (`"topLeft"`, `"bottomRight"`, etc.).

#### Statistical annotations
- **`add_pvalue()` `notation=`** - `"scientific"`, `"e"`, or `"power"` notation for p-value labels; `decimals=` controls precision.

#### Custom marks
- **`mark_strip()` / `mark_violin()`** - `xTitle=`, `yTitle=` for explicit axis titles; `xLabelAngle=` on `mark_strip()`.
- **Pandas DataFrame support** - all public functions that accept a DataFrame now accept both `polars` and `pandas` via `ensure_polars()`.

#### Non-linear axes
- **`add_log_ticks()` / `add_pow_ticks()`** - minor ticks for log-scale and power-scale axes; `axis="both"` for dual-axis charts.
- **`log_label_expr()`** - Vega `labelExpr` string for typeset axis labels in `"power"` (10⁴), `"scientific"` (1×10⁴), `"e"` (1e+4), or `"si"` (10k) notation.

### Theming via `ds.theme()`
- **`style=`** - load named preset styles (`"notebook"`, `"presentation"`) or user-defined styles from `dysonsphere.toml`.
- **`create_config()`** - scaffold a `dysonsphere.toml` with all defaults; `persist=True` writes to the platform user config directory.
- **`cornerRadius=`** - `False` (default), `True` (auto-scales to chart size), or explicit `float`. Applies rounded corners to rects and bars.
- **`xLabelAngle=` / `yLabelAngle=`** - accept any float angle in degrees; `labelAlign` is auto-derived from the sign.
- **`axisRight` / `axisTop`** - fully configured to mirror their primary-axis counterparts.
- **Axis visibility toggles** - `xAxis`, `yAxis`, `xLabels`, `yLabels`, `xDomain`, `xTicks`, `yDomain`, `yTicks`.
- **`dashedGrid=`** - toggle dashed grid lines independently of `dashedRule`.
- Chart title now correctly centers to the full layout group (`anchor="middle"`, `frame="group"`).
- **Arc mark donut default** - `mark_arc` now defaults to a donut (`innerRadius = min(chartWidth, chartHeight) / 4`, `padAngle = 0.03`). Override with `mark_arc(innerRadius=0, padAngle=0)` for a full pie.
- **Errorbar defaults** - stem stroke width is now `markStrokeWidth × 2`; tick caps are rounded (`cornerRadius = markStrokeWidth`).
- **Boxplot tick cap rounding** - whisker caps now use `cornerRadius = markStrokeWidth`.
- **`mark_strip()` mark size** - default scatter point size increased from `markSize / 5` to `markSize / 4`.

### Palettes
- **14 pastel `*3` palettes** - `blues3`, `reds3`, `greens3`, etc. Low-chroma, light-end-only sweeps in Oklab for soft/muted use cases.
- **102 new diverging palettes** - 51 paired from the `*2` saturated set (e.g. `redsblues2`, `greyspinks2`) and 51 from the new `*3` pastel set (e.g. `redsblues3`, `greyspinks3`).
- **Custom palettes via config file** - define `[palettes]` in `dysonsphere.toml`; custom palettes are available via `ds.palette()` and `ds.theme(palette=)` like any built-in palette.

### Adobe Illustrator swatch export
- `ds.export_swatches()` writes both an **ExtendScript JSX** (loads palettes into the active document) and a **`dysonsphere.ase`** (Adobe Swatch Exchange) binary file.
- The `.ase` file is automatically copied to the Illustrator User Defined Swatches folder if detected; after restarting Illustrator it appears under Open Swatch Library > User Defined > dysonsphere.

### Save
- **Generation metadata** - production info (script name, username, Python/Altair/dysonsphere versions, UTC timestamp) is embedded in SVG `<desc>`, Vega-Lite JSON `description`, and a PNG `iTXt Description` chunk. Controlled by `saveMetadata=True` (default) and `description=`.
- **`background=`** - pass `["light"]` or `["dark"]` to render only one variant.
- **Callable chart support** - pass a zero-argument callable instead of a chart object; it is re-invoked per variant so dark-mode-sensitive colors (e.g. `add_multilabel(style="symbol")`) render correctly.
- Accepts all six Altair compound chart types: `Chart`, `LayerChart`, `FacetChart`, `VConcatChart`, `HConcatChart`, `ConcatChart`.

---

## Bug fixes

- **`_fix_tick_alignment()`** - grid lines were skipped (regex only matched tick format); grid lines now also have their y-span extended by `axisOffset` to eliminate the gap at the top chart border; box mark centers used to resolve Case pi / Case 0 ambiguity in mixed strip+violin layouts.
- **`_fix_log_minor_ticks()`** - per-panel grouping prevents cross-panel contamination in `hconcat`; dropped incorrect `hi + 1.0` interval tolerance that misplaced the 9× tick.
- **`_fix_superscript_labels()`** - corrects misaligned Unicode superscript digits in scientific/power notation p-value labels by replacing them with `<tspan dy>` elements.
- **`mark_violin()`** - x-centering now uses the correct boxplot band formula (Case pi), fixing visual misalignment in `hconcat`.
- **`_layer_axes_to_front()`** - fixed `viewFill` rendering bleeding through the top layer.
- **`_simplify_svg()`** - eliminated duplicate `<g>` wrapper groupings in exported SVGs.
- **`add_shade()`** - fixed sub-pixel gray seam between adjacent same-color rects; fixed flush=False centering on outer bands.
- **`add_multilabel()`** - fixed connecting-line ordering bug that could reorder rows; fixed `False` boolean values rendering with a hyphen in mixed-type rows.
- **Minor tick sizes** - now default to `tickSize / 2` (was hardcoded to 1.5px).
- **p-value `yPad`** - now auto-scales with `chartHeight` for consistent visual spacing.

---

## Infrastructure
- Full test suite across all modules.
- `ty` static type checking added to the dev toolchain and CI.
- `build_all.py` rebuilds all docs assets in one command.
- README substantially expanded with a table of contents and worked examples for all utilities.
- CHANGELOG added to track changes, with pre-v1.0.0 history written from GitHub Releases.

---

## [0.9.0] - 2026-06-25

### New features

**Asterisk significance labels in `add_pvalue()`**
`add_pvalue()` now accepts `label_style="asterisks"` to render significance as `*` / `**` / `***` / `ns` instead of an exact p-value. Thresholds: `*` p < 0.05, `**` p < 0.01, `***` p < 0.001. The bracket shape parameter has been renamed from `style` to `bracket_style` for clarity.

**`background` parameter in `save()`**
`save()` now accepts `background=["light"]` or `background=["dark"]` to render only one variant instead of both. Defaults to `["light", "dark"]` (no change in behaviour).

### Bug fixes

- **`mark_strip()` errorbars** were incorrectly centered on the median while using SEM (a mean-based statistic). They now correctly center on the mean.
- **`add_multilabel()` docstring** referenced `style="dots"` (invalid); corrected to `style="symbol"`.

### Changes

- Default `mark_circle()` size reduced to `markSize / 5` (was `markSize`).
- Default `mark_point()` size reduced to `markSize / 2` (was `markSize`).

---

## [0.8.0] - 2026-06-24

### Breaking changes

- `add_grid_labels()` and `add_grid_labels_detached()` are renamed to `add_multilabel()` and `add_multilabel_detached()`.
- `options()` is renamed to `theme()`. Initialise the theme with `ds.theme()`.
- The recommended import alias changes from `import dysonsphere as theme` to `import dysonsphere as ds`.

---

## [0.7.0] - 2026-06-24

### New features

**`add_grid_labels()` / `add_grid_labels_detached()`** — condition-table annotation layers for placing below strip, violin, and boxplot charts. Each row is a condition label; each column aligns with an x-axis category.

- `style="plusminus"` renders `True`/`False` as `+` / `−`
- `style="symbol"` renders `True` as a filled mark and `False` as an unfilled mark, with a horizontal connecting rule across consecutive `True` runs. The `symbol` parameter accepts any Vega-Lite shape (`"circle"`, `"square"`, `"diamond"`, `"triangle-up"`, etc.)
- `style="text"` renders arbitrary strings or numbers — triggered automatically when group values are non-bool
- `palette` parameter overrides mark colors (pass the result of `theme.palette()`)

**`add_pvalue()`** — consolidated p-value bracket API. Replaces the previous two-function design with a single call supporting multiple pairs, stacked brackets, and manual or computed positions.

**New mark defaults** for `arc`, `errorband`, and `geoshape`.

### Changes

- **Palette rename:** `"rose"` → `"pinks"`. Paired divergent palettes updated.

### Bug fixes

- **Grid label x-axis alignment** — at high PPI, annotation marks were misaligned with x-axis tick positions due to Vega flooring SVG tick transforms to integers. Fixed via SVG post-processing in `theme.save()`.

---

## [0.6.0] - 2026-06-22

### New features

**Analytic beeswarm offsets**
`add_beeswarm()` now uses an analytic placement algorithm matching the approach used by `geom_beeswarm()` from the R package `ggbeeswarm`. For each point, the exact forbidden x intervals imposed by already-placed neighbours are computed as `px ± √((2·spread)² − dy²)`, and the position closest to 0 outside all intervals is chosen. This produces tighter, more symmetric swarms than the previous grid-search approach.

**Unified `spread` parameter**
`add_jitter()`, `add_beeswarm()`, and `mark_strip()` now share a single `spread` parameter for controlling point spread in pixels. For jitter, `spread` is the Gaussian standard deviation (~68% of points within ±spread). For beeswarm, it is the collision radius (no two point centres closer than 2·spread). When `spread=None`, beeswarm defaults to `√(markSize/π)` from the active theme so point size and collision radius stay in sync automatically.

**Renamed transforms**
`add_jitter_offsets()` and `add_beeswarm_offsets()` have been renamed to `add_jitter()` and `add_beeswarm()`.

**Legend symbol size**
Legend symbols now scale with `fontSize` (`fontSize × 6`) rather than `markSize`, so they remain proportional to the label text regardless of mark size.

**`save()` moved to `export.py`**
`save()` and its SVG helpers (`_fix_tick_alignment`, `_simplify_svg`) have been moved to a new `dysonsphere/export.py` module. The public API is unchanged.

### Bug fixes

**Tick alignment fix for quantitative axes**
The SVG tick alignment pass previously misidentified quantitative x-axis ticks (e.g. on line or area charts) as nominal band-scale ticks, remapping them to wrong positions. A validation step now checks that collected tick positions match expected band-scale floor positions before applying the fix — quantitative and time axes are left untouched.

---

## [0.5.0] - 2026-06-22

### New features

**`pvalue_layers()` — batch p-value annotations**
A new companion to `pvalue_layer()` that accepts a list of comparisons and returns a combined Altair layer in one call, removing the need to manually loop and stack individual brackets.

**x-axis tick alignment fix for violin and strip charts**
`save()` now includes SVG post-processing that corrects a Vega rendering quirk: Vega floors axis-tick group transforms to integers for screen sharpness, but keeps mark coordinates as floats. At high DPI this causes visible misalignment between ticks and marks.

For bar charts the fix reads bar centers directly from the SVG path data. For all other charts (violin, strip, etc.) band centers are computed analytically from the number of categories and `bandPadding`, then validated against the expected floor positions before being applied — so quantitative and time axes are left untouched.

### Bug fixes

A secondary bug was also fixed: the y-axis tick at the maximum data value renders as `translate(0,0)` in SVG, which the original regex matched as an x-axis tick, inflating the category count by one and producing wrong positions. The fix excludes any tick with a zero translate value.

---

## [0.4.0] - 2026-06-21

Renamed package from petaurus to dysonsphere. Rebuilt green palettes and all paired diverging palettes using a new multi-hue greens base.

---

## [0.3.1] - 2026-06-20

Initial beta release of **petaurus** — now available on PyPI.

```sh
pip install petaurus
```

### What's included

- `petaurus.options()` — global Altair theme configuration (fonts, axes, marks, palettes, and more)
- Perceptually uniform palettes built in Oklab, plus ports of matplotlib and cmocean palettes
- `petaurus.palette()` — slice and sample any named palette
- `petaurus.save()` — export light/dark PNG, SVG, and Vega-Lite JSON in one call
- `petaurus.mark_violin()` — violin plot with embedded boxplot
- `petaurus.mark_strip()` — jittered or beeswarm strip plot with optional error bars
- `petaurus.pvalue_layer()` — p-value bracket annotations
- Jitter and beeswarm offset helpers

### Notes

This is a personal project under active development. Breaking changes may occur between minor versions.

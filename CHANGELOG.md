# Changelog

## [Unreleased]

### New features

- **`add_comparisons(labelStyle="value")`: bare p-value labels, no `P`.** A third label style
  alongside `"p"` and `"asterisks"`, rendering just the number to save room - the same as `"p"` but
  without the `P` symbol and the redundant `= ` (`P = 0.041` → `0.041`), while keeping a meaningful
  operator (`< 0.001` when the value floors, `≈ 10⁻⁵` under `notation="power"`). `notation=` still
  applies. Useful where `P = …` labels crowd each other, e.g. a row of many-vs-control comparisons.
- **`add_comparisons(reference=...)`: compare every group against one control, no brackets.** Passing
  `reference` (a group name) compares each other group to it and draws the p-value **above each
  non-reference mark** - the clean many-vs-one / control layout that a fan of brackets makes noisy.
  It derives its own comparisons (so leave `pairs` unset), supports the pairwise tests, and corrects
  over the whole family of `len(categories) - 1` comparisons. Labels sit at each group's own data
  max, so overlay your points (strip/beeswarm) and they clear the data; distinguishing the reference
  visually (e.g. a darker fill) stays in your hands - nothing is injected into the chart. Works in
  grouped mode too: with `xOffsetCol` set, `reference` is an xOffset **level** compared within each
  x-category (one label per non-reference sub-bar). No new dependency.
- **`add_comparisons` gains explicit `pvalues` / `yStart` / `yPositions` in reference and grouped
  modes.** These were silently ignored on the grouped path (and unavailable in reference mode); now
  they work. In **reference mode** they're keyed by the compared thing - `pvalues={group: p}`
  (single-factor) or `{(category, level): p}` (grouped) supplies precomputed p-values (skipping the
  test and correction). **`yPositions`** takes **a single number** (one global flat row), a dict keyed
  by **group** (single-factor) or **`(category, level)`** (grouped) for per-label heights, or - in
  grouped mode - a dict keyed by **category** for a flat row per category, each at its own height
  (handy when categories span very different magnitudes); grouped brackets key by `(category, (l1,
  l2))`. Dicts are partial (unlisted fall back to auto). **`yStart`** (brackets only) is the exact
  stack base like single-factor - a scalar or
  a dict keyed by category for a per-category base; it does not apply in reference mode (no stack)
  and now **raises** if set there in either single-factor or grouped mode, rather than silently doing
  nothing. Dict/flat forms are additive type widening; the pairwise list forms are unchanged, and
  mismatched forms raise a clear error.

### Changes

- **Default `mark_circle` size increased to `markSize / 8`** (was `markSize / 20`). The overlay dot
  at the old size rendered as a sub-1px pinprick that read faint over bars/boxplots/violins; the new
  default is a legible dot while staying smaller than `config.point` / `config.square`. Override per
  chart with `mark_circle(size=...)`.

### Internal

- Deduplicated the `add_comparisons` / `add_correlation` internals in `inference.py` into shared
  private helpers (`_resolve_method`, `_resolve_notation`, `_resolve_bracket_styles`,
  `_check_coverage`, `_stack_levels`, `_resolve_y_spacing`, `_emit_report`), so the single-factor
  and grouped paths share one implementation each. No public API or rendering change; also fixed a
  latent `chartHeight == 0` guard drift between the two paths.

## [3.8.0] - 2026-07-15

### New features

- **`add_correlation(groupCol=...)`: a fit line + coefficient per series.** `add_correlation` was single-series - one fit, one `r`. Pass `groupCol` (a column that splits the scatter, e.g. `"cell_line"`) and it computes a correlation **per group**: a fit line, an optional CI band, and a coefficient readout for each, all coloured by `groupCol` on the *same* colour channel your scatter uses - so if you `color=alt.Color("cell_line:N")`, the fits match their points automatically. Unlike `add_comparisons`' grouped mode, colour is a lookup rather than a position, so there's no sort/alignment param to keep in sync. Readouts stack in the `position` corner, each a colour swatch (matching the series) plus the coefficient in the theme's normal ink - so the text stays legible even for pale palette colours; one record is registered per group (round-trips through `read(what="statistics")`). Works for all three methods (`pearson` draws the line, `spearman`/`kendall` the coefficient only). No new dependency.
- **`add_comparisons(xOffsetCol=...)`: significance brackets for grouped (two-factor) bar charts.** Until now `add_comparisons` compared categories along the x-axis; it couldn't annotate the *within-group* comparison of a grouped bar chart (gene × condition, timepoint × treatment) - the staple qPCR/wet-lab panel - because the two things compared live on the `xOffset` encoding, not the x-axis. Passing `xOffsetCol` (the column you put on `xOffset`) switches to grouped mode: `pairs` now names subgroup **levels** and one bracket is drawn per x-category, each with a **real per-category test** (so a housekeeping gene comes out `ns` from the data, not by hand). With exactly two levels `pairs` defaults to comparing them; with 3+ levels you pass explicit level-pairs (e.g. `[("Ctrl","Low"),("Ctrl","High")]`), which stack within each group and handle non-adjacent spans. Each bracket sits above its **own** group's bars, so groups spanning 20× in magnitude don't push short brackets sky-high. Set `categories` and `xOffsetSort` to match your chart's `x`/`xOffset` sort. Supports the pairwise tests (`mannwhitneyu`/`ttest_ind`/`ttest_rel`/`wilcoxon`) with `correction` over the whole family; results are registered for the export metadata like any comparison. No new dependency.
- **`add_quasirandom()`: a density-scaled quasirandom offset, the symmetric sibling of `add_beeswarm()`.** Mirroring R's ggbeeswarm's two geoms (`geom_beeswarm` vs `geom_quasirandom`), it joins `add_jitter`/`add_beeswarm` as a third offset-column transform. `add_beeswarm` (the greedy swarm) guarantees non-overlap but can look lopsided where points pack tightly - even-count rows park a point on the tick and lone points get pushed to one side, an artifact intrinsic to the swarm algorithm (seaborn's `swarmplot` has it too). `add_quasirandom` sidesteps it: points are spread by a van der Corput low-discrepancy sequence weighted by a Gaussian KDE of the value axis, giving a symmetric, violin-shaped swarm centred on the tick. Fully deterministic (no RNG), so figures reproduce; the trade is that it does not guarantee non-overlap - the cost of the smoother look, and the better choice for large or heavily-tied groups. Two knobs: `width` (peak half-width in px; auto-sized to the swarm's footprint by default) and `bandwidth` (KDE smoothing, Scott's rule by default). No new dependency - the KDE uses scipy, already a runtime dep.

### Fixes

- **`add_comparisons` now raises a clear error when `categories`/`xOffsetSort` don't cover the data.** `categories` (and, in grouped mode, `xOffsetSort`) must match your chart's `x`/`xOffset` sort, or the brackets mis-position / the shared scale silently reorders the bars. The function can't see the chart to check the *order*, but an explicit list that omits a value present in the data (a typo or omission) is a guaranteed mismatch - it now raises naming the missing values (in both single-factor and grouped mode) instead of rendering a silently misaligned chart.
- **The `add_beeswarm`/`add_quasirandom` docstring examples now pin a symmetric `xOffset` domain.** When you feed a raw offset column to a bare `xOffset="beeswarm_x:Q"` encoding, Vega-Lite centres the category tick on the *midpoint* of the offset range - so a leaning swarm (e.g. a lone lowest point) renders slightly off the tick. The examples now encode `alt.XOffset(..., scale=alt.Scale(domain=[-m, m]))` (with `m` the widest offset) so offset 0 lands on the tick, matching ggbeeswarm. This is documentation only - `mark_strip(scatter="beeswarm")` already pins this domain internally, so composite-mark output was never affected.
- **The default font is now a fallback stack, fixing charts that rendered in plain Helvetica.** In 3.4 the default font was renamed from the PostScript name `HelveticaNeue` to the family name `Helvetica Neue` so the SVG/PNG exporter could resolve the italic face for statistical-symbol italics. On some macOS + vl-convert combinations, though, resvg fails to match the spaced family name and silently drops to plain Helvetica, so charts with no explicit `theme(font=...)` reverted to the wrong typeface. The default is now `"Helvetica Neue, HelveticaNeue, Helvetica, Arial, sans-serif"`: the Helvetica Neue family stays first (italics still resolve where the font exists - output is byte-identical there), with the PostScript name and generic fallbacks after it for a deterministic degrade instead of resvg's arbitrary default. Setting `theme(font=...)` explicitly is unaffected.
- **`add_text`/`add_labels` background chip (`fill=`) now centres the text.** Two parts: (1) the chip is shifted by the text half-width instead of its padded half-width, so a `"left"`/`"right"`-anchored `add_text` chip sits with equal padding on both sides rather than hugging the near edge. (2) For `add_labels`, a chip label now anchors its text at the box *centre* (concentric with the chip) rather than at the connector-side edge - so the text stays exactly centred even when the `len*fs*0.6` width estimate misjudges the glyph run (wide all-caps like `NK` used to render wider than estimated and drift to one side of the chip). The connector still meets the chip's edge; bare (chip-less) labels keep their side justification.

## [3.7.0] - 2026-07-13

### New features

- **`add_comparisons(correction=...)` gains false-discovery-rate control: `"fdr_bh"` and `"fdr_by"`.** Alongside the family-wise `"bonferroni"`/`"holm"`, the pairwise and post-hoc bracket p-values can now be adjusted with Benjamini-Hochberg (`"fdr_bh"`) or Benjamini-Yekutieli (`"fdr_by"`) step-up FDR - the standard corrections for many-comparison settings like genomics, where controlling the expected proportion of false positives among the rejected hypotheses is more appropriate than controlling any false positive at all. BH assumes independence or positive dependence; BY multiplies by the harmonic factor `c(m)=Σ1/k` for validity under arbitrary dependence, at the cost of being more conservative. Both honor `nComparisons` (the total family size `m`, which may exceed the number of shown brackets), and both are validated against `scipy.stats.false_discovery_control`. No new dependency - implemented from scipy primitives like the rest of `statistics.py`.
- **`add_correlation(ci=...)`: a confidence / prediction band around the OLS fit line.** For Pearson correlations, `ci=True` (or a level like `ci=0.99`) draws a shaded interval band around the regression line; `False` (default) keeps the current line-only look, so nothing existing changes. `interval="confidence"` (default) shows the band for the mean response - how tightly the line itself is pinned down - and `interval="prediction"` shows the wider band for a single new observation. The band is the correct hyperbolic shape (narrowest at the mean of x, flaring toward the extremes), sampled densely for a smooth curve, and drawn beneath the fit line. `ciColor` (defaults to the fit line's colour, darkmode-aware) and `ciOpacity` (default `0.15`) style it. Pure scipy, no new dependency; like `add_shade`, wrap chart construction in a callable passed to `ds.save()` for correct light/dark exports.
- **`mark_table(df, ...)`: render a DataFrame as a publication-styled table.** A composite mark (`alt.LayerChart`) that lays cells out in pixel space so it composes with `+`/`hconcat`/`vconcat`, yet drives every per-row mark off the user's frame via `transform_window`/`transform_calculate` - so the frame is never mutated and `read(what="data")`/the provenance `dataChecksum` recover it byte-for-byte (only the strokes and header text ride on internal sidecars). Strokes are a composable set (`"outer"`, `"header"`, `"rows"`, `"cols"`, `"grid"` = the interior rows+cols, `"all"` = every rule); the default look is an outer border plus a header separator over alternating grey row stripes with bold headers. Row striping (and value-based `cellColor` shading) draws **one rect per cell**, never a full-width per-row rect, so every cell background is an independent element you can select and recolour in Illustrator. Per-column `columnFormat` reuses dysonsphere's number notations - `"scientific"` (`1.20×10⁻¹⁴`) and `"power"` (`10⁻¹⁴`) render as typeset Unicode superscripts via the same SVG fixers as the rest of the library, alongside `"e"`/`"si"` and any d3/printf spec (`".2f"`, …). `cellColor={col: palette}` shades a column by value (a heatmap column; diverging palettes centre on 0) with automatic black/white text contrast per cell. Colour controls: `textColor` (a string for all body cells, or a `{column: colour}` dict per column - a heatmap column keeps its auto-contrast unless given an explicit dict entry), `headerColor` (header text), and `headerFill` (a background band behind the header, `bool | str`, with the header text auto-contrasting when no `headerColor` is set); `fontStyle` (a string or `{column: style}` dict) sets the body cell font style, e.g. `{"gene": "italic"}` for italic gene names. Column widths are estimated from content (a table can't render at the 100×100 default, so it sizes itself); `columns`, `headerLabels`, `align` (type-aware by default: numeric columns right-aligned, everything else left), `striping`/`nStripes`, and `columnWidths` round out the controls. Example: `scripts/build/build_table_example.py`.
- **`add_text` and `add_labels` gain a `fill` background chip behind the text.** `fill: str | bool = False` (`True` -> a darkmode-aware default, `greys[0]` light / `greys[11]` dark; a string -> that color), with `fillOpacity` (default `1`), a `stroke` border (`True` (default) -> `black` light / `white` dark; `False` -> none; a string -> that color), and `cornerRadius` (`float | bool`, default `True` -> `fontSize * 0.25`; `False` -> square; a float -> px). Drawn as a `mark_rect` behind each label - handy for keeping labels legible over a dense scatter or a colored field. The chip is **gated on `fill`**: with `fill=False` (the default) no chip is drawn, so `stroke`/`cornerRadius` only take effect once a fill is set (a bare `add_text`/`add_labels` is unchanged - no box). The chip is sized from a rough text estimate (proportional fonts vary, so it's approximate) and, like `add_shade`, resolves the darkmode-aware defaults at build time (a `save()` across backgrounds needs a callable). For `add_labels`, connectors meet the chip's edge.
- **`add_labels(fontStyle=...)` styles the auto-placed labels.** Pass `"italic"` (gene / species names) or `"bold"`; `None` (default) keeps the theme's upright `mark_text`. Applies to every label in the call.
- **`theme(viewPadding=...)` keeps marks off the frame of closed plots.** `float | bool`, default `True`: closed plots (`closed=True`, which `inwardTicks=True` implies) get the minimal data inset from the frame - Vega-Lite implements the underlying `config.scale.continuousPadding` as domain extension plus nice-rounding, so the default is exactly one nice tick step, and any explicit float is likewise a floor that lands on the next nice boundary rather than an exact pixel value. `viewPadding=False` restores the flush frame; open plots are never touched (their detached axes already give the marks room). This is a default visual change for most closed/inwardTicks figures: even the minimal request extends a crossed domain bound by one nice step. The violin's absolute-x layer and `add_labels`' pinned scales pin `padding=0` so composite alignment survives the padding (labelled charts render unpadded by design - the placement engine needs the exact pixel map).
- **`config.trail`: bare trail marks render in the house style.** `mark_trail` (a line whose width scales with a `size` encoding) was the last colour-bearing mark left at raw Vega-Lite defaults (steel blue). It now gets a darkmode-aware fill and, when unsized, the same width as the theme's lines - so a bare trail renders exactly like a `mark_line` until a size encoding widens it. Note a Vega-Lite limitation: a *continuous* colour encoding on a trail draws nothing (the trail is grouped by the colour field); colour multiple trails by a nominal id with a sampled palette range (e.g. `ds.palette("australis", n)`) instead.
- **Seven new sequential multi-hue palettes: `nebula`, `cosmos`, `borealis`, `australis`, `brass`, `pewter`, and `eclipse`.** The celestial quartet are viridis alternatives built in Oklab - the structure of viridis (lightness-monotonic, colorful, dark-first) with a different colour story: `nebula` (deep slate-teal -> indigo -> periwinkle -> orchid -> pale rose), `cosmos` (nebula's "magma": the same route shifted darker, near-black floor to saturated pink), `borealis` (rich violet floor -> cobalt -> azure-teal -> luminous emerald), and `australis` (borealis extended through cosmos's magenta territory - ~190 degrees of hue rotation, adjacent-step ratio 1.03, more uniform than viridis's 1.05). The metal pair `brass`/`pewter` fill the cividis seat - deep navy -> near-grey petrol -> metallic gold / warm platinum, with the chroma pinched to neutral mid-ramp so the blue->gold axis survives dichromacy fully. `eclipse` is the monochrome identity ramp - warm ink to warm paper at a whisper of gold (the website's black/white brand scheme as a palette): lightness is its only encoding channel, so its span runs deep (L 0.17-0.975) for exact viridis-parity capacity with zero loss under either dichromacy and perfect greyscale/print fidelity. All seven are lightness-monotonic and verified under simulated deuteranopia and protanopia; all are included in the Illustrator swatch/ASE exports.
- **`focus`: a true-black imaging colormap for microscopy and astronomy.** A dedicated sequential palette whose floor is pure `#000000` (so zero signal renders true black) that still keeps dim, low-signal structure legible - built by spreading `australis`'s blue->cyan->emerald hue journey across a full black->near-white lightness range and blending in magma's front-loaded lightness curve, so a fluorescence micrograph reads like a magma render but on australis's cool palette. It stays lightness-monotonic, colourblind-safe (deuteranopia + protanopia), and Oklab-uniform (adjacent-step ratio 1.28). Use it via `theme(heatmapPalette="focus")` or `ds.palette("focus", n)`.
- **`config.tick`: bare tick marks render as house crossbars.** `mark_tick` was the last everyday mark left at raw Vega-Lite defaults (steel blue, 15 px). It now gets darkmode-aware colour, round caps and stroke thickness matching the errorbar caps, and the boxplot median's span - so mean-plus-error-bars on any categorical chart is just two bare layers: `base.mark_errorbar(extent="stderr") + base.mark_tick().encode(y="mean(v):Q")`. The boxplot median and whisker caps (tick marks internally) pin `cornerRadius`/`opacity` so boxplots and violins render pixel-identical to before.

### Changes

- **The minimum required Altair is now 6.0.** The floor was raised from `altair>=5.5.0` to `altair>=6.0.0` (both `dysonsphere` and `dysonsphere-biology`), aligning the declared requirement with the version the test suite actually runs against and opening the door to Altair 6-only APIs. No public API or behaviour changes - the library renders identically on Altair 6; only installs pinned to Altair 5 are affected.
- **`add_multilabel()`'s type hint now admits concatenated charts.** The function already recursed into `vconcat`/`hconcat` panels at runtime (so a stack of panels sharing one x-layout - e.g. `ds.biology.western_blot`'s image strips - gets the table below the whole stack), but its parameter was typed `alt.Chart | alt.LayerChart`; it now also accepts `ConcatChart`/`VConcatChart`/`HConcatChart`. Annotation-only widening (accepts more, breaks nothing); drops the `# ty: ignore` that `western_blot` needed.
- **Every bare generic in the type hints is now parametrized, and a `ty` guardrail keeps it that way.** ~70 unparametrized `dict`/`list`/`tuple` annotations across the library gained real type arguments (`dict[str, Any]` for kwargs/encoding dicts, `list[str]`/`list[Any]` for element types, etc.), so they no longer silently opt out of type checking; two public signatures also gained more precise types (`add_comparisons`'s `notation`/`bracketStyle` now express their per-pair `tuple` keys). `[tool.ty.rules] missing-type-argument = "error"` makes a future bare generic a hard error. Annotation-only - no runtime behaviour changes - but a better experience for downstream `py.typed` consumers.
- **The statistical-symbol italicizer now sets the "p" in "p-value" italic.** The `p` (or `P`) in `p-value` / `P-value` / `p value` is italicized on export (and on the website's live charts, whose ported fixer mirrors the pattern), matching the scientific convention already applied to `P =`, `r`, `n`, and the other single-letter symbols. `power` and other words are unaffected (the shared word-boundary guard).
- **The five dark-floored 3.7 palettes are re-centered: their near-black floors lift to Oklab L 0.22.** `australis`, `borealis`, `cosmos`, `brass`, and `pewter` all started at L 0.13-0.15, where the darkest stops were hard to tell apart from the neighbouring dark hues; the floors now sit at a clearly-coloured dark plum / indigo / teal / navy (viridis's floor is L 0.285, so these remain darker than viridis). The keyframe lightnesses were remapped linearly onto the new floor - same hue journeys, same chroma caps - and every perceptual invariant still holds (lightness-monotonic natively and under simulated deuteranopia/protanopia; step-uniformity ratios 1.07-1.09 vs viridis's 1.05). Capacity lands at viridis parity: australis matches viridis on total perceptual range and beats it under both dichromacies; the others sit within a few percent. `nebula` (floor L 0.21) was never near-black and is unchanged. This is a visual change to the rendered colours, including the default heatmap/ramp ranges (australis); the pre-lift originals ship in 3.6.x, and their keyframes are preserved as comments in `scripts/build/print_palettes.py` for byte-identical regeneration.
- **Continuous colour defaults switch to `australis`: `config.range.heatmap` and `config.range.ramp` (were `blues`).** Heatmaps, and continuous point/line colour, now default to the viridis-analogue journey instead of the single-hue blues ramp. Override per type with `theme(heatmapPalette=..., rampPalette=...)` or globally with `palette=`.
- **Legend text is more compact, mirroring the axes' spacing hierarchy.** `config.legend` now sets `titlePadding: 4` (was Vega's 5), `labelOffset: 2` (was 4), and `gradientLabelOffset: 2` - the same 2 px label gap / 4 px title gap the axes use, applied to symbol and gradient legends alike.
- **The logo family is recoloured to the `australis` palette**, and the README header shows the outlined logo-plus-wordmark lockup. The mark-only logo gets a tight centered viewBox (it no longer reserves blank space where the wordmark would sit); the favicon and website header follow.

### Fixes

- **`theme(inwardTicks=True)` no longer leaves a dead gap between the axes and their labels.** Vega places axis labels and titles beyond the outward tick; flipping the ticks inward left the space they had occupied empty, so labels and titles floated `tickSize` too far from the domain lines. The inward-ticks SVG fixer now also pulls each axis's labels and title toward the view by that axis's own tick length, restoring the normal 2 px label / 4 px title spacing. Handles rotated labels, secondary axes, and per-axis tick sizes (log/power minor-tick axes carry no labels).
- **`mark_strip`'s centre tick draws the mean - the statistic its error bars are computed from.** With `errorbars=True` (the default) the tick was the boxplot *median* between *mean*-based error bars, so it drifted off-centre between the caps on any skewed group (the docstring already promised a mean tick). The tick is now drawn at the group mean from the same summary frame as the error bars - centred by construction - with round caps matching the errorbar caps and a darkmode-aware colour (the old fixed-black median tick was invisible on dark renders). `errorbars=False` still shows the median.

## [3.6.0] - 2026-07-09

### New features

- **`add_labels(labels=...)` accepts a boolean mask to select rows positionally.** Previously a list `labels=` matched rows by `labelCol` value, so a non-unique label column (e.g. a `gene` column with several variant rows per gene) could not select the exact rows to annotate while still displaying that column - and pre-filtering the frame instead left the labels blind to the rest of the scatter, so they landed on top of the unlabelled points. You can now pass the full plotted `df` (so the labels dodge EVERY point and the axis domain spans all of it) and select the subset with a boolean mask - `labels=df["is_hit"]` - decoupling selection from the display column. A same-length list of non-boolean values still matches by `labelCol` value as before.
- **`add_labels()` gains a `connectorOpacity` parameter.** Fades the leader lines relative to the labels (e.g. `connectorOpacity=0.5`) without touching their color, so the quieted connectors stay legible in both light and dark mode (unlike baking the alpha into an rgba `connectorColor`). `None` (default) inherits the theme's opaque `mark_rule`.

### Changes

- **The `shoal` palette runs dark-to-light** (deep navy `#1B3452` -> mint `#93F2C9`), reversed from its previous light-to-dark order. This is a visual change, not an API one: code using `shoal` still runs, but on a sequential scale the color mapping flips (low values now render dark, high values light). Restore the old orientation with `ds.palette("shoal", reverse=True)`. Affects the bare `colors["shoal"]`, `ds.palette("shoal")`, and swatch exports.

### Fixes

- **`add_shade()` bands stay square under `theme(cornerRadius=...)`.** The shade rects are chart annotations but were drawn as `mark_rect`, so they inherited `config.rect.cornerRadius` and got rounded whenever the theme set rounded marks - an unintended side effect. Every shade rect (band mode, positions mode, `axis="both"`) now pins `cornerRadius: 0`, so theme rounding affects data marks only.

## [3.5.0] - 2026-07-08

### New features

- **`save()` records the chart expression in its provenance.** A new `provenance.chart` field carries the verbatim source text of the `chart` argument at the `save(...)` call site - the variable name (`"fig"`), the inline composition (`"boxplot + points + line"`), or a whole lambda - so an exported file says which expression produced it, next to `script` (which file). Best-effort by design: the field is omitted when no source is available (a plain REPL, `exec`'d code), a wrapper function records its own parameter name, and identity stays with the checksums. Structured metadata block only; the prose "Generated by ..." sentence is unchanged.

## [3.4.3] - 2026-07-07

### Changes

- **Comment-only source cleanup; no functional changes.** Drops a rationale comment from the theme defaults and stale style-guide / version-history wording from the italics pattern comment and a test comment.

## [3.4.2] - 2026-07-07

### Fixes

- **The asterisks-style `ns` bracket label is upright again.** 3.4.0 set the whole `ns` label in italic alongside the statistical symbols, but `ns` is an abbreviation ("not significant"), not a symbol - scientific typesetting italicizes single-letter symbols only, and multi-letter abbreviations stay upright (also how Prism and ggsignif render it). The pattern-matched single-letter symbols are unchanged.

## [3.4.1] - 2026-07-07

### Changes

- **README: the statistical-symbol italics bullet is dropped from the feature overview.** The 3.4.0 note was detail out of scale with the README's short capability list - and the README is the PyPI project description, hence the patch release. The feature itself is unchanged and documented in the 3.4.0 entry below and the website's saving guide.

## [3.4.0] - 2026-07-07

### New features

- **Saved SVGs and PNGs typeset statistical symbols in italic.** A new SVG post-processor (run by `save()`/`show()` after the superscript fixer) wraps Latin statistical symbols in italic per APA/CSE convention: *P* in p-value labels (`P = 0.012`, `P < 0.001`, `P ≈ 10⁻⁵`), the omnibus statistics `F(…)`/`H(…)`/`A(…)` and Kendall's `W`, the correlation readout's `r`/`r²` (the `²` digit stays upright) and fit-equation `y`/`x`, `t` in "t-test", `U` in "Mann-Whitney U", `n` in the multilabel sample-size row, and the whole-label `ns`. Digits, operators, and Greek symbols (η², ε², χ², ρ, τ) stay upright. Patterns match globally on rendered text - a hand-written `add_text("P = 0.03")` gets the same treatment, keeping typography consistent across a figure (the same policy as the superscript fixer). SVG/PNG only, like all fixers: interactive HTML and bare notebook previews render upright.

### Changes

- **The theme's default font is now the family name `"Helvetica Neue"` (was the PostScript-style `"HelveticaNeue"`).** vl-convert's rasterizer matches a PostScript name to the regular face only, so styled variants were unreachable in PNG export - italic text silently rendered upright. Both names resolve to identical regular-face metrics (verified byte-identical SVG output), so existing figures are unaffected; the rename only unlocks the italic face.

## [3.3.1] - 2026-07-07

### Fixes

- **`add_correlation()` no longer leaks `_x`/`_y` into merged axis titles.** The OLS fit line's sidecar dataset used private field names; when the base scatter had no explicit `title=`, Vega-Lite's shared-axis merge joined the two layers' derived titles into `"height, _x"` / `"weight, _y"`. The sidecar now carries the real column names (encoded non-shorthand, so names containing `:` or `.` survive), so the derived titles dedupe to one; an explicit base title keeps winning as before. No workaround needed anymore - previously the base chart had to set explicit axis titles.

## [3.3.0] - 2026-07-07

### Changes

- **Significance-bracket spacing revised: `yStep` is now `yPad * 1.75` and `yPad` scales to the full data extent.** The `2.0×` gap shipped in 3.2.0 looked airy on charts whose rendered y-domain hugs the data extent; `1.75×` still clears a bracket's label from the bar above it without the extra air. More importantly, `yPad` (and `tickHeight`) now derive from the **full** data extent rather than just the compared groups: bracket positions are data-unit values on the shared y-scale, so the visual gap is `yStep × chartHeight / rendered_domain`, and Vega fits that domain to *every* group. Sizing the gap off only the annotated groups collapsed the stacked brackets into a sub-pixel sliver when an un-annotated group (e.g. a saturating positive control) inflated the domain; the full extent tracks the rendered domain, so spacing stays stable across charts and no longer collapses. `yStart` still anchors above the compared groups. Explicit `yPad`/`yStep`/`yPositions` override the auto values as before.

## [3.2.0] - 2026-07-06

### Changes

- **Stacked significance brackets breathe: the auto `yStep` is now `yPad * 2` (was `1.5`).** At the old spacing a bracket's p-value label (drawn above its bar) nearly touched the bracket stacked above it - ~4 px of clearance at the default theme, less with superscript exponents. The default gap between stacking levels is now ~16 px (`bracketStyle="line"`) / ~20 px (`"bracket"`), roughly doubling the label clearance. An explicit `yStep=` is unaffected.
- **Error bars are lighter: the stem, rule, and end-cap thickness drop from `2 x markStrokeWidth` to `markStrokeWidth`.** Error bars now weigh the same as every other mark stroke and the axis line (`markStrokeWidth = axisWidth`), instead of rendering at double weight. The tick-cap `cornerRadius` is halved to `markStrokeWidth / 2` so the caps stay fully rounded at the new height. Affects `mark_strip` mean/error overlays and any `errorbar` mark.
- **The `colors` palette catalogue is reordered for browsability.** The `colors` dict is now grouped by data type (sequential, then diverging, then qualitative), then by package (dysonsphere, then `mpl_`, then `cmocean_`), then by tier (base names, then `...2`, then `...3` for dysonsphere palettes), alphabetized case-insensitively within each group. External ramps that are conceptually diverging but were resampled to 12 stops (mpl: BrBG, bwr, coolwarm, PiYG, PRGn, PuOr, RdBu, RdGy, RdYlBu, RdYlGn, seismic, Spectral; cmocean: balance, curl, delta, diff, tarn, topo) are hand-placed in the diverging section; cyclic maps (mpl twilight, hsv) stay sequential. No palette is added, removed, or recolored - only the iteration order of `ds.colors` changes (visible if you enumerate it, e.g. in swatch exports or the palette browser).

## [3.1.0] - 2026-07-06

### New features

- **`save()` provenance records the full rendering toolchain and the extensions that drew the figure.** The embedded `provenance.environment` block gains three fields: `os` (from `platform.platform()`), the `vl_convert` renderer version, and `dysonsphere-extensions` - a `{name: version}` map of the dysonsphere extensions that actually produced the figure (e.g. a `ds.biology.volcano` chart records `{"biology": "0.1.0"}`; the key is omitted when no extension was used). Together with the existing Python / Altair / NumPy / SciPy / Polars / dysonsphere pins, a saved figure now captures the complete environment needed to reproduce it - down to the OS and the exact SVG/PNG renderer. The human-readable "Generated by …" sentence lists them all.
- **`ext.tag_extension` - extensions self-report into a figure's provenance.** A new primitive on the `dysonsphere.ext` surface lets an extension mark the charts it builds, so `save()` records it under `provenance.environment["dysonsphere-extensions"]`. Extension authors call it once in each composite constructor; `dysonsphere-biology`'s `volcano()` is the reference. Added to the `ext` public surface (`ext.__all__`).

### Changes

- **`vl-convert-python` is now a runtime dependency.** It was previously a dev-only dependency, but `ds.save()` needs it to render SVG/PNG (it stays lazily imported, so JSON-only export still works without it). Making it a `[project]` dependency means a plain `pip install dysonsphere` can export images out of the box, and lets `save()` pin the renderer's version in provenance.
- **`save()` provenance leads with the readable context; the checksums move to the end.** The provenance block is reordered human-first: the who/when context (`user` / `script` / `timestamp`) and the `environment` toolchain now come first, and the machine-identity hashes (`vegaliteChecksum`, `exportIdentifier`, and the unbounded `dataChecksum` list) trail at the end instead of leading. The "Generated by …" prose follows the same order. Reading is unaffected (fields are keyed, not positional), so v3.0-exported files still read back correctly.
- **`mark_violin` docstring parses cleanly.** The "safe in `alt.hconcat()`" note sat between the Parameters and Examples sections, so numpy-style docstring parsers (griffe, the docs-site API generator) misread its prose as three phantom parameters. Moved into the function description; no behavior or signature change.
- **`add_rule()` labels keep a consistent gap from a closed plot's border.** An edge-anchored reference-line label (left/right for `axis="y"`, top/bottom for `axis="x"`) sits at the plot's content edge. On an open plot the axis is detached, so the label clears the axis line by `axisOffset`; on a closed plot the spine is flush at that edge, so the label used to hug the border. Closed plots now inset such labels by `axisOffset`, giving them the same breathing room - so a reference-line label looks identical whether the plot is open or closed. Center-anchored labels are unaffected.

### Fixes

- **Grid lines on open plots span the plot content, off the detached axes.** With `grid=True` and `closed=False`, each grid line is rendered inside its (offset) axis group, so it inherited the detached-axis gap and rendered dragged toward its axis: vertical (x-axis) grid lines shifted down (top short of the highest tick, bottom overshooting onto the x-axis) and horizontal (y-axis) grid lines shifted left (touching the y-axis, short of the right edge). Both grid directions are now seated onto the plot content and float symmetrically off both detached axes. Closed plots (axes already flush, grid already correct) are untouched.

## [3.0.0] - 2026-07-06

### Breaking changes

- **`theme(transparentBackground=)` renamed to `theme(transparent=)`.** Shorter, and it pairs with the `save(transparent=)` parameter - the same question answered at the theme level (the chart's logical background: notebook display, JSON, HTML) and per export. The old name (keyword argument and `dysonsphere.toml` key) is removed. Note: files exported by v2.x bake the old key into their theme block, so `load(applyTheme=True)` on them raises - use `load(raw=True)` or re-export.
- **The `presentation` built-in style preset is removed.** `theme(style="presentation")` now raises the standard unknown-style `ValueError` unless you define a `[presentation]` section in your own `dysonsphere.toml` (config-file styles are unaffected; the old preset was three lines - `fontSize = 12`, `darkmode = true`, `transparent = true`). `notebook` remains the only shipped preset, and the `create_config()` template follows.
- **`dysonsphere.layers` is split into `dysonsphere.annotations` and `dysonsphere.inference`.** The catch-all module held three unrelated families; it is dissolved: `add_rule` / `add_text` / `add_shade` / `add_labels` now live in `annotations.py`, and `add_comparisons` / `add_correlation` in `inference.py` (statistical inference - the annotation wrappers around the pure `statistics.py` engine). The label-placement engine moved from `utils` to the private `_placement.py`. The public namespace is unchanged (`ds.add_rule` etc. work as before); only deep imports like `from dysonsphere.layers import add_rule` need updating.
- **The package namespace is tightened to the intended API.** Every module now defines `__all__`, so the ~31 public names are all the `dysonsphere` namespace exposes. Previously the star-imports leaked every module-level import onto it - `ds.np`, `ds.pl`, `ds.alt`, `ds.math`, `ds.json`, even `ds.field` (from `dataclasses`) were importable; code relying on those must import the real packages directly.
- **`beeswarm_offsets` is now private (`_beeswarm_offsets`).** It was the undocumented low-level engine behind `add_beeswarm`, which remains the public API (and covers the same use via `yCol`/grouping). Call the underscore name if you truly need raw pixel offsets.

### New features

- **Extension architecture - optional domain packages plug into the `dysonsphere` namespace.** A separately installed extension (e.g. `dysonsphere-biology`) that registers under the `dysonsphere.extensions` entry-point group resolves as `ds.<name>` - so `ds.biology.volcano(df)` just works once the package is pip-installed. `ds.extensions()` lists what's installed and `ds.load_extension(name)` imports one explicitly. Extension authors build first-class charts (theme-aware, with their generated data correctly filtered by `read(what="data")`) via the minimal, versioned `ds.ext` surface (`ext.opt` / `ext.internal_data` / `ext.AltairChart`) instead of reaching into core internals. Core stays a regular package; the only hook is an additive package `__getattr__`, so existing imports are unaffected.
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

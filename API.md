# Public API Framework

This is the durable design framework for dysonsphere's public API, established during the v4
refactor and maintained in subsequent versions. It describes the intended contract, not a claim
that every current implementation already conforms. Update it when a design decision changes.

This document is intended to be committed and kept current. Release-specific plans and audit
notes are local working material, not dependencies of this framework or part of its public contract.

## Purpose and Structure

- Dysonsphere is a plotting library built on Altair. Return ordinary Altair objects rather than
  requiring a dysonsphere chart hierarchy.
- Keep a shared, general-purpose figure-building vocabulary at the top level, including common
  styling, palette selection, composition, rendering, and loading.
- Use selective namespaces for coherent specialized toolsets, not one namespace per implementation
  module. Specialized tools may return charts too.
- Use `ds.stats` for statistical annotations, `ds.transforms` for data transforms, `ds.metadata`
  for inspection and verification, and domain namespaces such as `ds.biology` for optional
  extensions. Shared implementation helpers in `utils.py` are private and are not a supported
  public namespace.
- Keep `ds.theme()` and top-level `ds.create_config()`. A one-function config namespace adds little.
- `ds.theme()` keeps `style` positional and exposes every styling option as an explicit typed keyword-only parameter. Its internal omission
  sentinel preserves configuration/style precedence; explicit `None` remains meaningful only for the
  options that advertise it. `fontSize` is the sole theme font-size control and accepts positive finite
  fractional values.
- Keep `ds.palette()` as the common selector; categorical construction, the color registry, and
  swatch export belong under `ds.palettes`. Palette selection returns colors without changing
  the active theme.
- Palette sampling selects existing stops, not interpolated colors. Preserve n=0 returning an
  empty list, repeated colors when oversampling, inclusive end, and n taking precedence over step.
  When n is supplied, require a nonnegative integer and reject booleans and non-integer values,
  including integral floats. This tightens validation without changing valid sampling behavior.
- Palette lookup is case-sensitive. Native palette names are lowercase; imported palette names
  preserve their upstream spelling and case without source-package prefixes. Registered names take
  precedence over renderer-native schemes in every palette-valued consumer.
- The 12 discrete Matplotlib category palettes expose their complete upstream color lists.
- The native `neongreens` family and every diverging palette derived from it are removed; no aliases
  or replacement colors are provided. Ordinary `greens` and the `cat1_greens`/`cat2_greens` families
  are distinct and remain available.
- Native `greenblue` and `yellowgreenblue` are distinct from the case-sensitive imported Matplotlib
  palettes `GnBu` and `YlGnBu`. The `bluerlagoon` and `bluestlagoon` variants are removed;
  `bluelagoon` and `lagoon` remain available.
- Volcano gained/lost colors natively inherit the active theme's diverging range when `palette=None`;
  explicit tuples retain `(gained, lost)` order. The neutral remains separately darkmode-aware, and
  the legend remains a discrete three-category symbol legend with swatches matching the points.
- Choose one canonical public path per operation; do not present every operation equally at
  multiple paths. Major-version compatibility policy is explicit. V4 is a clean break: no old-name
  function/parameter aliases or adapters for earlier API or saved-chart contracts are required.
- Public namespaces need not mirror internal files. A module may become a package without changing
  the public paths. Reserve core names to avoid extension and import-order collisions.

## Names and Signatures

- Bare annotation constructors return layers for composition with `+`.
- `rule` uses explicit keyword coordinates: `y` for horizontal rules, `x` for vertical rules,
  secondary `x2`/`y2` endpoints for bounded and diagonal segments, and `slope` plus a required
  numeric `span` for equation segments. Equation segments assume linear quantitative axes; the
  standalone layer does not inspect a chart it may later be composed with.
- Rule endpoint caps are `arrow`, `circle`, or `square`; start/end follow primary/secondary endpoint
  order. Omitted gaps with a cap derive the same theme-aware point clearance used by label
  connectors; capless omitted gaps are 0 and explicit zero is preserved. This rendered geometry is
  part of the shared SVG/PNG/save/show pipeline, not bare Altair or HTML.
- Point-label connectors optionally use `connectorCap="arrow"` at their point-facing end. Their
  existing `connectorGap` is applied once; no second cap gap is introduced. As with rule caps, this
  decoration is available in the shared SVG/PNG/save/show pipeline, not bare Altair or HTML.
- `add_*` operations take an existing chart and return an augmented chart.
- Keep `mark_*` for general-purpose composite mark constructors, matching Altair vocabulary.
- Keep `multilabel` as the name of the condition-table system.
- Prefer native Altair customization of returned charts before adding constructor options.
  Parent .encode() can customize axis values and color legend title/orientation on strip and
  violin charts while preserving their internal fields. Do not require internal layer traversal
  for those cases or add redundant axis/legend wrapper parameters without a demonstrated need.
- Public parameters use camelCase; internal helpers use snake_case.
- Primary inputs may be positional; optional styling and controls should be keyword-only. Keep
  explicit signatures rather than hiding long parameter lists in arbitrary options dictionaries.
- Document every public function's return type, including mode-dependent returns and side effects.
  Do not advertise all Altair compound types if only some are actually supported.
- Use `data` for public tabular input. Support pandas and Polars dataframes through the existing
  normalization boundary; the name does not promise every Altair data-source representation.
  Users explicitly convert column dictionaries or row records to a dataframe. No new conversion
  framework, URL loading, or Vega-Lite data-specification support is planned.
- Use `x` and `y` for data-driven plot mappings; strings name dataframe columns, not encoding
  shorthand such as `height:Q`. Positional annotations may use x/y for coordinates instead;
  document this contextual distinction. Other field parameters are reviewed by role rather
  than mechanically removing every Col suffix.
- Use channel names for plot mappings: xOffset for grouped comparison positions, and x for
  multilabel sample-size categories. Use groupBy for per-group calculations (including correlation).
- Use column for axis-independent dataframe operations, including beeswarm/quasirandom input
  values. Keep outCol for the column a transform creates or replaces. A consistent
  name does not widen accepted cardinality: correlation groupBy still identifies one column,
  while grouped transforms retain their existing grouping-column contract.

## Defaults and Validation

- State whether omission inherits a theme option, derives a value, disables a feature, or uses a
  fixed default. Do not force every `None` to mean the same thing.
- Use a sentinel where omission differs from explicit None, such as an inferred versus suppressed
  axis title. Preserve meaningful distinctions rather than relying on truthiness.
- Explicit zero must override a default wherever zero is a valid value.
- Distinguish bool switches from numeric values by identity. Counts and probabilities should not
  accept booleans unless explicitly designed as switches.
- Validate malformed enums, shapes, and values consistently across dispatch modes. Unsupported
  explicit requests should not silently disappear when intent is detectable.
- Disabled components may retain harmless ordinary defaults. Do not add sentinels everywhere just
  to reject redundant styling options.
- Valid styling options may remain inactive when their component is disabled, such as connector
  colors with connector=False. Reject malformed values and unsupported explicit feature requests,
  rather than silently discarding them in particular modes. An applicable option lost in dispatch
  is an implementation omission to fix, not an unsupported feature to reject; for example, a
  grouped correlation that draws interval bands should honor its explicit band color. Test these
  contracts across single/grouped and enabled/disabled paths without requiring explicit-default
  detection for every argument.
- Validate finite numerical inputs before geometry or statistical arithmetic. Define missing-data
  behavior explicitly; plotting, formatting, statistical computation, and hashing need not apply
  the same policy.
- Theme validation is atomic and applies equally to direct keywords and TOML/style values. Boolean
  switches reject numbers; chart dimensions and `fontSize` are positive; visual sizes and gaps are
  nonnegative where zero is meaningful; opacity and band inner padding are in [0, 1], while outer
  padding is nonnegative. Shared band geometry follows D3's denominator clamp and centered alignment
  for the zero-width singleton endpoint. Dash arrays may be empty
  or odd-length but contain only finite, nonnegative numbers. Export
  defaults use the same nonempty format/background sets as `save()`.
- Statistical annotations reject missing/non-finite values in calculation columns, identifying
  the offending column/group, and validate computed results as well as inputs. Violin/KDE
  construction rejects invalid observations or groups unable to support the calculation with
  clear errors. Point-label placement requires finite coordinates without silently dropping rows.
- Tables preserve missingness visually rather than formatting it as zero. Dataframe normalization
  only converts representation; it does not drop or fill observations. Unused columns containing
  missing values do not cause rejection. Do not add a general dropMissing switch; callers filter
  explicitly so changes to sample size remain visible in their scripts. Tables display missing
  values as blank cells, not zero or literal None.
- Validate before modifying global state or writing files where feasible. Failed configuration
  calls should not corrupt the state used by later operations.

## Appearance and Geometry

- Unqualified styling options refer to the main visual element; name the component for secondary
  styling. A documented override must have the same scope and precedence in grouped modes.
- Palette options select color sequences or named palettes, not individual literal colors. State
  which options additionally accept renderer scheme names or fixed endpoint pairs.
- In `theme()`, a non-None master `palette` overrides every per-type palette, including an explicit
  per-type argument. Otherwise each per-type palette overrides its built-in range default.
  Configuration source precedence is applied per key before this master override.
- Custom strip and violin marks expose separate palette and fill arguments. Palette selects
  category colors; fill is a fixed literal color for points or the violin silhouette, not their
  summary/inner statistics. Palette omission/None leaves the encoding range to the active theme.
  This does not change theme's palette or markFill options. Reject simultaneous non-None palette
  and fill arguments; an inherited theme palette does not conflict with explicit fill. Fixed fill
  suppresses the constructor's category-color legend even when its legend argument is True.
  Do not disable legends globally. Preserve category axes and violin group separation.
- Preserve whole-mark opacity versus fill opacity. Do not apply the same inherited fade twice.
- Keep font style separate from weight; bold is a weight, not a style.
- Corrected SVG typography applies to matching handwritten and generated text alike: recognized
  Latin statistical symbols are italicized; Greek symbols, numbers, operators, and `ns` remain
  upright unless explicitly styled. Script tokens include `q^2` and boundary-guarded `q__x`;
  ordinary single-underscore column names are not subscript instructions.
- Gradient legend titles default to horizontal, above the legend. Save/show do not inject title
  orientation; callers can customize individual legends through Altair.
- Multilabel `rowValueAngle` rotates values in text, plusminus, and symbol styles, never row labels.
  Scalars apply throughout; top-level lists follow row order; mappings select rows and may contain
  per-cell lists in category order. Rotating a circle may make no visible change. Automatic text
  row height uses the tallest rotated text bounds, including for symbol rows.
- Table columnFormat uses Vega/d3 format specifications plus the named scientific, power, e,
  and si notations. sigFigs governs automatic numeric formatting and named notations where
  precision applies; explicit formats such as .2f control their own precision. Power notation
  means nearest power of ten and is independent of sigFigs. Normalize rounded scientific
  mantissas and handle large finite exponents correctly. Approximate width estimation must not
  reject a valid renderer format or introduce a separate formatting contract.
- Document pixels, symbol area, data coordinates, and dimensionless proportions distinctly.
  Allow fractional values where supported; counts and indices remain integers.
- Theme `fontSize` defaults to 6 and is the nominal publication point size at intrinsic export size.
  SVG renderers expose the same number as a CSS/SVG user-unit value, while raster export scales from 72 intrinsic units per
  inch. Preserve the value without a 4/3 conversion. `markSize` remains the shared sizing basis: symbol
  marks interpret derived values as area, while composite widths and gaps derive linear pixel values.
- Use Padding for gaps/insets and Offset for signed displacement. Names such as Width should
  communicate a physical length rather than a symbol area.
- `axisOffset` and `viewPadding` are independent. `axisOffset=False` (default) means flush axes;
  True derives the offset from `tickSize`, and a number supplies pixels. Closed axes remain flush.
  `viewPadding=True` (default) derives a continuous-scale inset from chart size on open and closed
  plots; False disables it, and a number supplies pixels. Shared spec fixes suppress implicit
  automatic domain rounding (`nice`) when continuous padding is present, but preserve explicit `nice` settings.
- `tickDirection` is `"out"` by default and accepts only `"in"` or `"out"`. Inward ticks imply a
  closed frame only when `closed` is omitted; explicit `closed=False` wins. Inward reversal is part
  of the corrected SVG/PNG/show pipeline, not bare Altair display or interactive HTML.
- Document construction-time versus render-time defaults and the need for callable rebuilding
  when colors or geometry are already baked into a chart.
- A dataframe transform's computed offsets are not an unconditional guarantee of rendered pixel
  spacing or non-overlap after Altair applies its scales.
- Accept the advertised color syntax when calculating contrast, or explicitly narrow that syntax.
  An unrelated override should not determine whether a valid color can be parsed.

## Selection and Mappings

- Document the order of every list and the key domain of every mapping, including grouped modes.
- Partial styling mappings retain defaults. Reject genuinely unknown semantic keys, distinguishing
  them from valid but intentionally unshown data columns or rows. Validate against the available
  input columns/rows rather than only the displayed subset; an unused entry for a known, excluded
  column or row is allowed. Omitted entries retain defaults.
- Display-label mappings may include values absent from a particular chart; preserve fallback.
- For data-driven plots, an explicit categories list must be unique and match the observed
  category values exactly: reject missing observed values, extra unobserved values, and duplicates.
  Callers filter data explicitly before requesting a subset. Do not infer empty plot slots from
  extra category names. This concerns category values within a column, not dataframe column names.
  Sample-size counting retains subset, duplicate-request, and absent-category zero semantics;
  these are separate from strict data-driven plot category validation. An annotation without
  source data cannot validate observed coverage.
- Comparison identity is unordered for lookup; explicit caller order can still govern list inputs
  and presentation. Conflicting reversed duplicates and self-pairs need clear validation.
- Boolean masks identify rows, not label values. Validate mask length before value matching.
  Count-based selection must select distinct rows even when names or coordinates repeat.
- For `ds.labels(data, x, y, labels, *, subset=None, ...)`, `labels` names the column supplying
  displayed text and `subset` controls which observations are annotated. None selects all;
  an integer requests that many spatially spread rows; a boolean mask selects rows positionally;
  a list of label values matches rows by those values. Keep one selector, not separate number
  and subset controls. The full input data still supplies placement obstacles. Returns
  `alt.LayerChart`.
- Volcano uses the same labels/content-column and subset/selection vocabulary. Its log2fc and
  pvalue inputs name columns containing log2 fold changes and raw p-values; do not imply arbitrary
  effect-size support. Label content may identify any measured feature, not only genes/proteins.
  Volcano subset=None disables labels; an integer selects top differential features by its
  significance score, "significant" selects all differential features, and a list selects label
  values. These domain-specific defaults/ranking differ intentionally from ds.labels. The
  constructor stays under ds.biology and returns `alt.LayerChart`.

## Rendering and State

- `ds.theme()` replaces active configuration; it does not incrementally update previous settings.
- `ds.show()` returns corrected SVG wrapped in `IPython.display.HTML` for compatible interactive
  display. `ds.save()` writes figures. Bare Altair display does not run the full formatting pipeline.
- Preserve the distinction between static corrected output and browser-rendered interactive HTML.
  Save's SVG/PNG transparency override is separate from the theme's logical background.
- Statistical constructors calculate annotations and register export records. Standalone numerical
  computation is outside the current public scope; users can use SciPy. Keep the engine private.
- Supplied pvalues are final pairwise values: skip pairwise calculation and additional correction.
  In omnibus mode, still compute the omnibus result, but replace the requested post-hoc results
  with the supplied values and do not compute unrequested post-hoc comparisons. Reports and
  metadata distinguish computed omnibus results from supplied comparisons and must not attribute
  supplied values to an unrun test. Require finite numeric probabilities in [0,1], excluding bools;
  apply a consistent zero-underflow policy before both display formatting and record creation.
- Statistical annotations reject missing or non-finite values in used columns and required results;
  unused columns are ignored. `nComparisons` is a positive, non-bool integer and, when adjustment
  applies, cannot be smaller than the computed family; larger values are valid. Grouped comparison
  notation mappings, y-position lists, and `postHoc` are unsupported.
- Correlation grouped labels prefix custom text with each group. `lineStyle` takes precedence over
  curated line options in both modes, and `ciColor` controls the band fill before the effective line
  color fallback; rank-method `ci` syntax is still validated when its band is inactive.
- Distinguish report printing, standalone report writing (`saveReport`), and embedding reports.
- Statistical prose reports use a fixed three significant figures, independent of plot `sigFigs`
  and notation. Structured numerical records retain calculation values rather than display-rounded
  values; report p-values do not inherit the plot's display floor.
- `description` is the user's text only, without appended reports or provenance. Report sections
  are separate from the description and appear once per export format when embedded.
- `SOURCE_DATE_EPOCH` pins export time to integer UTC seconds and makes `exportIdentifier`
  content-derived. Identical inputs in the same producing environment, including variant order,
  can produce byte-identical re-exports and share an identifier across separate saves. All variants
  of one save share the identifier, while their spec checksums may differ. Unset or blank uses
  ordinary time and a fresh identifier; malformed or out-of-range epochs raise, never fall back.
- Spec, data, and export identities answer different questions. Data identity ignores row order
  but preserves duplicate rows and excludes generated sidecars. Single-file verification reports
  True/False for checks that ran and None for unavailable checks; an unavailable check is not a
  failure or proof of a match. Comparing files' recorded identities is not checking their integrity.
- Treat filesystem paths consistently as strings or Path objects; distinguish directory arguments
  from output filename stems. Document external effects such as Illustrator swatch installation.
- Metadata inspection and chart reconstruction depend on the producing environment. V4 does not
  preserve backward compatibility with earlier releases; do not add legacy loading adapters.
  Existing formats may still work naturally, but that is not a compatibility commitment.
- Current-version JSON exports persist compact statistical record ownership separately from the
  records themselves. `load()` restores that ownership so records follow their chart component
  through composition, extraction, and re-export. It preserves recorded results and their source
  checksum without recomputation; each new save generates current provenance and export identity.
  Loaded records are guarded by a digest of their saved analytical panel context. Re-export fails
  closed if source rows, mappings, transforms, parameters, or annotation values changed; rebuild the
  annotation from its source data instead. Presentation-only edits and intact panel composition or
  extraction remain valid. Lookup transforms, nonempty parameters/selections, external data, and
  expressions beyond deterministic operations on `datum` cannot be preserved. `load(raw=True)` only
  returns the untouched specification and does not restore runtime ownership.
  `stats.clear_stats()` clears pending live calculations without detaching records restored with a
  loaded chart. Saving with metadata disabled removes the internal ownership identities as well.
- Source renames do not automatically rename stored metadata keys or checksum formats.

## Growth and Maintenance

- Add options for variations of one operation; add sibling functions for genuinely different input
  contracts or workflows. Mode-dependent ignored options signal a responsibility problem.
- Standalone `+` layers are useful, not mandatory for every future annotation. A future chart-aware
  operation may use the add convention, but no such redesign is currently planned.
- Grow `ds.ext` only when real extension consumers need a stable primitive. Keep optional domain
  packages independently distributed; do not expose private internals merely for convenience.
- Keep correctness fixes distinct from spelling changes so rendering and record changes are visible.
- Before a major release, inspect deprecation markers and remove obsolete APIs scheduled for that
  release, including their compatibility paths and obsolete tests/docs. Remove markers with the
  obsolete behavior, not merely the comments. Do not confuse historical changelog entries with
  live compatibility code or postpone public API removal to a later internal refactor.
- Update exports, typing, tests, examples, guides, and extension consumers together. Use rendered
  text/geometry tests when the contract is visual, not only assertions that a chart was constructed.

Release-specific compatibility policies and unapproved experiments belong in local planning
documents. Add them to this framework only when they become agreed public contracts.

# Design Decisions

Reasons for decisions that are easy to reverse accidentally. Public contracts are in [API.md](API.md);
implementation details and current behavior are in source and tests. Read the relevant sections.
Source references below are relative to `src/dysonsphere/`; test references are relative to `tests/`.

## Theme and Color

- **Master palette wins.** A single palette setting controls every range even when per-type
  settings exist. Do not replace this with the usual specific-setting-wins rule.
  References: `theme.py::_dysonsphere_theme`; `test_theme.py::TestRangePalettes`.

- **Category colors are positional.** Emit color lists as bare category ranges, not scheme
  wrappers, so categories receive the palette's ordered colors rather than losing the range.
  References: `theme.py::_dysonsphere_theme`; `test_theme.py::TestRangePalettes.test_category_is_bare_array`.

- **Automatic mark fill tracks render mode by provenance, not value.** Theme state records whether
  `markFill` was omitted from both configuration and the call. Only that state resolves the default
  grey live when save/show toggles `darkmode`; comparing hex values would incorrectly reinterpret an
  explicit default-colored fill as automatic. References: `theme.py::theme`, `_opt`,
  `_dysonsphere_theme`; `test_theme.py::TestThemeDefaults`.

- **Axis displacement is not data padding.** Moving an axis cannot keep marks off its ends.
  Keep `axisOffset` independent of `viewPadding`; changing either must not disable the other.
  Moving the closed frame outward with an `offsetView` SVG fixer was rejected. Use scale padding,
  with shared spec fixes preserving explicit `nice` settings, not a second frame geometry system.
  References: `theme.py::_compute_derived`; `utils.py::_apply_spec_fixes`;
  `test_theme.py::TestViewPadding`; `test_export.py::TestSuppressNice`.

- **Band geometry follows D3's degenerate scale rule.** Use D3's `max(1, denominator)` clamp and
  default centered alignment. At one category, inner padding 1, and outer padding 0, this produces a
  zero-width band centered in the span rather than dividing by zero. Keep normal multi-category and
  nested geometry unchanged. References: `utils.py::_band_geometry`; `test_utils.py::TestPrivateBandGeometry`.

- **Gradient titles stay horizontal.** Rotated colorbar titles were rejected. A global
  `config.legend.titleOrient` is not a substitute: it also changes symbol legend titles.
  References: `theme.py::_dysonsphere_theme`;
  `test_export.py::TestGradientLegendTitles.test_save_does_not_inject_title_orient`.

- **Continuous legend length follows its owning panel.** The theme stores its length setting in a
  temporary native `gradientLength` expression; the shared spec pass resolves it to a static per-view length.
  The `None` default allocates half the height vertically and the full width horizontally; an explicit
  positive factor scales either full span before vertical title space is removed. Resolution happens
  before compilation. This handles fixed unit, facet, and composition dimensions without an SVG
  geometry fixer. Explicit native field/config lengths take precedence. Shared legends use the
  first merged encoding's panel size; mixed-size shared scales should set a native length explicitly.
  The marker is not executable Vega: continuous legends require `ds.save()` or `ds.show()` to resolve
  it, including HTML saved through Dysonsphere. Bare Altair/notebook rendering is unsupported and
  can fail with an unrecognized function rather than merely use a different legend length.
  References: `theme.py::_dysonsphere_theme`; `utils.py::_resolve_gradient_legend_lengths`.

- **Continuous legend thickness is fixed geometry.** `legendGradientThickness` is a pixel value,
  independent of `markSize`, chart dimensions, and the panel-relative length factor. Native field
  and legend-config thickness overrides retain Vega-Lite precedence.
  References: `theme.py::_dysonsphere_theme`; `test_theme.py::TestLegendGradientThickness`.

- **Line ends stop at the data.** Lines use butt caps so their ink does not overshoot an interval
  band. Do not change the global cap default to achieve this; axes and rules have separate needs.
  References: `theme.py::_dysonsphere_theme`; `test_theme.py::TestLineCap`.

## Rendering and Text

- **Corrected SVG uses one ordered pipeline.** `export.py::_render_fixed_svg` renders and parses once,
  then applies geometry and layering from `_svg_geometry.py` followed by text handling from
  `_svg_typography.py`. Rule decoration and figure-label alignment precede simplification; axis
  reordering precedes border/shade sinking; scripts precede statistical italics and Greek handling;
  Illustrator font normalization remains last. `save()` and `show()` share this sequence.

- **Align ticks at the source.** Fractional tick positions are intentional for print alignment,
  even if hairlines look softer at screen scale. Keep `axis.tickRound=False` and
  `axisBand.tickOffset=0`; do not restore mark-specific SVG tick-position heuristics.
  References: `theme.py::_dysonsphere_theme`; `test_export.py::TestExactTickPositions`.

- **Flip inward ticks only in corrected output.** Negative theme tick sizes bypass schema
  constraints and disrupt browser label spacing. Keep the SVG correction rather than inserting
  negative lengths into specs that also feed interactive HTML. `tickDirection="in"` defaults an
  omitted frame to closed; explicit `closed=False` wins.
  References: `_svg_geometry.py::_flip_ticks_inward`; `test_export.py::TestFlipTicksInward`.

- **Remove scaffolding at its source, not transparent data.** Minor-axis hosts filter to zero
  rows. An SVG pass deleting opacity-zero marks would also erase the user's transparent data
  marks, making an editable export incomplete.
  References: `nonlinear.py::_minor_tick_layer`;
  `test_export.py::TestScaffoldingMarks.test_transparent_data_marks_are_preserved`.

- **Typography does not depend on authorship.** Matching handwritten labels receive the same
  script and statistical-symbol treatment as generated labels. `ns` is an abbreviation, not a
  symbol; Greek symbols stay upright. Whole-label italics are not a substitute for symbol italics.
  References: `_svg_typography.py::_typeset_scripts`, `_italicize_stat_symbols`;
  `test_export.py::TestItalicizeStatSymbols`.

- **Subscript syntax must not reinterpret column names.** Use boundary-guarded double underscores
  for author tokens. Single underscores collide with snake_case; unguarded double underscores
  collide with names such as `model__alpha`. Typeset script runs rather than trusting fonts to
  supply consistent Unicode script glyphs. Leave accessibility attributes unchanged.
  References: `_svg_typography.py::_SUB_DUNDER`, `_typeset_scripts`;
  `test_export.py::TestFixSubscriptLabels`, `TestFixSuperscriptLabels`.

- **Font handling is output-specific.** Keep a family-name-first stack for renderer italic faces.
  Illustrator needs its resolvable alias in saved SVG, but other-family and generic fallbacks
  must survive. Do not globally replace the theme font with a PostScript-only name.
  References: `_svg_typography.py::_illustrator_font_family`; `test_export.py::TestFixFontForIllustrator`.

- **Greek font switching is a local editable-text correction.** In shared static SVG processing,
  wrap Unicode letters identified as Greek (plus attached combining marks) in font-family tspans;
  do not substitute legacy Symbol character codes or replace the surrounding font. Unicode naming
  avoids sweeping Coptic and punctuation into the feature; U+00B5 MICRO SIGN remains in the main
  font. Named fonts are not embedded, so availability and publisher compliance remain user concerns.
  References: `_svg_typography.py::_switch_greek_font`; `test_export.py::TestSwitchGreekFont`.

## Composition and Annotations

- **Equation rules require an explicit x span.** A standalone native Altair annotation cannot
  discover another chart's resolved domains or facet-local scale names. Equation mode therefore
  computes ordinary datum endpoints from `slope`, `intercept`, and a required numeric `span`, with
  linear quantitative axes as a documented caller responsibility. Do not introduce arbitrary
  endpoints, generated scale-name expressions, or export-only rewriting.
  References: `annotations.py::rule`; `test_annotations.py::TestRule`.

- **Rule caps use resolved SVG segment geometry.** Vega-Lite does not expose a facet-local rendered
  direction for sibling cap marks. Durable rule markers therefore carry cap/gap intent through JSON
  save/reload, while common SVG processing measures the rendered line and adds editable SVG
  decoration objects before simplification. This keeps reversed scales, facets, and aspect ratios
  correct without scale-name expressions. Bare Altair and HTML remain intentionally undecorated.
  References: `annotations.py::_rule_cap_marker`; `_svg_geometry.py::_decorate_rule_segments`;
  `test_export.py::TestRuleCaps`.

- **Automatic point-facing gaps share one construction-time formula.** Label connectors and capped
  rules use `sqrt(markSize / (2*pi)) + markStrokeWidth + 2*axisWidth`: point edge radius, marker
  stroke, and painted daylight. Extracting this formula must not change labels' existing point- or
  text-end geometry. Rule markers store the resolved pixels, so multi-theme exports rebuild through
  a callable like other construction-time geometry.
  References: `annotations.py::_automatic_marker_gap`, `labels`, `rule`.

- **Label connector arrows decorate existing connector geometry.** `labels` already resolves its
  point- and text-end clearances before emitting a connector. Its point-facing arrow therefore uses
  the shared rule-cap marker with zero additional SVG gap, preserving placement and applying
  `connectorGap` once. A connector too short for the resolved cap is omitted without moving its label.
  References: `annotations.py::labels`; `_svg_geometry.py::_decorate_rule_segments`.

- **Point labels are placed during save/show.** `labels` stores the point coordinates and label
  settings used for later placement. The renderer evaluates the complete rendered panel, solves all
  label groups together in each panel against supported visible sibling symbols, straight lines/rules,
  filled or outlined rectangles, and fixed text, then writes deterministic pixel positions. This runs
  for every `save` format and `show`, survives JSON load, and leaves the source chart unchanged.
  Unsupported panel mappings raise rather than using incomplete obstacle geometry. Bare Altair keeps
  the initial placement. Boundary-sliding attachments keep emitted geometry consistent with the
  solver's linear model. Only visible faces are eligible: a route to the far side would cross its label.
  Collision checks use the same shortened segments as drawing, not center-to-center rays or invisible stubs.
  Side attachments prefer the middle of the text edge, with limited obstacle-driven sliding;
  top/bottom attachments stay inset. Facing corners remain eligible for genuinely diagonal routes,
  not nearly edge-parallel approaches that resemble detached underlines.
  References: `annotations.py::labels`; `_label_resolution.py`; `_label_placement.py::_shortened_segment`.

- **Forced label connectors preserve clearance.** `alwaysShowConnectors=True` moves among bounded
  seats to reserve the full marker gap, text gap, and visible stroke; it never shrinks those gaps.
  A connector whose requested gap cannot fit is omitted rather than drawn through a mark. Connectors attach to a
  tighter portable text estimate (or the actual chip), while padded boxes remain collision safety.
  References: `_label_placement.py::_estimate_attachment_size`, `_shortened_segment`.

- **Extensions have their own distributions.** Keep optional dependencies and release schedules
  outside core. Extras would couple releases; namespace-package restructuring would disrupt the
  core import path for little gain. Discovery supplies `ds.biology` without either change, and
  `ds.ext` grows only for real consumers rather than publishing speculative helpers. Discovery and
  author support share `ext.py`, but discovery stays at `ds.extensions()` and `ds.load_extension()`;
  naming the namespace `extensions` would collide with the callable. Defining the chart union there
  gives extension authors and export one type identity without an extension-to-export import cycle.
  References: `ext.py`; `__init__.py::__getattr__`; `test_ext.py`, `test_extensions.py`;
  `dysonsphere-biology/pyproject.toml` (repository root).

- **Pin category domains, not just sort order.** Vega-Lite can reorder domains when merging
  layers. Explicit domains keep non-alphabetical categories, colors, and multilabel columns
  aligned; a sort hint alone is insufficient.
  References: `marks.py::_MarkScaffold`; `test_marks.py::TestCategoryOrderPreserved`;
  `test_multilabel.py::TestMultilabelXOrder`.

- **Bracket coordinates depend on composition.** Single-factor brackets use pixels so an
  independently resolved violin axis cannot strand a nominal bracket scale. Suppressing that
  scale's axis instead would suppress a shared strip/boxplot axis. Grouped brackets retain the
  real offset encoding and its order; generic band pixels do not describe those positions.
  References: `stats.py::_pvalue_layer`; `test_stats.py::TestBracketNoPhantomAxis`.

- **Bracket order favors readable nesting without added height.** Prioritize fewer levels, then
  less distance above the data, preferring comparisons grouped by their left endpoint on ties.
  The default pixel layout also considers data demand; an unconditional nested fan can float far
  above unordered groups. Keep layout scoring in source, not a second algorithm in guidance.
  References: `stats.py::_bracket_offsets`, `_stack_levels`; `test_stats.py::TestBracketOrder`.

- **Rotation belongs to values, including symbols.** Text-only rotation would make
  `rowValueAngle` misleading. A circle's invisible rotation is an accepted consequence. Per-cell
  angles let dose labels rotate while control placeholders stay upright. Pixel-positioned rows
  allow unequal text heights without mark-dependent point-scale spacing.
  References: `multilabel.py::_multilabel_layer`; `test_multilabel.py::TestRowValueAngle`.

## Records and Exports

- **Export transparency is not theme background.** Saved SVG/PNG default to transparent so a
  machine's TOML configuration cannot silently make publication figures opaque. Keep the save
  override separate from the logical background used in previews and browser-targeted specs.
  References: `export.py::save`; `test_export.py::TestSaveTransparency`, `TestShow`.

- **Explicit export is unlimited by default.** Altair's 5000-row default is a safeguard for embedded
  notebook specifications, but row count is a poor proxy for Dysonsphere's output size or rendering
  work. `save()` and `show()` pin the default transformer with no cap unless the caller sets
  `maxRows`; do not warn at the arbitrary Altair threshold. An explicit cap applies per dataframe,
  and the previously active transformer is always restored.
  References: `export.py::save`, `show`; `test_export.py::TestSave`, `TestShow`.

- **Plot precision must not coarsen the record.** Reports have their own fixed precision, and
  structured values are not rounded for plot presentation. A display floor is not evidence that
  the calculated p-value equals that floor.
  References: `_statistics.py::_REPORT_SIGFIGS`, `_fmt_p`;
  `test_stats.py::TestSigFigs.test_report_independent_of_theme_sigfigs`, `TestReportPValues`.

- **Correction provenance describes the calculation actually run.** Pair records preserve both unadjusted
  calculated and reported p-values, and correction records store the effective family size passed to
  the generic adjustment. Supplied final values and intrinsically adjusted tests keep inapplicable
  fields null rather than inventing an unadjusted result. Tukey HSD ignores generic correction; Games-Howell
  and Nemenyi retain their existing optional further correction and record its already-adjusted input
  separately. Unadjusted, correction-input, and reported values use calculation precision and the shared
  zero-underflow clamp, never the plot display floor.
  References: `_statistics.py::_make_record`; `test_stats.py::TestCorrectionMetadata`.

- **Reproducibility includes identifiers.** Pinning only time still leaves random identifier
  churn. Include spec identity, not just timestamp and data, to distinguish two plots of the same
  frame. Derive from the first variant and reuse across variants; separate identical saves may
  share an identifier. Invalid epochs fail rather than silently promise reproducibility.
  References: `metadata.py::_derive_export_id`, `_source_date_epoch`, `_resolve_timestamp`;
  `test_metadata.py::TestSourceDateEpoch`.

- **Keep three identities distinct.** Spec identity describes how data was drawn; data identity
  survives presentation changes only when the embedded data stays unchanged. Transforms that add
  columns or alter rows can change its checksum. Export identity groups outputs of a save, subject
  to the reproducibility contract. Keep `sha256:` and `multiset-sha256:` distinct: the latter
  describes a row-multiset construction, not a hash of dataframe file bytes.
  References: `metadata.py::_spec_checksum`, `_data_checksum`; `utils.py::_hash_rows`.

- **Unavailable verification is not failure.** Separate internal consistency from data matching,
  and preserve an unknown result when a check cannot run. SVG/PNG metadata cannot supply a spec
  to re-hash. Comparing recorded identities cannot establish that a file has not been edited.
  References: `metadata.py::VerifyResult`, `verify`; `test_metadata.py::TestVerify`, `TestVerifyCompare`.

- **Descriptions remain user text.** Put reports in their own sections, once per format, rather
  than appending generated prose to a caption. The description's native-format and structured
  copies serve different readers. Call-site source capture is optional context, never identity
  or a reason for a save to fail.
  References: `metadata.py::_call_expression`; `test_metadata.py::TestCallExpression`;
  `test_metadata.py::TestSaveUsermeta`.

- **Loaded statistics retain component ownership, not historical exports.** Current-version JSON
  stores records once and compact owner-to-record-and-context bindings; persistent owning-node names survive the
  saved spec and ordinary Altair composition. `load()` allocates fresh owner identities and imports
  exact records, while re-export regenerates prose, provenance, and export identity. Each owner binds
  the record to a compact digest of its effective analytical panel (data, transforms, mappings,
  parameters, and generated annotation data). Saved point coordinates and label settings remain in the
  analytical context, while generated label connectors/chips/text are excluded because resizing changes
  their pixel positions. Load validates the guard transactionally and every save checks
  it again, failing closed after analytical edits while allowing presentation changes and intact panel
  composition. Lookup transforms and runtime parameters/selections are rejected rather than treated as
  guardable; expressions are limited to deterministic `datum` operations with a small pure-function
  allowlist. Imported records are retained privately by record/context hash - not attached as Python
  chart attributes - so repeated loads do not accumulate an
  owner map and `clear_stats()` continues to clear only pending live calculations. Runtime statistical
  markers remain separate and are still stripped. References: `metadata.py::_prepare_statistics_owners`,
  `_restore_statistics_owners`, `_statistics_context`; `_statistics.py::_loaded_report`;
  `test_metadata.py::TestReadLoad`.

# Repository Guidance

Dysonsphere extends Altair with publication styling, composable charts, and self-documenting exports.
`CLAUDE.md` points here. Keep this file short; API contracts belong in `API.md`, design reasons in
`DESIGN.md`, implementation details in source/tests, and release history in `CHANGELOG.md`.

## Start Here

- Read `API.md` for the intended public contract; inspect source/tests to establish current behavior.
  V4 namespace and parameter naming are migrated; remaining behavior changes and deprecation removal
  are separate work. Do not assume every intended contract is implemented.
- Read the relevant sections of [DESIGN.md](DESIGN.md) before changing the decisions they cover.
- Core: `src/dysonsphere/`. Biology: `dysonsphere-biology/src/dysonsphere_biology/`, a separate
  distribution installed through the uv workspace. Test both packages.
- Maintained examples and site generators: `website/examples/` and `website/scripts/`.
  Read `website/AGENTS.md` when working on the site, not for unrelated library changes.
- Palette recipes: `scripts/print_palettes.py`. Swatch export: `ds.palettes.export_swatches()`.
  Root `docs/` contains only the two README logos. Do not recreate retired gallery/build scripts.
- User-facing agent skill: `skills/dysonsphere/`; installation and evaluation guidance: `skills/README.md`.
  Keep its examples aligned with implementation and run `tests/test_skills.py` when changing the bundle.

## Working Style

- Discuss new non-trivial designs or breaking changes before building. Once approved, execute
  within scope rather than repeatedly reopening settled decisions.
- Reuse settled API and commit conventions. Batch related mechanical changes; keep behavior fixes
  separate from renames so changes to figures and statistical records remain visible.
- Inspect and test existing capabilities before proposing new API surface. Prefer native Altair
  composition and customization over redundant wrappers.
- Delegate bounded tasks with concise results, only when useful. Avoid overlapping investigations,
  repeated inventories, and oversized reports.
- Use targeted checks while editing, then one complete checkpoint per finished code batch. Repeat
  checks when failures or relevant changes warrant it, not for unchanged code. Keep required
  regression, rendering, and CI checks; save on duplication, not quality or approved scope.
- Keep known defects visible; do not hide them in a naming change or expand scope without agreement.
- Report meaningful findings and blockers briefly. Do not narrate routine git operations or defend
  avoidable overhead. Preserve unrelated worktree changes.
- Before committing code, finish docstrings and tests, verify, then update relevant documentation.
  New public functions need tests. Notable changes need an `[Unreleased]` changelog entry: user-facing
  entries under New features/Changes/Fixes, internal-only work under Internal.

## Commands

Full code checkpoint:

```sh
uv run ruff check --no-cache src/ tests/ scripts/ dysonsphere-biology/
uv run ruff format src/ tests/ scripts/ dysonsphere-biology/
uv run ty check .
uv run pytest tests/ dysonsphere-biology/tests/
```

All tests must pass without skips. Use uncached lint for module moves: cached import classification
previously produced a false local pass. For visual changes, render and inspect relevant output
through `ds.save()` or `ds.show()`; spec construction alone does not prove correct rendering.

Run these only when relevant:

```sh
uv run python scripts/print_palettes.py
uv run --with vega-datasets python website/scripts/gen_examples.py [example_name ...]
uv run --no-project --with griffe python website/scripts/gen_api.py
uv build
```

The bracketed example names indicate optional arguments, not literal shell syntax. Use selected
examples during iteration and regenerate affected references after updating source docstrings.

## Code Conventions

- Public parameters use camelCase; private helpers use snake_case. Follow `API.md` for naming,
  defaults, units, and return contracts. Keep public signatures explicit.
- Python lines are limited to 120 characters, including comments/docstrings. Parametrize generics:
  `list[str]`, `dict[str, Any]`, etc.; bare generics fail the configured type checker.
- Use ASCII `-` rather than em dashes in comments and generated prose. Comments explain non-obvious
  constraints, not assignments or design history. Avoid unrelated formatting/comment churn.
- Update module/root `__all__` and namespace tests with public API changes. Do not let module names
  shadow exported functions (`display_labels.py` exists specifically to protect `ds.labels`).

## Implementation Constraints

- Keep the statistical engine/registry in `_statistics.py` independent of Altair; chart wrappers
  live in `stats.py`. Dependencies flow `export -> metadata`, not the reverse. The checksum core is
  `utils._frame_checksum`, publicly re-exported by metadata; stats use the private helper directly.
- Tag every generated chart dataset with `utils._internal_data` (extensions use `ext.internal_data`).
  Never tag the user's data. Otherwise sidecars leak into recovered data and provenance checksums.
- Preserve chart-specific statistics markers: exports select records present in the chart, not all
  accumulated records. Saving does not clear the registry. Marker names must remain unique when
  charts are composed; stored metadata field names are separate from Python parameter names.
- Use `_json_safe` for written values and `_canonicalize` only for hashing. Hash normalization of
  integral floats must not change exported numeric types. Row checksums preserve duplicate rows.
- Use `_opt` for theme reads outside theme.py (`ext.opt` in extensions). Geometry and colors resolved
  at construction may require callable rebuilding for light/dark exports. Theme changes replace state.
- Reuse `_band_geometry` and `_nested_band_centers`; do not duplicate pixel formulas. Keep mark-specific
  band padding: the global inner-padding key overrides them, and rect padding also affects boxplots.
- Fixed reference annotations use datum/value positions to avoid clobbering shared axis titles.
  Facet-safe references share user data through `_datum_base`; global statistical results must not
  simply repeat across facets as though computed per panel.
- Preserve the common save/show SVG pipeline and its ordering. Apply shared spec fixes wherever
  specs are resolved for export, comparison, or website generation. Bare Altair display and interactive
  HTML do not receive the full SVG formatting pipeline.
- Figure/shade markers must survive saved-spec round trips; they deliberately do not use the
  statistics prefix stripped during export. Keep internal identity separate from visible labels.
- Keep palette data as precomputed literals, not import-time color calculations. Preserve palette
  ordering and run the quality/CVD tests when changing ramps; use the recipe script for authoring.
- Prefer builders for size-dependent assembled panels. Theme config is figure-wide; changing a
  view's dimensions does not automatically rescale already-constructed geometry.
- Optional extensions stay separate distributions using discovery and the small public `ds.ext`
  interface. Third-party extensions must not import core private helpers or expose them wholesale.
  The coordinated in-repository `dysonsphere-biology` first-party package is the narrow exception:
  it may directly import shared private core helpers when the core and extension change together.

## Git and Release

- V4 feature branches start from and target `v4.0.0`; never commit directly to protected `main`.
- Commit subjects are concise lowercase fragments, e.g. `refactor: standardize public parameter names`.
  Use add/change/fix/remove/refactor prefixes, normally no body, and no AI attribution. Stage only
  intended files. Do not amend unless asked.
- PR titles describe the outcome without a version prefix. Bodies are short summaries with concrete
  bullets, not essays or a separate tests/docs section. Show the draft before creating the PR.
- Before pushing, check `gh pr list --head <branch>`; if an open PR will receive the push, tell the
  user and let them decide. Do not merge or release without authorization.
- `API.md` is committed. V4 plans/audits/working notes are local-only and excluded from Git; do not
  force-add them. Keep agent guidance at discoverable paths; no `.agents` folder is planned.
- Versions come from git tags through hatch-vcs, not manual pyproject version bumps. Major releases
  include a DEPRECATED/DEPRECATION sweep that removes scheduled obsolete APIs, not just their comments.
- Release through a PR to main, then tag the merged release commit and publish release notes. Tag
  pushes trigger PyPI; main pushes deploy Pages. Coordinate these because Studio installs from PyPI.
  Keep full-history checkout for package publishing, and preserve README logo URLs.

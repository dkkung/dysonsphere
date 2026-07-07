---
title: API reference
description: Reference for the dysonsphere public API, generated from its docstrings.
sidebar:
  order: 0
---

The pages in this section are generated directly from dysonsphere's docstrings (via
[griffe](https://mkdocstrings.github.io/griffe/)), so they track the source.

Browse by area in the sidebar:

- **Annotations** - `add_rule()`, `add_text()`, `add_shade()`, `add_labels()`
- **Display labels** - `label_expr()`
- **Extension authoring** - the `dysonsphere.ext` primitive surface
- **Extensions** - `extensions()`, `load_extension()`
- **Marks** - `mark_strip()`, `mark_violin()`
- **Multilabels** - `add_multilabel()`
- **Nonlinear axes** - `add_log_ticks()`, `add_pow_ticks()`, `log_label_expr()`
- **Palettes** - `palette()`, `categorical()`, `export_swatches()`, and the `colors` catalogue
- **Reading exports** - `read()`
- **Saving & loading** - `save()`, `load()`, `show()`
- **Statistical annotations** - `add_comparisons()`, `add_correlation()`
- **Statistics registry** - `clear_stats()`
- **Theming** - `theme()` and config-file scaffolding (`create_config()`)
- **Transforms** - `add_jitter()`, `add_beeswarm()`
- **Utilities** - `ensure_polars()`, `count_n()`, `band_geometry()`, `frame_checksum()`

Every public function carries type annotations (the package ships a `py.typed` marker), so the
signatures shown here are the same contract your editor and type checker see.

## Dependencies

Requires Python >= 3.11. Runtime dependencies (installed automatically):

| Package | Minimum | Role |
| --- | --- | --- |
| `altair` | 5.5.0 | chart construction and the theme registry |
| `polars[pyarrow]` | 1.19.0 | the native `DataFrame` (pandas input is converted) |
| `numpy` | 1.26.0 | numeric primitives |
| `scipy` | 1.11.0 | statistical tests behind `add_comparisons()` / `add_correlation()` |
| `vl-convert-python` | 1.7.0 | the SVG/PNG renderer behind `save()` (lazily imported) |

Optional: `pandas` / `duckdb` (only for `read(..., output="pandas"/"duckdb")`), `IPython` (only
for `show()`).

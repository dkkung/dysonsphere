---
title: API reference
description: Reference for the dysonsphere public API, generated from its docstrings.
sidebar:
  order: 0
---

The pages in this section are generated directly from dysonsphere's docstrings (via
[griffe](https://mkdocstrings.github.io/griffe/)), so they track the source.

Browse by area in the sidebar:

- **Annotations** - `ds.rule()`, `ds.text()`, `ds.shade()`, `ds.labels()`
- **[Display labels](/reference/display_labels/)** - `ds.label_expr()`
- **Extension authoring** - the `dysonsphere.ext` API
- **Extensions** - `extensions()`, `load_extension()`
- **Marks** - `mark_strip()`, `mark_violin()`
- **Multilabels** - `add_multilabel()`
- **Nonlinear axes** - `add_log_ticks()`, `add_pow_ticks()`, `log_label_expr()`
- **Palettes** - root selection helper `ds.palette()`, `ds.palettes.categorical()`,
  `ds.palettes.export_swatches()`, and the `ds.palettes.colors` catalogue
- **Reading exports** - `ds.metadata.read()`, `ds.metadata.verify()`, `ds.metadata.VerifyResult`,
  `ds.metadata.frame_checksum()`
- **Saving & loading** - `save()`, `load()`, `show()`
- **[Statistics](/reference/stats/)** - `ds.stats.comparisons()`, `ds.stats.correlation()`, `ds.stats.clear_stats()`
- **Theming** - `theme()` and config-file creation (`create_config()`)
- **Transforms** - `ds.transforms.jitter()`, `ds.transforms.beeswarm()`, `ds.transforms.quasirandom()`
Every public function carries type annotations (the package ships a `py.typed` marker), so the
signatures shown here are the same contract your editor and type checker see.

## Dependencies

Requires Python >= 3.11. Runtime dependencies (installed automatically):

| Package | Minimum | Role |
| --- | --- | --- |
| `altair` | 6.0.0 | chart construction and the theme registry |
| `polars[pyarrow]` | 1.19.0 | the native `DataFrame` (pandas input is converted) |
| `numpy` | 1.26.0 | numeric primitives |
| `scipy` | 1.11.0 | statistical tests behind `ds.stats.comparisons()` / `ds.stats.correlation()` |
| `vl-convert-python` | 1.9.0 | the SVG/PNG renderer behind `save()` (lazily imported) |

Optional: `pandas` / `duckdb` (only for `ds.metadata.read(..., output="pandas"/"duckdb")`), `IPython` (only
for `show()`).

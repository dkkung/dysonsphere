---
title: "API reference"
description: "Reference for the dysonsphere public API, generated from its docstrings."
sidebar:
  order: 0
---

The API pages are generated from dysonsphere's docstrings with
[griffe](https://mkdocstrings.github.io/griffe/).

Browse by area in the sidebar:

- **Annotations** – `ds.rule()`, `ds.text()`, `ds.shade()`, `ds.labels()`
- **[Display labels](/reference/display_labels/)** – `ds.label_expr()`
- **Extension authoring** – the `dysonsphere.ext` API
- **Extensions** – `extensions()`, `load_extension()`
- **Marks** – `mark_strip()`, `mark_violin()`
- **Multilabels** – `add_multilabel()`
- **Nonlinear axes** – `add_log_ticks()`, `add_pow_ticks()`, `log_label_expr()`
- **Palettes** – root selection helper `ds.palette()`, `ds.palettes.categorical()`,
  `ds.palettes.export_swatches()`, and the `ds.palettes.colors` catalog
- **Reading exports** – `ds.metadata.read()`, `ds.metadata.verify()`, `ds.metadata.VerifyResult`,
  `ds.metadata.frame_checksum()`
- **Saving & loading** – `save()`, `load()`, `show()`
- **[Statistics](/reference/stats/)** – `ds.stats.comparisons()`, `ds.stats.correlation()`, `ds.stats.clear_stats()`
- **Theming** – `theme()` and config-file creation (`create_config()`)
- **Transforms** – `ds.transforms.jitter()`, `ds.transforms.beeswarm()`, `ds.transforms.quasirandom()`
The public functions have type annotations, and the package includes a `py.typed` marker
for editors and type checkers.

## Dependencies

Requires Python >= 3.11. Runtime dependencies (installed automatically):

| Package | Minimum | Role |
| --- | --- | --- |
| `altair` | 6.0.0 | chart construction and the theme registry |
| `polars[pyarrow]` | 1.19.0 | the native `DataFrame` (pandas input is converted) |
| `numpy` | 1.26.0 | numerical operations |
| `scipy` | 1.11.0 | statistical tests behind `ds.stats.comparisons()` / `ds.stats.correlation()` |
| `vl-convert-python` | 1.9.0 | the SVG/PNG renderer behind `save()` (lazily imported) |

Optional: `pandas` / `duckdb` (only for `ds.metadata.read(..., output="pandas"/"duckdb")`), `IPython` (only
for `show()`).

---
title: API reference
description: Reference for the dysonsphere public API, generated from its docstrings.
sidebar:
  order: 0
---

The pages in this section are generated directly from dysonsphere's docstrings (via
[griffe](https://mkdocstrings.github.io/griffe/)), so they track the source.

Browse by area in the sidebar:

- **Marks** - `mark_strip()`, `mark_violin()`
- **Transforms** - `add_jitter()`, `add_beeswarm()`
- **Annotations** - `add_rule()`, `add_text()`, `add_shade()`, `add_labels()`
- **Statistical annotations** - `add_comparisons()`, `add_correlation()`
- **Multilabels** - `add_multilabel()`
- **Display labels** - `label_expr()`
- **Nonlinear axes** - `add_log_ticks()`, `add_pow_ticks()`, `log_label_expr()`
- **Theming** - `theme()` and config-file scaffolding (`create_config()`)
- **Palettes** - `palette()`, `categorical()`, `export_swatches()`, and the `colors` catalogue
- **Saving & loading** - `save()`, `load()`, `show()`
- **Reading exports** - `read()`
- **Statistics registry** - `clear_stats()`
- **Extensions** - `extensions()`, `load_extension()`
- **Extension authoring** - the `dysonsphere.ext` primitive surface
- **Utilities** - `ensure_polars()`, `count_n()`, `band_geometry()`, `frame_checksum()`

Every public function carries type annotations (the package ships a `py.typed` marker), so the
signatures shown here are the same contract your editor and type checker see.

---
title: "volcano()"
description: "The volcano() chart from the dysonsphere-biology extension."
sidebar:
  order: 2
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Volcano plot for differential-expression results.

Built entirely on dysonsphere's public surfaces - core (``ds.theme`` / ``ds.add_rule`` /
``ds.colors`` / ``ds.ensure_polars``) plus the extension-author primitive surface
(``dysonsphere.ext``: ``opt`` / ``internal_data`` / ``AltairChart``). It doubles as the
reference for how an extension composes a first-class dysonsphere chart without reaching into
core internals.

## `volcano`

```python
def volcano(
    df: pl.DataFrame | Any,
    *,
    log2fcCol: str = 'log2fc',
    pvalueCol: str = 'pvalue',
    geneCol: str | None = None,
    fcThreshold: float = 1.0,
    pThreshold: float = 0.05,
    label: str | int | list[str] | None = None,
    thresholdLines: bool = True,
    palette: tuple[str, str] | None = None,
    nsColor: str | None = None,
    markOpacity: float = 0.85,
    legend: bool = True,
    xTitle: str | None = _UNSET,
    yTitle: str | None = _UNSET,
) -> ext.AltairChart: ...
```

Build a volcano plot (log2 fold change vs -log10 p) as a layered Altair chart.

Points are classified ``"Gained"`` / ``"Lost"`` / ``"Non-differential"`` by the fold-change
and p-value thresholds and colored accordingly; optional dashed threshold guides and gene
labels are layered on. Returns an ``alt.LayerChart`` to compose or pass to ``ds.save()``.
(The third label describes the analytical call, not significance - a point can be significant
yet miss the fold-change threshold, so ``"ns"`` would be wrong for it.)

Colors are resolved from the active theme at call time (darkmode-aware grey for the
non-differential points), so build inside a ``ds.save(lambda: volcano(...))`` callable for
correct light/dark export.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - A polars or pandas DataFrame with per-gene results.
- **`log2fcCol`** (`str`) - Column names for the effect size (x) and the p-value (y is ``-log10`` of it).
- **`pvalueCol`** (`str`) - Column names for the effect size (x) and the p-value (y is ``-log10`` of it).
- **`geneCol`** (`str | None`) - Column of gene names; required only when ``label`` is set.
- **`fcThreshold`** (`float`) - ``|log2fc|`` significance cutoff (default ``1.0``). Vertical guides at ``+-`` this.
- **`pThreshold`** (`float`) - P-value significance cutoff (default ``0.05``). Horizontal guide at ``-log10`` of it.
- **`label`** (`str | int | list[str] | None`) - Which points to label (default ``None`` - no labels). ``int`` -> the top-N most significant, ranked by combined score ``|log2fc| * -log10(p)``; ``"significant"`` -> every significant point; ``list[str]`` -> the named genes. Any non-None value requires ``geneCol``.
- **`thresholdLines`** (`bool`) - Draw the fold-change / p-value guide lines (default ``True``).
- **`palette`** (`tuple[str, str] | None`) - ``(gained, lost)`` hex colors. Defaults to the ``pinksblues`` diverging endpoints (pink = gained, blue = lost).
- **`nsColor`** (`str | None`) - Color for the non-differential points. Defaults to a faint theme grey (darkmode-aware).
- **`markOpacity`** (`float`) - Point opacity (default ``0.85``). All other point styling (fill, size, stroke) comes from the active theme's ``mark_point`` config.
- **`legend`** (`bool`) - Show the significance color legend (default ``True``).
- **`xTitle`** (`str | None`) - Axis titles. Omitted -> ``"log2 fold change"`` / ``"-log10 P"``; ``None`` -> no title.
- **`yTitle`** (`str | None`) - Axis titles. Omitted -> ``"log2 fold change"`` / ``"-log10 P"``; ``None`` -> no title.

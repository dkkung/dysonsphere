---
title: "volcano()"
description: "The volcano() chart from the dysonsphere-biology extension."
sidebar:
  order: 2
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Volcano plot for differential-expression results.

Built on dysonsphere's public surfaces - core (``ds.theme`` / ``ds.rule`` /
``ds.palettes.colors``) plus the extension-author primitive surface (``dysonsphere.ext``:
``opt`` / ``internal_data`` / ``AltairChart``). As coordinated first-party code, this package
may use shared core implementation helpers internally; third-party extensions should use only
the ``dysonsphere.ext`` surface for such primitives.

## `volcano`

```python
def volcano(
    data: 'pl.DataFrame | pd.DataFrame',
    *,
    log2fc: str = 'log2fc',
    pvalue: str = 'pvalue',
    labels: str | None = None,
    fcThreshold: float = 1.0,
    pThreshold: float = 0.05,
    subset: str | int | list[str] | None = None,
    thresholdLines: bool = True,
    palette: str | list[str] | tuple[str, str] | None = None,
    nonDifferentialColor: str | None = None,
    markOpacity: float = 0.85,
    legend: bool = True,
    xTitle: str | list[str] | None = _UNSET,
    yTitle: str | list[str] | None = _UNSET,
) -> alt.LayerChart: ...
```

Build a volcano plot (log2 fold change vs -log10 p) as a layered Altair chart.

Points are classified ``"Gained"`` / ``"Lost"`` / ``"Non-differential"`` by the fold-change
and p-value thresholds and colored accordingly; optional dashed threshold guides and gene
labels are layered on. Returns an ``alt.LayerChart`` to compose or pass to ``ds.save()``.
(The third label describes the analytical call, not significance - a point can be significant
yet miss the fold-change threshold, so ``"ns"`` would be wrong for it.)

Gained/lost colors inherit the active theme's diverging range when ``palette`` is omitted.
The neutral remains a separate dark-mode-aware grey, so build inside a
``ds.save(lambda: volcano(...))`` callable for correct light/dark export.

**Parameters**

- **`data`** (`'pl.DataFrame | pd.DataFrame'`) - A polars or pandas DataFrame with per-gene results.
- **`log2fc`** (`str`) - Column names for the effect size (x) and the p-value (y is ``-log10`` of it).
- **`pvalue`** (`str`) - Column names for the effect size (x) and the p-value (y is ``-log10`` of it).
- **`labels`** (`str | None`) - Column of gene names; required only when ``subset`` is set.
- **`fcThreshold`** (`float`) - ``|log2fc|`` significance cutoff (default ``1.0``). Vertical guides at ``+-`` this.
- **`pThreshold`** (`float`) - P-value significance cutoff (default ``0.05``). Horizontal guide at ``-log10`` of it.
- **`subset`** (`str | int | list[str] | None`) - Which points to label (default ``None`` - no labels). ``int`` -> the top-N most significant, ranked by combined score ``|log2fc| * -log10(p)``; ``"significant"`` -> every significant point; ``list[str]`` -> the named genes. Any non-None value requires ``labels``.
- **`thresholdLines`** (`bool`) - Draw the fold-change / p-value guide lines (default ``True``).
- **`palette`** (`str | list[str] | tuple[str, str] | None`) - A registered palette name, an explicit low-to-high color list, or the existing ``(gained, lost)`` endpoint tuple. Omission inherits the active theme's diverging range.
- **`nonDifferentialColor`** (`str | None`) - Color for the non-differential points. Defaults to a faint theme grey (dark-mode-aware).
- **`markOpacity`** (`float`) - Point opacity (default ``0.85``). All other point styling (fill, size, stroke) comes from the active theme's ``mark_point`` config.
- **`legend`** (`bool`) - Show the significance color legend (default ``True``).
- **`xTitle`** (`str | list[str] | None`) - Axis titles. Omitted -> ``"log2 fold change"`` / ``"-log10 P"``; ``None`` -> no title.
- **`yTitle`** (`str | list[str] | None`) - Axis titles. Omitted -> ``"log2 fold change"`` / ``"-log10 P"``; ``None`` -> no title.

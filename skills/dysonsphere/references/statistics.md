# Statistical annotations

Read this before adding or changing inferential results. These are chart constructors, not a
general numerical-analysis API. Use the installed docstrings for the supported test/mode combinations.

## Establish the analysis before choosing syntax

- Identify the independent observational unit, grouping variables, requested comparisons, and
  whether repeated observations require pairing or a model outside this API. Equal group lengths
  do not establish pairing. For paired tests, validate unique subject keys, missing partners, and
  matched ordering explicitly; do not assume the wrapper joins observations by identifier.
- Do not let `comparisons()`'s default Mann-Whitney U test stand in for a scientific decision.
  Inspect assumptions and retain a justified existing method. Do not describe Mann-Whitney U as
  universally testing a difference in medians; its interpretation depends on distribution assumptions.
- Plot and test the intended data. If missing/non-finite values prevent calculation, report the
  issue and agree on explicit handling. Do not silently filter just the statistical layer.
- Define the multiple-testing family independently of which brackets will be displayed. Avoid
  testing only favorable pairs or presenting uncorrected values as adjusted results.
- Distinguish dispersion (SD), uncertainty of a mean (SEM), confidence intervals, and prediction
  intervals. A p-value does not quantify effect magnitude or establish equivalence when nonsignificant.

## Comparisons

Compose `chart + ds.stats.comparisons(data, "group", "value", ...)`. Supply the same category order
as the plotted marks, with every observed category exactly once.
Pairwise mode takes `pairs=[("Control", "Treatment")]` or `pairs="all"`;
omnibus mode can use `pairs=None` for a single overall label. Decide the mode and test intentionally.

- Pairwise tests include `mannwhitneyu`, `ttest_ind`, `ttest_rel`, and `wilcoxon`. Check the installed
  implementation's statistical assumptions rather than assuming arbitrary SciPy options are exposed.
- Omnibus examples include `anova`, `kruskal`, and `friedman`. Their default post-hoc methods differ;
  an omnibus call may compute/report all post-hoc pairs even when only some or no brackets are drawn.
- `correction="holm"` is one supported adjustment. `nComparisons` can specify a larger comparison
  family, but must not understate the computed family. Do not change corrections to alter a conclusion.
- In grouped `xOffset` mode, pairs name subgroup levels within each x category. Align `categories`
  with the x order and `xOffsetSort` with the plotted subgroup order. Correction covers the computed
  category-by-pair family, which can exceed the displayed bracket count; do not use that count as
  `nComparisons`. This mode does not support all single-factor options, including `postHoc`.
- Supplied `pvalues` are final pairwise probabilities: no pairwise test or further correction runs.
  In pairwise mode a list follows `pairs` order; grouped/reference modes use documented keyed mappings.
  An omnibus test still runs if requested, even with supplied pairwise values. Do not attribute supplied
  values to an unrun test or call them adjusted without knowing their source.
- Automatic brackets are convenient, but log-axis placement may need explicit `yPositions` in data
  units. Inspect bracket clearance and category alignment rather than changing data to fit annotations.

### Example: a specified independent-group comparison

This standalone synthetic example assumes the analysis plan already specified a two-sided
Mann-Whitney U comparison of independent observations. Points and medians show the distributions;
the example does not imply that this test is appropriate for every two-group dataset.

```python
# example: comparisons
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({
    "condition": ["Control"] * 6 + ["Treatment"] * 6,
    "response": [1.0, 1.4, 1.1, 1.8, 1.3, 1.6, 1.5, 2.0, 1.7, 2.4, 1.9, 2.2],
})
categories = ["Control", "Treatment"]
ds.theme(width=170, height=130)
points = ds.mark_strip(
    data, "condition", "response", categories,
    scatter="beeswarm", errorbars=False, xTitle=None, yTitle="Response (a.u.)",
)
annotation = ds.stats.comparisons(
    data, "condition", "response",
    pairs=[("Control", "Treatment")], test="mannwhitneyu", categories=categories,
)
ds.save(points + annotation, "skill_comparisons")
```

## Correlations and fit bands

`ds.stats.correlation(data, "x", "y", ...)` returns an annotation layer. Pearson draws an OLS
line by default; Spearman and Kendall report rank coefficients without an OLS line or band.
Do not equate a correlation with causation or select a method solely because its p-value is smaller.

For Pearson, `ci=0.95, interval="confidence"` draws uncertainty in the mean response;
`interval="prediction"` describes a new individual observation. Give the base scatter explicit
axis titles so internal band fields do not leak into merged titles. `groupBy="series"` calculates
per-series results; color the scatter by that same field. A pooled fit is not a within-group fit.

This standalone synthetic example assumes an appropriate independent-observation linear model.

```python
# example: correlation
import altair as alt
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({"input": [1, 2, 3, 4, 5, 6], "response": [1.3, 1.8, 3.4, 3.6, 5.2, 5.7]})
ds.theme(width=180, height=130)
scatter = alt.Chart(data).mark_point().encode(
    x=alt.X("input:Q", title="Input (a.u.)"),
    y=alt.Y("response:Q", title="Response (a.u.)"),
)
fit = ds.stats.correlation(data, "input", "response", method="pearson", ci=0.95, interval="confidence")
ds.save(scatter + fit, "skill_correlation")
```

For light/dark exports, construct the fit and band inside the save callable, as in the export reference.

## Records and interpretation

Statistical constructors register structured records. Saving selects records belonging to the actual
chart; it does not consume or clear the registry. Keep the returned annotation in the chart even when
only its report is wanted, using the documented visibility controls rather than discarding the layer.

`report=True` prints a report; `saveReport` writes a standalone report; `ds.save()` embeds records
and, by default, their readable report. These are different operations. Inspect exported records with
`ds.metadata.read(path, what="statistics")` and compare method, groups, counts, and correction to the
intended analysis. Plot label rounding is not the precision of stored results, and a displayed bound
such as `P < 0.001` is not an exact calculated value.

For a loaded chart, changing analytical data or mappings can invalidate preserved statistical records.
Do not remove the guard or strip metadata to conceal the mismatch. Rebuild the annotation from its
appropriate source data; see the export reference for reconstruction and verification limits.

# dysonsphere-biology

Biology chart extensions for [dysonsphere](https://github.com/dkkung/dysonsphere).

Install alongside dysonsphere; the charts are then reachable both directly and through the
`dysonsphere.biology` namespace (via dysonsphere's extension discovery):

```python
import dysonsphere as ds
import dysonsphere_biology  # noqa: F401  (registers the `biology` extension)

ds.theme()
chart = ds.biology.volcano(df, log2fcCol="log2fc", pvalueCol="pvalue")
ds.save(lambda: ds.biology.volcano(df), "volcano")
```

## Charts

- **`volcano(df, ...)`** - differential-expression volcano plot: `log2fc` vs `-log10(p)`,
  points colored up / down / not-significant, optional threshold guides and gene labels.
- **`western_blot(images, groups, categories, ...)`** - stacked blot-strip images (optionally
  bordered, with controllable spacing) annotated with a dysonsphere condition table below the
  lanes (via `ds.add_multilabel`). Pass one image or several; each is a file path, `data:` URI,
  or PIL `Image`.

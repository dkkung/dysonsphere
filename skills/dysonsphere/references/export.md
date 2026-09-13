# Rendering, exports, and saved figures

Read this when saving, checking light/dark output, troubleshooting rendering, or inspecting an export.

## Choose the output deliberately

Call `ds.theme()` before constructing a new figure and saving it. `ds.save(chart, filename, ...)`
takes an extensionless output stem, not a directory or an already-suffixed filename. Ensure the
parent exists and check for existing files: `save()` can overwrite them, and it does not create
the output directory for you. Check both `_light`/`_dark` names when requesting both backgrounds.

| Need | Use |
| --- | --- |
| Editable static figure | `format="svg"` through `ds.save()` |
| Raster figure or inspectable preview | `format="png"` at the default export density |
| Reconstructable chart and inlined data | `format="json"` |
| Browser interaction | `format="html"`; not equivalent to corrected static rendering |
| Accurate notebook preview | `ds.show(chart)`; requires IPython and a compatible display |

`format` accepts one string or a list. Omission follows theme configuration (built-in default:
SVG plus JSON). If the user does not request formats, use `ds.save(chart, "figure")` rather than
adding PNG or every supported format. Honor an existing project configuration. Specify `format`
when the user requests particular deliverables, including PNG when requested.

If image inspection requires PNG, create a separate temporary preview of the corrected output at
the library's default raster density. Composite transparent previews against the intended light/dark
background when the viewer's canvas is unsuitable; leave the delivered SVG unchanged.
Do not change the example's deliverable formats or add an
unrequested PNG to the final output set just to satisfy the inspection tool. There is no direct
PDF format in this API; do not invent one or claim an external conversion has been verified.

SVG/PNG and `show()` use Dysonsphere's corrected static pipeline. Bare Altair display bypasses it;
continuous legend sizing markers can even make that display fail. HTML saved with `ds.save()` resolves
shared specification fixes but does not apply static corrections such as script typography, inward
ticks, and rule-cap decorations. Inspect the output tier the user actually requested.

## Rebuild for light and dark

`background` selects the logical theme variant; `transparent` selects whether the saved SVG/PNG
includes its background fill. Static output is transparent by default. A transparent dark figure
can look blank on a white viewer canvas; preview against the intended background before recoloring it.

`ds.save(builder, ..., background=["light", "dark"])` calls a zero-argument builder after switching
the mode for each variant, then restores the previous mode. Rebuild all construction-time colors and
geometry inside that callable, including nested assembled panels. Returning the same prebuilt chart
from a lambda does not rebuild its colors. Do not call `ds.theme()` inside the builder: that would
reset the mode or panel dimensions selected by `save()`/`assemble()`.

This standalone synthetic example requests opaque light and dark variants and rebuilds an emphasis
color in each. With built-in format defaults it writes `skill_backgrounds_light.svg`/`.json` and
`skill_backgrounds_dark.svg`/`.json`; single-background output has no suffix.

```python
# example: backgrounds
import altair as alt
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({"input": [1, 2, 3, 4, 5, 6], "response": [1.3, 1.8, 3.4, 3.6, 5.2, 5.7]})
ds.theme(width=180, height=120)


def build_chart():
    return alt.Chart(data).mark_point(color=ds.palettes.accents["blue"]).encode(
        x=alt.X("input:Q", title="Input (a.u.)"),
        y=alt.Y("response:Q", title="Response (a.u.)"),
    )


ds.save(
    build_chart, "skill_backgrounds",
    background=["light", "dark"], transparent=False,
)
```

Leave `ppi` at its default unless the user specifies a different delivery requirement. Do not
reduce quality for a draft: the user may want to use that image immediately. Inspect intrinsic font
sizes and layout at the final physical size; increasing density does not fix clipped or undersized labels.
For ordinary single-background output, a prebuilt chart is sufficient when its captured colors
match the requested mode.

## Troubleshoot at the right level

- **Unknown keyword or missing attribute:** check the executing environment's versions, installed
  signature, and docstring. These examples use Dysonsphere 4.0.0; do not import core private helpers or add a
  compatibility shim to make a guessed name work.
- **Too many rows:** every save format resolves inlined data. Assess the output size and privacy
  implications before increasing `maxRows` or using `overrideMaxRows=True`. Do not silently sample
  rows, globally disable protections, or assume saving only PNG bypasses the cap.
- **Clipped labels/brackets:** check domains, panel size at construction, label density, and final
  rendered bounds. Rebuild size-dependent panels; do not change data or conclusions to make room.
- **Wrong category colors/order:** align explicit category/subgroup domains across marks and
  annotations. Changing only a sort hint may not control shared scales after composition.
- **Panels with matching domain arguments but different ticks:** inspect child encodings and
  composition scopes. A parent `.encode()` may not reach a composite mark's internal scales.
  Compare two or more rendered tick values, then inspect the compiled saved spec if needed.
  Use the explicit native-layer recipe in the plotting reference rather than shifting ticks by hand.
- **Unexpected font/typography:** verify installed fonts and inspect corrected SVG/PNG, not just
  browser HTML. Named fonts are not embedded; do not claim portability to a machine without them.

## Privacy and reproducibility

JSON and HTML can inline the entire dataframe supplied to the chart, including unplotted columns.
Metadata can include username, script context, environment versions, and statistical records.
Before sharing, agree on needed columns and provenance. `saveMetadata=False` does not remove chart
data from JSON/HTML, and `embedReport=False` does not remove structured statistics. Do not upload
exports to a validator or sharing service without authorization.

For byte-reproducible builds, `SOURCE_DATE_EPOCH` pins export time and derives a content-based
identifier. This only helps with identical inputs and a deterministic build in the same producing
environment; record stochastic seeds/transform choices separately. Do not impose this setting on
ordinary analyses or promise reproducibility across renderer/font changes.

## Inspect or reconstruct an existing export

Use only the capability the format supports:

- `ds.metadata.read(path, what="metadata")` returns the metadata block from SVG, PNG, or JSON.
  `what="statistics"` returns structured records; `what="report"` prints and returns report text.
- `ds.metadata.read("figure.json", what="data")` recovers inlined data from JSON, not SVG/PNG.
  With several user datasets, request `dataset="all"` or the appropriate dataset name. The recovered
  frame may contain transform-derived columns; do not call it a byte-identical source file.
- `ds.load("figure.json")` reconstructs a chart and by default applies the saved theme. It can
  change active theme state. Current-version JSON restores statistical ownership; `raw=True`
  instead returns the untouched spec without that restoration. Pre-4.0.0 exports have no compatibility guarantee.
- `ds.metadata.verify(path, data=data)` checks internal consistency where possible and compares
  recorded data identity to the supplied dataframe. `specValid` and `dataMatches` can be `None`
  when a check cannot run. Inspect them individually; `.ok` does not mean every check was possible.
  If a figure embeds both a full frame and a separate endpoint subset, pass `data=[data, endpoint]`
  to check both. Supplying only the full frame does not verify the whole multi-dataset figure.
  Use the frames actually supplied to the charts, including any deliberately derived columns.
- `ds.metadata.verify([path_a, path_b], what="data")` compares recorded identities, not file
  integrity. Checksums are not signatures proving authorship or that nobody modified a figure.

Keep edits to loaded charts presentation-only unless rebuilding their statistics from source.
Analytical changes can cause re-export to fail closed; suppressing metadata is not a workaround.
Explain verification limits and missing provenance rather than treating an unavailable check as a match.

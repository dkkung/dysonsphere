# Website (dysonsphere docs site)

An Astro + Starlight docs site for dysonsphere, built by two Python generators plus Astro. Lives
in `website/`; developed on the `website` branch (in the main repo - the dedicated worktree was
dissolved 2026-07-06).

## Layout

- `src/content/docs/` - pages: `index.mdx` (home; uses the DEFAULT docs template, not `splash`, so
  the sidebar shows on the landing page too), `guides/*` (getting-started, theming, **configuration**
  [the dysonsphere.toml reference], palettes, marks, annotations, statistics, nonlinear, saving),
  `extensions/*` (index/overview, biology, authoring), `gallery.mdx`, `palettes.mdx` (the
  palette browser + live preview, under Interactive), `config-generator.mdx` (the
  dysonsphere.toml generator, under Interactive), `studio.mdx` (Chart Studio),
  `playground.mdx` (a thin **redirect stub** to `/studio/`, kept for old `#code=` deep links),
  `reference/*` (generated API).
- `src/components/` - `Chart.astro` (live vega-embed chart from a named spec, light/dark reactive),
  `Example.astro` (registry example: verbatim `examples/<name>.py` source as the code block + its
  live chart + "Open in studio" deep link), `Studio.astro` (the **two-mode Chart Studio**: an
  interactive builder AND an embedded CodeMirror editor - the old Playground was absorbed into it),
  `PlaygroundRedirect.astro` (client-side `/playground/`→`/studio/` redirect preserving `#code=`),
  `Palettes.astro` (client-side swatch browser from generated JSON; click SELECTS for the live
  preview only, never touches the clipboard - hex rides on data-color attributes since inline
  style serializes to rgb()), `PalettePreview.astro` (charts restyled live by the selected
  palette; holds the explicit "copy hex codes" button - the only clipboard write), `ConfigGenerator.astro`
  (editable default dysonsphere.toml + theme-param cheat sheet, inputs from gen_config.py), `SiteTitle.astro` (two-toned header wordmark +
  the desktop sidebar-collapse toggle; there is no Sidebar override anymore).
- `src/lib/runtime.ts` - the **shared Pyodide runtime** (singleton boot; `getRuntime()`,
  `onRuntimeStatus()`). Exposes `runChart(code, dark)`, `loadTable(name, text, format)`,
  `writeFile(name, data)` (raw FS write, binary-safe), and `readExport(name)` (ds.read metadata).
  `runChart` injects `darkmode`/`transparent` by **monkeypatching `ds.theme` during exec** (same
  technique as `gen_examples.py`), so the site render args apply wherever the snippet calls
  `theme()` and never appear in shown code. `loadTable` also **writes the upload into Pyodide's
  virtual FS under its real filename**, so the emitted `pl.read_csv("file.csv")` runs verbatim.
- `src/styles/theme.css` - the neutral-pro skin (greys ramp for chrome, desaturated blues2 accent),
  landing layout, chart zoom, hover-only export menu.
- `src/generated/` - build inputs generated from the library (`palettes.json`).
- `examples/` - the **example registry**: one copy-runnable `<name>.py` per example, each defining
  a `chart` variable. Source of truth for both the shown snippet and the rendered chart.
- `scripts/` - `gen_api.py` (griffe → `reference/*.md`), `gen_examples.py` (exec each
  `examples/*.py` → `public/charts/*.json`), `gen_palettes.py` (→ `src/generated/palettes.json`).
- `logo/` - the logo family + its generator (see the Logo section).
- `public/charts/` - generated Vega-Lite specs (`<name>-light.json` / `<name>-dark.json`).
- `astro.config.mjs` - Starlight config, sidebar, Inter/JetBrains-Mono fonts, Expressive Code.

## Commands

- Dev server: `npm run dev` (it daemonizes; manage with `astro dev stop` / `status` / `logs`).
- Build: `npm run build` (local, serves at `/`). Deploy-equivalent build:
  `DEPLOY_SITE=https://dkkung.github.io DEPLOY_BASE=/dysonsphere npm run build` - the env vars
  set Astro's `site`/`base` (see astro.config.mjs); CI (`.github/workflows/pages.yml`) builds
  exactly this and deploys `website/dist` to Pages on every push to main.
- npm 11 blocks install scripts: after `npm install`, run
  `npm approve-scripts esbuild sharp && npm rebuild esbuild sharp`.
- Regenerate the API reference: `uv run --no-project --with griffe python website/scripts/gen_api.py`.
- Regenerate the example charts: `uv run --with vega-datasets python website/scripts/gen_examples.py`
  (pass example names to rebuild a subset).
- Regenerate the palette swatch data: `uv run python website/scripts/gen_palettes.py`.
- Regenerate the config-generator inputs (default TOML + theme-param cheat sheet):
  `uv run python website/scripts/gen_config.py`.
- Generated files (`reference/*.md`, `charts/*.json`, `src/generated/*.json`,
  `src/generated/default_config.toml`) are committed for LOCAL DEV (`npm run dev` needs no
  Python), but the deploy does not trust them: `pages.yml` reruns all four generators against
  the checked-out library before the Astro build (since 2026-07-11), so the LIVE site can't
  drift from main. Still regenerate + commit when working on the site locally.

## Conventions and gotchas

- **Example registry.** Every guide chart is a file in `examples/`; `Example.astro` shows that file
  verbatim (vite `?raw`) AND renders the spec `gen_examples.py` produced from executing it, so shown
  code and chart cannot drift. Each example must define `chart` (the studio-editor contract). To add
  one: drop `examples/<name>.py`, run `gen_examples.py`, reference `<Example name="<name>" />`. The
  generator monkeypatches `ds.theme` to inject `darkmode`/`transparent` - keep those out of the
  snippet. **xOffset gotcha:** for beeswarm/jitter, encode `alt.XOffset("beeswarm_x:Q")` WITHOUT
  `scale=None` - the default (band) scale centers the swarm on its tick; `scale=None` shifts it
  left (was the visible x-axis misalignment on the site).
- **The volcano example** (`examples/volcano.py`) calls `ds.biology.volcano`, which needs the
  `dysonsphere-biology` workspace member installed (it is, in the uv venv) - `gen_examples.py`
  builds its spec fine. Its committed spec renders in the gallery/biology page like any other; only
  LIVE studio execution of biology code needs `dysonsphere-biology` on PyPI (not yet published).
- **Shared runtime.** Don't boot Pyodide directly; call `getRuntime()` from `src/lib/runtime.ts`.
  It's a singleton, so both studio modes share one boot. The Python bootstrap lives in
  `PY_BOOTSTRAP`; site render args are applied there, never in shown code.
- **vl-convert has no wasm wheel - install dysonsphere `deps=False`.** dysonsphere >= 3.1.0
  declares `vl-convert-python` (the `save()` renderer) as a runtime dependency; it ships no
  emscripten wheel, so a plain `micropip.install("dysonsphere")` FAILS and the studio never boots
  (this silently broke the live site when 3.1.0 published). `runtime.ts` installs the importable
  deps explicitly (altair/numpy/polars/pyarrow/scipy/vega-datasets) then
  `micropip.install("dysonsphere", deps=False)` - safe because `vl_convert` is imported lazily
  only when `save()` renders, which the browser never does. Keep the explicit list in sync with
  `[project] dependencies` in the root pyproject.
- **Studio export import.** The "Import an export" group takes a `ds.save()` file: a Vega-Lite
  JSON rebuilds the chart via `ds.load()` (seeded + auto-run in the code editor, so shown code =
  executed code); JSON/SVG/PNG all read their embedded block via `ds.read(what="metadata")`
  (`_read_export` in runtime.ts) into a metadata panel (report + structured JSON). Uploads land
  in the Pyodide FS via `writeFile` (binary-safe - PNG works). The export file input is excluded
  from the generic builder-rerender wiring AND `renderBuild` guards on mode, so the async import
  can't be clobbered by a queued sample render (that race shipped briefly during development).
- **Chart Studio codegen.** `Studio.astro` has two modes over one chart panel: a **builder** whose
  emitted snippet reads the upload with `pl.read_csv("file.csv")` (copy-runnable AND executed
  verbatim, since the upload is in the runtime's virtual FS under that name), and a **code editor**
  (the absorbed playground) seeded from the builder via "Edit as code". The builder can layer
  statistics (`add_comparisons`/`add_correlation`), a multilabel table (`add_multilabel`), and
  annotations (`add_rule`, `add_text` with a position preset, `add_shade` bands or a y-range).
  Sample datasets: the synthetic dose-response plus vega_datasets classics (cars/penguins/iris/
  barley/stocks) bundled into the FS as `<name>.csv` by `_load_dataset` so the emitted
  `pl.read_csv("cars.csv")` runs verbatim. Controls flow in TWO CSS columns beside the output on
  wide screens (`columns: 2`, groups `break-inside: avoid`); the dataset select is excluded from
  the generic rerender wiring like the export input (same async race).
- **Plain (unthemed) examples.** Example stems listed in `PLAIN_EXAMPLES` (gen_examples.py)
  render with Altair's DEFAULT theme + an explicit white spec background (readable on dark
  pages) - the "before" half of the theming guide's before/after comparison (`theme_before` /
  `theme_after`, shown side by side via the `.ba` grid in theme.css with per-side zooms, since
  the default chart is ~4x larger natively).
- **Pinned-theme examples.** Stems in `PINNED_EXAMPLES` (gen_examples.py) keep their OWN
  `theme()` args - the site's darkmode/transparent injection is skipped - for fixed light/dark
  comparisons that bake a `chartFill` background (`darkmode_light`/`darkmode_dark` on the
  theming guide). Chart.astro only passes vega-embed's `background: 'transparent'` when the
  spec does NOT bake its own background (the embed option would override `config.background`).
- **Inward ticks are flipped client-side per chart.** `flipTicksInward` (fixSuperscripts.ts)
  ports `export._flip_ticks_inward`; the rendered spec carries no flag, so the page opts in via
  `<Example inwardTicks />` -> Chart.astro `data-inward`. Only the theming guide's example uses
  it.
- **Superscript exponents are re-typeset client-side.** The library's `_fix_superscript_labels`
  runs only in `save()`, never in the browser - so live charts rendered mixed-metric Unicode
  superscripts (`P = 5.03×10⁻¹⁷`). `src/lib/fixSuperscripts.ts` ports the fixer to the rendered
  SVG DOM (raised/shrunk ASCII tspan, same ratios); Chart.astro and the Studio call it after
  every vegaEmbed. Only text nodes are touched - aria-label attributes keep the original string.
- **Chart size.** Charts are authored at dysonsphere's publication defaults (100x100 px, small
  fonts/marks); scale them for the web with CSS `zoom` on `.vega-embed .chart-wrapper` (tune
  `--ds-chart-zoom` in theme.css). Do NOT zoom `.vega-embed` (that scales the export menu too) or
  the `<svg>` (zoom does not apply to `<svg>`). The chart SVG lives in `.chart-wrapper`; the menu is
  a sibling `<details>`.
- **Export menu** is hover/focus-only (opacity in theme.css, `!important` since vega-embed injects
  its own styles at runtime). The menu still exports the true, unscaled 100x100 spec.
- **Dark mode.** Each chart ships light + dark specs (`darkmode=False/True`, `transparent=True`);
  `Chart.astro` swaps on the site theme toggle (MutationObserver on `data-theme`) and renders with
  vega-embed `background:'transparent'` so the page provides contrast (no card background). The
  **Studio** re-renders on the same toggle (both builder and code modes), so its live chart inverts
  ink too - the previously-broken darkmode.
- **v3 theme-option rename.** The chart's logical-transparency flag is `transparent` (v3.0.0);
  the old `transparentBackground` was removed. `runtime.ts` and `gen_examples.py` set `transparent`.
- **Keep render args out of shown code.** darkmode/transparent/zoom are website concerns; only the
  chart-building code appears in snippets, so they stay copy-runnable.
- **Wide surfaces / persistent sidebar.** The landing page and the Studio widen the content column
  via `.main-pane:has(.landing/.st) { --sl-content-width }` in theme.css. The sidebar shows on
  EVERY page (landing uses the default docs template, not `splash`) and has a desktop collapse
  toggle (`Sidebar.astro` + `[data-ds-sidebar='collapsed']` in theme.css, persisted in
  localStorage).
- **Stale Expressive Code assets after styleOverrides changes.** The `.md` reference pages'
  rendered HTML is cached by Astro's content layer WITH the EC stylesheet link baked in; changing
  `expressiveCode.styleOverrides` renames the hashed `ec.*.css` asset and the cached pages keep
  linking the old (now 404) one - those pages then render with NO token colors and a collapsed
  16x6px copy button. Fix: `rm -rf .astro node_modules/.astro` and rebuild after any EC config
  change.
- **Reference signatures render as `def` statements** (`def name(...) -> X: ...`) - a bare
  call-style signature is almost all plain identifiers and highlights near-monochrome.
  `gen_api.py` writes extension pages (volcano) into `extensions/`, NOT `reference/` - the
  autogenerated Documentation sidebar group is core-only; extension API pages nest under their
  extension in the sidebar config.
- **Pages that embed a chart must be `.mdx`** (to `import Chart`). Generated API pages are `.md`,
  NOT `.mdx` - docstrings contain `{}`/`<>` that MDX parses as JSX and chokes on.
- **Quote frontmatter** `title`/`description` values - a colon in the text breaks the YAML parser.
- **Base-path discipline (project-pages deploy).** Astro/Starlight do NOT rewrite root-relative
  CONTENT links under a `base`; a `remarkBaseLinks` plugin in astro.config.mjs prefixes markdown
  `[text](/guides/...)` links at build time - keep writing them base-free. It CANNOT reach
  frontmatter (hero `link:`) or raw JSX anchors (`<a href>`): write those RELATIVE (the landing
  page's `guides/getting-started/`) or via `import.meta.env.BASE_URL` in components. Verify with
  the deploy-equivalent build + `grep -r 'href="/' dist | grep -v /dysonsphere`.
- **`.gitignore`.** The repo root ignores `*.json`; the site's JSON is kept via `!website/**/*.json`.
- vega-embed is bundled (npm); Pyodide loads from the CDN (v314.x). The CodeMirror editor uses the
  GitHub theme to match Starlight's Expressive Code docs code blocks.

## Logo

`logo/gen_dysonsphere_logo.py` generates the whole logo family (run:
`uv run --no-project --with fonttools python website/logo/gen_dysonsphere_logo.py`). The panel count,
tilt, palette range, colors, and font are parameters at the top of the generator.

- `logo/dysonsphere_logo.svg` - the **mark** (no text): a sphere of flat panels shaded across the
  MID of the **australis** palette (since 2026-07-11; was blues2) - the star-lit side emerald,
  falling through cobalt into deep violet shadow - with a bright **star glowing inside the shell**
  (a radial gradient - white-hot -> light yellow -> soft cyan -> turquoise - showing through the
  panel gaps, plus a turquoise corona; vivid on dark, a soft luminosity on light). A single
  dual-mode logo - the mid range skips near-white (vanishes on light) and near-black (vanishes on
  dark), so one transparent SVG works on both backgrounds (no light/dark variants). This is the
  file the site uses (copied to `src/assets/`; the favicon copy lives at `public/favicon.svg`;
  the README/PyPI copy lives at repo-root `docs/logo.svg`, referenced by absolute raw URL from
  the released README - re-copy ALL THREE after regenerating). The mark file carries its own
  TIGHT square viewBox centered on sphere + corona (`mark_viewbox()`; the portrait canvas would
  leave the wordmark's dead band below and clip the corona top - the sphere sat off-center
  when sized by height, e.g. the site header).
- `logo/dysonsphere_logo_portrait_with_text.svg` - mark + wordmark as live `<text>` (Graphik Light,
  two-tone: dyson = `#1374BA`, sphere = `#48DEB3` - australis stops; SiteTitle.astro's `.ds`/`.sp`
  colors must match). For editing / where Graphik is installed.
- `logo/dysonsphere_logo_portrait_with_text_outlined.svg` - the same lockup with the wordmark
  **outlined to `<path>`** (glyphs baked via fonttools; Graphik = face 6 in the system `Graphik.ttc`),
  so it's font-independent. Use this wherever a self-contained lockup is needed.
- `logo/double-dysonsphere/` - the user's archive of the superseded hand-drawn logo (gitignored).

The wordmark is one continuous `<text>` (two colors via an inline `<tspan>`), centered on the panel
group's exact horizontal extent (`x=100.0000`, computed from the panel vertices, not assumed).

**Site wiring:** header and homepage hero both use the **mark**; the wordmark on the site is real
page text - the header title (via the `SiteTitle` override, two-toned to match) and the homepage
`<h1>`. So there is no Graphik dependency on the live site. `logo: { replacesTitle: false }` so the
mark shows alongside the title.

**Verifying a logo SVG:** rasterize with `qlmanage -t -s 460 -o <outdir> <file>.svg` (macOS Quick
Look = the same engine as Preview) and view the PNG; the SVGs are transparent, so inject a `<rect>`
background to check them on light/dark. Do this in `/tmp` and delete the scratch when done.

## Working notes (living - update as we go)

- Verify with `npm run build` (fastest correctness gate) plus a running `npm run dev` for eyeballing.
  Routes, specs, and HTML can be checked with `curl`, but the actual chart render, Pyodide boot, and
  light/dark toggle are BROWSER-ONLY - the user confirms those.
- Regenerate specs/API when the underlying source changes.
- Commit per coherent chunk. The site lives on the `website` branch and reaches `main` via PR.
- **Multi-session safety.** The dedicated worktree was dissolved 2026-07-06 (site now develops on
  the `website` branch in the main repo). If parallel sessions return, recreate one
  (`git worktree add ../dysonsphere-website website`) - a second session once yanked HEAD.

## Status (living)

Done: neutral-pro skin (greys-ramp chrome, desaturated blues2 accent, Inter/JetBrains Mono);
redesigned landing (beeswarm + condition-table hero, no legend; feature cards; **sidebar shows on
the landing page** via the default docs template); the example registry (`examples/*.py` +
`Example.astro` + snippet-executing `gen_examples.py`, ~44 examples) with per-example "Open in
studio" deep links; the shared Pyodide runtime; full guide set (getting-started, theming,
**configuration [dysonsphere.toml]**, palettes w/ live swatch browser, marks & transforms,
annotations [incl. `add_labels`], statistics, nonlinear, saving & reading [with a real
embedded-metadata prose example]); **extensions section** (overview + biology [volcano] +
authoring); the **two-mode Chart Studio** (builder w/ statistics + multilabel + annotations,
AND an embedded code editor - the Playground was absorbed; `/playground/` redirects); griffe API
reference (v3 modules, multi-line signatures for wide APIs, ext/discovery/volcano pages);
persistent collapsible sidebar; "References" renamed "Documentation".

Rework done 2026-07-06 (v3.0.0 pass): regenerated all artifacts against v3.0.0; fixed the x-axis
tick/xOffset misalignment (dropped `scale=None`); fixed the correlation examples' `_x` axis-title
leak (explicit base title); Studio darkmode re-render + cursor-alignment fix (fonts.ready
remeasure); Ember swatch alignment (`not-content`); larger flush inline charts (zoom 3.5). All
verified in a real headless-chromium sweep (charts render on every new page, darkmode inverts the
hero ink, sidebar+toggle on landing, deep-link redirect preserves `#code=`).

Batch 2026-07-07 (post-PR-#64-open, same branch): guides reordered per user (getting started ->
theming/config/palettes -> marks -> annotations/stats -> multilabels [SPLIT out of annotations
into guides/multilabels.mdx] -> nonlinear -> saving); reference alphabetized; homepage hero is a
cars weight-vs-horsepower scatter (blues2, color=y, add_correlation fit); examples use polars
idioms (ensure_polars + drop_nulls, never pandas dropna); beeswarm examples switched to the
continuous Acceleration column + 50/group subsample (integer-tied MPG made arm artifacts);
shade examples use blues[0]; dependencies documented in getting-started + reference index;
authoring headings de-numbered; config generator cheat sheet height-locked to the editor panel
(height:0/min-height:100% grid trick) with internal scroll; studio gains sample datasets +
text/shade-range annotations + 2-column controls; sidebar toggle enlarged/bordered.

Rework done 2026-07-06/07 (v3.1.0 pass, `website` worktree): regenerated artifacts against v3.1.0
(API ref gains `ext.tag_extension`; saving guide's metadata example recaptured - new provenance
order, os/vl-convert env fields, extensions note). Example fixes verified in browser Vega: log
axes get explicit decade `values=` (browser Vega auto-ticks every log multiple FULL length -
that's the main axis, not the minor layer; vl-convert differs), comparisons categories now
alphabetical (the layer scale-merge renders alphabetical band order; pixel-anchored p-labels used
the passed order - mislabeled brackets), omnibus corner labels need a PADDED y domain + `yStart`
(the auto domain hugs the top bracket, so the pixel-anchored corner label always collides),
correlation readouts sized to their chartWidth. New beeswarm+brackets homepage hero (caption
dropped, zoom 2.6). "Condition tables" renamed "multilabels" sitewide (library docstring still
says condition table - core-side edit, not done). Sidebar toggle moved into the header next to
the wordmark (Sidebar override deleted); docs reordered build->style->export; Open-in-studio
links hover-only. The palette browser + live preview (four charts - bars/scatter/lines/heatmap - restyled
on swatch click via client-side config.range patching, each AUTO-FIT to the aside column with a
per-render --ds-chart-zoom (a shared zoom leaves narrow charts small); `ds-palette-select` CustomEvent from Palettes.astro) live on their own
`/palettes/` page under Interactive (swatch list = main column, preview charts in a STICKY
aside so they stay visible while scrolling the 300+ palettes; stacks on narrow screens); the
guide links to it. Studio
gains "Import an export" (ds.load rebuild + ds.read metadata panel) and the Pyodide boot fix (see
the deps=False gotcha above). All verified headless (incl. a full Pyodide boot + JSON/PNG import
round-trip) plus the deploy-equivalent base-path grep.

Deploy wiring (since 2026-07-11): pages.yml regenerates ALL site inputs from the checked-out
library (uv + the four gen_*.py scripts) before the Astro build, then deploys `website/dist` to
Pages on every push to main - the live site cannot drift from the code. Committed artifacts
remain for local dev only. Studio still installs dysonsphere from PyPI at runtime, so LIVE
studio execution of new APIs waits on a release even though the docs/specs are already current.

TODO: molecular-biology gallery (synthetic gene-expression / dose-response / qPCR datasets);
publish `dysonsphere-biology` to PyPI so LIVE studio execution of
`ds.biology.*` works (its committed specs already render). The `guides/saving.mdx` metadata JSON
is a real capture, accurate for v3.5.0 (adds `provenance.chart`; snippet saves
`strip + mpg_comparisons`).

# Website (dysonsphere docs site)

An Astro + Starlight docs site for dysonsphere, built by two Python generators plus Astro. Lives
in `website/`; developed on the `website` branch, in a git worktree (see Working notes).

## Layout

- `src/content/docs/` - pages: `index.mdx` (home), `guides/*` (getting-started + feature guides),
  `gallery.mdx`, `playground.mdx`, `reference/*` (generated API).
- `src/components/` - `Chart.astro` (live vega-embed chart, light/dark reactive),
  `Playground.astro` (Pyodide runtime + CodeMirror editor), and `SiteTitle.astro` (Starlight
  override that two-tones the header wordmark to match the logo).
- `src/styles/theme.css` - blues2 accent (from `ds.colors`), chart zoom, hover-only export menu.
- `scripts/` - `gen_api.py`, `gen_examples.py`.
- `logo/` - the logo family + its generator (see the Logo section).
- `public/charts/` - generated Vega-Lite specs (`<name>-light.json` / `<name>-dark.json`).
- `astro.config.mjs` - Starlight config + sidebar.

## Commands

- Dev server: `npm run dev` (it daemonizes; manage with `astro dev stop` / `status` / `logs`).
- Build: `npm run build`.
- npm 11 blocks install scripts: after `npm install`, run
  `npm approve-scripts esbuild sharp && npm rebuild esbuild sharp`.
- Regenerate the API reference: `uv run --no-project --with griffe python website/scripts/gen_api.py`.
- Regenerate the example charts: `uv run --with vega-datasets python website/scripts/gen_examples.py`.
- Generated files (`reference/*.md`, `charts/*.json`) are committed for now; CI regeneration is a
  deploy TODO.

## Conventions and gotchas

- **Chart size.** Charts are authored at dysonsphere's publication defaults (100x100 px, small
  fonts/marks); scale them for the web with CSS `zoom` on `.vega-embed .chart-wrapper` (tune
  `--ds-chart-zoom` in theme.css). Do NOT zoom `.vega-embed` (that scales the export menu too) or
  the `<svg>` (zoom does not apply to `<svg>`). The chart SVG lives in `.chart-wrapper`; the menu is
  a sibling `<details>`.
- **Export menu** is hover/focus-only (opacity in theme.css, `!important` since vega-embed injects
  its own styles at runtime). The menu still exports the true, unscaled 100x100 spec.
- **Dark mode.** Each chart ships light + dark specs (`darkmode=False/True`, `transparentBackground=True`);
  `Chart.astro` swaps on the site theme toggle (MutationObserver on `data-theme`) and renders with
  vega-embed `background:'transparent'` so the page provides contrast (no card background).
- **Playground** builds its spec at runtime, so it injects `alt.theme.options["darkmode"]` /
  `["transparentBackground"]` just before `to_dict()` to match the site theme - kept OUT of the
  user's shown snippet.
- **Keep render args out of shown code.** darkmode/transparent/zoom are website concerns; only the
  chart-building code appears in snippets, so they stay copy-runnable.
- **Pages that embed a chart must be `.mdx`** (to `import Chart`). Generated API pages are `.md`,
  NOT `.mdx` - docstrings contain `{}`/`<>` that MDX parses as JSX and chokes on.
- **Quote frontmatter** `title`/`description` values - a colon in the text breaks the YAML parser.
- **`.gitignore`.** The repo root ignores `*.json`; the site's JSON is kept via `!website/**/*.json`.
- vega-embed is bundled (npm); Pyodide loads from the CDN (v314.x). The CodeMirror editor uses the
  GitHub theme to match Starlight's Expressive Code docs code blocks.

## Logo

`logo/gen_dysonsphere_logo.py` generates the whole logo family (run:
`uv run --no-project --with fonttools python website/logo/gen_dysonsphere_logo.py`). The panel count,
tilt, palette range, colors, and font are parameters at the top of the generator.

- `logo/dysonsphere_logo.svg` - the **mark** (no text): a sphere of flat panels shaded across the
  MID of blues2. A single dual-mode logo - the mid range skips near-white (vanishes on light) and
  near-black (vanishes on dark), so one transparent SVG works on both backgrounds (no light/dark
  variants). This is the file the site uses.
- `logo/dysonsphere_logo_portrait_with_text.svg` - mark + wordmark as live `<text>` (Graphik Light,
  two-tone: dyson = blues2[6], sphere = blues2[2]). For editing / where Graphik is installed.
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
- **Multi-session safety.** Develop the site in a dedicated worktree
  (`git worktree add ../dysonsphere-website website`) so a second Claude session working elsewhere
  in the same repo can't yank HEAD out from under you (this happened once).

## Status (living)

Done: scaffold + blues2 theming + dark mode; griffe API reference; live gallery (vega-datasets);
playground island (Pyodide + CodeMirror/GitHub editor); dark-reactive transparent charts; feature
guides (theming, marks, statistics, nonlinear); chart display polish (zoom + hover menu); the logo
(see the Logo section), wired into the header + homepage.

TODO: finer theming; more guides (saving/reading, palettes, condition tables, transforms); deploy
(`site`/`base` + a GitHub Actions workflow running the generators, and switching Pages off the old
`docs/` gallery).

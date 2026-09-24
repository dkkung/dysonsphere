# Dysonsphere agent skill

The [`dysonsphere` skill](dysonsphere/SKILL.md) helps coding agents create, refine, and troubleshoot
scientific figures using core Dysonsphere and Altair. It has focused references for plotting,
statistics, exports, nonlinear axes, and chart utilities. Optional biology extensions are not covered.

The bundle uses the [Agent Skills format](https://agentskills.io/specification). The same skill
supports Claude Code, Codex, OpenCode, and Pi; it needs no harness-specific permissions, plugins, or
extensions. Pi instructions document format and discovery compatibility, not a completed behavioral
evaluation or activated installation. The skill provides guidance, not a Python environment or a
guarantee that an agent will follow it or choose an appropriate analysis.

## Compatibility and availability

This skill targets **Dysonsphere 4.0.0**, with Python 3.11+ and Altair 6. Its optional frontmatter
metadata records the library target as `dysonsphere: "4.0.0"`, not a separate skill version.
Compatibility information is advisory: harnesses do not install or enforce that library version.
Check installed signatures and docstrings when using a different release.

The skill is maintained here, not installed by the Python package. Installing it does not install
Dysonsphere, and installing Dysonsphere does not activate the skill. There is no Python export
helper or custom Dysonsphere installer CLI.

## Install from a checkout

Start with a **project-local** installation in your analysis project. The third-party
[`skills` CLI](https://github.com/vercel-labs/skills) can copy the skill for Pi:

```sh
npx skills add "/path/to/dysonsphere/skills/dysonsphere" \
  --skill dysonsphere --agent pi --copy
```

Replace the example path with the path to this checkout. To install for Claude Code, Codex, and
OpenCode with that CLI:

```sh
npx skills add "/path/to/dysonsphere/skills/dysonsphere" --skill dysonsphere \
  --agent claude-code codex opencode --copy
```

The CLI is optional and requires Node tooling. Review the destination and existing skills before
confirming an installation or update. Install this skill in one location per harness; duplicate
copies with the same skill name can cause discovery conflicts.

### Manual installation

Copy the **entire** `skills/dysonsphere/` directory, including `references/`, to the destination.
Do not copy only `SKILL.md` or overwrite an existing skill blindly.

| Harness | Project destination | Global destination |
| --- | --- | --- |
| Claude Code | `.claude/skills/dysonsphere/` | `~/.claude/skills/dysonsphere/` |
| Codex | `.agents/skills/dysonsphere/` | `~/.agents/skills/dysonsphere/` |
| OpenCode | `.opencode/skills/dysonsphere/` | `~/.config/opencode/skills/dysonsphere/` |
| Pi | `.pi/skills/dysonsphere/` or `.agents/skills/dysonsphere/` | `~/.pi/agent/skills/dysonsphere/` or `~/.agents/skills/dysonsphere/` |

OpenCode also discovers project skills in `.agents/skills/` and `.claude/skills/`; the CLI may
select a shared location instead of `.opencode/skills/`.

For Pi, `.pi/skills/` and `.agents/skills/` project discovery requires the project to be trusted.
Pi's default global skill directories are `~/.pi/agent/skills/` and `~/.agents/skills/`. To use a
custom directory, add its path to the `skills` array in the appropriate Pi `settings.json`:
`.pi/settings.json` for a project or `~/.pi/agent/settings.json` globally. Paths in these arrays
may be files or directories.

This repository's root `skills/` directory is a distribution source, not a standard Pi project skill
directory. Pi can discover a package's conventional `skills/` directory when that package is loaded,
but this checkout does not declare itself as a Pi package. No Pi package metadata is needed to copy
or load this skill.

## Use in Pi

Start Pi from the analysis project after installing the skill. It may select the skill from its
description when relevant; to load it explicitly in an interactive session, use:

```text
/skill:dysonsphere
```

Pi enables skill commands by default (`enableSkillCommands: true`). Use `/reload` after copying a
skill into a discovered directory to rescan skills in the current session. Restart Pi if the skill
or updated settings are not reflected.

For a single run without copying files or changing settings, pass the skill directory to Pi:

```sh
pi --skill "/path/to/dysonsphere/skills/dysonsphere"
```

`--skill` accepts a file or directory, can be repeated, and still loads explicit paths when
discovery is disabled with `--no-skills`. Pi loads the skill instructions; Python execution,
Dysonsphere, Altair, and image inspection still depend on the analysis environment and available
tools. Discovery and command behavior can vary with Pi settings and trust decisions.

### Other harnesses

| Harness | Invocation |
| --- | --- |
| Claude Code | `/dysonsphere` |
| Codex | `$dysonsphere` |
| OpenCode | Ask OpenCode to load `dysonsphere`. |

Restart the harness if it does not discover the skill after installation. Exact automatic
discovery and invocation behavior depends on the harness.

## Maintenance and verification

Keep workflow instructions in `dysonsphere/SKILL.md` and implementation-sensitive patterns in its
references. Update them alongside relevant API changes, using actual source, docstrings, and tests
rather than assuming every intended contract in a root `API.md` is implemented. The installed
bundle must remain useful without that file or any other source-checkout files.

Each fenced Python example is standalone and begins with a unique `# example: name` marker.
Update the inventory and artifact assertions in `tests/test_skills.py` when adding examples.
Examples omit `format` and `ppi`, preserving the library's built-in SVG + JSON deliverables and
default raster quality if PNG is requested separately. They do not add PNG solely for inspection.

```sh
uv run pytest tests/test_skills.py
```

These tests copy the skill directory to temporary storage, check its controlled frontmatter and
internal links, and execute the actual examples to produce SVG and JSON. They assert the exact
default deliverable set before rasterizing the corrected SVGs into a separate temporary inspection
directory. Those PNG previews use the default density from `ds.save()` and an appropriate background
for inspection, without changing the delivered SVGs. They are test artifacts, not extra example
deliverables. The tests check statistical records, specification checksums, and light/dark behavior.
The panel example also checks compiled scale domains, rendered tick alignment, endpoint counts,
summary semantics, and visible explanatory text. A regression exposes ineffective parent-only
domains on strip charts so guidance cannot silently assume those settings worked. These checks do
not test a model's skill selection or prove that all its generated figures are good.

Run the [behavioral evaluation](EVALUATION.md) separately in each target harness, comparing runs
with and without the skill. Visually inspect rendered outputs at default export quality. Keep
installation checks, executable-example tests, and behavioral results distinct when reporting
support.

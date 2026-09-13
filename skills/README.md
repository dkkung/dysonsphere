# Dysonsphere agent skill

[The `dysonsphere` skill](dysonsphere/SKILL.md) helps coding agents create, refine, and troubleshoot
scientific figures using core Dysonsphere and Altair. It includes focused plotting, statistics, and
export references, with five executable examples. Optional biology extensions are not covered.

The bundle uses the [Agent Skills format](https://agentskills.io/specification). One canonical
directory serves Claude Code, Codex, and OpenCode; no harness-specific permissions, plugins, or
subagent configuration are required. Installing a skill supplies guidance, not a guarantee that
an agent will follow it or choose a statistically appropriate analysis.

## Compatibility and availability

This skill targets **Dysonsphere 4.0.0**, with Python 3.11+ and Altair 6. Its optional frontmatter
metadata records the library target as `dysonsphere: "4.0.0"`, not a separate skill version.
Compatibility information is advisory: harnesses do not install or enforce that library version.
Check installed signatures and docstrings when using a different release.

The skill is maintained here, not installed by the Python package. Installing it does not install
Dysonsphere, and installing Dysonsphere does not activate the skill. There is no Python export
helper or custom Dysonsphere installer CLI.

## Install from a checkout

From your **analysis project's directory**, point the third-party
[`skills` CLI](https://github.com/vercel-labs/skills) at a checkout containing this folder:

```sh
npx skills add "/path/to/dysonsphere/skills/dysonsphere" --skill dysonsphere
```

Replace the example path with the actual path to this checkout. The CLI prompts for the target
agents and installation method. To select the three supported targets and copy the files:

```sh
npx skills add "/path/to/dysonsphere/skills/dysonsphere" --skill dysonsphere \
  --agent claude-code codex opencode --copy
```

Project-local installation is the recommended starting point. Add `--global` only if you want the
guidance available across projects, potentially with different Dysonsphere versions. Review the
destination and any existing skill before confirming an installation or update. Avoid duplicate
copies of the same skill at several discovery locations.

The CLI is optional and requires Node tooling. Its telemetry and security-audit requests can be
disabled with `DISABLE_TELEMETRY=1`; consult its documentation for current behavior.

### Manual installation

Copy the **entire** `skills/dysonsphere/` directory, including `references/`, into one of these
project locations. Do not copy only `SKILL.md`, and do not overwrite an existing skill blindly.

| Harness | Manual project destination |
| --- | --- |
| Claude Code | `.claude/skills/dysonsphere/` |
| Codex | `.agents/skills/dysonsphere/` |
| OpenCode | `.opencode/skills/dysonsphere/` |

OpenCode also discovers `.agents/skills/` and `.claude/skills/`; the CLI may use a shared location
instead of its native directory. This repository's `skills/` folder is the distribution source,
not a request to install the user-facing skill into the library development checkout.

Restart OpenCode after installing or changing a skill. If Claude Code or Codex does not discover
the skill, restart that harness too. Explicitly invoke it with `/dysonsphere` in Claude Code,
`$dysonsphere` in Codex, or ask OpenCode to load the `dysonsphere` skill. It can also be selected
automatically from its description; exact discovery and invocation behavior is harness-dependent.

### Remote distribution

The CLI can install from a published GitHub skill directory URL; no separate repository is needed.
Use a branch or release tag whose skill matches the library API in your project. A generic
`dkkung/dysonsphere` source selects the default branch and requires this skill to be present there.
Until the bundle is published, use a checkout containing it. A local draft is not a registry listing.

## Maintenance and verification

Keep workflow instructions in `dysonsphere/SKILL.md` and implementation-sensitive patterns in its
references. Update them alongside relevant API changes, using actual source, docstrings, and tests
rather than assuming every intended contract in the root `API.md` is implemented. The installed
bundle must remain useful without that root file or any other source-checkout files.

Each fenced Python example is standalone and begins with a unique `# example: name` marker.
Update the inventory and artifact assertions in `tests/test_skills.py` when adding examples.
Examples omit `format` and `ppi`, preserving the library's built-in SVG + JSON deliverables and
default raster quality if PNG is requested separately. They do not add PNG solely for inspection.

```sh
uv run pytest tests/test_skills.py
```

These tests copy just the skill directory to temporary storage, check its controlled frontmatter
and internal links, and execute the actual examples to produce SVG and JSON. They assert the exact
default deliverable set before rasterizing the corrected SVGs into a separate temporary inspection
directory. Those PNG previews use the default density from `ds.save()` and an appropriate background
for inspection, without changing the delivered SVGs. They are test artifacts, not extra example
deliverables. The tests check statistical records, specification checksums, and light/dark behavior. The panel example
also checks compiled scale domains, rendered tick alignment, endpoint counts, summary semantics,
and visible explanatory text. A regression exposes ineffective parent-only domains on strip charts
so guidance cannot silently assume those settings worked. These checks do not test a model's skill
selection or prove that all its generated figures are good.

Run the [behavioral evaluation](EVALUATION.md) separately in each target harness, comparing runs
with and without the skill. Visually inspect rendered outputs at default export quality. Keep
installation checks, executable-example tests, and behavioral results distinct when reporting support.

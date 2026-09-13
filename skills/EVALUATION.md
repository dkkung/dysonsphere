# Behavioral evaluation

This is a repeatable evaluation protocol, not a record of completed harness evaluations. It stays
outside the installed skill so agents do not receive the evaluator's expected answers.

## Setup

- Use disposable analysis projects outside the Dysonsphere repository, with the same supported
  Python environment, input files, and starting scripts for both conditions. Repository contributor
  instructions should not accidentally supply the baseline with the skill's guidance.
- Compare fresh sessions with and without this skill, using the same harness/model/settings and
  available tools. Use disposable harness profiles to isolate global skills; do not modify real
  user-wide installations just to obtain a baseline.
- Record the harness/model, library versions, skill revision, invocation mode, permissions, and
  availability of Python execution and image inspection. Keep private data out of fixtures.
- Test automatic discovery first with the prompts below. If activation fails, repeat with explicit
  invocation and record the distinction. Installation success alone is not activation success.
- Evaluate behavior and figure correctness, not exact wording or pixel identity. Repeat important
  failures to distinguish a systematic gap from model variability. Do not claim improvement from
  one favorable example; record the baseline failures that the skill actually changes.

## Cases

### 1. A simple figure should stay simple

Supply a CSV with columns `input,response` and rows `(1,1.3), (2,1.8), (3,3.4), (4,3.6), (5,5.2), (6,5.7)`.

Prompt: "Use Dysonsphere to plot response against input. Both are in arbitrary units. Save a PNG
and SVG plus a reusable script. These are independent observations; no statistical analysis is needed."

Pass: all six observations, correct mappings/units, no unsolicited fit/test, requested formats,
default raster density, executable source, and actual rendered inspection when available. No
unnecessary package upgrade or request for the user to choose routine cosmetic settings.

### 2. A cosmetic edit should preserve the analysis

Supply an existing Altair script with a documented filter, a categorical color domain, and a legend.
Keep an untouched copy for comparison.

Prompt: "Use Dysonsphere styling and put the legend below this chart. Do not change the analysis."

Pass: preserves rows, filter, mappings, category-to-color association, and script structure while
making the requested presentation change. Run before/after and compare the analytical content.

### 3. Ambiguous pairing should trigger a focused question

Supply two groups with equal row counts and no subject identifier or experimental-design notes.

Prompt: "Use Dysonsphere to show these groups and add a statistical comparison."

Pass: does not infer pairing or independence from row count/order, or silently select the default
test. Asks about observational unit/design; may produce a clearly descriptive plot while waiting.
For a follow-up, state that the rows are independent samples and provide a justified analysis plan.

### 4. Missing values should not disappear silently

Use case 1's CSV but leave one response blank.

Prompt: "Make a Dysonsphere scatterplot and add a Pearson correlation with its confidence band."

Pass: detects the missing value before claiming a six-observation correlation; explains its impact
and proposes explicit handling rather than substituting zero or silently filtering one layer.
If exclusion is authorized, both plotted and tested data use the agreed subset and counts are reported.

### 5. Light and dark should both be deliverable

Use case 1's complete CSV.

Prompt: "Create a Dysonsphere scatterplot using the named blue accent. Save light and dark PNG/SVG
versions on opaque backgrounds, with reusable code."

Pass: uses a callable with the accent lookup inside it, preserves default raster density, produces
the correct variant filenames, and inspects both actual backgrounds. No theme reset inside the builder
and no lambda that merely returns one prebuilt chart. Check that captured accent colors differ.

### 6. The requested library should be respected

Use case 1's complete CSV and an existing Matplotlib project with its dependencies already installed.

Prompt: "Make this scatterplot with Matplotlib. Keep using this project's plotting stack."

Pass: does not migrate to Dysonsphere, install it, or use its export functions. A harness may expose
the skill's description, but that should not override the user's explicit library choice.

### 7. Unavailable tools should produce an honest handoff

Repeat case 1 with Python execution unavailable, then in a separate session with execution allowed
but image inspection unavailable.

Pass: distinguishes unexecuted code from a rendered-but-not-visually-inspected figure. No fabricated
file paths or claims that code ran, images were viewed, or the figure is publication-ready.

### 8. Irrelevant columns should not block a valid analysis

Use case 1's complete CSV with an additional `notes` column containing blank values.

Prompt: "Make a Dysonsphere scatterplot of response against input, in arbitrary units. Keep a reusable script."

Pass: uses all six observations without rejecting the extra column, dropping rows because their
notes are blank, or demanding an exact input-column set. Validation focuses on the actual plotted
columns. The original input is preserved; selecting export columns for privacy is a separate decision.
With built-in theme settings and no requested formats, the deliverables are SVG + JSON. A PNG needed
only for inspection belongs in a separate temporary location, not in the default deliverable set.
Cases 1 and 5 separately check that explicitly requested PNG output is still provided at default quality.

### 9. Matching panel scales must survive rendering

Use only the synthetic dataframe from the skill's `panels` example as the input fixture, not its
plotting code. It contains 16 specimens, eight per formulation and four per formulation at 3 mN.

Prompt: "Use Dysonsphere to make two equally tall panels: extension versus load, and the 3 mN
measurements with individual points and mean plus sample SD. Use 0 to 5 mm on both extension axes.
Keep Reference before Modified. Explain the endpoint subset and summary in the figure or a caption."

Pass: correct subset/counts/summary; actual domains `[0,5]`, equal scale ranges and matching padding;
at least two common y ticks align after rendering, including a nonzero tick. The figure or delivered
caption explains 3 mN and mean/SD. A parent domain argument, an untested scale-sharing call, or a claim
that axes match is not evidence. Inspect saved JSON compiled to Vega when resolving a discrepancy.
Do not require a particular constructor if another supported implementation meets these invariants.

## Record outcomes

For each run, record activation, analytical fidelity, code execution, visual correctness, default
export quality, unnecessary edits/questions, and handoff accuracy. Mark unavailable checks explicitly
rather than counting them as passes. Retain generated code, rendered outputs, and a short failure
description so changes to the skill can be evaluated against the same task.

Independently check key requirements rather than trusting the agent's self-report. A passing JSON
checksum does not establish correct scales or statistical interpretation. Preserve submitted outputs
before asking for corrections, and distinguish the first result from a repaired one. After revising
the skill, a fresh-session rerun can test whether guidance transfers without hints from the failed run.
Keep published protocol separate from local experiment transcripts and artifacts; do not report one
successful rerun as broad evidence of improved reliability.

A skill revision is useful when it reduces consequential errors without increasing unnecessary
intervention. Correct misleading guidance first; add instructions only for recurring gaps. Do not
grow the skill to encode one model's incidental formatting preferences.

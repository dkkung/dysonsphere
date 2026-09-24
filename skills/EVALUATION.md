# Behavioral evaluation

This is a repeatable evaluation protocol, not a record of completed harness evaluations. It stays
outside the installed skill so agents do not receive the expected answers.

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
- For Pi, record its installed version and test activation in a disposable project only. Copy the
  whole skill directory, including `references/`, to `.pi/skills/dysonsphere/`; project discovery
  requires trust. Check `/skill:dysonsphere`, `/reload` after a copy, and a separate one-run
  `pi --skill <path>` load. If testing a custom `skills` settings path, record it separately. Do not
  install into a real global or project agent directory. A successful copy or discovery check does
  not establish that Pi followed the advice or produced a correct figure.

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

### 10. Pi discovers and can explicitly load the skill

In a disposable analysis project, copy the complete skill directory to `.pi/skills/dysonsphere/`.
Start Pi in that trusted project, confirm the skill appears as available, and invoke
`/skill:dysonsphere`. In a separate run, load it with `pi --skill <path>` from the checkout. After
changing files in the discovered directory, use `/reload` and check that Pi sees the updated skill.

Pass: the tested Pi version discovers the project skill after trust or loads the explicit directory,
its interactive skill command loads the guidance, and the reload check detects the changed skill.
Report project discovery, explicit loading, command invocation, and reload separately. Do not count
package installation, the appearance of a skill description, or a model's unverified claim as proof
that it read the full instructions. Do not treat a failure to discover untrusted project resources as
a skill-content failure.

### 11. Nonlinear ticks match the chart scale

Use positive synthetic concentrations `[1, 2, 5, 10, 20, 50, 100]` and corresponding responses
`[1.1, 1.4, 1.8, 2.3, 2.8, 3.4, 4.0]`.

Prompt: "Plot response against concentration on a base-10 log x-axis. Use major ticks at 1, 10,
and 100 with power-notation labels, add the conventional unlabeled minor ticks, and save an editable
figure plus reusable code."

Pass: the x scale is logarithmic with the specified major values, the major labels use `ds.log_label_expr()`,
`ds.add_log_ticks()` is applied with a matching base and field, and the rendered figure shows minor
ticks between decades without adding data marks for those ticks. Report actual execution and visual
inspection separately. Do not accept a chart whose tick positions are just manually overlaid.

### 12. Tabular details should preserve the plotted groups

Use four independent responses per group: Control `[1.0, 1.4, 1.2, 1.6]`, Dose A
`[1.5, 1.7, 1.9, 2.1]`, and Dose B `[2.0, 2.2, 2.3, 2.5]`. The descriptive means are 1.3,
1.8, and 2.25, respectively.

Prompt: "Make a descriptive Dysonsphere strip plot for these three groups. Add a condition row below
the x-axis showing Control as untreated and both doses as treated, plus each group's sample size.
Also render a small table with the group, sample size, and mean response. Do not add a statistical
test. Keep the group order Control, Dose A, Dose B and deliver reusable code."

Pass: all twelve observations and their group assignments remain; the condition row and sample-size
row align with the ordered x categories; the table reports n = 4 and the stated means; no test or
inferential claim is added. Check visible chart and table outputs and compare the computed summaries
to the fixture. Do not treat a correct table as evidence that the plotted data or category alignment
is correct.

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

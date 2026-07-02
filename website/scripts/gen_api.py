#!/usr/bin/env python
"""Generate the API reference pages from dysonsphere's docstrings via griffe.

griffe does static analysis of the source (no import), so this reflects the source tree it is
run against. Run from the repo/worktree root:

    uv run --no-project --with griffe python website/scripts/gen_api.py

It writes one Markdown page per module into website/src/content/docs/reference/, which Starlight
renders as the API reference. Regenerate whenever the public API changes (wired into CI later).
"""

from __future__ import annotations

from pathlib import Path

import griffe
from griffe import ParameterKind

# (module name, page title, sidebar order, one-line description)
MODULES = [
    ("theme", "Theming", 1, "Register the dysonsphere Altair theme and scaffold config files."),
    ("palettes", "Palettes", 2, "Perceptually uniform palettes and Adobe Illustrator swatch export."),
    ("marks", "Marks", 3, "Composite marks: strip and violin plots."),
    ("layers", "Annotations", 4, "Composable annotation layers: rules, text, shading, comparisons, correlation."),
    ("multilabel", "Condition tables", 5, "Attach a condition-table annotation below a chart."),
    ("nonlinear", "Nonlinear axes", 6, "Minor ticks and typeset labels for log and power axes."),
    ("transforms", "Transforms", 7, "Data transforms for jittered and beeswarm x-offsets."),
    ("export", "Saving & loading", 8, "Export charts to files and rebuild them from the Vega-Lite JSON."),
    ("metadata", "Reading exports", 9, "Read embedded metadata, statistics, reports, and data back out of exports."),
    ("statistics", "Statistics", 10, "Statistics report queue management."),
    ("utils", "Utilities", 11, "Shared helpers for DataFrame handling and counts."),
]

OUT = Path("website/src/content/docs/reference")


def public_functions(mod):
    """Public, non-imported functions defined in this module, in source order."""
    fns = []
    for name, obj in mod.members.items():
        if obj.is_alias:  # imported names / __future__ etc. - documented in their home module
            continue
        if obj.kind.value == "function" and not name.startswith("_"):
            fns.append(obj)
    fns.sort(key=lambda f: (f.lineno or 0))
    return fns


def format_signature(func) -> str:
    parts: list[str] = []
    star_added = False
    for p in func.parameters:
        if p.kind is ParameterKind.var_positional:
            parts.append(f"*{p.name}")
            star_added = True
            continue
        if p.kind is ParameterKind.var_keyword:
            parts.append(f"**{p.name}")
            continue
        if p.kind is ParameterKind.keyword_only and not star_added:
            parts.append("*")
            star_added = True
        piece = p.name
        if p.annotation is not None:
            piece += f": {p.annotation}"
        if p.default is not None:
            piece += f" = {p.default}"
        parts.append(piece)
    return f"{func.name}({', '.join(parts)})"


def render_docstring(func) -> list[str]:
    lines: list[str] = []
    if not func.docstring:
        return lines
    for sec in func.docstring.parsed:
        kind = sec.kind.value
        if kind == "text":
            lines += [sec.value, ""]
        elif kind == "parameters":
            lines.append("**Parameters**")
            lines.append("")
            for p in sec.value:
                typ = f" (`{p.annotation}`)" if p.annotation else ""
                desc = " ".join(str(p.description).split())
                lines.append(f"- **`{p.name}`**{typ} - {desc}")
            lines.append("")
        elif kind == "returns":
            lines.append("**Returns**")
            lines.append("")
            for r in sec.value:
                typ = f"`{r.annotation}` - " if r.annotation else ""
                desc = " ".join(str(r.description).split())
                lines.append(f"- {typ}{desc}")
            lines.append("")
        elif kind == "examples":
            lines.append("**Examples**")
            lines.append("")
            for item in sec.value:
                # griffe yields (section-kind, text) tuples; code parts render as python.
                text = item[1] if isinstance(item, tuple) else str(item)
                lines += ["```python", text.strip("\n"), "```", ""]
    return lines


def render_page(mod, title: str, order: int, description: str) -> str:
    fns = public_functions(mod)
    out = [
        "---",
        f'title: "{title}"',
        f'description: "{description}"',
        "sidebar:",
        f"  order: {order}",
        "---",
        "",
        "<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->",
        "",
    ]
    for f in fns:
        out.append(f"## `{f.name}`")
        out.append("")
        out += ["```python", format_signature(f), "```", ""]
        out += render_docstring(f)
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    pkg = griffe.load("dysonsphere", search_paths=["."], docstring_parser="numpy")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, title, order, description in MODULES:
        page = render_page(pkg[name], title, order, description)
        (OUT / f"{name}.md").write_text(page, encoding="utf-8")
        print(f"wrote {OUT / f'{name}.md'}  ({len(public_functions(pkg[name]))} functions)")


if __name__ == "__main__":
    main()

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
    ("annotations", "Annotations", 4, "Composable annotation layers: reference lines, text, shading, point labels."),
    ("inference", "Statistical annotations", 5, "Pairwise/omnibus comparisons and correlation layers."),
    ("multilabel", "Condition tables", 6, "Attach a condition-table annotation below a chart."),
    ("labels", "Display labels", 7, "Map raw data values to display labels on axes, legends, and headers."),
    ("nonlinear", "Nonlinear axes", 8, "Minor ticks and typeset labels for log and power axes."),
    ("transforms", "Transforms", 9, "Data transforms for jittered and beeswarm x-offsets."),
    ("export", "Saving & loading", 10, "Export charts to files and rebuild them from the Vega-Lite JSON."),
    ("metadata", "Reading exports", 11, "Read embedded metadata, statistics, reports, and data back out of exports."),
    ("statistics", "Statistics registry", 12, "Statistics report queue management."),
    ("discovery", "Extensions", 13, "Discover and load installed dysonsphere extensions."),
    ("ext", "Extension authoring", 14, "The stable primitive surface for extension authors (dysonsphere.ext)."),
    ("utils", "Utilities", 15, "Shared helpers: DataFrame handling, counts, band geometry, checksums."),
]

# Extension modules documented from a separate distribution's package (not part of core's
# `dysonsphere`). (griffe package name, submodule, page title, sidebar order, description).
EXTENSION_MODULES = [
    (
        "dysonsphere_biology",
        "volcano",
        "Extension: volcano",
        16,
        "The volcano() chart from the dysonsphere-biology extension.",
    ),
]

# Signatures longer than this render one-parameter-per-line instead of on a single line, so
# wide APIs (theme, add_comparisons, ...) never force horizontal scrolling.
ONE_LINE_LIMIT = 76

OUT = Path("website/src/content/docs/reference")


def public_functions(mod):
    """Public functions of this module, in source order.

    Includes deliberate re-exports (aliases listed in the module's ``__all__``, e.g. the whole
    ``dysonsphere.ext`` surface, which re-exports private core primitives under public names) -
    plain imports are skipped, since they are documented in their home module.
    """
    exports = set(mod.exports or [])
    fns = []
    for name, obj in mod.members.items():
        if name.startswith("_"):
            continue
        if obj.is_alias:
            if name not in exports:
                continue  # an incidental import, not part of this module's API
            try:
                obj = obj.final_target
            except Exception:
                continue
        if obj.kind.value == "function":
            fns.append((name, obj))
    fns.sort(key=lambda pair: (pair[1].lineno or 0))
    return fns


def format_signature(func, name: str) -> str:
    """Render a signature under its public ``name`` (aliases: the export name, not the target's)."""
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
    returns = f" -> {func.returns}" if func.returns is not None else ""
    one_line = f"{name}({', '.join(parts)}){returns}"
    if len(one_line) <= ONE_LINE_LIMIT:
        return one_line
    body = "\n".join(f"    {part}," for part in parts)
    return f"{name}(\n{body}\n){returns}"


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
    # The module docstring introduces the page (ext.py's carries the whole authoring contract).
    if mod.docstring:
        out += [mod.docstring.value.strip(), ""]
    for name, f in fns:
        out.append(f"## `{name}`")
        out.append("")
        out += ["```python", format_signature(f, name), "```", ""]
        out += render_docstring(f)
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    pkg = griffe.load("dysonsphere", search_paths=["."], docstring_parser="numpy")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, title, order, description in MODULES:
        page = render_page(pkg[name], title, order, description)
        (OUT / f"{name}.md").write_text(page, encoding="utf-8")
        print(f"wrote {OUT / f'{name}.md'}  ({len(public_functions(pkg[name]))} functions)")

    # Extension packages live in their own distributions; load each and document one submodule.
    for pkg_name, submodule, title, order, description in EXTENSION_MODULES:
        search = [str(Path("dysonsphere-biology"))] if pkg_name == "dysonsphere_biology" else ["."]
        ext_pkg = griffe.load(pkg_name, search_paths=search, docstring_parser="numpy")
        page = render_page(ext_pkg[submodule], title, order, description)
        (OUT / f"{submodule}.md").write_text(page, encoding="utf-8")
        print(f"wrote {OUT / f'{submodule}.md'}  ({len(public_functions(ext_pkg[submodule]))} functions)")


if __name__ == "__main__":
    main()

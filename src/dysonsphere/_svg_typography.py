"""Private SVG script, scientific typography, and font corrections."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET

from ._svg_geometry import _SVG_NS
from .theme import _opt
from .utils import _SUP

__all__: list[str] = []

# Super/subscript typesetting
#
# Vega renders each label as a flat string. `_typeset_scripts` moves super/subscripts into smaller,
# raised or lowered <tspan> elements. Plain ASCII avoids font substitution for missing Unicode glyphs,
# such as superscript zero in Helvetica Neue.

# Unicode super/subscript -> plain ASCII (the superscript minus becomes the real minus U+2212).
_SUPERSCRIPT_MAP = str.maketrans(_SUP + "⁻", "0123456789−")
_SUBSCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉₋ₐₑₒₓₕₖₗₘₙₚₛₜ", "0123456789-aeoxhklmnpst")

# Run size / shift as a fraction of the base glyph's font-size (2/3 and 5/12 - the original fixed
# 4px / 2.5px expressed against a 6px base), so a run scales to whatever size the label is.
_SCRIPT_SIZE_RATIO = 2 / 3
_SCRIPT_RISE_RATIO = 5 / 12

# Detection specs: (pattern, translate-map-or-None, direction). Each pattern captures the base
# and the run to typeset; author connectors (`^` and `__`) are outside those groups and are dropped.
# Superscript patterns cover Unicode exponents emitted by log labels and p-values, plus the caret
# form used by authors. Subscript patterns cover literal Unicode and the guarded double-underscore
# form. The boundary check prevents ordinary column names such as `x_1`, `model__alpha`, and
# `flipper_length_mm` from being interpreted as notation.
_SUP_UNICODE = re.compile(r"([×≈]\s*10|\d)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)")
_SUP_CARET = re.compile(r"([A-Za-z0-9])\^([A-Za-z0-9]{1,2})")
_SUB_UNICODE = re.compile(r"([A-Za-z0-9])([₀₁₂₃₄₅₆₇₈₉₋ₐₑₒₓₕₖₗₘₙₚₛₜ]+)")
_SUB_DUNDER = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9])__([A-Za-z0-9]{1,2})(?![A-Za-z0-9])")

_ScriptSpec = tuple["re.Pattern[str]", "dict[int, int] | None", str]
_SUP_SPECS: "list[_ScriptSpec]" = [(_SUP_UNICODE, _SUPERSCRIPT_MAP, "raise"), (_SUP_CARET, None, "raise")]
_SUB_SPECS: "list[_ScriptSpec]" = [(_SUB_UNICODE, _SUBSCRIPT_MAP, "lower"), (_SUB_DUNDER, None, "lower")]
_ALL_SCRIPTS: "list[_ScriptSpec]" = _SUP_SPECS + _SUB_SPECS


def _script_font_size(el: ET.Element) -> float:
    """Parse the base glyph's font-size in px; fall back to the theme's fontSize when absent."""
    raw = el.get("font-size")
    if raw:
        try:
            return float(raw.removesuffix("px"))
        except ValueError:
            pass
    return float(_opt("fontSize"))


def _typeset_scripts(root: ET.Element, specs: "list[_ScriptSpec]" = _ALL_SCRIPTS) -> None:
    """Typeset super/subscript runs in every label as shrunk, shifted ASCII <tspan>s.

    Handles, in one pass per element: Unicode superscripts (the misaligned/substituted `10⁰`,
    `×10⁻¹⁴` exponents log_label_expr and p-value labels emit), a `^` superscript author token
    (`q^2`), literal Unicode subscripts (`t₀`), and a `__` subscript author token (`q__x`). Each run
    becomes a <tspan> of plain ASCII, shrunk to `_SCRIPT_SIZE_RATIO` and shifted by `_SCRIPT_RISE_
    RATIO` of the label's own font-size (up for `raise`, down for `lower`) - so nothing depends on a
    Unicode super/sub glyph the font may lack, and the shift scales with the label. `specs` selects
    which detectors run (all four by default; the `_fix_superscript_labels` / `_fix_subscript_labels`
    wrappers pass a subset).

    Operates on element .text values in the parsed tree only, never attribute values (which carry the
    same label text in aria-label/title). Multiple runs in one label - and mixed super/sub - are all
    handled by collecting every match, dropping overlaps, and rebuilding the element once.
    """
    for el in list(root.iter()):
        if el.tag not in (f"{{{_SVG_NS}}}text", f"{{{_SVG_NS}}}tspan"):
            continue
        text = el.text
        if not text:
            continue
        # Gather every match from every spec: (base_start, base_end, run_end, ascii_run, direction).
        spans: list[tuple[int, int, int, str, str]] = []
        for pattern, translate, direction in specs:
            for m in pattern.finditer(text):
                run = m.group(2)
                spans.append(
                    (m.start(1), m.end(1), m.end(2), run.translate(translate) if translate else run, direction)
                )
        if not spans:
            continue
        # Sort by position and drop overlaps (keep the earlier match).
        spans.sort(key=lambda s: s[0])
        kept: list[tuple[int, int, int, str, str]] = []
        last_end = -1
        for span in spans:
            if span[0] >= last_end:
                kept.append(span)
                last_end = span[2]
        # Rebuild once: literal text (incl. each kept base) stays inline, each run becomes a tspan.
        fs = _script_font_size(el)
        size = f"{round(fs * _SCRIPT_SIZE_RATIO, 2):g}"
        existing = list(el)  # any pre-existing children follow el.text in reading order
        for child in existing:
            el.remove(child)
        tspans: list[ET.Element] = []
        cursor = 0
        head = ""
        for i, (_base_start, base_end, run_end, ascii_run, direction) in enumerate(kept):
            literal = text[cursor:base_end]  # preceding text + kept base (drops the ^/__ connector)
            dy = round((-1 if direction == "raise" else 1) * fs * _SCRIPT_RISE_RATIO, 2)
            tspan = ET.Element(f"{{{_SVG_NS}}}tspan")
            tspan.set("dy", f"{dy:g}")
            tspan.set("font-size", size)
            tspan.text = ascii_run
            if i == 0:
                head = literal
            else:
                tspans[-1].tail = literal
            tspans.append(tspan)
            cursor = run_end
        tspans[-1].tail = text[cursor:] or None
        el.text = head
        el.extend(tspans)
        el.extend(existing)


def _fix_superscript_labels(root: ET.Element) -> None:
    """Typeset only superscript runs (Unicode ×10ⁿ / 10ⁿ exponents + the `^` author token)."""
    _typeset_scripts(root, _SUP_SPECS)


def _fix_subscript_labels(root: ET.Element) -> None:
    """Typeset only subscript runs (literal Unicode t₀ + the `__` author token)."""
    _typeset_scripts(root, _SUB_SPECS)


# Single-letter Latin statistical symbols, set in italic by scientific convention; Greek
# symbols (ρ, τ, η², ε², χ²) and multi-letter abbreviations (ns) stay upright and are
# deliberately absent. Matched globally on rendered text - dysonsphere-generated labels
# and user annotations alike - because the typography is correct regardless of who wrote
# the text (same policy as _SUP_LABEL_PATTERN above). Each alternative is anchored to the
# exact context our labels generate, so accidental matches in prose are rare (and
# typographically right when they do occur).
_ITALIC_STAT_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:"
    r"P(?=\s*[=<≈])"  # p-value: P = 0.012 / P < 0.001 / P ≈ 10⁻⁵
    r"|[FHA](?=\()"  # omnibus statistic: F(2, 57) / H(2) / A(2)
    r"|W(?=\s*=)"  # Kendall's W = 0.18
    r"|r(?=²?\s*=)"  # correlation r = / r² =  (the ² digit stays upright)
    r"|n(?=\s*=)"  # sample size: n =
    r"|y(?=\s*=)"  # fit equation: y = 0.84x + 0.27
    r"|t(?=-test)"  # Student's t-test / Paired t-test
    r"|[Pp](?=[ \-]value)"  # p-value / P-value / p value (the p is italic by convention)
    r")"
    r"|(?<=Mann-Whitney )U(?![A-Za-z])"  # Mann-Whitney U test label
    r"|(?<=[\d.])x(?=\s*[+\-−]\s*\d)"  # fit equation slope term: 0.84x + 0.27
)


def _italicize_text_element(el: ET.Element) -> None:
    """Wrap every statistical-symbol match in *el*'s text content in an italic ``<tspan>``.

    Only the string nodes *el* owns are processed - ``el.text`` and each existing child's
    ``tail``, in document order - so symbols survive in text the superscript fixer has
    already split around an exponent ``<tspan>``. A child's own ``.text`` is NOT touched
    here: every ``<tspan>`` is itself a target of :func:`_italicize_stat_symbols` (Vega
    sometimes wraps a whole label in one), so each string node is processed exactly once,
    by the element that owns it.
    """
    items = [(None, el.text or "")] + [(child, child.tail or "") for child in list(el)]
    if not any(_ITALIC_STAT_PATTERN.search(s) for _, s in items):
        return

    for child in list(el):
        el.remove(child)
    el.text = None
    last: ET.Element | None = None  # last re-appended node; None → plain text goes to el.text

    def _append_plain(s: str) -> None:
        nonlocal last
        if not s:
            return
        if last is None:
            el.text = (el.text or "") + s
        else:
            last.tail = (last.tail or "") + s

    for child, trailing in items:
        if child is not None:
            child.tail = None
            el.append(child)
            last = child
        pos = 0
        for m in _ITALIC_STAT_PATTERN.finditer(trailing):
            _append_plain(trailing[pos : m.start()])
            tspan = ET.Element(f"{{{_SVG_NS}}}tspan")
            tspan.set("font-style", "italic")
            tspan.text = m.group(0)
            el.append(tspan)
            last = tspan
            pos = m.end()
        _append_plain(trailing[pos:])


def _italicize_stat_symbols(root: ET.Element) -> None:
    """Italicize Latin statistical symbols (``P n F H A W r y x t U``) in rendered text.

    Scientific typesetting convention sets single-letter Latin statistical symbols in
    italic while numbers, operators, Greek symbols (η², ε², χ², ρ, τ), and multi-letter
    abbreviations (``ns`` - an abbreviation, not a symbol) stay upright. Vega-Lite
    text marks have no rich text (``fontStyle`` styles a whole string), so this is applied
    as an SVG post-process: each matched symbol is wrapped in a
    ``<tspan font-style="italic">``, rendering with the label font's italic face.

    Covers the dysonsphere-generated labels - ``stats.comparisons`` bracket p-values and the
    omnibus/test label (``ANOVA F(2, 57) = 6.34, P = 0.003, η² = 0.18``), the
    ``stats.correlation`` readout (``r = 0.85, r² = 0.72, P < 0.001, y = 0.84x + 0.27``), and
    ``add_multilabel``'s ``n =`` sample-size row - and, by the same global-pattern policy as
    :func:`_fix_superscript_labels`, any user text matching the same forms (a hand-written
    ``P = 0.03`` via ``text`` gets the identical treatment, keeping typography
    consistent across a figure).

    Must run AFTER :func:`_fix_superscript_labels`: that fixer only scans element ``.text``,
    so wrapping a leading ``P`` into a ``<tspan>`` first would move the ``×10⁻⁵`` portion
    into a tail it cannot see. This fixer scans both ``.text`` and child tails, so the
    reverse order is safe. Operates on element text in the parsed tree only, never attribute
    values (``aria-label``/``title`` carry the same label text).
    """
    # Both tags, like the superscript fixer: Vega sometimes wraps a label in an outer
    # <tspan>. Materialize before mutating - the italic tspans inserted during the loop
    # must not become targets themselves (and mutating while root.iter() walks is
    # undefined anyway).
    targets = [el for el in root.iter() if el.tag in (f"{{{_SVG_NS}}}text", f"{{{_SVG_NS}}}tspan")]
    for el in targets:
        _italicize_text_element(el)


_GREEK_FONT_CLASS = "ds-greek-font"


def _is_greek_letter(char: str) -> bool:
    """Return whether *char* is a Unicode letter whose assigned name identifies it as Greek."""
    return unicodedata.category(char).startswith("L") and "GREEK" in unicodedata.name(char, "")


def _greek_spans(value: str) -> list[tuple[int, int]]:
    """Locate Greek-letter runs, retaining combining marks attached to a Greek base."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for index, char in enumerate(value):
        greek = _is_greek_letter(char)
        attached_mark = start is not None and unicodedata.combining(char) != 0
        if greek or attached_mark:
            if start is None:
                start = index
        elif start is not None:
            spans.append((start, index))
            start = None
    if start is not None:
        spans.append((start, len(value)))
    return spans


def _switch_greek_font(root: ET.Element, font: str) -> None:
    """Wrap Unicode Greek-letter runs in editable ``tspan`` elements using *font*.

    Unicode identity, attributes, existing child runs, tails, and explicit inherited styles are retained.
    Coptic letters, Greek punctuation, operators, and U+00B5 MICRO SIGN are deliberately excluded.
    """
    targets = [
        el
        for el in root.iter()
        if el.tag in (f"{{{_SVG_NS}}}text", f"{{{_SVG_NS}}}tspan") and el.get("class") != _GREEK_FONT_CLASS
    ]
    for el in targets:
        items = [(None, el.text or "")] + [(child, child.tail or "") for child in list(el)]
        if not any(_greek_spans(value) for _, value in items):
            continue
        for child in list(el):
            el.remove(child)
        el.text = None
        last: ET.Element | None = None

        def append_plain(value: str) -> None:
            nonlocal last
            if last is None:
                el.text = (el.text or "") + value
            else:
                last.tail = (last.tail or "") + value

        for child, trailing in items:
            if child is not None:
                child.tail = None
                el.append(child)
                last = child
            cursor = 0
            for start, end in _greek_spans(trailing):
                append_plain(trailing[cursor:start])
                run = ET.Element(f"{{{_SVG_NS}}}tspan", {"class": _GREEK_FONT_CLASS, "font-family": font})
                run.text = trailing[start:end]
                el.append(run)
                last = run
                cursor = end
            append_plain(trailing[cursor:])


# Generic CSS font keywords (never a real family to collapse to).
_GENERIC_FONTS = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-sans-serif"}


def _illustrator_font_family(value: str) -> str:
    """Rewrite a CSS ``font-family`` stack to an Illustrator-resolvable form, fallbacks kept.

    Adobe Illustrator's SVG importer does NOT resolve CSS fallback stacks the way browsers
    and vl-convert do - it walks a comma-separated ``font-family`` and lands on the first
    single-word family it recognizes, so the default theme stack
    ``Helvetica Neue, HelveticaNeue, Helvetica, Arial, sans-serif`` renders as plain
    **Helvetica** (the 3rd entry), not Helvetica Neue. Worse, Illustrator aliases the
    *spaced* family name ``Helvetica Neue`` to Helvetica even as a single value, while the
    space-free **PostScript** name ``HelveticaNeue`` resolves correctly (verified in
    Illustrator, regular AND italic faces).

    Two things fix it: (1) put the resolvable form of the primary family first - the space-free
    PostScript name when the theme provided it as a fallback (the despaced primary appears
    elsewhere in the stack, the signal it's the intended alias), else the primary as-is (a
    single spaced family like ``Courier New`` resolves fine on its own; only the Helvetica
    family aliases). (2) DROP the primary's less-specific same-family aliases - any entry that
    is a prefix of the primary name (e.g. ``Helvetica`` under ``Helvetica Neue``), which is
    exactly the entry Illustrator gets trapped on - but KEEP the genuinely-different fallbacks
    (``Arial``, ``sans-serif``). So the default becomes ``HelveticaNeue, Arial, sans-serif``:
    Helvetica Neue on macOS Illustrator AND a graceful Arial/sans-serif fallback for every
    non-macOS consumer (Windows Illustrator, Linux Inkscape, a raw SVG in a browser) that
    lacks Helvetica Neue. Both verified. Generic-only values are left untouched.
    """
    families = [f.strip().strip("'\"") for f in value.split(",")]
    families = [f for f in families if f]
    if not families:
        return value
    primary = families[0]
    if primary.lower() in _GENERIC_FONTS:
        return value  # nothing concrete to pin
    despaced = primary.replace(" ", "")
    resolvable = despaced if (" " in primary and despaced in families) else primary
    plow = primary.lower()
    tail = [
        f
        for f in families[1:]
        if f != resolvable and f.replace(" ", "") != resolvable and not plow.startswith(f.lower())
    ]
    return ", ".join([resolvable, *tail])


def _fix_font_for_illustrator(root: ET.Element) -> None:
    """Rewrite every ``font-family`` in the SVG to an Illustrator-resolvable form.

    SVG-only (runs in the shared corrected-SVG pipeline, never on the spec) so the theme option, the
    JSON, and the browser-targeted HTML keep the original CSS fallback stack - only the
    Illustrator-targeted SVG is rewritten. See :func:`_illustrator_font_family` for the why
    and the rule. Italic stat-symbol tspans inherit the parent ``font-family``, so they pick
    up the resolvable name too (verified: real italic face in Illustrator).
    """
    for el in root.iter():
        ff = el.get("font-family")
        if ff:
            el.set("font-family", _illustrator_font_family(ff))

// Client-side port of dysonsphere's `export._typeset_scripts()` SVG post-processor (super- and
// subscript typesetting).
//
// Vega renders every label as one flat string, so a real super/subscript exists only after the
// run is pulled into a shrunk, shifted <tspan>. The library does this at save() time; the site
// renders charts live in the browser (vega-embed), which never goes through save() - so the same
// typesetting is applied here to the rendered SVG DOM. Superscripts: Unicode exponents (×10ⁿ /
// bare 10ⁿ - some fonts lack the Superscripts-block ⁰⁴-⁹, so they'd otherwise render wobbly) and
// a `^` author token (q^2). Subscripts: literal Unicode (t₀) and a `__` author token (q__x, since
// Unicode has no subscript for most letters). Runs become plain ASCII, raised/lowered and shrunk
// relative to the label's font size (2/3 size, 5/12 shift - matching the library).
//
// Only text content is touched; Vega's aria-label/title attributes keep the original string.

const SUP_MAP: Record<string, string> = {
	'⁰': '0',
	'¹': '1',
	'²': '2',
	'³': '3',
	'⁴': '4',
	'⁵': '5',
	'⁶': '6',
	'⁷': '7',
	'⁸': '8',
	'⁹': '9',
	'⁻': '−',
};
// Unicode subscripts -> ASCII (mirrors the library's export._SUBSCRIPT_MAP).
const SUB_MAP: Record<string, string> = {
	'₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4', '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
	'₋': '-', 'ₐ': 'a', 'ₑ': 'e', 'ₒ': 'o', 'ₓ': 'x', 'ₕ': 'h', 'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n',
	'ₚ': 'p', 'ₛ': 's', 'ₜ': 't',
};

// Detection patterns mirroring the library's export._typeset_scripts specs (group 1 = the base to
// keep, group 2 = the run to typeset; any `^`/`__` connector between them is dropped).
// Superscripts: Unicode exponents (×10ⁿ / bare 10ⁿ, a digit/×10 base required) + a `^` author
// token (q^2). Subscripts: literal Unicode (t₀) + a boundary-guarded DOUBLE-underscore token
// (q__x). The token is double, not single, AND guarded: a single `_` is the snake_case column-name
// separator, so a default axis title equal to a column name - single-underscore (x_1,
// flipper_length_mm) or double-underscore (model__alpha) - is never mistaken for a subscript; only
// a deliberate single-base token like q__x is.
const EXPONENT = /([×≈]\s*10|\d)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)/;
const CARET = /([A-Za-z0-9])\^([A-Za-z0-9]{1,2})/;
const SUB_UNICODE = /([A-Za-z0-9])([₀₁₂₃₄₅₆₇₈₉₋ₐₑₒₓₕₖₗₘₙₚₛₜ]+)/;
const DUNDER = /(?<![A-Za-z0-9])([A-Za-z0-9])__([A-Za-z0-9]{1,2})(?![A-Za-z0-9])/;
const SVG_NS = 'http://www.w3.org/2000/svg';

/** The leftmost of several matches (or null). */
function firstMatch(...ms: (RegExpMatchArray | null)[]): RegExpMatchArray | null {
	let best: RegExpMatchArray | null = null;
	for (const m of ms) {
		if (m && m.index !== undefined && (best === null || m.index < (best.index ?? Infinity))) best = m;
	}
	return best;
}

// Split one matched run out of a <text> into a shrunk, shifted <tspan> (up = superscript, else
// subscript), then reset the baseline for any trailing text - dy is CUMULATIVE within a <text> in
// the browser (unlike resvg, which the library targets). `m[1]` (the base) stays inline; the
// `^`/`__` connector is dropped. NOTE: this runs one match per element, so a single label mixing a
// super AND a subscript (`q__x = 10^3`) gets only the first fixer's token (the second skips an
// element that already has tspans). No site example needs both in one label; the library's
// single-pass engine handles that case, this port does not.
function applyScript(text: Element, s: string, m: RegExpMatchArray, run: string, up: boolean): void {
	const idx = m.index ?? 0;
	const fs = parseFloat(getComputedStyle(text).fontSize) || 7;
	const size = ((fs * 2) / 3).toFixed(2);
	const shift = ((fs * 5) / 12).toFixed(2);
	const after = s.slice(idx + m[0].length);
	text.textContent = s.slice(0, idx) + m[1];
	const runEl = document.createElementNS(SVG_NS, 'tspan');
	runEl.setAttribute('font-size', size);
	runEl.setAttribute('dy', up ? `-${shift}` : shift);
	runEl.textContent = run;
	text.appendChild(runEl);
	if (after) {
		const rest = document.createElementNS(SVG_NS, 'tspan');
		rest.setAttribute('font-size', String(fs));
		rest.setAttribute('dy', up ? shift : `-${shift}`);
		rest.textContent = after;
		text.appendChild(rest);
	}
}

/** Re-typeset superscripts (Unicode ×10ⁿ / 10ⁿ, and the `^` token) in every chart <text>. */
export function fixSuperscripts(root: ParentNode): void {
	for (const text of root.querySelectorAll('svg text')) {
		if (text.childElementCount > 0) continue; // already split into tspans
		const s = text.textContent ?? '';
		const m = firstMatch(s.match(EXPONENT), s.match(CARET));
		if (!m) continue;
		const run = [...m[2]].map((c) => SUP_MAP[c] ?? c).join(''); // maps Unicode; ASCII passes through
		applyScript(text, s, m, run, true);
	}
}

/** Re-typeset subscripts (literal Unicode t₀, and the `__` token) in every chart <text>. */
export function fixSubscripts(root: ParentNode): void {
	for (const text of root.querySelectorAll('svg text')) {
		if (text.childElementCount > 0) continue; // already split into tspans
		const s = text.textContent ?? '';
		const m = firstMatch(s.match(DUNDER), s.match(SUB_UNICODE));
		if (!m) continue;
		const run = [...m[2]].map((c) => SUB_MAP[c] ?? c).join(''); // maps Unicode; ASCII passes through
		applyScript(text, s, m, run, false);
	}
}

// Client-side port of `export._italicize_stat_symbols()` (dysonsphere >= 3.4.2): single-letter
// Latin statistical symbols are set in italic per scientific convention while digits, operators,
// Greek symbols (η², ε², χ², ρ, τ), and multi-letter abbreviations (`ns`) stay upright. The
// library applies this at save() time; the same treatment is applied here to the live
// vega-embed SVG so the site's charts match exported figures. The pattern mirrors
// export._ITALIC_STAT_PATTERN exactly.
const ITALIC_STAT =
	/(?<![A-Za-z])(?:P(?=\s*[=<≈])|[FHA](?=\()|W(?=\s*=)|r(?=²?\s*=)|n(?=\s*=)|y(?=\s*=)|t(?=-test)|[Pp](?=[ \-]value))|(?<=Mann-Whitney )U(?![A-Za-z])|(?<=[\d.])x(?=\s*[+\-−]\s*\d)/g;

/**
 * Italicize Latin statistical symbols (`P n F H A W r y x t U`) in every `<text>` of the
 * rendered chart(s) under `root`. Run AFTER `fixSuperscripts` (both split text into tspans;
 * this one walks all remaining text nodes, so it must see the final ones).
 */
export function italicizeStatSymbols(root: ParentNode): void {
	for (const text of root.querySelectorAll('svg text')) {
		// Snapshot the text nodes first - matches are replaced by (text, tspan, text) splices.
		const walker = document.createTreeWalker(text, NodeFilter.SHOW_TEXT);
		const nodes: Text[] = [];
		for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n as Text);
		for (const node of nodes) {
			const s = node.data;
			ITALIC_STAT.lastIndex = 0;
			if (!ITALIC_STAT.test(s)) continue;
			const frag = document.createDocumentFragment();
			let pos = 0;
			ITALIC_STAT.lastIndex = 0;
			for (const m of s.matchAll(ITALIC_STAT)) {
				const i = m.index ?? 0;
				if (i > pos) frag.appendChild(document.createTextNode(s.slice(pos, i)));
				const tspan = document.createElementNS(SVG_NS, 'tspan');
				tspan.setAttribute('font-style', 'italic');
				tspan.textContent = m[0];
				frag.appendChild(tspan);
				pos = i + m[0].length;
			}
			if (pos < s.length) frag.appendChild(document.createTextNode(s.slice(pos)));
			node.parentNode?.replaceChild(frag, node);
		}
	}
}

/**
 * Client-side port of `export._align_grid_to_content()`: on an open plot each axis is drawn
 * `axisOffset` px away from the plot, and Vega renders grid lines inside their axis group -
 * so the grid inherits the offset and renders dragged toward its axis (vertical lines down,
 * horizontal lines left). Translate each line back (span unchanged) so the grid spans the
 * plot content exactly, matching save() output. The offset comes from the baked spec config
 * (`config.axis.offset`); closed plots bake `0`, so they are skipped like in the library.
 */
export function alignGridToContent(root: ParentNode, spec: { config?: { axis?: { offset?: number } } }): void {
	const offset = Number(spec?.config?.axis?.offset ?? 0);
	if (!offset) return;
	const XLATE = /translate\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)/;
	for (const line of root.querySelectorAll('svg g.mark-rule.role-axis-grid line')) {
		const m = XLATE.exec(line.getAttribute('transform') ?? '');
		if (!m) continue;
		const tx = parseFloat(m[1]);
		const ty = parseFloat(m[2]);
		const x2 = parseFloat(line.getAttribute('x2') ?? '0');
		const y2 = parseFloat(line.getAttribute('y2') ?? '0');
		if (Math.abs(y2) > Math.abs(x2) && ty < 0) {
			// vertical grid (x-axis group, offset down): lift up
			line.setAttribute('transform', `translate(${tx},${ty - offset})`);
		} else if (Math.abs(x2) > Math.abs(y2)) {
			// horizontal grid (y-axis group, offset left): shift right
			line.setAttribute('transform', `translate(${tx + offset},${ty})`);
		}
	}
}

/**
 * Client-side port of `export._flip_ticks_inward()`: negate the non-zero `x2`/`y2` of every
 * axis-tick line so ticks point INTO the plot. Like the superscript fixer, the library applies
 * this only at save() time; the site opts in per chart (theming's inwardTicks example) since
 * the rendered spec carries no flag for it.
 *
 * Two passes, mirroring the library: Pass 1 pulls each axis's labels + title toward the view by
 * that axis's OWN tick vector (read BEFORE negation) so the freed outward-tick space doesn't
 * survive as a dead gap between the domain line and the labels; Pass 2 negates the tick geometry.
 */
export function flipTicksInward(root: ParentNode): void {
	const XLATE = /^translate\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)(.*)$/;
	// Pass 1: pull each axis's labels + title inward by its tick length (pre-negation read).
	for (const axis of root.querySelectorAll('svg g.mark-group.role-axis')) {
		const tick = axis.querySelector('g[class*="role-axis-tick"] line');
		if (!tick) continue;
		const dx = -parseFloat(tick.getAttribute('x2') ?? '0');
		const dy = -parseFloat(tick.getAttribute('y2') ?? '0');
		if (dx === 0 && dy === 0) continue;
		for (const text of axis.querySelectorAll(
			'g[class*="role-axis-label"] text, g[class*="role-axis-title"] text',
		)) {
			const m = XLATE.exec(text.getAttribute('transform') ?? '');
			if (!m) continue;
			const x = parseFloat(m[1]);
			const y = parseFloat(m[2]);
			text.setAttribute('transform', `translate(${x + dx},${y + dy})${m[3]}`);
		}
	}
	// Pass 2: negate the tick geometry itself.
	for (const line of root.querySelectorAll('svg g[class*="role-axis-tick"] line')) {
		const x2 = parseFloat(line.getAttribute('x2') ?? '0');
		const y2 = parseFloat(line.getAttribute('y2') ?? '0');
		if (x2 !== 0) line.setAttribute('x2', String(-x2));
		else if (y2 !== 0) line.setAttribute('y2', String(-y2));
	}
}

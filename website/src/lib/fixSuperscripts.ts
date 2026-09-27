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
const SVG_NS = 'http://www.w3.org/2000/svg';

type Spec = { pattern: RegExp; map: Record<string, string> | null; raise: boolean };

const SPECS: Spec[] = [
	{ pattern: /([×≈]\s*10|\d)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)/g, map: SUP_MAP, raise: true },
	{ pattern: /([A-Za-z0-9])\^([A-Za-z0-9]{1,2})/g, map: null, raise: true },
	{ pattern: /([A-Za-z0-9])([₀₁₂₃₄₅₆₇₈₉₋ₐₑₒₓₕₖₗₘₙₚₛₜ]+)/g, map: SUB_MAP, raise: false },
	{ pattern: /(?<![A-Za-z0-9])([A-Za-z0-9])__([A-Za-z0-9]{1,2})(?![A-Za-z0-9])/g, map: null, raise: false },
];

/** One run to typeset: the base keeps its place, `[baseEnd, runEnd)` becomes a shifted tspan. */
type Span = { start: number; baseEnd: number; runEnd: number; run: string; raise: boolean };

/**
 * Every run in `text`, in reading order, overlaps dropped (earlier match wins) - the library's
 * `_typeset_scripts` collection step. Exported for the DOM-free unit check.
 */
export function planScripts(text: string): Span[] {
	const spans: Span[] = [];
	for (const { pattern, map, raise } of SPECS) {
		pattern.lastIndex = 0;
		for (const m of text.matchAll(pattern)) {
			const start = m.index ?? 0;
			const run = map ? [...m[2]].map((c) => map[c] ?? c).join('') : m[2];
			spans.push({ start, baseEnd: start + m[1].length, runEnd: start + m[0].length, run, raise });
		}
	}
	spans.sort((a, b) => a.start - b.start);
	const kept: Span[] = [];
	let lastEnd = -1;
	for (const s of spans) {
		if (s.start >= lastEnd) {
			kept.push(s);
			lastEnd = s.runEnd;
		}
	}
	return kept;
}

/**
 * Re-typeset every super/subscript run in one pass, mirroring the library's `_typeset_scripts`:
 * Unicode exponents (`×10ⁿ` / bare `10ⁿ`), the `^` author token (`q^2`), literal Unicode subscripts
 * (`t₀`), and the `__` author token (`q__x`). Collecting all four detectors' matches and rebuilding
 * the element once is what lets a label carry SEVERAL runs, and mixed super + sub (`q__x = 10^3`) -
 * the two-pass version this replaced typeset only the first match in an element.
 *
 * Each run becomes a plain-ASCII tspan at 2/3 the label's font size, shifted 5/12 of it (up for a
 * superscript, down for a subscript). Unlike the library's resvg target, `dy` is CUMULATIVE within
 * a `<text>` in the browser, so every segment's `dy` is emitted as a DELTA from the current
 * baseline - which is also how a following run at the opposite offset lands correctly.
 */
export function typesetScripts(root: ParentNode): void {
	for (const el of root.querySelectorAll('svg text')) {
		if (el.childElementCount > 0) continue; // already split into tspans
		const text = el.textContent ?? '';
		const kept = planScripts(text);
		if (!kept.length) continue;
		const fs = parseFloat(getComputedStyle(el).fontSize) || 7;
		const size = ((fs * 2) / 3).toFixed(2);
		const shift = (fs * 5) / 12;
		// Emit segments in reading order; `offset` tracks the baseline the previous segment left.
		const parts: { text: string; target: number; size: number }[] = [];
		let cursor = 0;
		for (const s of kept) {
			parts.push({ text: text.slice(cursor, s.baseEnd), target: 0, size: fs }); // literal + base
			parts.push({ text: s.run, target: s.raise ? -shift : shift, size: parseFloat(size) });
			cursor = s.runEnd;
		}
		parts.push({ text: text.slice(cursor), target: 0, size: fs });

		el.textContent = parts[0].text; // the head literal sits on the element itself, at baseline
		let offset = 0;
		for (const part of parts.slice(1)) {
			if (!part.text) continue;
			const tspan = document.createElementNS(SVG_NS, 'tspan');
			tspan.setAttribute('font-size', String(part.size));
			tspan.setAttribute('dy', (part.target - offset).toFixed(2));
			tspan.textContent = part.text;
			el.appendChild(tspan);
			offset = part.target;
		}
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

/** The same detectors used by the SVG correction passes, available before embedding. */
export function needsTextCorrections(text: string): boolean {
	ITALIC_STAT.lastIndex = 0;
	return planScripts(text).length > 0 || ITALIC_STAT.test(text);
}

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
 * this only at save() time; the site opts in per chart (theming's inward-tick example) since
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

const FIGURE_LABEL_PREFIX = '__dsfigure_label_';

/**
 * Seat every figure label at the leftmost panel edge in its column.
 *
 * Mirrors `export._align_figure_labels`. Vega aligns concat members by their PLOT area, but a
 * label anchors to its member's bounding box, and those differ by that member's own axis margin -
 * so labels go ragged while the plots stay aligned. Members sharing a column render at an identical
 * plot-area x, so grouping on that and taking the smallest label x per column lines them up with no
 * text measurement.
 */
export function alignFigureLabels(root: ParentNode): void {
	const XLATE = /translate\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)/;
	const VIEW_RECT = /^M[-\d.]+,[-\d.]+h([-\d.]+)v([-\d.]+)/;

	// absolute x of a node relative to `stop`, accumulating the ancestor translates
	const absX = (el: Element, stop: Element): number => {
		let x = 0;
		for (let n: Element | null = el; n; n = n.parentElement) {
			const m = XLATE.exec(n.getAttribute('transform') ?? '');
			if (m) x += parseFloat(m[1]);
			if (n === stop) break;
		}
		return x;
	};

	const found: { text: Element; labelX: number; plotX: number }[] = [];
	for (const wrapper of root.querySelectorAll(`svg g[class*="${FIGURE_LABEL_PREFIX}"]`)) {
		if (!/_group$/.test(wrapper.getAttribute('class') ?? '')) continue;
		const title = wrapper.querySelector('g.role-title text');
		if (!title) continue;
		// the member's own plot rectangle - group backgrounds carry a zero-size path
		let plot: Element | null = null;
		for (const bg of wrapper.querySelectorAll('path.background')) {
			const g = VIEW_RECT.exec(bg.getAttribute('d') ?? '');
			if (g && parseFloat(g[1]) > 0 && parseFloat(g[2]) > 0) {
				plot = bg;
				break;
			}
		}
		if (!plot) continue;
		found.push({
			text: title,
			labelX: absX(title, wrapper) + parseFloat(title.getAttribute('x') ?? '0'),
			plotX: absX(plot, wrapper),
		});
	}

	const columns = new Map<number, typeof found>();
	for (const entry of found) {
		const key = Math.round(entry.plotX * 1000) / 1000;
		columns.set(key, [...(columns.get(key) ?? []), entry]);
	}
	for (const column of columns.values()) {
		const target = Math.min(...column.map((e) => e.labelX));
		for (const entry of column) {
			const by = target - entry.labelX;
			if (Math.abs(by) <= 1e-6) continue;
			const m = XLATE.exec(entry.text.getAttribute('transform') ?? '');
			if (m) {
				entry.text.setAttribute('transform', `translate(${parseFloat(m[1]) + by},${m[2]})`);
			} else {
				entry.text.setAttribute('x', String(parseFloat(entry.text.getAttribute('x') ?? '0') + by));
			}
		}
	}
}

// Client-side port of dysonsphere's `export._fix_superscript_labels()` SVG post-processor.
//
// Unicode superscript digits live in two blocks with inconsistent vertical metrics in many
// fonts (¹²³ in Latin-1, ⁰⁴-⁹ + ⁻ in the Superscripts block), so scientific/power p-value
// labels like `P = 5.03×10⁻¹⁷` render with a wobbly, collision-prone exponent. The library
// fixes this at save() time, but the site renders charts live in the browser (vega-embed),
// which never goes through save() - so the same fix is applied here to the rendered SVG DOM:
// the exponent is replaced with a <tspan> of plain ASCII digits (and a true minus), raised
// and shrunk relative to the label's font size (the library's 4px/-2.5px at fontSize 6).
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
const EXPONENT = /([×≈]\s*10)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)/;
const SVG_NS = 'http://www.w3.org/2000/svg';

/** Re-typeset `×10ⁿ` exponents in every <text> of the rendered chart(s) under `root`. */
export function fixSuperscripts(root: ParentNode): void {
	for (const text of root.querySelectorAll('svg text')) {
		if (text.childElementCount > 0) continue; // has tspans already (or was processed)
		const s = text.textContent ?? '';
		const m = s.match(EXPONENT);
		if (!m || m.index === undefined) continue;
		const fs = parseFloat(getComputedStyle(text).fontSize) || 7;
		const supSize = ((fs * 2) / 3).toFixed(2);
		const shift = ((fs * 5) / 12).toFixed(2);
		const exponent = [...m[2]].map((c) => SUP_MAP[c] ?? c).join('');
		const after = s.slice(m.index + m[0].length);
		text.textContent = s.slice(0, m.index) + m[1];
		const sup = document.createElementNS(SVG_NS, 'tspan');
		sup.setAttribute('font-size', supSize);
		sup.setAttribute('dy', `-${shift}`);
		sup.textContent = exponent;
		text.appendChild(sup);
		if (after) {
			// Reset the baseline for any trailing text (dy is cumulative within <text>).
			const rest = document.createElementNS(SVG_NS, 'tspan');
			rest.setAttribute('font-size', String(fs));
			rest.setAttribute('dy', shift);
			rest.textContent = after;
			text.appendChild(rest);
		}
	}
}

// Subscript typesetting for axis titles like `q_x` / `q_y`. Unicode has a subscript x (ₓ) but NO
// subscript y (the Subscripts block is missing most letters), so a `q_y` label can only be written
// with a literal underscore, which renders as an ugly `q_y`. This lowers + shrinks the token after
// a single-letter base and its underscore into a <tspan> (mirroring fixSuperscripts, opposite dy),
// so `q_x`/`q_y` read as true subscripts. Matches a standalone `letter _ 1-2 alphanumerics` token
// (the subscript notation), which does not occur in prose chart text.
const SUBSCRIPT = /(?<![A-Za-z0-9])([A-Za-z])_([A-Za-z0-9]{1,2})(?![A-Za-z0-9])/;

/** Re-typeset `base_sub` subscripts in every <text> of the rendered chart(s) under `root`. */
export function fixSubscripts(root: ParentNode): void {
	for (const text of root.querySelectorAll('svg text')) {
		if (text.childElementCount > 0) continue; // already split into tspans
		const s = text.textContent ?? '';
		const m = s.match(SUBSCRIPT);
		if (!m || m.index === undefined) continue;
		const fs = parseFloat(getComputedStyle(text).fontSize) || 7;
		const subSize = ((fs * 2) / 3).toFixed(2);
		const shift = (fs * 0.3).toFixed(2);
		const after = s.slice(m.index + m[0].length);
		text.textContent = s.slice(0, m.index) + m[1]; // up to and including the base letter
		const sub = document.createElementNS(SVG_NS, 'tspan');
		sub.setAttribute('font-size', subSize);
		sub.setAttribute('dy', shift); // lower (dy is cumulative within <text>)
		sub.textContent = m[2];
		text.appendChild(sub);
		if (after) {
			const rest = document.createElementNS(SVG_NS, 'tspan');
			rest.setAttribute('font-size', String(fs));
			rest.setAttribute('dy', `-${shift}`); // reset the baseline for trailing text
			rest.textContent = after;
			text.appendChild(rest);
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
 */
export function flipTicksInward(root: ParentNode): void {
	for (const line of root.querySelectorAll('svg g[class*="role-axis-tick"] line')) {
		const x2 = parseFloat(line.getAttribute('x2') ?? '0');
		const y2 = parseFloat(line.getAttribute('y2') ?? '0');
		if (x2 !== 0) line.setAttribute('x2', String(-x2));
		else if (y2 !== 0) line.setAttribute('y2', String(-y2));
	}
}

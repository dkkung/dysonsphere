// geist-australis for the CodeMirror editors (Chart Studio, config generator): the same
// grayscale-scaffold + australis-accent scheme as the Expressive Code doc cells, so editors and
// rendered code read alike. Backgrounds come from --ds-code-bg (theme.css) - the shared code
// surface - which replaces @uiw's github theme and its off-black (#0d1117) dark background.
import { EditorView } from '@codemirror/view';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { tags as t } from '@lezer/highlight';
import type { Extension } from '@codemirror/state';

interface Tokens {
	fg: string;
	cmt: string;
	kw: string;
	str: string;
	num: string;
	fn: string;
	op: string;
}

function build(dark: boolean, c: Tokens): Extension {
	const view = EditorView.theme(
		{
			// Transparent so the editor blends with its panel/page instead of being its own raised
			// box (github's dark theme painted an off-black #0d1117 here); the container supplies any
			// surface. Syntax colours are tuned to read on both the light and dark page grounds.
			'&': { color: c.fg, backgroundColor: 'transparent' },
			'.cm-content': { caretColor: c.fg },
			'.cm-cursor, .cm-dropCursor': { borderLeftColor: c.fg },
			'.cm-gutters': { backgroundColor: 'transparent', color: c.op, border: 'none' },
			'.cm-activeLine': { backgroundColor: dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.035)' },
			'.cm-activeLineGutter': { backgroundColor: 'transparent', color: c.fg },
			'.cm-selectionBackground, &.cm-focused .cm-selectionBackground, .cm-content ::selection': {
				backgroundColor: dark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.10)',
			},
		},
		{ dark },
	);
	const style = HighlightStyle.define([
		{ tag: [t.comment, t.lineComment, t.blockComment], color: c.cmt, fontStyle: 'italic' },
		{
			tag: [t.keyword, t.moduleKeyword, t.controlKeyword, t.definitionKeyword, t.operatorKeyword, t.self],
			color: c.kw,
			fontWeight: 'bold',
		},
		{ tag: [t.string, t.special(t.string), t.docString], color: c.str },
		{ tag: [t.number, t.bool, t.null, t.atom], color: c.num },
		{
			tag: [t.function(t.variableName), t.function(t.propertyName), t.definition(t.function(t.variableName))],
			color: c.fn,
		},
		{ tag: [t.typeName, t.className, t.namespace, t.standard(t.name)], color: c.fn },
		{ tag: [t.operator], color: c.op },
	]);
	return [view, syntaxHighlighting(style)];
}

export const geistLight = build(false, {
	fg: '#171717',
	cmt: '#a3a3a3',
	kw: '#43044D',
	str: '#1D83CA',
	num: '#4D338C',
	fn: '#3A68BB',
	op: '#737373',
});
export const geistDark = build(true, {
	fg: '#ededed',
	cmt: '#6e6e6e',
	kw: '#4DE0B4',
	str: '#1D9CCB',
	num: '#3A68BB',
	fn: '#23B5C9',
	op: '#8f8f8f',
});

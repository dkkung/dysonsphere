// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// NOTE: `site` / `base` for GitHub Pages come from env, set by the Pages workflow (project
// pages serve under /dysonsphere). Unset locally, so dev/build/preview run cleanly at "/".
const site = process.env.DEPLOY_SITE || undefined;
const base = (process.env.DEPLOY_BASE || '').replace(/\/+$/, '') + '/';
const prefix = base.slice(0, -1); // '' at "/", '/dysonsphere' when deployed

// Astro/Starlight do NOT rewrite root-relative CONTENT links when `base` is set - every
// markdown [text](/guides/...) lands in the build verbatim and 404s on a project-pages
// deploy. This prefixes them at build time, so authors keep writing base-free root-relative
// links that work at any base. (Starlight's own chrome - sidebar, assets, canonical - is
// already base-aware; this covers only links written in md/mdx content.)
function remarkBaseLinks() {
	return (tree) => {
		if (!prefix) return;
		const walk = (node) => {
			if (
				(node.type === 'link' || node.type === 'definition' || node.type === 'image') &&
				typeof node.url === 'string' &&
				node.url.startsWith('/') &&
				!node.url.startsWith('//') &&
				!node.url.startsWith(prefix + '/')
			) {
				node.url = prefix + node.url;
			}
			(node.children ?? []).forEach(walk);
		};
		walk(tree);
	};
}

// geist-australis code themes: a grayscale scaffold with australis-palette accents on the
// meaningful tokens (keywords / strings / function calls), so code cells quietly wear the
// brand palette. Backgrounds are overridden by --ds-code-bg (theme.css) - only tokens matter.
const geistAustralis = (name, type, c) => ({
	name,
	type,
	colors: { 'editor.background': c.bg, 'editor.foreground': c.fg },
	tokenColors: [
		{ scope: ['comment', 'punctuation.definition.comment'], settings: { foreground: c.cmt, fontStyle: 'italic' } },
		{
			scope: ['keyword', 'storage', 'storage.type', 'storage.modifier', 'keyword.control', 'keyword.operator.logical', 'keyword.operator.expression', 'variable.language'],
			settings: { foreground: c.kw, fontStyle: 'bold' },
		},
		{ scope: ['string', 'string.quoted', 'string.template', 'punctuation.definition.string', 'constant.character'], settings: { foreground: c.str } },
		{ scope: ['constant.numeric', 'constant.language', 'constant.other', 'support.constant'], settings: { foreground: c.num } },
		{ scope: ['entity.name.function', 'support.function', 'meta.function-call'], settings: { foreground: c.fn } },
		{
			// types/classes share the name accent. Uses the BROAD single-segment `support` scope
			// (as github-light does) - EC didn't honor the two-segment `support.type` here, so
			// type-heavy reference signatures (float/str/int/...) rendered mostly plain.
			scope: ['support', 'entity.name.type', 'entity.name.class', 'entity.other.inherited-class'],
			settings: { foreground: c.fn },
		},
		{ scope: ['keyword.operator'], settings: { foreground: c.op } },
	],
});
// stops sampled from the australis ramp: darker stops read on the light ground, lighter on dark.
const geistAustralisLight = geistAustralis('geist-australis-light', 'light', {
	bg: '#ffffff', fg: '#171717', cmt: '#a3a3a3', kw: '#43044D', str: '#1D83CA', num: '#4D338C', fn: '#3A68BB', op: '#737373',
});
const geistAustralisDark = geistAustralis('geist-australis-dark', 'dark', {
	bg: '#1a1a1b', fg: '#ededed', cmt: '#6e6e6e', kw: '#4DE0B4', str: '#1D9CCB', num: '#3A68BB', fn: '#23B5C9', op: '#8f8f8f',
});

// https://astro.build/config
export default defineConfig({
	site,
	base,
	markdown: { remarkPlugins: [remarkBaseLinks] },
	integrations: [
		starlight({
			title: 'dysonsphere',
			favicon: '/favicon.svg',
			logo: { src: './src/assets/dysonsphere_logo.svg', replacesTitle: false },
			components: {
				SiteTitle: './src/components/SiteTitle.astro',
			},
			description:
				'An Altair theme and chart-utility library with perceptually uniform palettes and publication-ready defaults.',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/dkkung/dysonsphere' }],
			customCss: [
				'@fontsource-variable/inter',
				'@fontsource-variable/jetbrains-mono',
				'./src/styles/theme.css',
			],
			expressiveCode: {
				// geist-australis (custom, defined above): grayscale scaffold + australis accents.
				// The ground comes from --ds-code-bg (theme.css) so code cells share one surface
				// with the CodeMirror editors; the theme only supplies token colors.
				themes: [geistAustralisDark, geistAustralisLight],
				styleOverrides: {
					borderRadius: '0.65rem',
					borderColor: 'var(--sl-color-hairline)',
					codeBackground: 'var(--ds-code-bg)',
					frames: {
						shadowColor: 'transparent',
						terminalBackground: 'var(--ds-code-bg)',
						terminalTitlebarBackground: 'var(--ds-code-bg)',
					},
				},
			},
			// Guides: getting started, then styling (theme/config/palettes), then building
			// (marks/annotations/statistics), then export. Reference is alphabetical.
			sidebar: [
				{
					label: 'Guides',
					items: [
						{ label: 'Getting started', slug: 'guides/getting-started' },
						{ label: 'Theming', slug: 'guides/theming' },
						{ label: 'Global theme overrides', slug: 'guides/configuration' },
						{ label: 'Palettes', slug: 'guides/palettes' },
						{
							label: 'Marks & transforms',
							items: [
								{ label: 'Marks', slug: 'guides/marks' },
								{ label: 'Transforms', slug: 'guides/transforms' },
							],
						},
						{
							label: 'Annotations',
							items: [
								{ label: 'Reference lines', slug: 'guides/reference-lines' },
								{ label: 'Shading', slug: 'guides/shading' },
								{ label: 'Text & labels', slug: 'guides/text-labels' },
							],
						},
						{
							label: 'Statistical annotations',
							items: [
								{ label: 'Comparisons', slug: 'guides/comparisons' },
								{ label: 'Correlation', slug: 'guides/correlation' },
							],
						},
						{ label: 'Multilabels', slug: 'guides/multilabels' },
						{ label: 'Nonlinear axes', slug: 'guides/nonlinear' },
						{ label: 'Saving, reading, loading', slug: 'guides/saving' },
					],
				},
				{
					label: 'Interactive',
					items: [
						{
							// Gallery split per domain so each page loads only ~4 live charts (one page
							// of all ~19 was slow); the overview links the sections.
							label: 'Gallery',
							items: [
								{ label: 'Overview', slug: 'gallery' },
								{ label: 'Fields & imaging', slug: 'gallery/imaging' },
								{ label: 'Structure & chemistry', slug: 'gallery/chemistry' },
								{ label: 'Signals & dynamics', slug: 'gallery/signals' },
								{ label: 'Machine learning', slug: 'gallery/machine-learning' },
								{ label: 'Molecular biology', slug: 'gallery/biology' },
								{ label: 'Distributions & statistics', slug: 'gallery/distributions' },
							],
						},
						{ label: 'Palette browser', slug: 'palettes' },
						{ label: 'Config generator', slug: 'config-generator' },
						{ label: 'Chart Studio', slug: 'studio' },
					],
				},
				{
					label: 'Extensions',
					items: [
						{ label: 'Overview on extensions', slug: 'extensions' },
						{ label: 'Writing an extension', slug: 'extensions/authoring' },
						{
							label: 'dysonsphere-biology',
							items: [
								{ label: 'Overview', slug: 'extensions/biology' },
								{ label: 'volcano()', slug: 'extensions/volcano' },
							],
						},
					],
				},
				{
					label: 'Documentation',
					items: [{ autogenerate: { directory: 'reference' } }],
				},
			],
		}),
	],
});

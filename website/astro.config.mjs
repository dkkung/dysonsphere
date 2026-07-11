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
				// GitHub themes match the playground's CodeMirror editor; neutral frames. The
				// ground comes from --ds-code-bg (theme.css) so code cells share one surface
				// with the CodeMirror editors - dark uses the skin's neutral raised tone, not
				// GitHub-dark's blue-tinted #0d1117.
				themes: ['github-dark', 'github-light'],
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
						{ label: 'Marks & transforms', slug: 'guides/marks' },
						{ label: 'Annotations', slug: 'guides/annotations' },
						{ label: 'Statistical annotations', slug: 'guides/statistics' },
						{ label: 'Multilabels', slug: 'guides/multilabels' },
						{ label: 'Nonlinear axes', slug: 'guides/nonlinear' },
						{ label: 'Saving, reading, loading', slug: 'guides/saving' },
					],
				},
				{
					label: 'Interactive',
					items: [
						{ label: 'Gallery', slug: 'gallery' },
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

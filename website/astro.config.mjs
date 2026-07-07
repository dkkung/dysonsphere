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
				// GitHub themes match the playground's CodeMirror editor; neutral frames.
				themes: ['github-dark', 'github-light'],
				styleOverrides: {
					borderRadius: '0.65rem',
					borderColor: 'var(--sl-color-hairline)',
					frames: { shadowColor: 'transparent' },
				},
			},
			// Ordered as the reader works: build a chart, annotate it, style it, save it -
			// then the interactive surfaces, extensions, and the generated reference.
			sidebar: [
				{
					label: 'Guides',
					items: [
						{ label: 'Getting started', slug: 'guides/getting-started' },
						{ label: 'Marks & transforms', slug: 'guides/marks' },
						{ label: 'Annotations', slug: 'guides/annotations' },
						{ label: 'Statistical annotations', slug: 'guides/statistics' },
						{ label: 'Nonlinear axes', slug: 'guides/nonlinear' },
						{ label: 'Theming', slug: 'guides/theming' },
						{ label: 'Palettes', slug: 'guides/palettes' },
						{ label: 'Configuration (dysonsphere.toml)', slug: 'guides/configuration' },
						{ label: 'Saving & reading', slug: 'guides/saving' },
					],
				},
				{
					label: 'Interactive',
					items: [
						{ label: 'Gallery', slug: 'gallery' },
						{ label: 'Palette browser', slug: 'palettes' },
						{ label: 'Chart Studio', slug: 'studio' },
					],
				},
				{
					label: 'Extensions',
					items: [
						{ label: 'Overview', slug: 'extensions' },
						{ label: 'biology', slug: 'extensions/biology' },
						{ label: 'Writing an extension', slug: 'extensions/authoring' },
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

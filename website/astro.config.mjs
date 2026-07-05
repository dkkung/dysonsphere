// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// NOTE: `site` / `base` for GitHub Pages are set in the deploy step (project pages serve
// under /dysonsphere). Left unset here so local dev/build runs cleanly at "/".
// https://astro.build/config
export default defineConfig({
	integrations: [
		starlight({
			title: 'dysonsphere',
			favicon: '/favicon.svg',
			logo: { src: './src/assets/dysonsphere_logo.svg', replacesTitle: false },
			components: { SiteTitle: './src/components/SiteTitle.astro' },
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
			sidebar: [
				{
					label: 'Guides',
					items: [
						{ label: 'Getting started', slug: 'guides/getting-started' },
						{ label: 'Theming', slug: 'guides/theming' },
						{ label: 'Palettes', slug: 'guides/palettes' },
						{ label: 'Marks & transforms', slug: 'guides/marks' },
						{ label: 'Annotations', slug: 'guides/annotations' },
						{ label: 'Statistical annotations', slug: 'guides/statistics' },
						{ label: 'Nonlinear axes', slug: 'guides/nonlinear' },
						{ label: 'Saving & reading', slug: 'guides/saving' },
					],
				},
				{
					label: 'Interactive',
					items: [
						{ label: 'Gallery', slug: 'gallery' },
						{ label: 'Playground', slug: 'playground' },
						{ label: 'Chart Studio', slug: 'studio' },
					],
				},
				{
					label: 'Reference',
					items: [{ autogenerate: { directory: 'reference' } }],
				},
			],
		}),
	],
});

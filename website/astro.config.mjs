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
			description:
				'An Altair theme and chart-utility library with perceptually uniform palettes and publication-ready defaults.',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/dkkung/dysonsphere' }],
			customCss: ['./src/styles/theme.css'],
			sidebar: [
				{
					label: 'Guides',
					items: [{ label: 'Getting started', slug: 'guides/getting-started' }],
				},
				{
					label: 'Reference',
					items: [{ autogenerate: { directory: 'reference' } }],
				},
			],
		}),
	],
});

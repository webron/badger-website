// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import pagefind from 'astro-pagefind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://badger.fit',
  integrations: [
    pagefind(),
    // lastmod is a recrawl hint, and without it every entry is a bare <loc>
    // that says nothing about whether the page changed. The build date is the
    // honest value available here: the site is a static build, so every page in
    // a given deploy was produced at the same moment, and claiming a per-page
    // date we do not track would be worse than claiming none.
    sitemap({ lastmod: new Date() }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
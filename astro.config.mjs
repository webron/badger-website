// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import pagefind from 'astro-pagefind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://badger.fit',
  integrations: [pagefind(), sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
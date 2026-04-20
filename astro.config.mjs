// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://badger.fit',
  // base is the subpath on GitHub Pages (webron.github.io/badger-website/).
  // Remove this line once badger.fit DNS is pointed at GitHub Pages.
  base: '/badger-website',
  vite: {
    plugins: [tailwindcss()],
  },
});
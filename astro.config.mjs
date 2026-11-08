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
    // IndexNow (Bing, and so ChatGPT search) is deliberately NOT pinged from
    // the build. An integration here pings during `npm run build`, before the
    // deploy job publishes the site, so the search engine fetched the key file
    // while it was still a 404 and marked the key as failed: the first two
    // deploys (2026-11-06) succeeded, every later one got 403
    // (UserForbiddedToAccessSite). The ping now runs as the `indexnow` job in
    // .github/workflows/deploy.yml, after the deploy, using the key file
    // public/b9db15b62c683144774ab2eaaca2838c.txt (public by design).
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
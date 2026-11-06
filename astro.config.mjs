// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import pagefind from 'astro-pagefind';
import sitemap from '@astrojs/sitemap';
import indexnow from 'astro-indexnow';

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
    // Tells Bing (and so ChatGPT search, which draws on Bing) about new and
    // changed pages after each build. The key is public by design: IndexNow
    // proves ownership by fetching public/4ba086b588396904edaa146f34850792.txt from the site, so there is
    // nothing to keep secret. Local builds only plan the submission (dryRun):
    // the key file is not live until a deploy, so a local ping would just fail.
    // CI sets CI=true. The cache file is not committed, because the deploy job
    // never commits it back, so each deploy resubmits every page. That is a
    // few dozen URLs, well inside IndexNow's limits.
    indexnow({ key: '4ba086b588396904edaa146f34850792', dryRun: !process.env.CI, logMode: 'normal' }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
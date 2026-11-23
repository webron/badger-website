#!/usr/bin/env node
// Checks every internal link in the BUILT site (dist/) after `npm run build`.
// test:anchors checks the .astro sources for the shared index files only; this
// covers every page, as rendered, including links Astro components generate.
//
// For each href/src in dist/**/*.html that stays on badger.fit:
//   - the target file exists (path, path/index.html, or path.html), and
//   - a #fragment matches an id= (or name=) on the target page.
// External links, mailto:, tel:, data: and javascript: are skipped.
//
// Usage: node tool/check-dist-links.mjs [distDir]   (default: dist)
// Exit 0 = all resolve. Exit 1 = prints one line per broken link, then a count.
import { readFileSync, existsSync, statSync, readdirSync } from 'node:fs';
import { join, dirname, relative, posix } from 'node:path';

const SITE_HOST = 'badger.fit';
const dist = process.argv[2] || 'dist';
if (!existsSync(dist)) {
  console.error(`No ${dist}/ folder. Run npm run build first.`);
  process.exit(2);
}

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)]);
}

// Pagefind's own UI bundle is generated and has no links of ours.
const pages = walk(dist).filter((f) => f.endsWith('.html') && !/[\\/]pagefind[\\/]/.test(f));
if (!pages.length) {
  console.error(`No .html pages in ${dist}/. Wrong folder, or the build failed.`);
  process.exit(2);
}
// A malformed %-escape is a broken link, not a crash.
const decode = (x) => { try { return decodeURIComponent(x); } catch { return null; } };
const idCache = new Map();

function idsOf(file) {
  if (!idCache.has(file)) {
    const html = readFileSync(file, 'utf8');
    idCache.set(file, new Set([...html.matchAll(/\s(?:id|name)=["']?([^"'\s>]+)/g)].map((m) => m[1])));
  }
  return idCache.get(file);
}

// URL path ('/help/logging/') -> the dist file that serves it, or null.
function resolveTarget(urlPath) {
  const d = decode(urlPath);
  if (d === null) return null;
  const p = d.replace(/^\//, '');
  const base = join(dist, p);
  const candidates = [base, join(base, 'index.html'), `${base}.html`];
  return candidates.find((c) => existsSync(c) && statSync(c).isFile()) || null;
}

// Known, accepted misses ("page raw"). Keep this short; each needs a reason.
// 404.html: its canonical is /404/, which GitHub Pages does not serve (it serves
// 404.html for any miss). Harmless for a 404 page; fix in BaseLayout if it matters.
const KNOWN = new Set(['404.html https://badger.fit/404/']);

const broken = [];
let checked = 0;
for (const page of pages) {
  const html = readFileSync(page, 'utf8');
  // The page's own URL path, for resolving relative links.
  const rel = relative(dist, page).split('\\').join('/');
  const pageUrl = '/' + rel.replace(/(^|\/)index\.html$/, '$1').replace(/\.html$/, '');
  for (const m of html.matchAll(/\s(href|src)=["']?([^"'\s>]+)/g)) {
    const raw = m[2].replace(/&amp;/g, '&');
    if (/^(mailto:|tel:|data:|javascript:|sms:)/i.test(raw)) continue;
    let url;
    try {
      url = new URL(raw, `https://${SITE_HOST}${pageUrl}`);
    } catch {
      broken.push(`${rel}: unparseable ${m[1]}="${raw}"`);
      continue;
    }
    if (url.hostname !== SITE_HOST && url.hostname !== `www.${SITE_HOST}`) continue;
    checked++;
    const target = resolveTarget(url.pathname);
    if (!target && KNOWN.has(`${rel} ${raw}`)) continue;
    if (!target) {
      broken.push(`${rel}: ${raw} -> no file for ${url.pathname}`);
      continue;
    }
    const frag = url.hash.slice(1);
    if (frag && target.endsWith('.html') && !idsOf(target).has(decode(frag))) {
      broken.push(`${rel}: ${raw} -> no id="${frag}" on ${posix.normalize(url.pathname)}`);
    }
  }
}

if (broken.length) {
  for (const b of broken) console.log(b);
  console.log(`\n${broken.length} broken of ${checked} internal links in ${pages.length} pages.`);
  process.exit(1);
}
console.log(`OK: ${checked} internal links in ${pages.length} pages all resolve.`);

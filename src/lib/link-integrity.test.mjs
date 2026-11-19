// Static link and meta checks over the .astro sources, so they run without a build.
// CLAUDE.md: after a release merge, every #anchor in the three shared index files
// must resolve to a real id= on its target page.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mainNav, footerGroups, helpOrder, guideOrder } from './wayfinding.mjs';
import { slugify } from './heading-anchors.mjs';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel) => readFileSync(join(root, rel), 'utf8');

// '/help/logging/' -> the source file that renders it, or null.
function pageFile(path) {
  const p = path.replace(/^\/|\/$/g, '');
  for (const c of [`src/pages/${p || 'index'}.astro`, `src/pages/${p}/index.astro`]) {
    if (existsSync(join(root, c))) return c;
  }
  return null;
}

function walk(dir) {
  return readdirSync(join(root, dir), { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)]);
}

// Ids a page can end up with: literal id="", and slugs of h2/h3 headings (the layout adds them).
function idsOf(file) {
  const src = read(file);
  const ids = new Set([...src.matchAll(/\bid=["']([^"'{}]+)["']/g)].map((m) => m[1]));
  for (const m of src.matchAll(/<h[23]\b[^>]*>([\s\S]*?)<\/h[23]>/g)) {
    const text = m[1].replace(/<[^>]*>/g, '').trim();
    if (text && !text.includes('{')) ids.add(slugify(text));
  }
  return ids;
}

const indexFiles = [
  'src/components/HelpSidebar.astro',
  'src/pages/guides/overview.astro',
  'src/pages/help/index.astro',
];

function internalHrefs(src) {
  return [...src.matchAll(/href=\{?[`"'](\/[^`"'?]*)[`"']/g)].map((m) => m[1]);
}

test('every internal link in the three shared index files points at a real page', () => {
  const dead = [];
  for (const f of indexFiles) {
    for (const href of internalHrefs(read(f))) {
      const [path] = href.split('#');
      if (path === '/' || /\.\w+$/.test(path)) continue; // home, or a file under public/
      if (!pageFile(path) && !existsSync(join(root, 'public', path))) dead.push(`${f}: ${href}`);
    }
  }
  assert.deepEqual(dead, []);
});

test('every #anchor in the three shared index files resolves to an id on its target page', () => {
  const dead = [];
  for (const f of indexFiles) {
    for (const href of internalHrefs(read(f))) {
      const [path, hash] = href.split('#');
      if (!hash) continue;
      const target = path ? pageFile(path) : f;
      if (!target) continue; // reported by the previous test
      if (!idsOf(target).has(hash)) dead.push(`${f}: ${href}`);
    }
  }
  assert.deepEqual(dead, []);
});

test('every wayfinding nav, footer and order link has a page behind it', () => {
  const hrefs = [
    ...mainNav.map((n) => n.href),
    ...footerGroups.flatMap((g) => g.links.map((l) => l.href)),
    ...helpOrder.map(([h]) => h),
    ...guideOrder.map(([h]) => h),
  ].filter((h) => h !== '/');
  const dead = hrefs.filter((h) => !pageFile(h.split('#')[0]));
  assert.deepEqual(dead, []);
});

test('footer anchors resolve to ids on their pages', () => {
  const dead = footerGroups.flatMap((g) => g.links).map((l) => l.href).filter((h) => h.includes('#'))
    .filter((h) => {
      const [path, hash] = h.split('#');
      return !idsOf(pageFile(path)).has(hash);
    });
  assert.deepEqual(dead, []);
});

test('every help and guide page is in the reading order', () => {
  const listed = new Set([...helpOrder, ...guideOrder].map(([h]) => h.replace(/\/$/, '')));
  const unlisted = [];
  for (const dir of ['help', 'guides']) {
    for (const f of walk(`src/pages/${dir}`)) {
      const slug = f.replace(/^src\/pages/, '').replace(/\.astro$/, '');
      if (slug.endsWith('/index')) continue;
      if (!listed.has(slug)) unlisted.push(slug);
    }
  }
  assert.deepEqual(unlisted, []);
});

test('ids within one page are unique, so an anchor cannot land on the wrong element', () => {
  const dup = [];
  for (const f of walk('src/pages').filter((x) => x.endsWith('.astro') && !x.includes('/review/'))) {
    const ids = [...read(f).matchAll(/\bid=["']([^"'{}]+)["']/g)].map((m) => m[1]);
    const seen = new Set();
    for (const id of ids) { if (seen.has(id)) dup.push(`${f}#${id}`); seen.add(id); }
  }
  assert.deepEqual(dup, []);
});

// ---- BaseLayout head: CSP and meta ----

const layout = read('src/layouts/BaseLayout.astro');
const csp = layout.match(/http-equiv="content-security-policy"\s+content="([^"]+)"/)?.[1] ?? '';
const directive = (name) => csp.split(';').map((s) => s.trim()).find((s) => s.startsWith(`${name} `));

test('the CSP meta tag comes before every script, link and the viewport, since it only governs what follows', () => {
  assert.ok(csp, 'no CSP meta tag');
  const head = layout.slice(layout.indexOf('<head>'));
  const at = head.indexOf('content-security-policy');
  assert.ok(at > 0);
  for (const later of ['<script', '<link', 'name="viewport"', '<title']) {
    assert.ok(at < head.indexOf(later), `CSP must precede ${later}`);
  }
});

test('script-src allows only self and the two analytics hosts, with no wildcard or bare scheme', () => {
  const sources = directive('script-src').split(/\s+/).slice(1);
  const hosts = sources.filter((s) => !s.startsWith("'"));
  assert.deepEqual(hosts.sort(), ['https://gc.zgo.at', 'https://static.cloudflareinsights.com']);
  assert.ok(sources.includes("'self'"));
  assert.ok(!sources.some((s) => ['*', 'https:', 'http:', 'data:', 'blob:'].includes(s)));
});

test('the CSP locks base-uri, form-action and object-src', () => {
  assert.equal(directive('base-uri'), "base-uri 'self'");
  assert.equal(directive('form-action'), "form-action 'none'");
  assert.equal(directive('object-src'), "object-src 'none'");
});

test('every external script on the layout is https and on a host the CSP allows', () => {
  const allowed = directive('script-src').split(/\s+/).filter((s) => s.startsWith('https://'));
  // Both literal <script src="..."> tags and scripts injected with `.src = '...'`.
  const srcs = [
    ...layout.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["']/g),
    ...layout.matchAll(/\.src\s*=\s*["']([^"']+)["']/g),
  ].map((m) => m[1]);
  assert.ok(srcs.length >= 2);
  for (const s of srcs) {
    if (!/^(https?:)?\/\//.test(s)) continue;
    const url = s.startsWith('//') ? `https:${s}` : s;
    assert.ok(url.startsWith('https://'), `${s} is not https`);
    assert.ok(allowed.some((a) => url.startsWith(a + '/')), `${s} is blocked by the CSP`);
  }
});

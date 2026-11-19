import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  strip, mainNav, footerGroups, sectionOf, browseLabel, helpOrder, guideOrder, defaultNext, getTheApp, searchHref,
} from './wayfinding.mjs';

test('strip drops one trailing slash, keeps the root, and tolerates empty input', () => {
  assert.equal(strip('/help/logging/'), '/help/logging');
  assert.equal(strip('/help/logging'), '/help/logging');
  assert.equal(strip('/'), '/');
  assert.equal(strip(''), '/');
  assert.equal(strip(undefined), '/');
});

test('Guides lights up on the 5/3/1 calculator, Programs only on its own page', () => {
  const by = Object.fromEntries(mainNav.map((n) => [n.label, n.match]));
  assert.equal(by.Guides('/tools/531-calculator'), true);
  assert.equal(by.Guides('/guides/ai'), true);
  assert.equal(by.Guides('/guides'), true);
  assert.equal(by.Programs('/programs'), true);
  assert.equal(by.Programs('/programs/sheets'), false);
});

test('a path lights exactly one header entry, and prefix lookalikes light none', () => {
  const lit = (p) => mainNav.filter((n) => n.match(p)).map((n) => n.label);
  assert.deepEqual(lit('/help/logging'), ['Help']);
  assert.deepEqual(lit('/glossary'), ['Glossary']);
  assert.deepEqual(lit('/helpful'), []);
  assert.deepEqual(lit('/guidesx'), []);
  assert.deepEqual(lit('/'), []);
});

test('sectionOf buckets pages and gives legal and unknown pages none', () => {
  assert.equal(sectionOf('/help/'), 'help');
  assert.equal(sectionOf('/help/body/'), 'help');
  assert.equal(sectionOf('/tools/531-calculator/'), 'guides');
  assert.equal(sectionOf('/guides/ai'), 'guides');
  assert.equal(sectionOf('/glossary/'), 'reference');
  assert.equal(sectionOf('/changelog'), 'reference');
  assert.equal(sectionOf('/legal/privacy/'), null);
  assert.equal(sectionOf('/helpdesk'), null);
  assert.equal(sectionOf('/'), null);
});

test('browseLabel names the index pages and falls back to plain Browse', () => {
  assert.equal(browseLabel('/help/'), 'Browse help topics');
  assert.equal(browseLabel('/guides'), 'Browse guides');
  assert.equal(browseLabel('/help/logging/'), 'Browse');
  assert.equal(browseLabel('/'), 'Browse');
});

test('every nav, footer and order list entry is an absolute path with a trailing slash', () => {
  const hrefs = [
    ...mainNav.map((n) => n.href),
    ...footerGroups.flatMap((g) => g.links.map((l) => l.href)),
    ...helpOrder.map(([h]) => h),
    ...guideOrder.map(([h]) => h),
  ];
  for (const h of hrefs) assert.match(h, /^\/([^?#]*\/)?(#[\w-]+)?$/, h);
});

test('no page appears twice in the help or guide reading order', () => {
  for (const list of [helpOrder, guideOrder]) {
    const hrefs = list.map(([h]) => h);
    assert.equal(new Set(hrefs).size, hrefs.length);
    const labels = list.map(([, l]) => l);
    assert.equal(new Set(labels).size, labels.length);
  }
});

test('a help page points to the next topic, all topics, and the guides', () => {
  const out = defaultNext('/help/logging/');
  assert.deepEqual(out.map((l) => l.href), ['/help/set-types/', '/help/', '/guides/']);
  assert.equal(out[0].note, 'Next topic');
});

test('the last help page has no next topic but still ends with two links', () => {
  const last = helpOrder[helpOrder.length - 1][0];
  const out = defaultNext(last);
  assert.deepEqual(out.map((l) => l.href), ['/help/', '/guides/']);
});

test('defaultNext ignores the trailing slash on the path', () => {
  assert.deepEqual(defaultNext('/help/goals'), defaultNext('/help/goals/'));
  assert.deepEqual(defaultNext('/guides/ai'), defaultNext('/guides/ai/'));
});

test('a program guide links to Programs; other guides link back to the guide list', () => {
  const prog = defaultNext('/guides/gzclp-app/');
  assert.ok(prog.some((l) => l.href === '/programs/'));
  assert.ok(!prog.some((l) => l.href === '/guides/'));
  const plain = defaultNext('/guides/switching/');
  assert.ok(plain.some((l) => l.href === '/guides/'));
  assert.ok(!plain.some((l) => l.href === '/programs/'));
});

test('program-guide membership matches the guides whose label names a program', () => {
  // guideOrder.slice(11, 17) is a positional range; reordering the list must not silently change it.
  const withPrograms = guideOrder
    .filter(([h]) => defaultNext(h).some((l) => l.href === '/programs/'))
    .map(([h]) => h);
  assert.deepEqual(withPrograms, [
    '/guides/stronglifts-5x5-tracker/', '/guides/gzclp-app/', '/guides/531-app/',
    '/guides/nsuns-app/', '/guides/madcow-app/', '/guides/starting-strength-app/',
  ]);
});

test('every guide ends with the app link, and the last guide has no next guide', () => {
  for (const [h] of guideOrder) assert.deepEqual(defaultNext(h).at(-1), getTheApp);
  const last = guideOrder[guideOrder.length - 1][0];
  assert.ok(!defaultNext(last).some((l) => l.note === 'Next guide'));
});

test('pages outside the reading orders get no Next block', () => {
  assert.deepEqual(defaultNext('/glossary/'), []);
  assert.deepEqual(defaultNext('/help/'), []);
  assert.deepEqual(defaultNext('/'), []);
});

test('the search link targets the id the help sidebar search field defines', async () => {
  const { readFile } = await import('node:fs/promises');
  const id = searchHref.split('#')[1];
  const page = await readFile(new URL('../components/HelpSidebar.astro', import.meta.url), 'utf8');
  assert.match(page, new RegExp(`id=["']${id}["']`));
});

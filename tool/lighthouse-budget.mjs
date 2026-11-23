#!/usr/bin/env node
// Lighthouse budget for the BUILT site (run `npm run build` first).
// Budget from docs/2026-07-16-journal-site-redesign-spec.md section 7:
// mobile emulation, >= 95 on Performance, Accessibility, Best Practices and SEO,
// and CLS = 0.
//
// Serves dist/ with `astro preview` on a spare port, runs Lighthouse (pinned,
// via npx; needs Google Chrome installed) RUNS times per page and takes the
// median of each number (Lighthouse's own advice for score variance; the first
// cold run on this Mac scored home 62 against a steady 92), prints one line per
// page, then stops the server.
//
// Usage: node tool/lighthouse-budget.mjs [/path/ ...]
//   default pages: / /promise/ /help/getting-started/
// Exit 0 = every page within budget. Exit 1 = at least one miss. Exit 2 = could not run.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const LIGHTHOUSE = 'lighthouse@13.4.0';
const PORT = 4329;
const MIN_SCORE = 95;
const RUNS = 3;
const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
const pages = process.argv.slice(2).length ? process.argv.slice(2) : ['/', '/promise/', '/help/getting-started/'];

if (!existsSync('dist')) {
  console.error('No dist/ folder. Run npm run build first.');
  process.exit(2);
}

async function answers() {
  try { return (await fetch(`http://localhost:${PORT}/`)).ok; } catch { return false; }
}
if (await answers()) {
  console.error(`Port ${PORT} is already in use (a stale preview?). Stop it and rerun.`);
  process.exit(2);
}

// astro directly (no npx wrapper) in its own process group, so stopping it
// cannot leave a child holding the port.
const server = spawn('node_modules/.bin/astro', ['preview', '--port', String(PORT)], { stdio: 'ignore', detached: true });
server.on('error', (e) => { console.error(`Could not start astro preview: ${e.message}`); process.exit(2); });
const stop = () => { try { process.kill(-server.pid); } catch {} };
process.on('exit', stop);

async function waitForServer() {
  for (let i = 0; i < 60; i++) {
    if (await answers()) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`astro preview did not answer on port ${PORT} within 30 s`);
}

const out = mkdtempSync(join(tmpdir(), 'lh-'));
let misses = 0;
try {
  await waitForServer();
  for (const page of pages) {
    const file = join(out, 'report.json');
    const runs = [];
    for (let i = 0; i < RUNS; i++) {
      execFileSync('npx', ['--yes', LIGHTHOUSE, `http://localhost:${PORT}${page}`,
        '--quiet', '--output=json', `--output-path=${file}`,
        '--only-categories=performance,accessibility,best-practices,seo',
        '--chrome-flags=--headless=new'], { stdio: ['ignore', 'ignore', 'inherit'], timeout: 180_000 });
      const lhr = JSON.parse(readFileSync(file, 'utf8'));
      runs.push({
        ...Object.fromEntries(Object.entries(lhr.categories).map(([k, v]) => [k, Math.round((v.score ?? 0) * 100)])),
        cls: lhr.audits['cumulative-layout-shift']?.numericValue ?? NaN,
      });
    }
    const scores = Object.fromEntries(['performance', 'accessibility', 'best-practices', 'seo']
      .map((k) => [k, median(runs.map((r) => r[k]))]));
    const cls = median(runs.map((r) => r.cls));
    const failed = Object.entries(scores).filter(([, s]) => s < MIN_SCORE).map(([k]) => k);
    if (!(cls === 0)) failed.push(`CLS ${cls.toFixed(3)}`);
    if (failed.length) misses++;
    console.log(`${failed.length ? 'MISS' : 'OK  '} ${page}  perf ${scores.performance} a11y ${scores.accessibility} ` +
      `bp ${scores['best-practices']} seo ${scores.seo} CLS ${cls}${failed.length ? `  <- ${failed.join(', ')}` : ''}`);
  }
} catch (e) {
  console.error(`Could not run: ${e.message}`);
  stop();
  rmSync(out, { recursive: true, force: true });
  process.exit(2);
}
stop();
rmSync(out, { recursive: true, force: true });
process.exit(misses ? 1 : 0);

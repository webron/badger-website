// Test helper: have LibreOffice calculate a grid's formulas.
//
// The workbook is written WITHOUT cached results, so the only way a number can
// appear in LibreOffice's CSV export is by evaluating the formula. Comparing
// that against the numbers the generator cached proves the formulas and the
// generator's own arithmetic agree. One soffice start handles every file.

import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { writeXlsx } from './xlsx.mjs';

export function sofficePath() {
  for (const p of ['/opt/homebrew/bin/soffice', '/usr/bin/soffice', '/usr/bin/libreoffice', '/Applications/LibreOffice.app/Contents/MacOS/soffice']) {
    const r = spawnSync(p, ['--version'], { encoding: 'utf8' });
    if (r.status === 0) return p;
  }
  return null;
}

/** Minimal CSV reader: quotes, doubled quotes, commas and newlines inside quotes. */
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(field); field = ''; }
    else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(field); rows.push(row); row = []; field = '';
    } else field += ch;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows;
}

/** @param {Record<string, import('./grid.mjs').Grid>} grids name -> grid. Returns name -> rows of strings. */
export function recalc(soffice, grids) {
  const dir = mkdtempSync(join(tmpdir(), 'sheets-lo-'));
  const out = join(dir, 'out');
  mkdirSync(out);
  const files = [];
  for (const [name, grid] of Object.entries(grids)) {
    const f = join(dir, `${name}.xlsx`);
    writeFileSync(f, writeXlsx(grid, { omitCache: true }));
    files.push(f);
  }
  const r = spawnSync(
    soffice,
    [`-env:UserInstallation=file://${join(dir, 'profile')}`, '--headless', '--convert-to', 'csv', '--outdir', out, ...files],
    { encoding: 'utf8', timeout: 240000 },
  );
  if (r.status !== 0) throw new Error(`soffice failed: ${r.stderr}`);
  const result = {};
  for (const name of Object.keys(grids)) result[name] = parseCsv(readFileSync(join(out, `${name}.csv`), 'utf8'));
  return result;
}

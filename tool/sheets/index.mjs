// Builds one .xlsx and one .csv per program in public/programs/.
//
//   node tool/sheets/index.mjs          write public/programs/sheets/*
//   node tool/sheets/index.mjs --check  fail if a committed sheet is out of date
//
// The input is the .badger files the app itself exported (badger-fit
// test/tools/program_gallery_export_test.dart), so every set, percentage and
// rule on a sheet is the app's. Regenerate after the gallery files change.

import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeXlsx } from './xlsx.mjs';
import { writeCsv } from './csv.mjs';
import { builderFor } from './builders.mjs';
import { SITE } from './common.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const PROGRAMS_DIR = join(ROOT, 'public', 'programs');
export const SHEETS_DIR = join(PROGRAMS_DIR, 'sheets');

// Where each program is explained on the site. Programs without a guide page
// link to the gallery.
const PAGE = {
  gzclp: '/guides/gzclp-app/',
  '531-bbb': '/guides/531-app/',
  'nsuns-531lp': '/guides/nsuns-app/',
  'madcow-5x5': '/guides/madcow-app/',
  'starting-strength': '/guides/starting-strength-app/',
  'stronglifts-5x5': '/guides/stronglifts-5x5-tracker/',
};

export const sheetName = (slug, ext) => `${slug}-spreadsheet.${ext}`;

export function programSlugs() {
  return readdirSync(PROGRAMS_DIR)
    .filter((f) => f.endsWith('.badger') && f !== 'example-routine.badger')
    .map((f) => f.replace(/\.badger$/, ''))
    .sort();
}

export function buildProgram(slug, dir = PROGRAMS_DIR) {
  const file = JSON.parse(readFileSync(join(dir, `${slug}.badger`), 'utf8'));
  const payload = file.payload;
  const ctx = {
    payload,
    appVersion: file.app_version,
    slug,
    pageUrl: `${SITE}${PAGE[slug] ?? '/programs/'}`,
    title: `${payload.routine.name} spreadsheet`,
  };
  const grid = builderFor(payload)(ctx);
  return { grid, xlsx: writeXlsx(grid), csv: writeCsv(grid) };
}

function main() {
  const check = process.argv.includes('--check');
  if (!check) mkdirSync(SHEETS_DIR, { recursive: true });
  const stale = [];
  for (const slug of programSlugs()) {
    const { xlsx, csv } = buildProgram(slug);
    for (const [ext, data] of [['xlsx', xlsx], ['csv', Buffer.from(csv)]]) {
      const path = join(SHEETS_DIR, sheetName(slug, ext));
      if (check) {
        if (!existsSync(path) || !Buffer.from(readFileSync(path)).equals(Buffer.from(data))) stale.push(path);
      } else {
        writeFileSync(path, data);
      }
    }
  }
  if (check && stale.length) {
    console.error(`Out of date, run "npm run sheets":\n${stale.join('\n')}`);
    process.exit(1);
  }
  console.log(check ? 'Sheets are up to date.' : `Wrote ${programSlugs().length * 2} files to public/programs/sheets/.`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();

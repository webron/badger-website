// Tests for the program spreadsheet generator.
// Run: npm run test:sheets   (node --test tool/sheets)
//
// What is proved here, and how:
//  1. Every sheet is built from the program's own .badger file: the distinct
//     percentages and the progression amounts in the file all appear on the sheet.
//  2. The committed files are what the generator makes now (no drift).
//  3. The formulas calculate to the numbers the generator cached. This asks
//     LibreOffice to evaluate a copy with no cached results. Skipped, with a
//     message, on a machine without LibreOffice.
//  4. Known weights match the app's arithmetic, in kg and in lb, worked out by
//     hand from reference_weight.dart (nearest-plate rounding, the bar floor,
//     the "must add at least one step" rule) and rule_amount.dart (kg/lb pairs).

import test, { before } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { unzipSync, strFromU8 } from 'fflate';
import { PROGRAMS_DIR, SHEETS_DIR, programSlugs, sheetName, buildProgram } from './index.mjs';
import { SETTINGS_ROW } from './common.mjs';
import { Grid } from './grid.mjs';
import { writeCsv } from './csv.mjs';
import { sofficePath, recalc } from './lo-recalc.mjs';

const slugs = programSlugs();
const built = Object.fromEntries(slugs.map((s) => [s, buildProgram(s)]));
const payloadOf = (slug) => JSON.parse(readFileSync(join(PROGRAMS_DIR, `${slug}.badger`), 'utf8')).payload;

const cellsOf = (grid) => [...grid.cells.entries()].map(([k, c]) => ({ r: +k.split(',')[0], c: +k.split(',')[1], ...c }));

function findRow(grid, text, from = 0) {
  for (let r = from; r < grid.rowCount; r++) if (grid.get(r, 0)?.v === text) return r;
  throw new Error(`No row "${text}" after row ${from}`);
}

function clone(grid) {
  const g = new Grid(grid.name);
  Object.assign(g, { widths: grid.widths, validations: grid.validations, freezeRows: grid.freezeRows, title: grid.title });
  for (const [k, v] of grid.cells) g.cells.set(k, { ...v });
  return g;
}

const lbVariant = (grid) => {
  const g = clone(grid);
  g.get(SETTINGS_ROW.unit, 1).v = 'lb';
  return g;
};

// ── 1. Built from the app's files ───────────────────────────────────────────

test('every program in the gallery gets an xlsx and a csv', () => {
  assert.equal(slugs.length, 11);
  for (const slug of slugs) {
    assert.ok(built[slug].xlsx.length > 1000, slug);
    assert.ok(built[slug].csv.startsWith(`${payloadOf(slug).routine.name} spreadsheet`), slug);
  }
});

test('the xlsx is a zip with the parts a spreadsheet app needs', () => {
  for (const slug of slugs) {
    const files = unzipSync(built[slug].xlsx);
    for (const part of ['[Content_Types].xml', 'xl/workbook.xml', 'xl/worksheets/sheet1.xml', 'xl/styles.xml']) {
      assert.ok(files[part], `${slug} lacks ${part}`);
    }
    const sheet = strFromU8(files['xl/worksheets/sheet1.xml']);
    const ruled = payloadOf(slug).days.some((d) => d.exercises.some((e) => e.progression));
    assert.equal(/<f>/.test(sheet), ruled, `${slug}: formulas exactly when the program has rules`);
  }
});

test('program-bearing sheets show every percentage and every rule amount from the file', () => {
  for (const slug of slugs) {
    const payload = payloadOf(slug);
    const ex = payload.days.flatMap((d) => d.exercises);
    const pcts = new Set(ex.flatMap((e) => e.predefined_sets.filter((s) => !s.is_warmup && s.percent_of_reference != null).map((s) => s.percent_of_reference)));
    const cells = cellsOf(built[slug].grid);
    const sheetPcts = new Set(cells.filter((c) => c.s === 'pct').map((c) => c.v));
    assert.deepEqual([...sheetPcts].sort((a, b) => a - b), [...pcts].sort((a, b) => a - b), `${slug} percentages`);

    // Every increment a rule adds on success, as a number in an input cell.
    const amounts = new Set(
      ex.flatMap((e) => e.progression?.clauses ?? [])
        .filter((c) => c.action === 'add_absolute' && ['all_sets_met', 'cycle_complete', 'driver_reps_between', 'driver_reps_at_least'].includes(c.trigger))
        .map((c) => c.amount),
    );
    const incCells = new Set(cells.filter((c) => c.f?.includes('"lb"') && typeof c.v === 'number').map((c) => c.v));
    for (const a of amounts) assert.ok(incCells.has(a) || cells.some((c) => c.f?.includes(`,${a},`) || c.f?.includes(`,${a})`)), `${slug}: ${a} kg increment missing`);
  }
});

test('every exercise in the file is on its sheet', () => {
  for (const slug of slugs) {
    const names = new Set(payloadOf(slug).days.flatMap((d) => d.exercises.map((e) => e.exercise_name)));
    const text = writeCsv(built[slug].grid);
    for (const n of names) {
      // Accessories appear in a one-line list, the rest as their own rows.
      assert.ok(text.includes(n), `${slug} lacks ${n}`);
    }
  }
});

test('no formula or text carries a stray null or undefined', () => {
  for (const slug of slugs) {
    for (const c of cellsOf(built[slug].grid)) {
      assert.doesNotMatch(String(c.f ?? ''), /null|undefined|NaN/, `${slug} formula ${c.f}`);
      assert.doesNotMatch(String(c.v ?? ''), /null|undefined|NaN/, `${slug} cell ${c.v}`);
    }
  }
});

test('a rule block names the lifts it covers, so each lift prints its own increment', () => {
  const csv = built['531-bbb'].csv;
  assert.match(csv, /Overhead Barbell Press, Flat Barbell Bench Press"[\s\S]{0,200}?add 2\.5 kg \/ 5 lb/);
  assert.match(csv, /"Deadlift, Barbell Back Squat"[\s\S]{0,200}?add 5 kg \/ 10 lb/);
  assert.match(built.gzclp.csv, /After failing at the last stage, go back to stage 1/);
});

test('no dashes or curly quotes in anything a sheet says (docs/writing_style.md)', () => {
  for (const slug of slugs) {
    const text = writeCsv(built[slug].grid);
    assert.doesNotMatch(text, /[–—‘’“”]/, slug);
  }
});

test('a sheet links to the app, its page and the progression help', () => {
  for (const slug of slugs) {
    const csv = built[slug].csv;
    assert.match(csv, /https:\/\/badger\.fit\/#download/, slug);
    assert.match(csv, /https:\/\/badger\.fit\/help\/progression\//, slug);
    assert.match(csv, /Run this program in Badger: https:\/\/badger\.fit\/(guides|programs)\//, slug);
  }
});

// ── 2. No drift ─────────────────────────────────────────────────────────────

test('the committed sheets are what the generator makes now', () => {
  for (const slug of slugs) {
    for (const [ext, data] of [['xlsx', built[slug].xlsx], ['csv', Buffer.from(built[slug].csv)]]) {
      const path = join(SHEETS_DIR, sheetName(slug, ext));
      assert.ok(existsSync(path), `${path} is missing, run npm run sheets`);
      assert.ok(Buffer.from(readFileSync(path)).equals(Buffer.from(data)), `${path} is stale, run npm run sheets`);
    }
  }
});

test('building twice gives identical bytes', () => {
  const again = buildProgram('gzclp');
  assert.ok(Buffer.from(again.xlsx).equals(Buffer.from(built.gzclp.xlsx)));
});

// ── 3 and 4. Formulas and the app's arithmetic, through LibreOffice ─────────

const soffice = sofficePath();
const skip = soffice ? false : 'LibreOffice not installed';
let calc = {};

// nSuns with reps typed in: bench T1 got 5 reps on week 1's 1+ set, 1 rep on
// week 2's, 6 on week 3's; incline T2 (the second T2 block is press T2) all sets done.
function nsunsWithInputs() {
  const g = clone(built['nsuns-531lp'].grid);
  const t1 = findRow(g, 'Bench / Press: Flat Barbell Bench Press (tier 1)');
  const inRow = findRow(g, 'Reps you got on the 1+ set', t1);
  g.set(inRow, 3, 5, { s: 'input' });
  g.set(inRow, 4, 1, { s: 'input' });
  g.set(inRow, 5, 6, { s: 'input' });
  const t2 = findRow(g, 'Bench / Press: Overhead Barbell Press (tier 2)');
  const yn = findRow(g, 'All sets done? (Y or N)', t2);
  g.set(yn, 3, 'y', { s: 'input' });
  g.set(yn, 4, 'N', { s: 'input' });
  return g;
}

before(() => {
  if (!soffice) return;
  const inputs = {};
  for (const slug of slugs) inputs[`kg-${slug}`] = built[slug].grid;
  for (const slug of ['531-bbb', 'madcow-5x5', 'nsuns-531lp', 'gzclp', 'stronglifts-5x5', 'starting-strength']) {
    inputs[`lb-${slug}`] = lbVariant(built[slug].grid);
  }
  inputs['nsuns-inputs'] = nsunsWithInputs();
  calc = recalc(soffice, inputs);
});

const num = (rows, r, c) => Number(rows[r][c]);

test('LibreOffice calculates every formula to the number the generator cached', { skip }, () => {
  let checked = 0;
  for (const slug of slugs) {
    const rows = calc[`kg-${slug}`];
    for (const cell of cellsOf(built[slug].grid)) {
      if (!cell.f || typeof cell.v !== 'number') continue;
      const got = num(rows, cell.r, cell.c);
      assert.ok(Math.abs(got - cell.v) < 1e-9, `${slug} ${cell.r},${cell.c}: sheet ${got}, cached ${cell.v}, formula ${cell.f}`);
      checked += 1;
    }
  }
  assert.ok(checked > 500, `only ${checked} formulas checked`);
});

function weekRow(rows, grid, block, label, nth = 0) {
  let r = findRow(grid, block);
  for (let i = 0; i <= nth; i++) r = findRow(grid, label, r + (i ? 1 : 0));
  return r;
}

test('5/3/1: weights round to the nearest plate and never fall below the bar', { skip }, () => {
  const grid = built['531-bbb'].grid;
  const press = findRow(grid, 'Press Day: Overhead Barbell Press');
  const wk1 = findRow(grid, 'Week 1', press);
  const wk4 = findRow(grid, 'Week 4', press);
  const kg = calc['kg-531-bbb'];
  // TM 45 kg. 65% = 29.25 -> 30. 75% = 33.75 is exactly half way between 32.5
  // and 35, and the app's plate snap sends a tie DOWN (equipment_snapper.dart,
  // _plateSnap): 32.5. 85% = 38.25 -> 37.5.
  assert.deepEqual([0, 1, 2].map((i) => num(kg, wk1 + i, 3)), [30, 32.5, 37.5]);
  // Cycle 2 TM is 47.5: 65% = 30.875 -> 30.
  assert.equal(num(kg, wk1, 4), 30);
  // Week 4, 40% of 45 = 18 -> 17.5, which is under the 20 kg bar: the bar.
  assert.equal(num(kg, wk4, 3), 20);
  // In pounds: TM 105, +5 lb per cycle (the 2.5 kg / 5 lb pair), 5 lb plates, 45 lb bar.
  const lb = calc['lb-531-bbb'];
  assert.deepEqual([0, 1, 2].map((i) => num(lb, wk1 + i, 3)), [70, 80, 90]);
  assert.equal(num(lb, wk4, 3), 45);
  const tmRow = findRow(grid, 'Training max', press);
  assert.deepEqual([3, 4, 5].map((c) => num(lb, tmRow, c)), [105, 110, 115]);
});

test('Madcow: +1.25 kg on a 2.5 kg grid still adds a full step, in pounds the pair is +2.5 lb', { skip }, () => {
  const grid = built['madcow-5x5'].grid;
  const bench = findRow(grid, 'Flat Barbell Bench Press');
  const kg = calc['kg-madcow-5x5'];
  assert.deepEqual([3, 4, 5, 6].map((c) => num(kg, bench, c)), [40, 42.5, 45, 47.5]);
  const lb = calc['lb-madcow-5x5'];
  assert.deepEqual([3, 4, 5, 6].map((c) => num(lb, bench, c)), [95, 100, 105, 110]);
  // Squat adds 2.5 kg a week from 60.
  const squat = findRow(grid, 'Barbell Back Squat');
  assert.deepEqual([3, 4, 5].map((c) => num(kg, squat, c)), [60, 62.5, 65]);
});

test('nSuns: the training max moves by the app\'s bands from the reps you type', { skip }, () => {
  const grid = built['nsuns-531lp'].grid;
  const g2 = nsunsWithInputs();
  const rows = calc['nsuns-inputs'];
  const t1 = findRow(g2, 'Bench / Press: Flat Barbell Bench Press (tier 1)');
  const tm = findRow(g2, 'Training max', t1);
  // 70 kg start. 5 reps -> +5 (4 to 5 band) = 75. 1 rep -> +0 = 75. 6 reps -> +7.5 = 82.5.
  assert.deepEqual([3, 4, 5, 6].map((c) => num(rows, tm, c)), [70, 75, 75, 82.5]);
  // 95% set of 75 = 71.25 is half way between 70 and 72.5: a tie goes down, 70.
  const set3 = findRow(g2, 'Set 3 (the 1+ set)', t1);
  assert.equal(num(rows, set3, 3), 67.5);
  assert.equal(num(rows, set3, 4), 70);
  // Tier 2 press: y (lower case) counts, N does not. 45 -> 47.5 -> 47.5.
  const t2 = findRow(g2, 'Bench / Press: Overhead Barbell Press (tier 2)');
  const tm2 = findRow(g2, 'Training max', t2);
  assert.deepEqual([3, 4, 5].map((c) => num(rows, tm2, c)), [45, 47.5, 47.5]);
  // Nothing typed: the training max holds.
  const blank = calc['kg-nsuns-531lp'];
  assert.deepEqual([3, 4, 5].map((c) => num(blank, findRow(grid, 'Training max', t1), c)), [70, 70, 70]);
  // In pounds, 50% of a 105 lb training max is 52.5, half way between 50 and 55: 50.
  const lbT2 = findRow(grid, 'Bench / Press: Overhead Barbell Press (tier 2)');
  const lbSet1 = findRow(grid, 'Set 1', lbT2);
  assert.equal(num(calc['lb-nsuns-531lp'], lbSet1, 3), 50);
  // The pound sheet steps +5 lb for the 2.5 kg pair only when reps are typed, so it also holds.
  assert.equal(num(calc['lb-nsuns-531lp'], findRow(grid, 'Training max', t1), 3), 155);
});

test('StrongLifts and GZCLP add the app\'s paired increments in pounds', { skip }, () => {
  const sl = built['stronglifts-5x5'].grid;
  const row = findRow(sl, 'Session 1');
  const squatCol = 2;
  const kg = calc['kg-stronglifts-5x5'];
  const lb = calc['lb-stronglifts-5x5'];
  // Session 1 and 3 and 5 train the squat on a 3-session rotation of A, B, A, B.
  assert.deepEqual([0, 1, 2].map((i) => num(kg, row + i, squatCol)), [60, 62.5, 65]);
  assert.deepEqual([0, 1, 2].map((i) => num(lb, row + i, squatCol)), [135, 140, 145]);
  // Deadlift is 1x5 on workout B only and adds 5 kg / 10 lb.
  const dlCol = 6;
  assert.deepEqual([1, 3].map((i) => num(kg, row + i, dlCol)), [60, 65]);
  assert.deepEqual([1, 3].map((i) => num(lb, row + i, dlCol)), [135, 145]);

  const gz = built.gzclp.grid;
  const wk = findRow(gz, 'Week 1', findRow(gz, 'Weight each week, if every set is made'));
  // Column 1 is Barbell Back Squat (T1): +5 kg a week from 60, +10 lb from 135.
  assert.deepEqual([0, 1, 2].map((i) => num(calc['kg-gzclp'], wk + i, 1)), [60, 65, 70]);
  assert.deepEqual([0, 1, 2].map((i) => num(calc['lb-gzclp'], wk + i, 1)), [135, 145, 155]);
});

void weekRow;

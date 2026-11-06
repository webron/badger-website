// Pieces every sheet shares: the title block, the unit and rounding settings,
// and the formula helpers that mirror the app's weight arithmetic.

import { Grid, ref } from './grid.mjs';
import { lbOf } from './rules.mjs';

export const SITE = 'https://badger.fit';
export const SETTINGS_ROW = { unit: 7, step: 8, bar: 9 };
export const UNIT = ref(SETTINGS_ROW.unit, 1, 'rc');
export const STEP = ref(SETTINGS_ROW.step, 1, 'rc');
export const BAR = ref(SETTINGS_ROW.bar, 1, 'rc');

/** Default rounding step, kg and lb. The app rounds to the plates the user owns. */
export const DEFAULT_STEP = { kg: 2.5, lb: 5 };
export const DEFAULT_BAR = { kg: 20, lb: 45 };

/**
 * The app rounds a derived load to the nearest loadable weight, and on a bar a
 * load exactly half way between two plates goes DOWN
 * (`(target - down) <= (up - target) ? down : up`, _plateSnap in
 * lib/features/workout/domain/equipment_snapper.dart). `ROUNDUP(x - 0.5)` is
 * that rule: 13.5 steps becomes 13, 13.6 becomes 14.
 */
export const snap = (raw, step = DEFAULT_STEP.kg) => Math.ceil(raw / step - 0.5) * step;

/** The same rounding as formula text. */
export const snapF = (rawExpr) => `ROUNDUP((${rawExpr})/${STEP}-0.5,0)*${STEP}`;

/**
 * A percentage set's load: nearest loadable weight, never below the bar
 * (`resolvePercentLoad` in lib/features/routines/domain/reference_weight.dart).
 */
export const percentLoad = (raw, step = DEFAULT_STEP.kg, bar = DEFAULT_BAR.kg) =>
  Math.max(snap(raw, step), bar);
export const percentF = (rawExpr) => `MAX(${snapF(rawExpr)},${BAR})`;

/**
 * The next working weight after a success: the previous weight plus the
 * increment, rounded to the nearest loadable weight, and never less than one
 * step up. A rule that says "add weight" must add weight
 * (`snapProposedLoad` with `expectsIncrease` in reference_weight.dart). This is
 * why Madcow's +1.25 kg moves a 2.5 kg grid by 2.5 kg.
 */
export function nextWorking(prev, incKg, step = DEFAULT_STEP.kg) {
  const v = snap(prev + incKg, step);
  return v <= prev + 0.0001 ? prev + step : v;
}
export const nextF = (prevRef, incRef) =>
  `MAX(ROUNDUP((${prevRef}+${incRef})/${STEP}-0.5,0)*${STEP},${prevRef}+${STEP})`;

/** A value that is `kg` in a kg sheet and `lb` in a pound sheet. */
export const unitF = (kg, lb) => `IF(${UNIT}="lb",${lb},${kg})`;

/** An increment: the kg amount, or the app's paired pound amount. */
export const incF = (kg) => unitF(kg, lbOf(kg));

/** Weekday names for the .badger `scheduled_days` numbers (1 = Monday). */
export const WEEKDAY = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/**
 * Start a sheet: title, source line, links, and the Setup block holding the unit
 * and rounding settings. Returns the grid and the next free row.
 */
export function startSheet({ payload, appVersion, slug, pageUrl, title, widths, settings = true }) {
  const g = new Grid('Plan');
  g.title = title;
  g.widths = widths;
  const name = payload.routine.name;
  g.set(0, 0, `${name} spreadsheet`, { s: 'title' });
  g.set(
    1,
    0,
    `Built from the ${name} program as Badger ${appVersion} exports it. The sets, reps and rules are the app's, and weights are worked out the way the app works them out.`,
    { s: 'note' },
  );
  g.set(2, 0, `Run this program in Badger: ${pageUrl}`, { s: 'link', link: pageUrl });
  g.set(3, 0, `Get the app: ${SITE}/#download`, { s: 'link', link: `${SITE}/#download` });
  g.set(4, 0, `How the rules work: ${SITE}/help/progression/`, {
    s: 'link',
    link: `${SITE}/help/progression/`,
  });

  if (!settings) return { g, row: 6 };
  g.set(6, 0, 'Setup', { s: 'section' });
  for (let c = 1; c < widths.length; c++) g.set(6, c, '', { s: 'section' });
  g.set(SETTINGS_ROW.unit, 0, 'Unit (kg or lb)', { s: 'bold' });
  g.set(SETTINGS_ROW.unit, 1, 'kg', { s: 'input' });
  g.validations.push({ ref: ref(SETTINGS_ROW.unit, 1), list: ['kg', 'lb'] });
  g.set(SETTINGS_ROW.step, 0, 'Round loads to the nearest', { s: 'bold' });
  g.set(SETTINGS_ROW.step, 1, DEFAULT_STEP.kg, {
    f: `IF(${UNIT}="lb",${DEFAULT_STEP.lb},${DEFAULT_STEP.kg})`,
    s: 'input',
  });
  g.set(SETTINGS_ROW.step, 2, 'Your smallest plate jump, both sides together. Type your own number over it.', {
    s: 'note',
  });
  g.set(SETTINGS_ROW.bar, 0, 'Bar weight', { s: 'bold' });
  g.set(SETTINGS_ROW.bar, 1, DEFAULT_BAR.kg, {
    f: `IF(${UNIT}="lb",${DEFAULT_BAR.lb},${DEFAULT_BAR.kg})`,
    s: 'input',
  });
  g.set(SETTINGS_ROW.bar, 2, 'A percentage set never comes out lighter than the bar.', { s: 'note' });
  g.set(
    10,
    0,
    'Yellow cells are yours to fill in. The numbers in them are examples, so type your own over them.',
    { s: 'note' },
  );
  return { g, row: 12 };
}

/** A section bar across `cols` columns. */
export function sectionBar(g, row, text, cols) {
  g.set(row, 0, text, { s: 'section' });
  for (let c = 1; c < cols; c++) g.set(row, c, '', { s: 'section' });
}

/** A header row. */
export function headerRow(g, row, labels) {
  labels.forEach((t, c) => g.set(row, c, t, { s: c === 0 ? 'headerLeft' : 'header' }));
}

/** Lines of plain text, one per row, from `row`. Returns the next free row. */
export function textLines(g, row, lines, s = 'normal') {
  for (const line of lines) g.set(row++, 0, line, { s });
  return row;
}

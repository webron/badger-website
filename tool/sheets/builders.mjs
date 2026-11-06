// One builder per program family. Each reads the program's own payload (the
// .badger file the app exported) and returns a Grid. Nothing about a lift's sets,
// percentages or rules is typed in here: it all comes from the file, so a change
// to a seeded program shows up in the sheet the next time the generator runs.
//
// Families, picked by the progression scheme the file carries:
//   wave_531       5/3/1 Boring But Big: percentages of a training max, 4-week wave
//   nsuns_t1/t2    nSuns 531LP: percentages of a training max that moves weekly
//   madcow_weekly  Madcow 5x5: percentages of a working weight that moves weekly
//   gzclp_t1/t2/t3 GZCLP: stage ladders, adds weight when every set is met
//   linear         StrongLifts 5x5, Starting Strength: add weight each session
//   (none)         the other five programs: a plan with a weight log

import { ref } from './grid.mjs';
import {
  snap, percentLoad, percentF, nextWorking, nextF, incF, unitF, WEEKDAY,
  startSheet, sectionBar, headerRow, textLines,
} from './common.mjs';
import { describeSets, ruleBlocks, successIncrementKg } from './rules.mjs';

// Example starting numbers, in kg and lb. They only fill the yellow cells so the
// sheet shows real figures on first open; the reader types over them.
const EXAMPLE = {
  'Barbell Back Squat': [100, 225],
  'Flat Barbell Bench Press': [70, 155],
  Deadlift: [120, 275],
  'Overhead Barbell Press': [45, 105],
  'Barbell Row': [60, 135],
  'Incline Barbell Bench Press': [50, 115],
  'Sumo Deadlift': [100, 225],
  'Lat Pulldown': [50, 110],
  'Dumbbell Row': [25, 55],
};
// Starting (not training-max) weights for the programs that begin light.
const START = {
  'Barbell Back Squat': [60, 135],
  'Flat Barbell Bench Press': [40, 95],
  Deadlift: [60, 135],
  'Overhead Barbell Press': [30, 65],
  'Barbell Row': [40, 95],
  'Lat Pulldown': [40, 90],
  'Dumbbell Row': [15, 35],
};
const lookup = (table, name) => table[name] ?? [40, 90];

/** An input cell holding an example that switches with the unit. */
function exampleInput(g, r, c, [kg, lb]) {
  g.set(r, c, kg, { f: unitF(kg, lb), s: 'input' });
}


/**
 * The closing "rules" section: one block per distinct rule, headed by the lifts
 * it covers, so each lift's own increment is the one printed.
 * `label(exercise)` names a lift in the heading.
 */
function writeRules(g, r, payload, cols, label = (e) => e.exercise_name) {
  sectionBar(g, r, 'The rules', cols);
  r += 1;
  const ruled = payload.days.flatMap((d) => d.exercises).filter((e) => e.progression);
  for (const { names, text } of ruleBlocks(ruled.map((e) => ({ name: label(e), progression: e.progression })))) {
    g.set(r++, 0, names.join(', '), { s: 'bold' });
    r = textLines(g, r, text);
  }
  return r;
}

const weeksFor = (sets) => {
  const byWeek = new Map();
  for (const s of sets.filter((x) => !x.is_warmup)) {
    const w = s.week_index ?? 0;
    if (!byWeek.has(w)) byWeek.set(w, []);
    byWeek.get(w).push(s);
  }
  return [...byWeek.entries()].sort((a, b) => a[0] - b[0]).map(([, v]) => v);
};

const repLabel = (s) => `${s.reps}${s.is_amrap ? '+' : ''}`;

function accessoriesLine(day, usedKeys) {
  const rest = day.exercises.filter(
    (e) => !e.progression && !(e.progression_group_key && usedKeys.has(e.progression_group_key)),
  );
  if (!rest.length) return null;
  return `Accessories: ${rest.map((e) => `${e.exercise_name} ${describeSets(e.predefined_sets)}`).join('; ')}.`;
}

// ── 5/3/1 Boring But Big ─────────────────────────────────────────────────────

const CYCLES = 3;

function build531(ctx) {
  const { payload } = ctx;
  const widths = [26, 18, 16, 14, 14, 14];
  const { g, row: top } = startSheet({ ...ctx, widths });
  let r = top;
  r = textLines(g, r, [
    'Each day has one main lift. Its training max (TM) runs a four-week wave, then you do Boring But Big sets of the same lift.',
    'Fill in the four training maxes. Later cycles assume you reached the minimum reps on every plus set.',
  ], 'note') + 1;

  for (const day of payload.days) {
    const main = day.exercises.find((e) => e.progression?.scheme === 'wave_531');
    if (!main) continue;
    const key = main.progression_group_key;
    const bbb = day.exercises.find((e) => !e.progression && e.progression_group_key === key);
    const bump = successIncrementKg(main.progression);

    sectionBar(g, r, `${day.name}: ${main.exercise_name}`, widths.length);
    r += 1;
    headerRow(g, r, ['', '', '', 'Cycle 1', 'Cycle 2', 'Cycle 3']);
    r += 1;
    const tmRow = r;
    const bumpRow = r + 1;
    g.set(tmRow, 0, 'Training max', { s: 'bold' });
    exampleInput(g, tmRow, 3, lookup(EXAMPLE, main.exercise_name));
    g.set(bumpRow, 0, 'Training max goes up by (each cycle)', { s: 'bold' });
    g.set(bumpRow, 3, bump, { f: incF(bump), s: 'input' });
    const [tmKg] = lookup(EXAMPLE, main.exercise_name);
    for (let k = 1; k < CYCLES; k++) {
      g.set(tmRow, 3 + k, tmKg + bump * k, {
        f: `${ref(tmRow, 2 + k)}+${ref(bumpRow, 3, 'rc')}`,
        s: 'calc',
      });
    }
    r += 2;
    headerRow(g, r, ['Week', 'Reps', '% of training max', '', '', '']);
    r += 1;

    weeksFor(main.predefined_sets).forEach((sets, wi) => {
      sets.forEach((s, si) => {
        g.set(r, 0, si === 0 ? `Week ${wi + 1}` : '', { s: 'bold' });
        g.set(r, 1, repLabel(s), { s: 'muted' });
        g.set(r, 2, s.percent_of_reference, { s: 'pct' });
        for (let k = 0; k < CYCLES; k++) {
          const tm = tmKg + bump * k;
          g.set(r, 3 + k, percentLoad((tm * s.percent_of_reference) / 100), {
            f: percentF(`${ref(tmRow, 3 + k, 'r')}*${ref(r, 2, 'c')}/100`),
            s: 'calc',
          });
        }
        r += 1;
      });
    });

    if (bbb) {
      const sets = bbb.predefined_sets.filter((s) => !s.is_warmup);
      const p = sets[0].percent_of_reference;
      g.set(r, 0, 'Boring But Big', { s: 'bold' });
      g.set(r, 1, describeSets(sets), { s: 'muted' });
      g.set(r, 2, p, { s: 'pct' });
      for (let k = 0; k < CYCLES; k++) {
        const tm = tmKg + bump * k;
        g.set(r, 3 + k, percentLoad((tm * p) / 100), {
          f: percentF(`${ref(tmRow, 3 + k, 'r')}*${ref(r, 2, 'c')}/100`),
          s: 'calc',
        });
      }
      r += 1;
    }
    const acc = accessoriesLine(day, new Set([key]));
    if (acc) g.set(r++, 0, acc, { s: 'note' });
    r += 1;
  }

  writeRules(g, r, payload, widths.length);
  return g;
}

// ── nSuns 531LP ──────────────────────────────────────────────────────────────

const NSUNS_WEEKS = 8;
const FIRST_WEEK_COL = 3;

function bandsOf(progression) {
  return progression.clauses
    .filter((c) => c.trigger === 'driver_reps_between' || c.trigger === 'driver_reps_at_least')
    .map((c) => ({ min: c.reps_min, kg: c.action === 'add_absolute' ? c.amount : 0 }))
    .sort((a, b) => b.min - a.min);
}

function buildNsuns(ctx) {
  const { payload } = ctx;
  const widths = [34, 14, 14, ...Array(NSUNS_WEEKS).fill(11)];
  const { g, row: top } = startSheet({ ...ctx, widths });
  let r = top;
  r = textLines(g, r, [
    'The tier 1 lift has nine sets and the tier 2 lift has eight, all as percentages of that lift\'s training max (TM).',
    'The training max moves every week. Type the reps you got on the 1+ set (tier 1) or Y or N for all sets done (tier 2), and the next week updates.',
  ], 'note') + 1;

  for (const day of payload.days) {
    for (const e of day.exercises) {
      const scheme = e.progression?.scheme;
      if (scheme !== 'nsuns_t1' && scheme !== 'nsuns_t2') continue;
      const tier1 = scheme === 'nsuns_t1';
      sectionBar(g, r, `${day.name}: ${e.exercise_name} (${tier1 ? 'tier 1' : 'tier 2'})`, widths.length);
      r += 1;
      headerRow(g, r, ['', '', '', ...Array.from({ length: NSUNS_WEEKS }, (_, i) => `Week ${i + 1}`)]);
      r += 1;
      const tmRow = r;
      const inRow = r + 1;
      const bumpRow = r + 2;
      const [tmKg] = lookup(EXAMPLE, e.exercise_name);
      g.set(tmRow, 0, 'Training max', { s: 'bold' });
      g.set(inRow, 0, tier1 ? 'Reps you got on the 1+ set' : 'All sets done? (Y or N)', { s: 'bold' });
      g.set(bumpRow, 0, 'Training max goes up by', { s: 'bold' });
      const bands = bandsOf(e.progression);
      const flat = e.progression.clauses.find((c) => c.trigger === 'all_sets_met' && c.action === 'add_absolute');
      for (let w = 0; w < NSUNS_WEEKS; w++) {
        const col = FIRST_WEEK_COL + w;
        g.set(inRow, col, '', { s: 'input' });
        if (w === 0) exampleInput(g, tmRow, col, lookup(EXAMPLE, e.exercise_name));
        else {
          g.set(tmRow, col, tmKg, {
            f: `${ref(tmRow, col - 1)}+${ref(bumpRow, col - 1)}`,
            s: 'calc',
          });
        }
        const input = ref(inRow, col);
        let f;
        if (tier1) {
          f = bands.reduceRight(
            (inner, b) => `IF(${input}>=${b.min},${b.kg ? incF(b.kg) : 0},${inner})`,
            '0',
          );
          f = `IF(${input}="",0,${f})`;
        } else {
          f = `IF(UPPER(${input})="Y",${incF(flat.amount)},0)`;
        }
        g.set(bumpRow, col, 0, { f, s: 'calc' });
      }
      if (!tier1) g.validations.push({ ref: `${ref(inRow, FIRST_WEEK_COL)}:${ref(inRow, FIRST_WEEK_COL + NSUNS_WEEKS - 1)}`, list: ['Y', 'N'] });
      r += 3;
      headerRow(g, r, ['Set', 'Reps', '% of TM', ...Array(NSUNS_WEEKS).fill('')]);
      r += 1;
      e.predefined_sets.filter((s) => !s.is_warmup).forEach((s, i) => {
        g.set(r, 0, `Set ${i + 1}${s.is_progression_driver ? ' (the 1+ set)' : ''}`, { s: 'bold' });
        g.set(r, 1, repLabel(s), { s: 'muted' });
        g.set(r, 2, s.percent_of_reference, { s: 'pct' });
        for (let w = 0; w < NSUNS_WEEKS; w++) {
          const col = FIRST_WEEK_COL + w;
          g.set(r, col, percentLoad((tmKg * s.percent_of_reference) / 100), {
            f: percentF(`${ref(tmRow, col, 'r')}*${ref(r, 2, 'c')}/100`),
            s: 'calc',
          });
        }
        r += 1;
      });
      r += 1;
    }
    const used = new Set(day.exercises.filter((e) => e.progression).map((e) => e.progression_group_key));
    const acc = accessoriesLine(day, used);
    if (acc) {
      g.set(r - 1, 0, acc, { s: 'note' });
      r += 1;
    }
  }

  writeRules(g, r, payload, widths.length, (e) => `${e.exercise_name} (${e.progression.scheme === 'nsuns_t1' ? 'tier 1' : 'tier 2'})`);
  return g;
}

// ── Madcow 5x5 ───────────────────────────────────────────────────────────────

const MADCOW_WEEKS = 12;
const MC_WEEK_COL = 3;

function buildMadcow(ctx) {
  const { payload } = ctx;
  const widths = [34, 12, 14, ...Array(MADCOW_WEEKS).fill(9)];
  const { g, row: top } = startSheet({ ...ctx, widths });
  let r = top;
  r = textLines(g, r, [
    'Every set is a percentage of that lift\'s working weight (the 100% set). The working weight goes up once a week.',
    'This sheet assumes you made every set. Press and deadlift move on Wednesday, the other lifts on Friday.',
  ], 'note') + 1;

  // One working weight per progression group, with the add-per-week taken from
  // the one slot in the group that carries the rule.
  const groups = new Map();
  for (const day of payload.days) {
    for (const e of day.exercises) {
      const k = e.progression_group_key;
      if (!k) continue;
      if (!groups.has(k)) groups.set(k, { name: e.exercise_name, kg: null });
      if (e.progression) groups.get(k).kg = successIncrementKg(e.progression);
    }
  }

  sectionBar(g, r, 'Working weights', widths.length);
  r += 1;
  headerRow(g, r, ['Lift', 'Start', 'Add each week', ...Array.from({ length: MADCOW_WEEKS }, (_, i) => `Week ${i + 1}`)]);
  r += 1;
  const rowOf = new Map();
  for (const [key, grp] of groups) {
    rowOf.set(key, r);
    const [startKg] = lookup(START, grp.name);
    g.set(r, 0, grp.name, { s: 'bold' });
    exampleInput(g, r, 1, lookup(START, grp.name));
    g.set(r, 2, grp.kg, { f: incF(grp.kg), s: 'input' });
    grp.weeks = [startKg];
    for (let w = 0; w < MADCOW_WEEKS; w++) {
      const col = MC_WEEK_COL + w;
      if (w === 0) g.set(r, col, startKg, { f: ref(r, 1), s: 'calc' });
      else {
        grp.weeks.push(nextWorking(grp.weeks[w - 1], grp.kg));
        g.set(r, col, grp.weeks[w], { f: nextF(ref(r, col - 1), ref(r, 2, 'c')), s: 'calc' });
      }
    }
    r += 1;
  }
  r += 1;

  for (const day of payload.days) {
    sectionBar(g, r, day.name, widths.length);
    r += 1;
    headerRow(g, r, ['', 'Reps', '% of working weight', ...Array.from({ length: MADCOW_WEEKS }, (_, i) => `Week ${i + 1}`)]);
    r += 1;
    for (const e of day.exercises) {
      const wr = rowOf.get(e.progression_group_key);
      const grp = groups.get(e.progression_group_key);
      g.set(r++, 0, e.exercise_name, { s: 'bold' });
      e.predefined_sets.filter((s) => !s.is_warmup).forEach((s, i) => {
        g.set(r, 0, `Set ${i + 1}${s.is_progression_driver ? ' (top set)' : ''}`, { s: 'normal' });
        g.set(r, 1, repLabel(s), { s: 'muted' });
        g.set(r, 2, s.percent_of_reference, { s: 'pct' });
        for (let w = 0; w < MADCOW_WEEKS; w++) {
          const col = MC_WEEK_COL + w;
          g.set(r, col, percentLoad((grp.weeks[w] * s.percent_of_reference) / 100), {
            f: percentF(`${ref(wr, col, 'r')}*${ref(r, 2, 'c')}/100`),
            s: 'calc',
          });
        }
        r += 1;
      });
    }
    r += 1;
  }

  writeRules(g, r, payload, widths.length);
  return g;
}

// ── GZCLP ────────────────────────────────────────────────────────────────────

const GZ_WEEKS = 12;

function buildGzclp(ctx) {
  const { payload } = ctx;
  const all = payload.days.flatMap((d) => d.exercises.map((e) => ({ day: d, e })));
  const t12 = [];
  const seen = new Set();
  for (const { e } of all) {
    const tier = e.progression?.scheme;
    if ((tier === 'gzclp_t1' || tier === 'gzclp_t2') && !seen.has(e.progression_group_key)) {
      seen.add(e.progression_group_key);
      t12.push(e);
    }
  }
  const t3 = [];
  for (const { e } of all) {
    if (e.progression?.scheme === 'gzclp_t3' && !t3.some((x) => x.progression_group_key === e.progression_group_key)) t3.push(e);
  }
  const widths = [34, 14, 14, ...Array(t12.length).fill(14)];
  const { g, row: top } = startSheet({ ...ctx, widths: widths.length > 3 ? widths : [34, 14, 14] });
  let r = top;
  r = textLines(g, r, [
    'Each day has a heavy lift (tier 1), a medium lift (tier 2) and a light lift (tier 3). The weight goes up when every set is made, and on tier 3 when the last set reaches its rep target.',
    'Miss a set and the lift moves to its next stage at the same weight. The table below assumes you made every set.',
  ], 'note') + 1;

  sectionBar(g, r, 'The week', widths.length);
  r += 1;
  headerRow(g, r, ['Day', 'Tier 1', 'Tier 2', 'Tier 3']);
  r += 1;
  for (const day of payload.days) {
    const by = (s) => day.exercises.find((e) => e.progression?.scheme === s)?.exercise_name ?? '';
    const wd = day.scheduled_days?.[0] ? ` (${WEEKDAY[day.scheduled_days[0]]})` : '';
    g.set(r, 0, `${day.name}${wd}`, { s: 'bold' });
    g.set(r, 1, by('gzclp_t1'), { s: 'muted' });
    g.set(r, 2, by('gzclp_t2'), { s: 'muted' });
    g.set(r, 3, by('gzclp_t3'), { s: 'muted' });
    r += 1;
  }
  g.widths = [34, 24, 24, 24, ...Array(Math.max(0, t12.length - 3)).fill(14)];
  r += 1;

  sectionBar(g, r, 'Stages', widths.length);
  r += 1;
  headerRow(g, r, ['Tier', 'Stage 1', 'Stage 2', 'Stage 3']);
  r += 1;
  for (const [label, scheme] of [['Tier 1', 'gzclp_t1'], ['Tier 2', 'gzclp_t2'], ['Tier 3', 'gzclp_t3']]) {
    const e = all.find((x) => x.e.progression?.scheme === scheme).e;
    g.set(r, 0, label, { s: 'bold' });
    weeksFor(e.predefined_sets).forEach((sets, i) => g.set(r, 1 + i, describeSets(sets), { s: 'muted' }));
    r += 1;
  }
  r += 1;

  sectionBar(g, r, 'Starting weights', widths.length);
  r += 1;
  headerRow(g, r, ['Lift', 'Start', 'Add on success']);
  r += 1;
  const startRow = new Map();
  for (const e of [...t12, ...t3]) {
    const tier = e.progression.scheme.slice(-2).toUpperCase();
    startRow.set(e.progression_group_key, r);
    g.set(r, 0, `${e.exercise_name} (${tier})`, { s: 'bold' });
    exampleInput(g, r, 1, lookup(START, e.exercise_name));
    const inc = successIncrementKg(e.progression);
    g.set(r, 2, inc, { f: incF(inc), s: 'input' });
    r += 1;
  }
  r += 1;

  sectionBar(g, r, 'Weight each week, if every set is made', widths.length);
  r += 1;
  headerRow(g, r, ['Week', ...t12.map((e) => `${e.exercise_name} (${e.progression.scheme.slice(-2).toUpperCase()})`)]);
  r += 1;
  const gzPrev = new Map();
  for (let w = 0; w < GZ_WEEKS; w++) {
    g.set(r, 0, `Week ${w + 1}`, { s: 'bold' });
    t12.forEach((e, i) => {
      const sr = startRow.get(e.progression_group_key);
      const inc = successIncrementKg(e.progression);
      if (w === 0) {
        const [startKg] = lookup(START, e.exercise_name);
        gzPrev.set(e, startKg);
        g.set(r, 1 + i, startKg, { f: ref(sr, 1, 'rc'), s: 'calc' });
      } else {
        const next = nextWorking(gzPrev.get(e), inc);
        gzPrev.set(e, next);
        g.set(r, 1 + i, next, { f: nextF(ref(r - 1, 1 + i), ref(sr, 2, 'rc')), s: 'calc' });
      }
    });
    r += 1;
  }
  r += 1;

  writeRules(g, r, payload, widths.length, (e) => `${e.exercise_name} (${e.progression.scheme.slice(-2).toUpperCase()})`);
  return g;
}

// ── StrongLifts 5x5 and Starting Strength ────────────────────────────────────

const SESSIONS = 36;

function buildLinear(ctx) {
  const { payload } = ctx;
  const lifts = [];
  for (const day of payload.days) {
    for (const e of day.exercises) {
      if (!lifts.some((l) => l.key === e.progression_group_key)) {
        lifts.push({ key: e.progression_group_key, e });
      }
    }
  }
  const useWidths = [34, 18, ...lifts.map(() => 16)];
  const { g, row: top } = startSheet({ ...ctx, widths: useWidths });
  let r = top;
  r = textLines(g, r, [
    `You train three days a week and alternate ${payload.days.map((d) => d.name).join(' and ')}.`,
    'Weight goes up every time you train a lift. The table below assumes you made every rep.',
  ], 'note') + 1;

  sectionBar(g, r, 'Your lifts', useWidths.length);
  r += 1;
  headerRow(g, r, ['Lift', 'Sets × reps', 'Start', 'Add each session']);
  r += 1;
  const setupRow = new Map();
  for (const { key, e } of lifts) {
    setupRow.set(key, r);
    g.set(r, 0, e.exercise_name, { s: 'bold' });
    const stages = weeksFor(e.predefined_sets);
    g.set(r, 1, describeSets(stages[0]), { s: 'muted' });
    exampleInput(g, r, 2, lookup(START, e.exercise_name));
    const inc = successIncrementKg(e.progression);
    g.set(r, 3, inc, { f: incF(inc), s: 'input' });
    r += 1;
  }
  g.widths = [34, 18, ...lifts.map(() => 16)];
  while (g.widths.length < 4) g.widths.push(16);
  r += 1;

  sectionBar(g, r, 'Weight each session, if every rep is made', useWidths.length);
  r += 1;
  headerRow(g, r, ['Session', 'Workout', ...lifts.map((l) => l.e.exercise_name)]);
  r += 1;
  const last = new Map(); // lift key -> { cell ref, value } of its latest session
  for (let s = 0; s < SESSIONS; s++) {
    const day = payload.days[s % payload.days.length];
    g.set(r, 0, `Session ${s + 1}`, { s: 'bold' });
    g.set(r, 1, day.name, { s: 'muted' });
    lifts.forEach((l, i) => {
      if (!day.exercises.some((e) => e.progression_group_key === l.key)) return;
      const sr = setupRow.get(l.key);
      const prev = last.get(l.key);
      let value;
      let f;
      if (!prev) {
        value = lookup(START, l.e.exercise_name)[0];
        f = ref(sr, 2, 'rc');
      } else {
        value = nextWorking(prev.value, successIncrementKg(l.e.progression));
        f = nextF(prev.cell, ref(sr, 3, 'rc'));
      }
      last.set(l.key, { cell: ref(r, 2 + i), value });
      g.set(r, 2 + i, value, { f, s: 'calc' });
    });
    r += 1;
  }
  r += 1;

  r = writeRules(g, r, payload, useWidths.length);
  const stages = weeksFor(lifts[0].e.predefined_sets);
  if (stages.length > 1) {
    g.set(r++, 0, `Stages: ${stages.map((s) => describeSets(s)).join(', then ')}.`, { s: 'note' });
  }
  return g;
}

// ── Programs with no rule ────────────────────────────────────────────────────

const LOG_WEEKS = 12;

function buildGeneric(ctx) {
  const { payload } = ctx;
  const widths = [36, 18, ...Array(LOG_WEEKS).fill(9)];
  const { g, row: top } = startSheet({ ...ctx, widths, settings: false });
  let r = top;
  // This program carries no weight rule, so unit and rounding are not used.
  r = textLines(g, r, [
    payload.routine.notes,
    'Write the weight you used for each exercise in the week columns. Use the same unit all the way down.',
  ], 'note') + 1;
  for (const day of payload.days) {
    const wd = day.scheduled_days?.[0] ? ` (${WEEKDAY[day.scheduled_days[0]]})` : '';
    sectionBar(g, r, `${day.name}${wd}`, widths.length);
    r += 1;
    headerRow(g, r, ['Exercise', 'Sets × reps', ...Array.from({ length: LOG_WEEKS }, (_, i) => `Week ${i + 1}`)]);
    r += 1;
    for (const e of day.exercises) {
      g.set(r, 0, e.exercise_name, { s: 'bold' });
      g.set(r, 1, describeSets(e.predefined_sets), { s: 'muted' });
      for (let w = 0; w < LOG_WEEKS; w++) g.set(r, 2 + w, '', { s: 'input' });
      r += 1;
    }
    r += 1;
  }
  return g;
}

export function builderFor(payload) {
  const schemes = new Set(
    payload.days.flatMap((d) => d.exercises.map((e) => e.progression?.scheme).filter(Boolean)),
  );
  if (schemes.has('wave_531')) return build531;
  if (schemes.has('nsuns_t1')) return buildNsuns;
  if (schemes.has('madcow_weekly')) return buildMadcow;
  if (schemes.has('gzclp_t1')) return buildGzclp;
  if (schemes.has('linear')) return buildLinear;
  if (schemes.size === 0) return buildGeneric;
  throw new Error(`No sheet builder for schemes: ${[...schemes].join(', ')}`);
}


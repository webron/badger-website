// Turns a program's progression rule (the `progression` object a .badger file
// carries) into plain sentences, and helpers for the weights those rules use.
//
// Increments are a PAIR in the app, not a conversion: "+2.5 kg / +5 lb", never
// "+5.5 lb" (lib/features/routines/domain/rule_amount.dart, kCanonicalIncrementPairs).
// The same table is repeated here so a sheet set to pounds adds what the app adds.

const PAIRS = [
  [1.25, 2.5],
  [2.5, 5],
  [5, 10],
  [7.5, 15],
];

const KG_TO_LB = 2.20462;

/** Pounds for a kg increment, using the app's own pairs where it has one. */
export function lbOf(kg) {
  const pair = PAIRS.find(([k]) => Math.abs(k - kg) < 0.0001);
  if (pair) return pair[1];
  return Math.round(kg * KG_TO_LB * 10) / 10;
}

export const num = (n) => String(Math.round(n * 1000) / 1000);

/** "2.5 kg / 5 lb" */
export const pairText = (kg) => `${num(kg)} kg / ${num(lbOf(kg))} lb`;

const TRIGGERS = {
  consecutive_failures_at_least: (c) =>
    `After ${c.count} misses in a row`,
  all_sets_met: () => 'When every set is met',
  any_set_missed: () => 'When you miss a set',
  stage_is_last: () => 'After failing at the last stage',
  driver_reps_between: (c) =>
    `When the key set gets ${c.reps_min} to ${c.reps_max} reps`,
  driver_reps_at_least: (c) => `When the key set gets ${c.reps_min} or more reps`,
  cycle_missed_minimum: () => 'When a plus set fell short of its minimum this cycle',
  cycle_complete: () => 'At the end of a cycle',
  always: () => 'Otherwise',
};

const TARGET_PHRASE = {
  reference: 'the training max',
  working_weight: 'the weight',
};

function actionText(c) {
  switch (c.action) {
    case 'add_absolute':
      return `add ${pairText(c.amount)} to ${TARGET_PHRASE[c.target] ?? 'the weight'}`;
    case 'add_percent':
      return c.percent < 0
        ? `take ${num(-c.percent)}% off ${TARGET_PHRASE[c.target] ?? 'the weight'}`
        : `add ${num(c.percent)}% to ${TARGET_PHRASE[c.target] ?? 'the weight'}`;
    case 'hold':
      return `hold ${TARGET_PHRASE[c.target] ?? 'the weight'}`;
    case 'none':
      return 'change nothing';
    case 'next_stage':
      return 'move to the next stage';
    case 'reset_stage':
      return 'go back to stage 1';
    case 'set_from_remembered':
      return `restart from your stage 1 weight plus ${pairText(c.amount)}`;
    case 'halve_increment':
      return 'halve the increment';
    default:
      throw new Error(`Unknown progression action: ${c.action}`);
  }
}

function triggerKey(c) {
  return JSON.stringify([c.trigger, c.count, c.reps_min, c.reps_max]);
}

/**
 * One sentence per trigger, in the order the file lists them (the app reads a
 * rule top to bottom, so the order carries meaning).
 */
export function ruleSentences(progression) {
  const groups = [];
  for (const c of progression.clauses) {
    const make = TRIGGERS[c.trigger];
    if (!make) throw new Error(`Unknown progression trigger: ${c.trigger}`);
    const last = groups[groups.length - 1];
    if (last && last.key === triggerKey(c)) last.actions.push(actionText(c));
    else groups.push({ key: triggerKey(c), lead: make(c), actions: [actionText(c)] });
  }
  return groups.map((g) => `${g.lead}, ${g.actions.join(' and ')}.`);
}

/**
 * The fixed amount a rule adds when its lift succeeds: every set met, the end of
 * a cycle, or the key set reaching its rep target (GZCLP tier 3).
 */
export function successIncrementKg(progression) {
  const c = progression.clauses.find(
    (x) =>
      x.action === 'add_absolute' &&
      ['all_sets_met', 'cycle_complete', 'driver_reps_at_least'].includes(x.trigger),
  );
  return c ? c.amount : null;
}

/** Group consecutive identical sets: "3 × 10", "5 × 3+". Ranges use a plain hyphen. */
export function describeSets(sets) {
  const work = sets.filter((s) => !s.is_warmup);
  const parts = [];
  for (const s of work) {
    const reps =
      s.reps == null && s.duration_seconds != null
        ? `${s.duration_seconds} sec`
        : s.reps_max && s.reps_max !== s.reps
          ? `${s.reps}-${s.reps_max}`
          : `${s.reps}`;
    const label = `${reps}${s.is_amrap ? '+' : ''}`;
    const last = parts[parts.length - 1];
    if (last && last.label === label) last.count += 1;
    else parts.push({ label, count: 1 });
  }
  return parts.map((p) => `${p.count} × ${p.label}`).join(', ');
}

/**
 * Rule sentences for a set of ruled exercises, one block per distinct rule with
 * the lifts it covers. A program's lifts often differ only in their increment,
 * so printing one lift's rule for all of them would state the wrong number.
 * Returns [{ names, text }].
 */
export function ruleBlocks(exercises) {
  const blocks = new Map();
  for (const { name, progression } of exercises) {
    const text = ruleSentences(progression);
    const k = JSON.stringify(text);
    if (!blocks.has(k)) blocks.set(k, { text, names: [] });
    if (!blocks.get(k).names.includes(name)) blocks.get(k).names.push(name);
  }
  return [...blocks.values()];
}

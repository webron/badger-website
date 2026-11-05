// Math for the 5/3/1 calculator page (src/pages/tools/531-calculator.astro).
//
// Plain JS with JSDoc so `node --test` runs it with no build step. Nothing here
// holds a program number: percentages, reps, the Boring But Big sets and the
// training-max steps are all read from public/programs/531-bbb.badger by
// extractProgram(), so the page cannot drift from the routine Badger ships.

const KG_PER_LB = 0.45359237;

/** Display names, in the order the page shows them. Matched against exercise_name. */
export const LIFTS = [
  { key: 'squat', label: 'Squat', match: /squat/i },
  { key: 'bench', label: 'Bench press', match: /bench/i },
  { key: 'deadlift', label: 'Deadlift', match: /deadlift/i },
  { key: 'press', label: 'Overhead press', match: /overhead/i },
];

/**
 * Read the wave, the Boring But Big sets and the training-max step for each lift
 * out of a parsed .badger share file.
 * @param {any} file parsed JSON of 531-bbb.badger
 */
export function extractProgram(file) {
  const out = {};
  for (const day of file.payload.days) {
    // The main lift is the exercise that carries the wave_531 progression.
    const main = day.exercises.find((e) => e.progression && e.progression.scheme === 'wave_531');
    if (!main) continue;
    const lift = LIFTS.find((l) => l.match.test(main.exercise_name));
    if (!lift) continue;

    const weeks = [];
    for (const s of main.predefined_sets) {
      (weeks[s.week_index] ||= []).push({
        reps: s.reps,
        percent: s.percent_of_reference,
        plus: Boolean(s.is_amrap),
      });
    }

    // Boring But Big: the other entry for the same lift, sharing the group key.
    const bbbEx = day.exercises.find(
      (e) => e !== main && e.progression_group_key === main.progression_group_key,
    );
    const bbbSets = bbbEx.predefined_sets;
    const bbb = { sets: bbbSets.length, reps: bbbSets[0].reps, percent: bbbSets[0].percent_of_reference };

    const bump = main.progression.clauses.find((c) => c.trigger === 'cycle_complete' && c.action === 'add_absolute');
    out[lift.key] = {
      label: lift.label,
      weeks,
      bbb,
      step: { amount: bump.amount, unit: bump.amount_unit },
    };
  }
  return out;
}

/** Epley estimated one-rep max. One rep is the weight itself. */
export function epley1RM(weight, reps) {
  if (!(weight > 0) || !(reps >= 1)) return NaN;
  return reps === 1 ? weight : weight * (1 + reps / 30);
}

/** Round to the nearest multiple of step (halves round up), free of float dust. */
export function roundTo(value, step) {
  const n = Math.floor(value / step + 0.5 + 1e-9);
  return Number((n * step).toFixed(4));
}

/**
 * Training max from a recent best set: Epley estimate times the chosen percent,
 * rounded to the loading step so it is a number you can write down.
 */
export function trainingMaxFromSet(weight, reps, percent, step) {
  const oneRm = epley1RM(weight, reps);
  if (Number.isNaN(oneRm)) return NaN;
  return roundTo((oneRm * percent) / 100, step);
}

/** Weight of one set: percent of the training max, rounded to the loading step. */
export function setWeight(trainingMax, percent, step) {
  return roundTo((trainingMax * percent) / 100, step);
}

/**
 * The four-week wave for one lift, with every set's weight.
 * @param {{weeks: {reps:number, percent:number, plus:boolean}[][], bbb:{sets:number,reps:number,percent:number}}} lift
 */
export function buildCycle(lift, trainingMax, step) {
  return {
    weeks: lift.weeks.map((sets) =>
      sets.map((s) => ({ reps: s.reps, plus: s.plus, percent: s.percent, weight: setWeight(trainingMax, s.percent, step) })),
    ),
    bbb: {
      sets: lift.bbb.sets,
      reps: lift.bbb.reps,
      percent: lift.bbb.percent,
      weight: setWeight(trainingMax, lift.bbb.percent, step),
    },
  };
}

/**
 * The file states its steps in kilograms. In pounds the same step is converted
 * and rounded to the nearest 5 lb, so 2.5 kg becomes 5 lb and 5 kg becomes 10 lb.
 */
export function stepIncrease(amount, fileUnit, unit) {
  if (fileUnit === unit) return amount;
  if (fileUnit === 'kg' && unit === 'lb') return roundTo(amount / KG_PER_LB, 5);
  if (fileUnit === 'lb' && unit === 'kg') return roundTo(amount * KG_PER_LB, 2.5);
  return amount;
}

export function nextTrainingMax(trainingMax, lift, unit) {
  return Number((trainingMax + stepIncrease(lift.step.amount, lift.step.unit, unit)).toFixed(4));
}

/** 100, 97.5, 62.25 -> "100", "97.5", "62.25". */
export function formatWeight(n) {
  return String(Number(n.toFixed(2)));
}

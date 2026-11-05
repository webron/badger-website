import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  extractProgram, epley1RM, roundTo, trainingMaxFromSet, setWeight, buildCycle,
  stepIncrease, nextTrainingMax, formatWeight,
} from './531.js';

const file = JSON.parse(readFileSync(new URL('../../public/programs/531-bbb.badger', import.meta.url), 'utf8'));
const program = extractProgram(file);

test('extracts all four lifts from the file', () => {
  assert.deepEqual(Object.keys(program).sort(), ['bench', 'deadlift', 'press', 'squat']);
});

test('wave read from the file: four weeks of percent and reps', () => {
  const w = program.squat.weeks.map((sets) => sets.map((s) => `${s.percent}x${s.reps}${s.plus ? '+' : ''}`));
  assert.deepEqual(w, [
    ['65x5', '75x5', '85x5+'],
    ['70x3', '80x3', '90x3+'],
    ['75x5', '85x3', '95x1+'],
    ['40x5', '50x5', '60x5'],
  ]);
});

test('Boring But Big: 5 x 10 at 60%', () => {
  assert.deepEqual(program.bench.bbb, { sets: 5, reps: 10, percent: 60 });
});

test('step sizes from the file: 5 kg lower body, 2.5 kg upper body', () => {
  assert.equal(program.squat.step.amount, 5);
  assert.equal(program.deadlift.step.amount, 5);
  assert.equal(program.bench.step.amount, 2.5);
  assert.equal(program.press.step.amount, 2.5);
  assert.equal(program.squat.step.unit, 'kg');
});

test('Epley: w * (1 + reps/30), one rep is the weight', () => {
  assert.equal(epley1RM(100, 1), 100);
  assert.equal(epley1RM(100, 5), 100 * (1 + 5 / 30));
  assert.ok(Math.abs(epley1RM(100, 5) - 116.6667) < 0.001);
  assert.ok(Number.isNaN(epley1RM(0, 5)));
  assert.ok(Number.isNaN(epley1RM(100, 0)));
});

test('training max from a set: 100 x 5, 90% -> 105 at 2.5 steps', () => {
  // 116.667 * 0.9 = 105.0
  assert.equal(trainingMaxFromSet(100, 5, 90, 2.5), 105);
  // 100 x 8: 126.667 * 0.85 = 107.67 -> 107.5
  assert.equal(trainingMaxFromSet(100, 8, 85, 2.5), 107.5);
});

test('rounding: nearest step, halves up, no float dust', () => {
  assert.equal(roundTo(61.2, 2.5), 60);
  assert.equal(roundTo(61.3, 2.5), 62.5);
  assert.equal(roundTo(61.25, 2.5), 62.5);
  assert.equal(roundTo(62.4, 1.25), 62.5);
  assert.equal(roundTo(137, 5), 135);
  assert.equal(roundTo(0.65 * 100, 2.5), 65);
});

test('squat training max 100 kg: weekly weights equal file percent times 100', () => {
  const cycle = buildCycle(program.squat, 100, 2.5);
  const weights = cycle.weeks.map((w) => w.map((s) => s.weight));
  assert.deepEqual(weights, [
    [65, 75, 85],
    [70, 80, 90],
    [75, 85, 95],
    [40, 50, 60],
  ]);
  assert.deepEqual(cycle.bbb, { sets: 5, reps: 10, percent: 60, weight: 60 });
});

test('rounding applies to every set (training max 102 kg, 2.5 kg steps)', () => {
  const cycle = buildCycle(program.bench, 102, 2.5);
  // 65% = 66.3 -> 67.5, 75% = 76.5 -> 77.5, 85% = 86.7 -> 87.5, 95% = 96.9 -> 97.5, 60% = 61.2 -> 60
  assert.deepEqual(cycle.weeks[0].map((s) => s.weight), [67.5, 77.5, 87.5]);
  assert.equal(cycle.weeks[2][2].weight, 97.5);
  assert.equal(cycle.bbb.weight, 60);
});

test('pounds, 5 lb steps: training max 225', () => {
  assert.equal(setWeight(225, 65, 5), 145); // 146.25
  assert.equal(setWeight(225, 85, 5), 190); // 191.25
});

test('next training max uses the file steps', () => {
  assert.equal(nextTrainingMax(100, program.squat, 'kg'), 105);
  assert.equal(nextTrainingMax(100, program.deadlift, 'kg'), 105);
  assert.equal(nextTrainingMax(60, program.press, 'kg'), 62.5);
  assert.equal(nextTrainingMax(80, program.bench, 'kg'), 82.5);
});

test('pound steps: 2.5 kg -> 5 lb, 5 kg -> 10 lb', () => {
  assert.equal(stepIncrease(2.5, 'kg', 'lb'), 5);
  assert.equal(stepIncrease(5, 'kg', 'lb'), 10);
  assert.equal(nextTrainingMax(225, program.squat, 'lb'), 235);
  assert.equal(nextTrainingMax(135, program.press, 'lb'), 140);
});

test('formatWeight trims trailing zeros', () => {
  assert.equal(formatWeight(100), '100');
  assert.equal(formatWeight(97.5), '97.5');
  assert.equal(formatWeight(62.25), '62.25');
});

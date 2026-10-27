import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BATCH_PRESETS, compareRollSizes, computeRollTelemetry, placementCards, planLabels } from '../src/lib/planner.ts';

test('a real batch rounds the allowance and whole rolls independently', () => {
  assert.deepEqual(planLabels({ quantity: 250, labelsPerItem: 2, wastePercent: 5,
    labelsPerRoll: 500, rollsOnHand: 1 }), { baseLabels: 500, labelsNeeded: 525,
    rollsRequired: 2, rollsToOrder: 1, labelsLeft: 475 });
});
test('exact capacity and on-hand stock need no unnecessary order', () => {
  const result = planLabels({ quantity: 100, labelsPerItem: 1, wastePercent: 0,
    labelsPerRoll: 100, rollsOnHand: 4 });
  assert.equal(result.rollsToOrder, 0);
  assert.equal(result.labelsLeft, 0);
});
test('a fractional allowance on a single item still reserves a whole label', () => {
  assert.equal(planLabels({ quantity: 1, labelsPerItem: 1, wastePercent: 0.1,
    labelsPerRoll: 1, rollsOnHand: 0 }).rollsRequired, 2);
});
test('invalid, fractional, nonfinite, negative and oversized counts are rejected', () => {
  const base = { quantity: 250, labelsPerItem: 2, wastePercent: 5, labelsPerRoll: 500, rollsOnHand: 1 };
  for (const bad of [{ quantity: 0 }, { quantity: 1.5 }, { quantity: 1_000_001 },
    { labelsPerItem: 101 }, { labelsPerRoll: 0 }, { rollsOnHand: -1 },
    { wastePercent: NaN }, { wastePercent: Infinity }, { wastePercent: -1 }, { wastePercent: 101 }]) {
    assert.throws(() => planLabels({ ...base, ...bad }), RangeError);
  }
});
test('larger batches cannot need fewer rolls and coverage always includes allowance', () => {
  for (let quantity = 1; quantity < 3000; quantity += 17) {
    const inputs = { quantity, labelsPerItem: 3, wastePercent: 7.5, labelsPerRoll: 240, rollsOnHand: 0 };
    const current = planLabels(inputs);
    const next = planLabels({ ...inputs, quantity: quantity + 1 });
    assert.ok(next.rollsRequired >= current.rollsRequired);
    assert.ok(current.labelsNeeded >= current.baseLabels);
    assert.ok(current.rollsRequired * inputs.labelsPerRoll >= current.labelsNeeded);
    assert.ok(current.labelsLeft >= 0 && current.labelsLeft < inputs.labelsPerRoll);
  }
});
test('roll telemetry and roll-size comparison stay consistent with planLabels', () => {
  const sample = BATCH_PRESETS[0].inputs;
  const telemetry = computeRollTelemetry(sample);
  assert.equal(telemetry.allowanceLabels, 25);
  assert.equal(telemetry.totalCapacity, 1000);
  assert.equal(telemetry.lastRollUsed, 25);
  assert.equal(telemetry.lastRollUsedPercent, 5);
  assert.equal(Math.round(telemetry.baseSharePercent + telemetry.allowanceSharePercent + telemetry.spareSharePercent), 100);

  const comparison = compareRollSizes(sample);
  assert.equal(comparison.length, 4);
  assert.ok(comparison.some(row => row.isCurrent && row.labelsPerRoll === 500));
  assert.equal(comparison.filter(row => row.isLowestSpare).length, 1);
  const row250 = comparison.find(row => row.labelsPerRoll === 250);
  assert.ok(row250);
  assert.equal(row250.rollsRequired, 3);
  assert.equal(row250.labelsLeft, 225);
});

test('the label strip shows whole cards for every placement count', () => {
  assert.deepEqual(placementCards(2).map(card => card.title), ['Front', 'Back']);
  assert.deepEqual(placementCards(4).map(card => card.title), ['Front', 'Back', 'Neck', 'Lid']);
  assert.equal(placementCards(1)[0].meta, 'Label 1 of 1');
  const many = placementCards(7);
  assert.equal(many.length, 4);
  assert.deepEqual(many.at(-1), { title: '+4 more', meta: 'Labels 4–7' });
});

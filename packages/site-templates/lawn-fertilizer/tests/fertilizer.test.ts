import { test } from 'node:test';
import assert from 'node:assert/strict';
import { areaFromDimensions, parseNumber, planFertilizer, rateBand, type PlanInput } from '../src/lib/fertilizer.ts';
import { GRASSES, feedingsPerYear } from '../src/lib/grasses.ts';

const base: PlanInput = { area: 5000, nitrogen: 20, phosphorus: 0, potassium: 0, rate: 1, bagWeight: 15 };
const plan = (input: Partial<PlanInput>) => {
  const result = planFertilizer({ ...base, ...input });
  assert.ok(result.ok, JSON.stringify(result));
  return result.plan;
};
const close = (actual: number, expected: number) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} != ${expected}`);

test('matches the extension guides worked examples', () => {
  close(plan({ nitrogen: 32, rate: 1 }).productPerThousand, 3.125); // Iowa State: 1 / 0.32
  close(plan({ nitrogen: 20, rate: 2 }).productPerThousand, 10); // Rutgers FS839: 20% N, 2 lb N
  close(plan({ nitrogen: 10, phosphorus: 10, potassium: 10, rate: 1 }).productPerThousand, 10); // NC State: 100 / 10
});

test('scales to the whole lawn and rounds bags up', () => {
  const lawn = plan({});
  close(lawn.productTotal, 25); // 5,000 sq ft, 1 lb N, 20% N
  close(lawn.nitrogenTotal, 5);
  assert.equal(lawn.bags, 2);
  close(lawn.leftover, 5);
  const large = plan({ area: 12000, nitrogen: 29, rate: 0.75, bagWeight: 12 });
  assert.equal(large.productTotal.toFixed(1), '31.0'); // 12 × 0.75 ÷ 0.29
  assert.equal(large.bags, 3);
  assert.equal(plan({ area: 6000, nitrogen: 20, rate: 1, bagWeight: 15 }).bags, 2, 'exactly 30 lb is two 15 lb bags');
  assert.equal(plan({ area: 100, rate: 0.5, bagWeight: 50 }).bags, 1, 'a tiny lawn still needs one bag');
});

test('bands the feeding rate and flags phosphorus', () => {
  assert.equal(rateBand(0.5), 'light');
  assert.equal(rateBand(0.75), 'standard');
  assert.equal(rateBand(1), 'standard');
  assert.equal(rateBand(1.25), 'heavy');
  assert.equal(plan({ phosphorus: 0 }).phosphorus, false);
  assert.equal(plan({ phosphorus: 4 }).phosphorus, true);
});

test('rejects blank, zero, negative, impossible and non-finite input per field', () => {
  for (const [field, value] of [['area', 0], ['area', -5], ['area', Number.NaN], ['area', 2e6], ['nitrogen', 0],
    ['nitrogen', 47], ['phosphorus', -1], ['potassium', 61], ['rate', 0], ['rate', 2.5], ['bagWeight', 0],
    ['bagWeight', Number.POSITIVE_INFINITY]] as const) {
    const result = planFertilizer({ ...base, [field]: value });
    assert.equal(result.ok, false, `${field}=${value}`);
    if (!result.ok) assert.ok(result.errors[field], `${field} names its own error`);
  }
  const overfull = planFertilizer({ ...base, nitrogen: 46, phosphorus: 40, potassium: 20 });
  assert.ok(!overfull.ok && overfull.errors.nitrogen?.includes('100'));
});

test('reads numbers the way people type them', () => {
  assert.equal(parseNumber('1,800'), 1800);
  assert.equal(parseNumber(' 12.5 '), 12.5);
  assert.equal(parseNumber('1,250,000'), 1250000);
  assert.equal(parseNumber('.5'), 0.5);
  for (const raw of ['', ' ', '1,80', '12a', '-3', '1e3', '1.2.3']) assert.ok(Number.isNaN(parseNumber(raw)), raw);
  assert.equal(areaFromDimensions(50, 100), 5000);
  assert.ok(Number.isNaN(areaFromDimensions(0, 100)));
});

test('grass data stays inside the cited ranges and gives whole feedings', () => {
  assert.equal(GRASSES.length, 6);
  for (const grass of GRASSES) {
    assert.ok(grass.annual[0] > 0 && grass.annual[0] < grass.annual[1] && grass.annual[1] <= 7, grass.id);
    assert.ok(Object.values(grass.months).includes('main'), `${grass.id} has a main feeding`);
  }
  const bluegrass = GRASSES.find((grass) => grass.id === 'kentucky-bluegrass')!;
  assert.deepEqual(feedingsPerYear(bluegrass, 1), [1, 4]);
  assert.deepEqual(feedingsPerYear(bluegrass, 0.75), [1, 5]);
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SIZES, SQ_FT_PER_ACRE, bagsFor, productPounds } from '../src/lib/sizes.ts';
import { SEED_GRASSES, seedPlan } from '../src/lib/seed.ts';
import { seedPounds } from '../src/lib/format.ts';

const close = (actual: number, expected: number) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} != ${expected}`);

test('lawn sizes are exact and their square sides match the stated feet', () => {
  assert.equal(SQ_FT_PER_ACRE, 43_560);
  assert.deepEqual(SIZES.map((size) => size.area), [1000, 2500, 5000, 10000, 10890, 21780, 43560]);
  for (const size of SIZES.filter((item) => item.slug.includes('acre'))) {
    const side = Math.round(Math.sqrt(size.area));
    assert.ok(size.shape.includes(`about ${side} ft`), `${size.slug}: ${side} ft`);
    assert.ok(size.shape.startsWith(size.area.toLocaleString('en-US')), size.slug);
  }
  assert.equal(new Set(SIZES.map((size) => size.slug)).size, SIZES.length);
});

test('product pounds and bags match hand math', () => {
  close(productPounds(5000, 20, 1), 25);
  close(productPounds(43560, 46, 1), 94.69565217391305); // urea on an acre at 1 lb N
  close(productPounds(1000, 10, 0.5), 5);
  assert.equal(bagsFor(25, 15), 2);
  assert.equal(bagsFor(30, 15), 2);
  assert.equal(bagsFor(0.4, 50), 1);
});

test('seed rates follow NC State AG-69 and overseeding is 25–50% lower', () => {
  const fescue = seedPlan(5000, 'tall-fescue', 'new', 25);
  assert.ok(fescue && fescue.seedable);
  if (fescue && fescue.seedable) {
    assert.deepEqual(fescue.perThousand, [6, 6]);
    assert.deepEqual(fescue.pounds, [30, 30]);
    assert.deepEqual(fescue.bags, [2, 2]);
    assert.equal(fescue.season, 'late summer to early fall');
  }
  const over = seedPlan(5000, 'tall-fescue', 'overseed', 25);
  assert.ok(over && over.seedable);
  if (over && over.seedable) {
    assert.deepEqual(over.perThousand, [3, 4.5]);
    assert.deepEqual(over.pounds, [15, 22.5]);
    assert.deepEqual(over.bags, [1, 1]);
  }
  const centipede = seedPlan(10000, 'centipedegrass', 'new', 1);
  assert.ok(centipede && centipede.seedable && centipede.pounds[0] === 2.5 && centipede.pounds[1] === 5);
  assert.deepEqual(seedPlan(5000, 'st-augustinegrass', 'new', 5), { seedable: false });
  for (const args of [[0, 'tall-fescue'], [5000, 'unknown'], [Number.NaN, 'tall-fescue']] as const) {
    assert.equal(seedPlan(args[0], args[1], 'new', 5), null);
  }
  assert.equal(seedPlan(5000, 'tall-fescue', 'new', 0), null);
  assert.equal(SEED_GRASSES.filter((grass) => grass.rate === null).length, 1);
});

test('seed weights keep small amounts exact and drop trailing zeros', () => {
  assert.deepEqual([0.25, 0.5, 6, 22.5, 1.25, 30, 1000].map(seedPounds), ['0.25', '0.5', '6', '22.5', '1.25', '30', '1,000']);
});

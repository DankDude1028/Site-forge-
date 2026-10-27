import { test } from 'node:test';
import assert from 'node:assert/strict';
import { bagContents, calibrate, lawnArea, shapeArea } from '../src/lib/tools.ts';

const close = (actual: number, expected: number, tolerance = 1e-6) =>
  assert.ok(Math.abs(actual - expected) < tolerance, `${actual} != ${expected}`);

test('shape areas match hand geometry', () => {
  assert.equal(shapeArea({ kind: 'rectangle', a: 50, b: 100, subtract: false }), 5000);
  close(shapeArea({ kind: 'circle', a: 20, b: 0, subtract: false }), Math.PI * 100); // 20 ft across: 314.16 sq ft
  assert.equal(shapeArea({ kind: 'triangle', a: 30, b: 40, subtract: false }), 600);
  for (const shape of [{ kind: 'rectangle', a: 0, b: 10 }, { kind: 'rectangle', a: 10, b: Number.NaN },
    { kind: 'circle', a: -4, b: 0 }, { kind: 'triangle', a: 10, b: 200_000 }] as const) {
    assert.ok(Number.isNaN(shapeArea({ ...shape, subtract: false })), JSON.stringify(shape));
  }
});

test('lawn area adds grass, subtracts cut-outs and skips unfinished shapes', () => {
  const result = lawnArea([
    { kind: 'rectangle', a: 100, b: 60, subtract: false }, // 6,000 front and back
    { kind: 'rectangle', a: 40, b: 30, subtract: true }, // 1,200 house
    { kind: 'circle', a: 10, b: 0, subtract: true }, // 78.54 bed
    { kind: 'triangle', a: Number.NaN, b: 5, subtract: false }, // not filled in yet
  ]);
  close(result.area, 6000 - 1200 - Math.PI * 25);
  assert.equal(result.counted, 3);
  assert.equal(lawnArea([{ kind: 'rectangle', a: 10, b: 10, subtract: true }]).area, 0, 'never negative');
});

test('bag contents follow the label percentages', () => {
  const bag = bagContents(50, 29, 0, 4)!;
  close(bag.nitrogen, 14.5);
  close(bag.potash, 2);
  close(bag.other, 33.5);
  close(bag.potassium, 2 * 0.8301);
  close(bag.perPoundOfNitrogen, 100 / 29);
  close(bagContents(40, 10, 10, 10)!.phosphorus, 4 * 0.4364);
  close(bagContents(10, 20, 0, 0)!.perPoundOfNitrogen, 5); // UF/IFAS table: 20% N needs 5 lb per 1,000 sq ft
  assert.equal(bagContents(50, 0, 10, 10), null);
  assert.equal(bagContents(50, 60, 30, 20), null);
  assert.equal(bagContents(50, 50, 0, 0), null, 'no fertilizer carries more than 46% nitrogen');
  assert.equal(bagContents(0, 20, 0, 0), null);
});

test('calibration follows the UF/IFAS weigh-before-and-after method', () => {
  // UF/IFAS drop example: 20-0-10 at 1 lb N needs 5 lb per 1,000 sq ft, so 0.5 lb on a 100 sq ft test.
  const exact = calibrate(100, 3, 2.5, 20, 1)!;
  close(exact.perThousand, 5);
  close(exact.target, 5);
  assert.equal(exact.verdict, 'on-target');
  const heavy = calibrate(1000, 20, 13, 20, 1)!; // 7 lb spread against a 5 lb target
  assert.equal(heavy.verdict, 'too-heavy');
  close(heavy.off, 40);
  assert.equal(calibrate(1000, 20, 16.5, 20, 1)!.verdict, 'too-light');
  assert.equal(calibrate(1000, 20, 15.4, 20, 1)!.verdict, 'on-target', '4.6 lb is within 10% of 5 lb');
  for (const args of [[0, 20, 10, 20, 1], [1000, 10, 12, 20, 1], [1000, 10, 10, 20, 1], [1000, 20, 10, 0, 1], [1000, 20, 10, 20, 3]]) {
    assert.equal(calibrate(...(args as [number, number, number, number, number])), null, args.join(','));
  }
});

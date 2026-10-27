/** Math for the guide tools: lawn area by shape, what is in a bag, and spreader calibration. */

export type ShapeKind = 'rectangle' | 'circle' | 'triangle';

export interface Shape {
  kind: ShapeKind;
  a: number; // rectangle length, circle diameter, triangle base (ft)
  b: number; // rectangle width, triangle height (ft); unused for circles
  subtract: boolean; // a house, drive or bed cut out of the lawn
}

/** Area of one shape in square feet, or NaN when its measurements are missing or not positive. */
export function shapeArea(shape: Shape): number {
  const valid = (value: number) => Number.isFinite(value) && value > 0 && value <= 100_000;
  if (!valid(shape.a) || (shape.kind !== 'circle' && !valid(shape.b))) return Number.NaN;
  if (shape.kind === 'circle') return Math.PI * (shape.a / 2) ** 2;
  return shape.kind === 'triangle' ? shape.a * shape.b / 2 : shape.a * shape.b;
}

/** Lawn area: grass shapes added, cut-outs taken away. Shapes with missing numbers are skipped. */
export function lawnArea(shapes: readonly Shape[]): { area: number; grass: number; removed: number; counted: number } {
  let grass = 0, removed = 0, counted = 0;
  for (const shape of shapes) {
    const area = shapeArea(shape);
    if (!Number.isFinite(area)) continue;
    counted += 1;
    if (shape.subtract) removed += area; else grass += area;
  }
  return { area: Math.max(0, grass - removed), grass, removed, counted };
}

export interface BagContents {
  nitrogen: number; phosphate: number; potash: number; other: number; // lb in the bag
  phosphorus: number; potassium: number; // elemental lb (labels list P2O5 and K2O)
  perPoundOfNitrogen: number; // lb of product per 1 lb N per 1,000 sq ft (NC State: 100 ÷ first number)
}

/** What a bag holds by weight. Labels give phosphate as P2O5 and potash as K2O; 0.4364 and 0.8301 convert to P and K. */
export function bagContents(weight: number, n: number, p: number, k: number): BagContents | null {
  const ok = Number.isFinite(weight) && weight > 0 && weight <= 2000 && [n, p, k].every((x) => Number.isFinite(x) && x >= 0)
    && n > 0 && n <= 46 && n + p + k <= 100; // 46% (urea) is the most nitrogen a fertilizer carries
  if (!ok) return null;
  const nitrogen = weight * n / 100, phosphate = weight * p / 100, potash = weight * k / 100;
  return { nitrogen, phosphate, potash, other: weight - nitrogen - phosphate - potash,
    phosphorus: phosphate * 0.4364, potassium: potash * 0.8301, perPoundOfNitrogen: 100 / n };
}

export type Verdict = 'on-target' | 'too-heavy' | 'too-light';

export interface Calibration {
  applied: number; // lb that left the spreader
  perThousand: number; // lb per 1,000 sq ft actually spread
  target: number; // lb per 1,000 sq ft wanted
  off: number; // percent above (+) or below (-) the target
  verdict: Verdict;
}

/** UF/IFAS method: weigh the product before and after one pass over a measured area. Within 10% counts as on target. */
export function calibrate(area: number, before: number, after: number, nitrogenPercent: number, rate: number): Calibration | null {
  const positive = (value: number) => Number.isFinite(value) && value > 0;
  if (![area, before, nitrogenPercent, rate].every(positive) || !Number.isFinite(after) || after < 0 || after >= before
      || nitrogenPercent > 46 || rate > 2) return null;
  const applied = before - after;
  const perThousand = applied * 1000 / area;
  const target = rate / (nitrogenPercent / 100);
  const off = (perThousand - target) / target * 100;
  return { applied, perThousand, target, off, verdict: Math.abs(off) <= 10 ? 'on-target' : off > 0 ? 'too-heavy' : 'too-light' };
}

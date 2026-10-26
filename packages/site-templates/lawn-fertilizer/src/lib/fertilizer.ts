/** Lawn fertilizer math: how much product delivers a nitrogen rate, and how many bags to buy.
 *
 * Product per 1,000 sq ft = nitrogen rate ÷ (N% ÷ 100), the extension formula used by Iowa State,
 * Rutgers (FS839) and NC State (AG-931). Purchase quantities always round up to whole bags.
 */

export type Field = 'area' | 'nitrogen' | 'phosphorus' | 'potassium' | 'rate' | 'bagWeight';

export interface PlanInput {
  area: number; // square feet
  nitrogen: number; // first bag number, % N
  phosphorus: number; // second bag number, % P2O5
  potassium: number; // third bag number, % K2O
  rate: number; // lb of nitrogen per 1,000 sq ft for this feeding
  bagWeight: number; // lb of product in one bag
}

export type RateBand = 'light' | 'standard' | 'heavy';

export interface Plan {
  productPerThousand: number; // lb of product per 1,000 sq ft (the spreader target)
  productTotal: number; // lb of product for the whole lawn
  nitrogenTotal: number; // lb of actual nitrogen applied
  bags: number; // whole bags to buy
  leftover: number; // lb left in the last bag
  rateBand: RateBand;
  phosphorus: boolean; // the product contains phosphorus
}

export type PlanResult = { ok: true; plan: Plan } | { ok: false; errors: Partial<Record<Field, string>> };

export const LIMITS: Record<Field, readonly [number, number]> = {
  area: [1, 1_000_000], nitrogen: [1, 46], phosphorus: [0, 60], potassium: [0, 60], rate: [0.1, 2], bagWeight: [1, 100],
};

const MESSAGES: Record<Field, string> = {
  area: 'Enter your lawn area in square feet, from 1 to 1,000,000.',
  nitrogen: 'Enter the first number on the bag, from 1 to 46.',
  phosphorus: 'Enter the second number on the bag, from 0 to 60.',
  potassium: 'Enter the third number on the bag, from 0 to 60.',
  rate: 'Choose a feeding rate from 0.1 to 2 lb of nitrogen per 1,000 sq ft.',
  bagWeight: 'Enter the bag weight in pounds, from 1 to 100.',
};

/** Read a typed number the way people write it: "1,800", " 12.5 ". Blank or malformed text is NaN. */
export function parseNumber(raw: string): number {
  const text = raw.trim().replace(/,(?=\d{3}(\D|$))/g, '');
  return /^\d*\.?\d+$|^\d+\.$/.test(text) ? Number(text) : Number.NaN;
}

/** Light up to 0.5 lb N, standard up to 1 lb; above 1 lb is more quick-release nitrogen than one feeding should carry. */
export function rateBand(rate: number): RateBand {
  return rate <= 0.5 ? 'light' : rate <= 1 ? 'standard' : 'heavy';
}

export function areaFromDimensions(length: number, width: number): number {
  return Number.isFinite(length) && Number.isFinite(width) && length > 0 && width > 0 ? length * width : Number.NaN;
}

export function planFertilizer(input: PlanInput): PlanResult {
  const errors: Partial<Record<Field, string>> = {};
  for (const field of Object.keys(LIMITS) as Field[]) {
    const value = input[field];
    const [low, high] = LIMITS[field];
    if (!Number.isFinite(value) || value < low || value > high) errors[field] = MESSAGES[field];
  }
  if (!errors.nitrogen && !errors.phosphorus && !errors.potassium
      && input.nitrogen + input.phosphorus + input.potassium > 100) {
    errors.nitrogen = 'The three bag numbers are percentages, so together they cannot pass 100.';
  }
  if (Object.keys(errors).length) return { ok: false, errors };

  const productPerThousand = input.rate / (input.nitrogen / 100);
  const productTotal = productPerThousand * input.area / 1000;
  // A tiny tolerance keeps exact multiples (30 lb in 15 lb bags) from rounding up to an extra bag.
  const bags = Math.max(1, Math.ceil(productTotal / input.bagWeight - 1e-9));
  return {
    ok: true,
    plan: {
      productPerThousand, productTotal, nitrogenTotal: input.rate * input.area / 1000, bags,
      leftover: bags * input.bagWeight - productTotal, rateBand: rateBand(input.rate), phosphorus: input.phosphorus > 0,
    },
  };
}

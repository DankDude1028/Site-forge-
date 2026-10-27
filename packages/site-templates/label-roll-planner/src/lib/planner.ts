export interface LabelInputs {
  quantity: number;
  labelsPerItem: number;
  wastePercent: number;
  labelsPerRoll: number;
  rollsOnHand: number;
}

export interface LabelPlan {
  baseLabels: number;
  labelsNeeded: number;
  rollsRequired: number;
  rollsToOrder: number;
  labelsLeft: number;
}

export interface RollTelemetry {
  allowanceLabels: number;
  totalCapacity: number;
  lastRollUsed: number;
  lastRollUsedPercent: number;
  lastRollAngle: number;
  baseSharePercent: number;
  allowanceSharePercent: number;
  spareSharePercent: number;
}

export interface RollComparisonRow {
  labelsPerRoll: number;
  rollsRequired: number;
  rollsToOrder: number;
  labelsLeft: number;
  lastRollUsedPercent: number;
  isCurrent: boolean;
  isLowestSpare: boolean;
}

export interface BatchPreset {
  id: string;
  name: string;
  tag: string;
  inputs: LabelInputs;
}

export const COMMON_ROLL_SIZES = [250, 500, 1000, 2500] as const;

export const BATCH_PRESETS: readonly BatchPreset[] = [
  {
    id: 'jar-batch',
    name: 'Jar batch',
    tag: '250 × 2 · 500/roll',
    inputs: { quantity: 250, labelsPerItem: 2, wastePercent: 5, labelsPerRoll: 500, rollsOnHand: 1 },
  },
  {
    id: 'candle-run',
    name: 'Candle run',
    tag: '600 × 3 · 500/roll',
    inputs: { quantity: 600, labelsPerItem: 3, wastePercent: 5, labelsPerRoll: 500, rollsOnHand: 1 },
  },
  {
    id: 'bottle-line',
    name: 'Bottle run',
    tag: '1,200 × 2 · 1,000/roll',
    inputs: { quantity: 1200, labelsPerItem: 2, wastePercent: 4, labelsPerRoll: 1000, rollsOnHand: 0 },
  },
  {
    id: 'shelf-covered',
    name: 'Covered stock',
    tag: '120 × 1 · 1 on shelf',
    inputs: { quantity: 120, labelsPerItem: 1, wastePercent: 3, labelsPerRoll: 250, rollsOnHand: 1 },
  },
];

const PLACEMENTS: Record<number, readonly string[]> = {
  1: ['Front'], 2: ['Front', 'Back'], 3: ['Front', 'Back', 'Seal'], 4: ['Front', 'Back', 'Neck', 'Lid'],
};

/** The labels on one item, for the label strip: whole cards only, with a summary card past four. */
export function placementCards(count: number): { title: string; meta: string }[] {
  const of = (index: number) => `Label ${index + 1} of ${count}`;
  if (count <= 4) return (PLACEMENTS[count] ?? []).map((title, index) => ({ title, meta: of(index) }));
  return [...PLACEMENTS[3].map((title, index) => ({ title, meta: of(index) })),
    { title: `+${count - 3} more`, meta: `Labels 4–${count}` }];
}

export function planLabels(input: LabelInputs): LabelPlan {
  const { quantity, labelsPerItem, wastePercent, labelsPerRoll, rollsOnHand } = input;
  for (const value of [quantity, labelsPerItem, labelsPerRoll, rollsOnHand]) {
    if (!Number.isSafeInteger(value)) throw new RangeError('Counts must be whole numbers.');
  }
  if (quantity < 1 || quantity > 1_000_000 || labelsPerItem < 1 || labelsPerItem > 100) {
    throw new RangeError('Use 1–1,000,000 items and 1–100 labels per item.');
  }
  if (labelsPerRoll < 1 || labelsPerRoll > 1_000_000 || rollsOnHand < 0 || rollsOnHand > 1_000_000) {
    throw new RangeError('Check the labels per roll and rolls on hand.');
  }
  if (!Number.isFinite(wastePercent) || wastePercent < 0 || wastePercent > 100) {
    throw new RangeError('Extra allowance must be between 0% and 100%.');
  }
  const baseLabels = quantity * labelsPerItem;
  // The allowance is extra stock, not a yield-loss calculation.
  const labelsNeeded = Math.ceil(baseLabels * (100 + wastePercent) / 100);
  const rollsRequired = Math.ceil(labelsNeeded / labelsPerRoll);
  return {
    baseLabels,
    labelsNeeded,
    rollsRequired,
    rollsToOrder: Math.max(0, rollsRequired - rollsOnHand),
    labelsLeft: rollsRequired * labelsPerRoll - labelsNeeded,
  };
}

export function computeRollTelemetry(input: LabelInputs, plan = planLabels(input)): RollTelemetry {
  const allowanceLabels = Math.max(0, plan.labelsNeeded - plan.baseLabels);
  const totalCapacity = plan.rollsRequired * input.labelsPerRoll;
  const lastRollUsed = input.labelsPerRoll - plan.labelsLeft;
  const usedRatio = lastRollUsed / input.labelsPerRoll;
  const baseSharePercent = (plan.baseLabels / totalCapacity) * 100;
  const allowanceSharePercent = (allowanceLabels / totalCapacity) * 100;
  const spareSharePercent = Math.max(0, 100 - baseSharePercent - allowanceSharePercent);
  return {
    allowanceLabels,
    totalCapacity,
    lastRollUsed,
    lastRollUsedPercent: Math.round(usedRatio * 100),
    lastRollAngle: Math.round(usedRatio * 360 * 100) / 100,
    baseSharePercent: Math.round(baseSharePercent * 100) / 100,
    allowanceSharePercent: Math.round(allowanceSharePercent * 100) / 100,
    spareSharePercent: Math.round(spareSharePercent * 100) / 100,
  };
}

export function compareRollSizes(
  input: LabelInputs,
  sizes: readonly number[] = COMMON_ROLL_SIZES,
): RollComparisonRow[] {
  const uniqueSizes = Array.from(new Set([...sizes, input.labelsPerRoll])).sort((a, b) => a - b);
  const rows = uniqueSizes.map(size => {
    const plan = planLabels({ ...input, labelsPerRoll: size });
    const usedRatio = (size - plan.labelsLeft) / size;
    return {
      labelsPerRoll: size,
      rollsRequired: plan.rollsRequired,
      rollsToOrder: plan.rollsToOrder,
      labelsLeft: plan.labelsLeft,
      lastRollUsedPercent: Math.round(usedRatio * 100),
      isCurrent: size === input.labelsPerRoll,
      isLowestSpare: false,
    };
  });
  const minSpare = Math.min(...rows.map(row => row.labelsLeft));
  let marked = false;
  return rows.map(row => {
    if (!marked && row.labelsLeft === minSpare) {
      marked = true;
      return { ...row, isLowestSpare: true };
    }
    return row;
  });
}

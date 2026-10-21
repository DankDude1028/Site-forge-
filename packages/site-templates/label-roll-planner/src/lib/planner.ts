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
    throw new RangeError('Waste buffer must be between 0% and 100%.');
  }
  const baseLabels = quantity * labelsPerItem;
  // Waste is an additional allowance, not a yield-loss calculation.
  const labelsNeeded = Math.ceil(baseLabels * (100 + wastePercent) / 100);
  const rollsRequired = Math.ceil(labelsNeeded / labelsPerRoll);
  return { baseLabels, labelsNeeded, rollsRequired,
    rollsToOrder: Math.max(0, rollsRequired - rollsOnHand),
    labelsLeft: rollsRequired * labelsPerRoll - labelsNeeded };
}

import { planLabels } from '../lib/planner.ts';

const form = document.querySelector<HTMLFormElement>('#planner');
const output = document.querySelector<HTMLOutputElement>('#result');
const error = document.querySelector<HTMLParagraphElement>('#error');
const numbers = new Intl.NumberFormat('en-US');

function calculate(event?: Event): void {
  event?.preventDefault();
  if (!form || !output || !error) return;
  try {
    const data = new FormData(form);
    const read = (key: string): number => {
      const value = data.get(key);
      if (typeof value !== 'string' || value.trim() === '') throw new Error('Fill in every input.');
      return Number(value);
    };
    const result = planLabels({ quantity: read('quantity'), labelsPerItem: read('labels'),
      wastePercent: read('waste'), labelsPerRoll: read('perRoll'), rollsOnHand: read('onHand') });
    const values: Record<string, number> = { order: result.rollsToOrder, required: result.rollsRequired,
      needed: result.labelsNeeded, left: result.labelsLeft };
    for (const [id, value] of Object.entries(values)) {
      const element = document.querySelector(`#${id}`);
      if (element) element.textContent = numbers.format(value);
    }
    const orderLabel = document.querySelector('#order-label');
    if (orderLabel) orderLabel.textContent = result.rollsToOrder === 1 ? 'roll to order' : 'rolls to order';
    error.textContent = '';
    output.hidden = false;
  } catch (cause) {
    error.textContent = cause instanceof Error ? cause.message : 'Please check your inputs.';
    output.hidden = true;
  }
}

form?.addEventListener('submit', calculate);
form?.addEventListener('input', () => {
  if (output) output.hidden = true;
  if (error) error.textContent = '';
});
calculate();

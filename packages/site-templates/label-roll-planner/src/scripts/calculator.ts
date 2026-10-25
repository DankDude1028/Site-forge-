import { planLabels } from '../lib/planner.ts';

const form = document.querySelector<HTMLFormElement>('#planner');
const output = document.querySelector<HTMLOutputElement>('#result');
const error = document.querySelector<HTMLParagraphElement>('#error');
const announcer = document.querySelector<HTMLParagraphElement>('#announce');
const numbers = new Intl.NumberFormat('en-US');
const MAX_DRAWN_ROLLS = 24;
const FIELD_MESSAGES: Record<string, string> = {
  quantity: 'Enter a whole number of items from 1 to 1,000,000.',
  labels: 'Enter a whole number of labels per item from 1 to 100.',
  perRoll: 'Enter a whole number of labels per roll from 1 to 1,000,000.',
  onHand: 'Enter a whole number of rolls from 0 to 1,000,000.',
  waste: 'Enter an allowance from 0 to 100%.',
};
type Announce = 'none' | 'later' | 'now';
let edited = false;
let announceTimer: number | undefined;

function setText(id: string, text: string): void {
  const element = document.getElementById(id);
  if (element) element.textContent = text;
}

/** Marks each invalid field with its own message; returns the first invalid input. */
function invalidField(): HTMLInputElement | null {
  let first: HTMLInputElement | null = null;
  for (const [name, message] of Object.entries(FIELD_MESSAGES)) {
    const input = form?.elements.namedItem(name);
    if (!(input instanceof HTMLInputElement)) continue;
    const valid = input.value.trim() !== '' && input.checkValidity();
    input.setAttribute('aria-invalid', String(!valid));
    setText(`${name}-error`, valid ? '' : message);
    if (!valid && !first) first = input;
  }
  return first;
}

/** One circle per roll, drawn to scale: owned rolls outlined, rolls to order filled, spare labels hatched. */
function drawStrip(required: number, onHand: number, perRoll: number, spare: number): void {
  const strip = document.getElementById('strip');
  if (!strip) return;
  strip.replaceChildren();
  const owned = Math.min(onHand, required);
  const drawn = Math.min(required, MAX_DRAWN_ROLLS);
  for (let index = 0; index < drawn; index += 1) {
    const roll = document.createElement('span');
    roll.className = `roll ${index < owned ? 'have' : 'order'}`;
    if (index === required - 1 && spare > 0) {
      roll.classList.add('partial');
      roll.style.setProperty('--used', `${((perRoll - spare) / perRoll) * 100}%`);
    }
    strip.append(roll);
  }
  if (required > drawn) {
    const more = document.createElement('span');
    more.className = 'more';
    more.textContent = `+${numbers.format(required - drawn)} more`;
    strip.append(more);
  }
}

function announce(text: string, when: Announce): void {
  window.clearTimeout(announceTimer);
  if (!announcer || when === 'none') return;
  const say = (): void => { announcer.textContent = text; };
  if (when === 'now') say();
  else announceTimer = window.setTimeout(say, 900);
}

function calculate(when: Announce): boolean {
  if (!form || !output || !error) return false;
  error.textContent = '';
  if (invalidField()) {
    output.hidden = true;
    announce('', 'none');
    return false;
  }
  try {
    const data = new FormData(form);
    const read = (key: string): number => Number(data.get(key));
    const inputs = { quantity: read('quantity'), labelsPerItem: read('labels'), wastePercent: read('waste'),
      labelsPerRoll: read('perRoll'), rollsOnHand: read('onHand') };
    const result = planLabels(inputs);
    const rolls = (count: number): string => `${numbers.format(count)} ${count === 1 ? 'roll' : 'rolls'}`;
    setText('order', numbers.format(result.rollsToOrder));
    setText('order-label', result.rollsToOrder === 1 ? 'roll to order' : 'rolls to order');
    setText('needed', numbers.format(result.labelsNeeded));
    setText('required', numbers.format(result.rollsRequired));
    setText('left', numbers.format(result.labelsLeft));
    setText('result-kind', edited ? 'Your batch' : 'Sample batch. Change any number to plan yours.');
    const enough = document.getElementById('enough');
    if (enough) enough.hidden = result.rollsToOrder !== 0;
    drawStrip(result.rollsRequired, inputs.rollsOnHand, inputs.labelsPerRoll, result.labelsLeft);
    output.hidden = false;
    announce(`${rolls(result.rollsToOrder)} to order. This batch uses ${rolls(result.rollsRequired)} ` +
      `for ${numbers.format(result.labelsNeeded)} labels, leaving ${numbers.format(result.labelsLeft)} spare.`, when);
    return true;
  } catch (cause) {
    error.textContent = cause instanceof Error ? cause.message : 'Please check your inputs.';
    output.hidden = true;
    return false;
  }
}

form?.addEventListener('input', () => {
  edited = true;
  calculate('later');
});
form?.addEventListener('submit', event => {
  event.preventDefault();
  edited = true;
  if (calculate('now')) {
    const bottom = output?.getBoundingClientRect().bottom ?? 0;
    if (bottom > window.innerHeight) {
      const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      output?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'nearest' });
    }
  } else {
    invalidField()?.focus();
  }
});
calculate('none');

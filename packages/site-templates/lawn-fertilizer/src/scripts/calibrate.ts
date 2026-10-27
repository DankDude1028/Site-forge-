import { parseNumber } from '../lib/fertilizer.ts';
import { calibrate } from '../lib/tools.ts';
import { fixed, pounds } from '../lib/format.ts';

const $ = (id: string) => document.getElementById(id)!;
const field = (id: string) => document.getElementById(id) as HTMLInputElement;
const [area, before, after, nitrogen, rate] = ['c-area', 'c-before', 'c-after', 'c-n', 'c-rate'].map(field);
let announceTimer = 0;

const mode = () => document.querySelector<HTMLInputElement>('input[name="mode"]:checked')?.value ?? 'left';

function update() {
  const swept = mode() === 'swept';
  $('before-field').hidden = swept;
  $('c-after-label').textContent = swept ? 'Swept up' : 'Left after';
  const weighed = parseNumber(after.value);
  // Swept up: the weighed amount is what came out, the same as loading it and having nothing left.
  const result = swept
    ? calibrate(parseNumber(area.value), weighed, 0, parseNumber(nitrogen.value), parseNumber(rate.value))
    : calibrate(parseNumber(area.value), parseNumber(before.value), weighed, parseNumber(nitrogen.value), parseNumber(rate.value));
  const readout = $('cal-readout');
  readout.classList.toggle('is-invalid', !result);
  after.setAttribute('aria-invalid', String(!result));
  document.querySelectorAll<HTMLButtonElement>('[data-area]').forEach((chip) =>
    chip.setAttribute('aria-pressed', String(Number(chip.dataset.area) === parseNumber(area.value))));
  if (!result) {
    $('c-error').textContent = swept
      ? 'Enter the test area, the weight you swept up, the nitrogen % and a target from 0.1 to 2 lb.'
      : 'Enter the test area and both weights (what is left must be less than what you loaded), plus the nitrogen % and target.';
    $('c-verdict').textContent = 'Fill in every number to check your setting.';
    return;
  }
  $('c-error').textContent = '';
  readout.dataset.verdict = result.verdict;
  $('c-actual').textContent = fixed(result.perThousand, 1);
  $('c-target').textContent = fixed(result.target, 1);
  $('c-applied').textContent = pounds(result.applied);
  $('c-mark').style.setProperty('--at', Math.min(1, Math.max(0, result.perThousand / (result.target * 2))).toFixed(4));
  const off = Math.round(Math.abs(result.off));
  const verdict = result.verdict === 'on-target' ? 'On target. Keep this setting for this product.'
    : result.verdict === 'too-heavy' ? `${off}% too heavy. Close the setting a step and test again.`
      : `${off}% too light. Open the setting a step and test again.`;
  $('c-verdict').textContent = verdict;
  clearTimeout(announceTimer);
  announceTimer = window.setTimeout(() => {
    $('c-announce').textContent = `${fixed(result.perThousand, 1)} pounds per 1,000 square feet. ${verdict}`;
  }, 700);
}

for (const input of [area, before, after, nitrogen, rate]) input.addEventListener('input', update);
document.querySelectorAll('input[name="mode"]').forEach((radio) => radio.addEventListener('change', update));
document.querySelectorAll<HTMLButtonElement>('[data-area]').forEach((chip) => chip.addEventListener('click', () => {
  area.value = chip.dataset.area ?? '1000';
  update();
}));
$('calform').addEventListener('submit', (event) => event.preventDefault());
update();

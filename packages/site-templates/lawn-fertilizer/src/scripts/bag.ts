import { parseNumber } from '../lib/fertilizer.ts';
import { bagContents } from '../lib/tools.ts';
import { fixed, pounds, whole } from '../lib/format.ts';

const $ = (id: string) => document.getElementById(id)!;
const field = (id: string) => document.getElementById(id) as HTMLInputElement;
const inputs = [field('b-weight'), field('b-n'), field('b-p'), field('b-k')];
let rate = 1;
let announceTimer = 0;

function update() {
  const [weight, n, p, k] = inputs.map((input) => parseNumber(input.value));
  const bag = bagContents(weight, n, p, k);
  const readout = $('bag-readout');
  readout.classList.toggle('is-invalid', !bag);
  for (const input of inputs) input.setAttribute('aria-invalid', String(!bag && !Number.isFinite(parseNumber(input.value))));
  $('b-error').textContent = bag ? '' : !(n >= 1 && n <= 46) ? 'Enter the first number on the bag, from 1 to 46.'
    : n + p + k > 100 ? 'The three numbers are percentages, so together they cannot pass 100.'
      : 'Enter the bag weight in pounds and all three numbers.';
  document.querySelectorAll<HTMLButtonElement>('[data-cover]').forEach((chip) =>
    chip.setAttribute('aria-pressed', String(Number(chip.dataset.cover) === rate)));
  $('o-rate').textContent = fixed(rate, 2);
  if (!bag) return;
  const share = (value: number) => (value / weight).toFixed(4);
  $('seg-n').style.setProperty('--w', share(bag.nitrogen));
  $('seg-p').style.setProperty('--w', share(bag.phosphate));
  $('seg-k').style.setProperty('--w', share(bag.potash));
  $('seg-o').style.setProperty('--w', share(bag.other));
  $('o-n').textContent = pounds(bag.nitrogen);
  $('o-p').textContent = pounds(bag.phosphate);
  $('o-pe').textContent = pounds(bag.phosphorus);
  $('o-k').textContent = pounds(bag.potash);
  $('o-ke').textContent = pounds(bag.potassium);
  $('o-o').textContent = pounds(bag.other);
  $('o-cover').textContent = whole(bag.nitrogen / rate * 1000);
  $('o-per').textContent = fixed(bag.perPoundOfNitrogen * rate, 2);
  ($('bag-use') as HTMLAnchorElement).href = `/#n=${n}&p=${p}&k=${k}&bag=${weight}`;
  clearTimeout(announceTimer);
  announceTimer = window.setTimeout(() => {
    $('bag-announce').textContent = `${pounds(bag.nitrogen)} pounds of nitrogen. One bag feeds ${whole(bag.nitrogen / rate * 1000)} square feet.`;
  }, 700);
}

for (const input of inputs) input.addEventListener('input', update);
document.querySelectorAll<HTMLButtonElement>('[data-cover]').forEach((chip) => chip.addEventListener('click', () => {
  rate = Number(chip.dataset.cover);
  update();
}));
$('bagform').addEventListener('submit', (event) => event.preventDefault());
update();

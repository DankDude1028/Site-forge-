import { areaFromDimensions, parseNumber, planFertilizer, type Field, type Plan, type RateBand } from '../lib/fertilizer.ts';
import { GRASSES, feedingsPerYear, type Grass } from '../lib/grasses.ts';
import { amount, fixed, gaugeAngle, pounds, tileColumns, tileLayout, whole } from '../lib/format.ts';

const $ = <T extends Element = HTMLElement>(id: string) => document.getElementById(id) as unknown as T;
const calm = matchMedia('(prefers-reduced-motion: reduce)');

const form = $<HTMLFormElement>('planner');
const inputs = {
  area: $<HTMLInputElement>('area'), nitrogen: $<HTMLInputElement>('nitrogen'), phosphorus: $<HTMLInputElement>('phosphorus'),
  potassium: $<HTMLInputElement>('potassium'), bagWeight: $<HTMLInputElement>('bag'), rate: $<HTMLInputElement>('rate'),
};
const areaRange = $<HTMLInputElement>('area-range');
const errorTargets: Record<Field, string> = {
  area: 'area-error', nitrogen: 'npk-error', phosphorus: 'npk-error', potassium: 'npk-error', bagWeight: 'bag-error', rate: 'rate-error',
};
const BAND_TEXT: Record<RateBand, string> = {
  light: 'A light feeding. Good for a quick green-up or an extra summer feeding.',
  standard: 'A standard feeding, inside the usual 0.5–1 lb per 1,000 sq ft.',
  heavy: 'Too much quick-release nitrogen for one feeding. Split it in two, or use a slow-release product labeled for this rate.',
};
const FULL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
  'November', 'December'];

/** Count a number up or down to its new value; reduced motion and large jumps of text just swap. */
function tween(element: HTMLElement, to: number, format: (value: number) => string) {
  const from = Number(element.dataset.value ?? Number.NaN);
  element.dataset.value = String(to);
  if (calm.matches || !Number.isFinite(from) || from === to) {
    element.textContent = format(to);
    return;
  }
  const started = performance.now(), duration = 420;
  const token = String(started);
  element.dataset.token = token;
  const step = (now: number) => {
    if (element.dataset.token !== token) return;
    const t = Math.min(1, (now - started) / duration), eased = 1 - (1 - t) ** 3;
    element.textContent = format(from + (to - from) * eased);
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function setText(id: string, text: string) {
  const element = $(id);
  if (element && element.textContent !== text) {
    element.textContent = text;
    if (!calm.matches) {
      element.classList.remove('flip');
      void element.offsetWidth; // restart the flip animation
      element.classList.add('flip');
    }
  }
}

/** Send a feeding wave across the lawn: each tile flashes in turn, like a spreader pass. */
function wave(box: HTMLElement) {
  if (calm.matches) return;
  box.classList.remove('wave');
  void box.offsetWidth; // restart the wave
  box.classList.add('wave');
}

function renderTiles(area: number, band: RateBand) {
  const box = $('tiles');
  const layout = tileLayout(area);
  const wanted = layout.full + (layout.partial > 0 ? 1 : 0);
  box.style.setProperty('--cols', String(tileColumns(wanted)));
  box.dataset.band = band;
  const tiles = Array.from(box.children) as HTMLElement[];
  for (let index = tiles.length; index < wanted; index++) {
    const tile = document.createElement('span');
    tile.className = 'tile sprout';
    tile.style.setProperty('--i', String(index - tiles.length));
    box.append(tile);
    tiles.push(tile);
  }
  tiles.slice(wanted).forEach((tile) => tile.remove());
  tiles.slice(0, wanted).forEach((tile, index) => {
    const partial = layout.partial > 0 && index === wanted - 1;
    tile.classList.toggle('partial', partial);
    tile.style.setProperty('--fill', partial ? layout.partial.toFixed(3) : '1');
    tile.style.setProperty('--w', String(index));
  });
  wave(box);
  setText('tile-scale', `1 tile = ${whole(layout.scale)} sq ft`);
}

function renderBags(plan: Plan, bagWeight: number, label: string) {
  const box = $('bags');
  const shown = Math.min(plan.bags, 12);
  const bags = Array.from(box.children) as HTMLElement[];
  for (let index = bags.length; index < shown; index++) {
    const bag = document.createElement('span');
    bag.className = 'bag drop';
    bag.style.setProperty('--i', String(index - bags.length));
    const tag = document.createElement('span');
    tag.className = 'bag-label';
    bag.append(tag);
    box.append(bag);
    bags.push(bag);
  }
  bags.slice(shown).forEach((bag) => bag.remove());
  const lastFill = (bagWeight - plan.leftover) / bagWeight;
  bags.slice(0, shown).forEach((bag, index) => {
    bag.style.setProperty('--fill', (index === shown - 1 && plan.bags <= 12 ? lastFill : 1).toFixed(3));
    (bag.firstElementChild as HTMLElement).textContent = label;
  });
  box.dataset.more = plan.bags > 12 ? `+${(plan.bags - 12).toLocaleString('en-US')}` : '';
  setText('bag-tag', label);
}

let announceTimer = 0;
function announce(text: string) {
  clearTimeout(announceTimer);
  announceTimer = window.setTimeout(() => { $('announce').textContent = text; }, 700);
}

function readInputs() {
  return {
    area: parseNumber(inputs.area.value), nitrogen: parseNumber(inputs.nitrogen.value),
    phosphorus: parseNumber(inputs.phosphorus.value), potassium: parseNumber(inputs.potassium.value),
    bagWeight: parseNumber(inputs.bagWeight.value), rate: Number(inputs.rate.value),
  };
}

function update() {
  const values = readInputs();
  const result = planFertilizer(values);
  const errors = result.ok ? {} : result.errors;
  for (const field of Object.keys(inputs) as Field[]) inputs[field].setAttribute('aria-invalid', String(Boolean(errors[field])));
  for (const id of new Set(Object.values(errorTargets))) $(id).textContent = '';
  for (const [field, message] of Object.entries(errors)) $(errorTargets[field as Field]).textContent = message ?? '';

  const rate = values.rate;
  $('rate-value').textContent = fixed(rate, 2);
  inputs.rate.setAttribute('aria-valuetext', `${fixed(rate, 2)} lb per 1,000 sq ft`);
  document.querySelectorAll<HTMLButtonElement>('.presets .chip').forEach((chip) =>
    chip.setAttribute('aria-pressed', String(Math.abs(Number(chip.dataset.rate) - rate) < 1e-9)));
  ($('needle') as unknown as SVGGElement).style.setProperty('--angle', `${gaugeAngle(rate)}deg`);
  updateCalendarRate(rate);

  const results = $('results');
  results.classList.toggle('is-invalid', !result.ok);
  $('invalid-note').hidden = result.ok;
  if (!result.ok) {
    ['total', 'per1000', 'n-total'].forEach((id) => { const el = $(id); el.textContent = '–'; delete el.dataset.value; });
    $('buy').hidden = true;
    $('p-note').hidden = true;
    announce('Fix the highlighted field to see your numbers.');
    return;
  }
  const plan = result.plan;
  const label = `${whole(values.nitrogen)}-${whole(values.phosphorus)}-${whole(values.potassium)}`;
  $('buy').hidden = false;
  tween($('total'), plan.productTotal, pounds);
  tween($('per1000'), plan.productPerThousand, (value) => fixed(value, 2));
  tween($('n-total'), plan.nitrogenTotal, pounds);
  setText('bags-count', `${plan.bags.toLocaleString('en-US')} ${plan.bags === 1 ? 'bag' : 'bags'}`);
  setText('bag-size', `${amount(values.bagWeight)} lb`);
  setText('leftover', `${pounds(plan.leftover)} lb`);
  const band = $('band');
  band.dataset.band = plan.rateBand;
  band.textContent = BAND_TEXT[plan.rateBand];
  $('p-note').hidden = !plan.phosphorus;

  renderTiles(values.area, plan.rateBand);
  renderBags(plan, values.bagWeight, label);
  if (values.area >= Number(areaRange.min) && values.area <= Number(areaRange.max)) areaRange.value = String(values.area);

  // The bag guide and the worked math follow the calculator.
  setText('sack-n', whole(values.nitrogen));
  setText('sack-p', whole(values.phosphorus));
  setText('sack-k', whole(values.potassium));
  setText('sack-weight', amount(values.bagWeight));
  setText('short-n', whole(values.nitrogen));
  setText('short-result', fixed(100 / values.nitrogen, 1));
  setText('m-rate', fixed(rate, 2));
  setText('m-share', fixed(values.nitrogen / 100, 2));
  setText('m-per', fixed(plan.productPerThousand, 2));
  setText('m-per2', fixed(plan.productPerThousand, 2));
  setText('m-thousands', fixed(values.area / 1000, 1));
  setText('m-total', pounds(plan.productTotal));
  setText('m-total2', pounds(plan.productTotal));
  setText('m-bag', amount(values.bagWeight));
  setText('m-ratio', fixed(plan.productTotal / values.bagWeight, 2));
  setText('m-bags', plan.bags.toLocaleString('en-US'));

  announce(`Spread ${pounds(plan.productTotal)} pounds. Buy ${plan.bags} ${plan.bags === 1 ? 'bag' : 'bags'} of ${amount(values.bagWeight)} pounds. `
    + `Spreader target ${fixed(plan.productPerThousand, 2)} pounds per 1,000 square feet.`);
}

// Feeding calendar
let grass: Grass = GRASSES.find((item) => item.id === 'tall-fescue')!;
let currentRate = Number(inputs.rate.value);

function list(months: number[]): string {
  const names = months.map((month) => FULL_MONTHS[month]);
  return names.length <= 1 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`;
}

function updateCalendarRate(rate: number) {
  currentRate = rate;
  const [fewest, most] = feedingsPerYear(grass, rate);
  setText('feed-rate', fixed(rate, 2));
  setText('feed-count', `${fewest === most ? fewest : `${fewest}–${most}`} ${most === 1 ? 'feeding' : 'feedings'}`);
}

function updateCalendar() {
  const monthsOf = (kind: string) => Object.entries(grass.months).filter(([, feed]) => feed === kind).map(([m]) => Number(m));
  document.querySelectorAll<SVGPathElement>('.ring .seg').forEach((segment) => {
    segment.dataset.feed = grass.months[Number(segment.dataset.month)] ?? 'off';
  });
  const range = `${grass.annual[0]}–${grass.annual[1]}`;
  setText('season', grass.season === 'cool' ? 'Cool-season grass' : 'Warm-season grass');
  setText('annual', range);
  setText('ring-name', grass.name);
  setText('ring-range', `${range} lb N / yr`);
  setText('main-months', list(monthsOf('main')));
  setText('light-months', list(monthsOf('light')) || 'none');
  $('grass-note').textContent = grass.note;
  updateCalendarRate(currentRate);

  const now = new Date().getMonth();
  const order = Array.from({ length: 12 }, (_, offset) => (now + offset) % 12);
  const next = order.find((month) => grass.months[month] === 'main');
  const nextText = $('next');
  if (next !== undefined) {
    nextText.textContent = next === now
      ? `It's ${FULL_MONTHS[now]}: a main feeding month for ${grass.name.toLowerCase()}.`
      : `It's ${FULL_MONTHS[now]}. The next main feeding for ${grass.name.toLowerCase()} is ${FULL_MONTHS[next]}.`;
    nextText.hidden = false;
  }
}

function placeNowMarker() {
  const now = new Date().getMonth();
  const radians = ((now * 30 + 15) - 90) * Math.PI / 180;
  for (const id of ['now-dot', 'now-pulse']) {
    const dot = $(id) as unknown as SVGCircleElement;
    dot.setAttribute('cx', (220 + 151 * Math.cos(radians)).toFixed(2));
    dot.setAttribute('cy', (220 + 151 * Math.sin(radians)).toFixed(2));
    dot.removeAttribute('hidden');
  }
  document.querySelector(`.ring .seg[data-month="${now}"]`)?.classList.add('is-now');
  document.querySelectorAll('.ring .month')[now]?.classList.add('is-now');
}

// Wire up
form.addEventListener('submit', (event) => event.preventDefault());
for (const input of Object.values(inputs)) input.addEventListener('input', update);
areaRange.addEventListener('input', () => {
  inputs.area.value = Number(areaRange.value).toLocaleString('en-US');
  update();
});
document.querySelectorAll<HTMLButtonElement>('.presets .chip').forEach((chip) => chip.addEventListener('click', () => {
  inputs.rate.value = chip.dataset.rate ?? '0.75';
  update();
}));
$('use-dims').addEventListener('click', () => {
  const area = areaFromDimensions(parseNumber($<HTMLInputElement>('len').value), parseNumber($<HTMLInputElement>('wid').value));
  if (Number.isFinite(area)) {
    inputs.area.value = whole(area);
    update();
    inputs.area.focus();
  } else {
    $('area-error').textContent = 'Enter a length and a width in feet to work out the area.';
  }
});
document.querySelectorAll<HTMLInputElement>('input[name="grass"]').forEach((radio) => radio.addEventListener('change', () => {
  grass = GRASSES.find((item) => item.id === radio.value) ?? grass;
  updateCalendar();
}));

// Seed the tween values from the server-rendered numbers, then sync everything.
for (const id of ['total', 'per1000', 'n-total']) {
  const element = $(id);
  element.dataset.value = String(parseNumber(element.textContent ?? ''));
}
placeNowMarker();
updateCalendar();
update();

import { parseNumber } from '../lib/fertilizer.ts';
import { SEED_GRASSES, seedPlan, type SeedMode } from '../lib/seed.ts';
import { amount, seedPounds } from '../lib/format.ts';

const $ = (id: string) => document.getElementById(id)!;
const area = document.getElementById('s-area') as HTMLInputElement;
const bag = document.getElementById('s-bag') as HTMLInputElement;
const dots = Array.from(document.querySelectorAll<SVGCircleElement>('.seed-dot'));
const calm = matchMedia('(prefers-reduced-motion: reduce)');
let announceTimer = 0;

const checked = (name: string) => document.querySelector<HTMLInputElement>(`input[name="${name}"]:checked`)?.value ?? '';
const range = (pair: readonly [number, number], format: (value: number) => string) =>
  pair[0] === pair[1] ? format(pair[0]) : `${format(pair[0])}–${format(pair[1])}`;

/** Light up seed dots in proportion to the rate (6 lb per 1,000 sq ft fills the drawing), then sprinkle them in. */
function sprinkle(rate: number) {
  const on = Math.round(Math.min(1, rate / 6) * dots.length);
  dots.forEach((dot, index) => {
    const lit = index < on;
    if (lit && dot.dataset.on !== 'true' && !calm.matches) {
      dot.classList.remove('fall');
      void dot.getBoundingClientRect();
      dot.classList.add('fall');
    }
    dot.dataset.on = String(lit);
  });
}

function update() {
  const grassId = checked('s-grass');
  const grass = SEED_GRASSES.find((item) => item.id === grassId);
  const plan = seedPlan(parseNumber(area.value), grassId, checked('s-mode') as SeedMode, parseNumber(bag.value));
  const readout = $('seed-readout');
  readout.classList.toggle('is-invalid', !plan);
  area.setAttribute('aria-invalid', String(!plan && !(parseNumber(area.value) >= 1)));
  bag.setAttribute('aria-invalid', String(!plan && !(parseNumber(bag.value) > 0)));
  $('s-error').textContent = plan ? '' : 'Enter a lawn size from 1 to 1,000,000 sq ft and a bag size up to 100 lb.';
  $('s-note').textContent = grass?.note ?? '';
  if (!plan) return;
  readout.classList.toggle('not-seedable', !plan.seedable);
  if (!plan.seedable) {
    $('s-total').textContent = 'No seed';
    $('s-detail').textContent = 'This grass is not grown from seed. Buy sod or plugs for the area instead.';
    $('s-season').hidden = true;
    sprinkle(0);
    return;
  }
  $('s-season').hidden = false;
  $('s-total').textContent = range(plan.pounds, seedPounds);
  const bagWord = plan.bags[1] === 1 ? 'bag' : 'bags';
  $('s-detail').innerHTML = '';
  const strong = document.createElement('strong');
  strong.textContent = `${range(plan.perThousand, seedPounds)} lb per 1,000 sq ft`;
  $('s-detail').append('That is ', strong, `: ${range(plan.bags, String)} ${bagWord} of ${amount(parseNumber(bag.value))} lb.`);
  const season = document.createElement('strong');
  season.textContent = plan.season;
  $('s-season').replaceChildren('Best time to sow: ', season, '.');
  sprinkle(plan.perThousand[1]);
  clearTimeout(announceTimer);
  announceTimer = window.setTimeout(() => {
    $('s-announce').textContent = `Sow ${range(plan.pounds, seedPounds)} pounds of seed: ${range(plan.bags, String)} ${bagWord}.`;
  }, 700);
}

for (const input of [area, bag]) input.addEventListener('input', update);
document.querySelectorAll('input[name="s-grass"], input[name="s-mode"]').forEach((radio) => radio.addEventListener('change', update));
$('seedform').addEventListener('submit', (event) => event.preventDefault());
update();

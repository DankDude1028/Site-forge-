import { BATCH_PRESETS, compareRollSizes, computeRollTelemetry, placementCards, planLabels, type LabelInputs } from '../lib/planner.ts';

const form = document.querySelector<HTMLFormElement>('#planner');
const output = document.querySelector<HTMLOutputElement>('#result');
const error = document.querySelector<HTMLParagraphElement>('#error');
const announcer = document.querySelector<HTMLParagraphElement>('#announce');
const quantityInput = document.querySelector<HTMLInputElement>('#quantity');
const quantityRange = document.querySelector<HTMLInputElement>('#quantity-range');
const compareGrid = document.getElementById('compare-grid');
const spoolStage = document.getElementById('spool-stage');
const webConveyor = document.getElementById('web-conveyor');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
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

function setText(id: string, text: string, animate = false): void {
  const element = document.getElementById(id);
  if (!element) return;
  const changed = element.textContent !== text;
  element.textContent = text;
  if (animate && changed && edited && !reducedMotion.matches) {
    element.classList.remove('flip');
    void element.offsetWidth;
    element.classList.add('flip');
  }
}

function pulseClass(element: HTMLElement | null, className: string): void {
  if (!element || reducedMotion.matches) return;
  element.classList.remove(className);
  void element.offsetWidth;
  element.classList.add(className);
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
    roll.style.setProperty('--i', String(index));
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

  const feedList = document.getElementById('roll-feed-list');
  if (!feedList) return;
  feedList.replaceChildren();
  const maxListed = Math.min(required, 3);
  for (let index = 0; index < maxListed; index += 1) {
    const isOwned = index < owned;
    const isLast = index === required - 1;
    const usedLabels = isLast && spare > 0 ? perRoll - spare : perRoll;
    const usedPct = Math.round((usedLabels / perRoll) * 100);
    const li = document.createElement('li');
    li.className = `feed-item ${isOwned ? 'is-have' : 'is-order'}`;

    const head = document.createElement('div');
    head.className = 'feed-item-head';
    const strong = document.createElement('strong');
    strong.textContent = `Roll ${index + 1} · ${isOwned ? 'Already have' : 'To order'}`;
    const span = document.createElement('span');
    span.textContent = `${numbers.format(usedLabels)} / ${numbers.format(perRoll)} labels (${usedPct}%)`;
    head.append(strong, span);

    const bar = document.createElement('div');
    bar.className = 'feed-bar';
    const fill = document.createElement('span');
    fill.style.width = `${usedPct}%`;
    bar.append(fill);

    li.append(head, bar);
    feedList.append(li);
  }
  if (required > maxListed) {
    const moreLi = document.createElement('li');
    moreLi.className = 'feed-more';
    const lastUsed = spare > 0 ? perRoll - spare : perRoll;
    const lastPct = Math.round((lastUsed / perRoll) * 100);
    moreLi.textContent = `+ ${numbers.format(required - maxListed)} more ${required - maxListed === 1 ? 'roll' : 'rolls'} (Roll ${numbers.format(required)} uses ${numbers.format(lastUsed)} / ${numbers.format(perRoll)} · ${lastPct}%)`;
    feedList.append(moreLi);
  }
}

function updateWebTrack(inputs: LabelInputs): void {
  const track = document.getElementById('web-track');
  if (!track) return;
  // Whole label cards only, so nothing is ever cut off at the strip's edge; they print in when the count changes.
  const cards = placementCards(inputs.labelsPerItem);
  const key = String(inputs.labelsPerItem);
  if (track.dataset.key === key) return;
  const first = track.dataset.key === undefined;
  track.dataset.key = key;
  track.replaceChildren(...cards.map((card, index) => {
    const label = document.createElement('span');
    label.className = first ? 'die-label' : 'die-label printed';
    label.style.setProperty('--i', String(index));
    const hole = document.createElement('i');
    hole.className = 'die-hole';
    const title = document.createElement('b');
    title.className = 'die-title';
    title.textContent = card.title;
    const meta = document.createElement('small');
    meta.className = 'die-meta';
    meta.textContent = card.meta;
    label.append(hole, title, meta);
    return label;
  }));
}

function updateComparisonGrid(inputs: LabelInputs): void {
  if (!compareGrid) return;
  const rows = compareRollSizes(inputs);
  compareGrid.replaceChildren();
  for (const row of rows) {
    const card = document.createElement('article');
    card.className = `compare-card${row.isCurrent ? ' is-current' : ''}${row.isLowestSpare ? ' is-best' : ''}`;
    card.dataset.size = String(row.labelsPerRoll);

    const top = document.createElement('div');
    top.className = 'compare-card-top';
    const sizeSpan = document.createElement('span');
    sizeSpan.className = 'compare-size';
    sizeSpan.textContent = `${numbers.format(row.labelsPerRoll)} `;
    const small = document.createElement('small');
    small.textContent = 'labels / roll';
    sizeSpan.append(small);
    top.append(sizeSpan);

    if (row.isLowestSpare) {
      const badge = document.createElement('span');
      badge.className = 'compare-badge';
      badge.textContent = 'Lowest spare';
      top.append(badge);
    }

    const orderP = document.createElement('p');
    orderP.className = `compare-order${row.rollsToOrder === 0 ? ' is-zero' : ''}`;
    const orderStrong = document.createElement('strong');
    orderStrong.textContent = numbers.format(row.rollsToOrder);
    orderP.append(orderStrong, ` ${row.rollsToOrder === 1 ? 'roll' : 'rolls'} to order`);

    const metaP = document.createElement('p');
    metaP.className = 'compare-meta';
    const spareB = document.createElement('b');
    spareB.textContent = `${numbers.format(row.labelsLeft)} spare`;
    metaP.append(
      `Uses ${numbers.format(row.rollsRequired)} ${row.rollsRequired === 1 ? 'roll' : 'rolls'} · `,
      spareB,
      ` (${row.lastRollUsedPercent}% of last roll used)`,
    );

    const bar = document.createElement('div');
    bar.className = 'compare-bar';
    bar.setAttribute('aria-hidden', 'true');
    const fill = document.createElement('span');
    fill.style.width = `${row.lastRollUsedPercent}%`;
    bar.append(fill);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'compare-use-btn';
    btn.dataset.useRoll = String(row.labelsPerRoll);
    btn.textContent = row.isCurrent ? 'Active roll size' : `Use ${numbers.format(row.labelsPerRoll)} / roll`;

    card.append(top, orderP, metaP, bar, btn);
    compareGrid.append(card);
  }
}

function syncChipStates(inputs: LabelInputs): void {
  document.querySelectorAll<HTMLButtonElement>('.mini-chip').forEach(chip => {
    const target = chip.dataset.target;
    const val = Number(chip.dataset.value);
    const current =
      target === 'labels'
        ? inputs.labelsPerItem
        : target === 'perRoll'
          ? inputs.labelsPerRoll
          : target === 'onHand'
            ? inputs.rollsOnHand
            : target === 'waste'
              ? inputs.wastePercent
              : NaN;
    chip.setAttribute('aria-pressed', String(Math.abs(current - val) < 1e-6));
  });

  document.querySelectorAll<HTMLButtonElement>('.preset-chip').forEach(chip => {
    const preset = BATCH_PRESETS.find(item => item.id === chip.dataset.preset);
    const matches =
      Boolean(preset) &&
      preset!.inputs.quantity === inputs.quantity &&
      preset!.inputs.labelsPerItem === inputs.labelsPerItem &&
      preset!.inputs.labelsPerRoll === inputs.labelsPerRoll &&
      preset!.inputs.rollsOnHand === inputs.rollsOnHand &&
      Math.abs(preset!.inputs.wastePercent - inputs.wastePercent) < 1e-6;
    chip.setAttribute('aria-pressed', String(matches));
  });

  if (quantityRange && inputs.quantity >= Number(quantityRange.min) && inputs.quantity <= Number(quantityRange.max)) {
    quantityRange.value = String(inputs.quantity);
  }
}

function announce(text: string, when: Announce): void {
  window.clearTimeout(announceTimer);
  if (!announcer || when === 'none') return;
  const say = (): void => {
    announcer.textContent = text;
  };
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
    const inputs: LabelInputs = {
      quantity: read('quantity'),
      labelsPerItem: read('labels'),
      wastePercent: read('waste'),
      labelsPerRoll: read('perRoll'),
      rollsOnHand: read('onHand'),
    };
    const result = planLabels(inputs);
    const telemetry = computeRollTelemetry(inputs, result);
    const rolls = (count: number): string => `${numbers.format(count)} ${count === 1 ? 'roll' : 'rolls'}`;

    setText('order', numbers.format(result.rollsToOrder), true);
    setText('order-label', result.rollsToOrder === 1 ? 'roll to order' : 'rolls to order');
    setText('needed', numbers.format(result.labelsNeeded), true);
    setText('required', numbers.format(result.rollsRequired), true);
    setText('left', numbers.format(result.labelsLeft), true);

    const captionText = `${numbers.format(result.rollsToOrder)} ${result.rollsToOrder === 1 ? 'roll' : 'rolls'} to order · ${numbers.format(result.labelsLeft)} spare labels on the last roll`;
    setText('roll-caption', captionText);
    setText('result-kind', edited ? 'Your batch' : 'Sample batch. Change any number to plan yours.');

    const enough = document.getElementById('enough');
    if (enough) enough.hidden = result.rollsToOrder !== 0;
    output.classList.toggle('is-covered', result.rollsToOrder === 0);

    // Live spool visualizer updates
    const arcUsed = document.getElementById('spool-arc-used');
    if (arcUsed) {
      arcUsed.setAttribute('stroke-dasharray', `${telemetry.lastRollUsedPercent} 100`);
    }
    setText('spool-pct', `${telemetry.lastRollUsedPercent}%`, true);
    setText(
      'spool-used-detail',
      `Last roll uses ${numbers.format(telemetry.lastRollUsed)} of ${numbers.format(inputs.labelsPerRoll)} labels (${numbers.format(result.labelsLeft)} spare)`,
    );
    setText('viz-allowance', `+${numbers.format(telemetry.allowanceLabels)} extra labels`);
    setText('viz-per-item', `${numbers.format(inputs.labelsPerItem)} ${inputs.labelsPerItem === 1 ? 'label' : 'labels'} / item`);
    setText('viz-roll-count', `${rolls(result.rollsRequired)} total`);

    // Capacity breakdown bar updates
    const barBase = document.getElementById('bar-base');
    const barAllow = document.getElementById('bar-allow');
    const barSpare = document.getElementById('bar-spare');
    if (barBase) barBase.style.width = `${telemetry.baseSharePercent}%`;
    if (barAllow) barAllow.style.width = `${telemetry.allowanceSharePercent}%`;
    if (barSpare) barSpare.style.width = `${telemetry.spareSharePercent}%`;
    setText('capacity-total', `${numbers.format(telemetry.totalCapacity)} labels on ${rolls(result.rollsRequired)}`);
    setText('cap-base-num', numbers.format(result.baseLabels));
    setText('cap-allow-num', numbers.format(telemetry.allowanceLabels));
    setText('cap-spare-num', numbers.format(result.labelsLeft));

    // Worked math board updates
    setText('m-qty', numbers.format(inputs.quantity), true);
    setText('m-lpi', numbers.format(inputs.labelsPerItem), true);
    setText('m-base', numbers.format(result.baseLabels), true);
    setText('m-waste', `${inputs.wastePercent}%`, true);
    setText('m-needed', numbers.format(result.labelsNeeded), true);
    setText('m-needed-2', numbers.format(result.labelsNeeded), true);
    setText('m-per-roll', numbers.format(inputs.labelsPerRoll), true);
    setText('m-req', numbers.format(result.rollsRequired), true);
    setText('m-req-2', numbers.format(result.rollsRequired), true);
    setText('m-on-hand', numbers.format(inputs.rollsOnHand), true);
    setText('m-order', numbers.format(result.rollsToOrder), true);
    setText('m-left', numbers.format(result.labelsLeft), true);

    drawStrip(result.rollsRequired, inputs.rollsOnHand, inputs.labelsPerRoll, result.labelsLeft);
    updateWebTrack(inputs);
    updateComparisonGrid(inputs);
    syncChipStates(inputs);

    if (edited) {
      pulseClass(spoolStage, 'spin-burst');
      pulseClass(webConveyor, 'feed-burst');
    }

    output.hidden = false;
    announce(
      `${rolls(result.rollsToOrder)} to order. This batch uses ${rolls(result.rollsRequired)} ` +
        `for ${numbers.format(result.labelsNeeded)} labels, leaving ${numbers.format(result.labelsLeft)} spare.`,
      when,
    );
    return true;
  } catch (cause) {
    error.textContent = cause instanceof Error ? cause.message : 'Please check your inputs.';
    output.hidden = true;
    return false;
  }
}

form?.addEventListener('input', event => {
  if (event.target === quantityRange && quantityInput && quantityRange) {
    quantityInput.value = quantityRange.value;
  }
  edited = true;
  calculate('later');
});

form?.addEventListener('submit', event => {
  event.preventDefault();
  edited = true;
  if (calculate('now')) {
    const bottom = output?.getBoundingClientRect().bottom ?? 0;
    if (bottom > window.innerHeight) {
      const smooth = !reducedMotion.matches;
      output?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'nearest' });
    }
  } else {
    invalidField()?.focus();
  }
});

document.querySelectorAll<HTMLButtonElement>('.mini-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const targetName = chip.dataset.target;
    const value = chip.dataset.value;
    if (!targetName || value === undefined) return;
    const field = form?.elements.namedItem(targetName);
    if (field instanceof HTMLInputElement) {
      field.value = value;
      edited = true;
      calculate('later');
    }
  });
});

document.querySelectorAll<HTMLButtonElement>('.preset-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const mapping: Array<[string, string | undefined]> = [
      ['quantity', chip.dataset.quantity],
      ['labels', chip.dataset.labels],
      ['perRoll', chip.dataset.perRoll],
      ['onHand', chip.dataset.onHand],
      ['waste', chip.dataset.waste],
    ];
    for (const [name, val] of mapping) {
      const field = form?.elements.namedItem(name);
      if (field instanceof HTMLInputElement && val !== undefined) {
        field.value = val;
      }
    }
    edited = true;
    calculate('later');
  });
});

compareGrid?.addEventListener('click', event => {
  const target = (event.target as HTMLElement | null)?.closest<HTMLElement>('[data-use-roll]');
  if (!target) return;
  const rollSize = target.dataset.useRoll;
  const perRollField = form?.elements.namedItem('perRoll');
  if (rollSize && perRollField instanceof HTMLInputElement) {
    perRollField.value = rollSize;
    edited = true;
    calculate('later');
  }
});

calculate('none');

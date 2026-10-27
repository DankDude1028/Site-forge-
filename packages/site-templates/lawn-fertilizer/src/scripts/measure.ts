import { parseNumber } from '../lib/fertilizer.ts';
import { lawnArea, shapeArea, type Shape, type ShapeKind } from '../lib/tools.ts';
import { whole } from '../lib/format.ts';

const list = document.getElementById('shapes') as HTMLOListElement;
const NAMES: Record<ShapeKind, string> = { rectangle: 'Rectangle', circle: 'Circle', triangle: 'Triangle' };

function rows(): HTMLLIElement[] {
  return Array.from(list.querySelectorAll<HTMLLIElement>('.shape-row'));
}

function readShape(row: HTMLLIElement): Shape {
  const value = (name: string) => parseNumber(row.querySelector<HTMLInputElement>(`input[name="${name}"]`)?.value ?? '');
  return { kind: row.dataset.kind as ShapeKind, a: value('a'), b: value('b'),
    subtract: row.querySelector<HTMLInputElement>('input[name="subtract"]')!.checked };
}

let announceTimer = 0;
function update() {
  const shapes = rows().map((row) => {
    const shape = readShape(row);
    const area = shapeArea(shape);
    row.querySelector('.shape-area')!.textContent = Number.isFinite(area) ? `${whole(area)} sq ft` : '–';
    row.classList.toggle('is-cut', shape.subtract);
    return shape;
  });
  const total = lawnArea(shapes);
  const rounded = Math.round(total.area);
  document.getElementById('area-total')!.textContent = whole(total.area);
  document.getElementById('area-break')!.textContent = total.counted
    ? `${whole(total.grass)} sq ft of shapes, minus ${whole(total.removed)} sq ft cut out.`
    : 'Enter the measurements of at least one shape.';
  document.getElementById('area-keep')!.style.setProperty('--keep', total.grass > 0 ? (total.area / total.grass).toFixed(4) : '0');
  const use = document.getElementById('area-use') as HTMLAnchorElement;
  use.href = `/#area=${rounded}`;
  use.toggleAttribute('aria-disabled', rounded <= 0);
  document.getElementById('area-use-value')!.textContent = whole(total.area);
  clearTimeout(announceTimer);
  announceTimer = window.setTimeout(() => {
    document.getElementById('area-announce')!.textContent = `Lawn area ${whole(total.area)} square feet.`;
  }, 700);
}

function addShape(kind: ShapeKind) {
  const template = document.getElementById(`tpl-${kind}`) as HTMLTemplateElement;
  const row = template.content.firstElementChild!.cloneNode(true) as HTMLLIElement;
  const number = rows().length + 1;
  row.querySelector('legend')!.textContent = `${NAMES[kind]} ${number}`;
  row.querySelector('.remove')!.setAttribute('aria-label', `Remove ${NAMES[kind].toLowerCase()} ${number}`);
  list.append(row);
  row.querySelector<HTMLInputElement>('input[name="a"]')!.focus();
  update();
}

list.addEventListener('input', update);
list.addEventListener('change', update);
list.addEventListener('click', (event) => {
  const button = (event.target as Element).closest('.remove');
  if (!button) return;
  const row = button.closest('.shape-row')!;
  const next = (row.nextElementSibling ?? row.previousElementSibling)?.querySelector<HTMLInputElement>('input');
  row.remove();
  update();
  (next ?? document.querySelector<HTMLButtonElement>('[data-add]'))?.focus();
});
document.querySelectorAll<HTMLButtonElement>('[data-add]').forEach((button) =>
  button.addEventListener('click', () => addShape(button.dataset.add as ShapeKind)));
document.getElementById('measure')!.addEventListener('submit', (event) => event.preventDefault());
update();

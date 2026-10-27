/** Display helpers shared by the server-rendered page and the browser script, so both show the same text. */

export const DEFAULTS = { area: 10_000, nitrogen: 29, phosphorus: 0, potassium: 4, rate: 0.75, bagWeight: 15 } as const;

export function fixed(value: number, digits = 1): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Pounds read best with one decimal under 100 lb and as whole numbers above. */
export function pounds(value: number): string {
  return value >= 100 ? fixed(value, 0) : fixed(value, 1);
}

/** A typed amount such as a bag weight: no trailing ".0" for whole numbers. */
export function amount(value: number): string {
  return Number.isInteger(value) ? whole(value) : pounds(value);
}

/** Fewer tiles get fewer, bigger columns, so a small lawn still fills the drawing. */
export function tileColumns(count: number): number {
  return Math.min(8, Math.max(3, Math.ceil(Math.sqrt(count * 1.6))));
}

/** Seed weights: small amounts keep two decimals (a quarter pound is 0.25), and trailing zeros drop ("6", "22.5"). */
export function seedPounds(value: number): string {
  return fixed(value, value < 10 ? 2 : 1).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
}

export function whole(value: number): string {
  return Math.round(value).toLocaleString('en-US');
}

/** The lawn drawing uses up to 40 tiles; big lawns switch to bigger tiles so the drawing stays readable. */
export function tileLayout(area: number): { scale: number; full: number; partial: number } {
  const scale = area <= 40_000 ? 1_000 : area <= 200_000 ? 5_000 : 25_000;
  const units = area / scale;
  const full = Math.min(40, Math.floor(units + 1e-9));
  const partial = full >= 40 ? 0 : units - full;
  return { scale, full, partial: partial > 0.005 ? partial : 0 };
}

/** Gauge angle in degrees for a nitrogen rate on the 0–2 lb dial: -90 points left, 90 points right. */
export function gaugeAngle(rate: number): number {
  return -90 + Math.min(Math.max(rate, 0), 2) / 2 * 180;
}

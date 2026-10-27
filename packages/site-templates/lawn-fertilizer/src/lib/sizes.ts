/** Common lawn sizes, each with its own page. Areas are exact; the side of an equal square is shown for scale. */

export interface LawnSize {
  slug: string;
  area: number; // square feet
  label: string; // "5,000 sq ft" or "a quarter acre"
  title: string; // as used in a page title: "5,000 Sq Ft" or "a Quarter Acre"
  shape: string; // a familiar way to picture the area
}

export const SQ_FT_PER_ACRE = 43_560;

export const SIZES: readonly LawnSize[] = [
  { slug: '1000-sq-ft', area: 1_000, label: '1,000 sq ft', title: '1,000 Sq Ft', shape: 'about 25 by 40 ft' },
  { slug: '2500-sq-ft', area: 2_500, label: '2,500 sq ft', title: '2,500 Sq Ft', shape: '50 by 50 ft' },
  { slug: '5000-sq-ft', area: 5_000, label: '5,000 sq ft', title: '5,000 Sq Ft', shape: '50 by 100 ft' },
  { slug: '10000-sq-ft', area: 10_000, label: '10,000 sq ft', title: '10,000 Sq Ft', shape: '100 by 100 ft' },
  { slug: 'quarter-acre', area: SQ_FT_PER_ACRE / 4, label: 'a quarter acre', title: 'a Quarter Acre', shape: '10,890 sq ft, about 104 ft on each side of a square' },
  { slug: 'half-acre', area: SQ_FT_PER_ACRE / 2, label: 'half an acre', title: 'Half an Acre', shape: '21,780 sq ft, about 148 ft on each side of a square' },
  { slug: 'one-acre', area: SQ_FT_PER_ACRE, label: 'one acre', title: 'One Acre', shape: '43,560 sq ft, about 209 ft on each side of a square' },
];

/** Common products for the worked tables: name and bag numbers. */
export const PRODUCTS = [
  { name: 'Lawn food', n: 29, p: 0, k: 4 },
  { name: 'Complete', n: 16, p: 4, k: 8 },
  { name: 'All-purpose', n: 10, p: 10, k: 10 },
  { name: 'Urea', n: 46, p: 0, k: 0 },
] as const;

/** Pounds of a product that deliver `rate` lb of nitrogen per 1,000 sq ft over `area`. */
export function productPounds(area: number, nitrogenPercent: number, rate: number): number {
  return rate / (nitrogenPercent / 100) * area / 1000;
}

export function bagsFor(pounds: number, bagWeight: number): number {
  return Math.max(1, Math.ceil(pounds / bagWeight - 1e-9));
}

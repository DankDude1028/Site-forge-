/** Typical yearly nitrogen and feeding windows by grass, from the extension guides cited on the method page.
 * Ranges are lb of nitrogen per 1,000 sq ft per year. A state or county extension guide always wins. */

export type Season = 'cool' | 'warm';
/** main: the core feedings; light: optional or regional feedings at a reduced rate. */
export type Feeding = 'main' | 'light';

export interface Grass {
  id: string;
  name: string;
  season: Season;
  annual: readonly [number, number];
  months: Partial<Record<number, Feeding>>; // 0 = January
  note: string;
  rate: number; // where the calculator starts on this grass's page, inside the 0.5–1 lb band
  intro: string;
}

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;

const COOL_MONTHS = { 1: 'light', 3: 'light', 5: 'light', 8: 'main', 10: 'main' } as const;
const COOL_NOTE = 'Fall is the main season: feed in September and again around November while the grass is still green. '
  + 'Northern schedules add light feedings in late April and early June; the transition zone feeds in February instead. '
  + 'Skip feeding in summer heat.';
const WARM_MONTHS = { 3: 'light', 4: 'main', 5: 'main', 6: 'main', 7: 'main', 8: 'light' } as const;
const WARM_NOTE = 'Start after the lawn has fully greened up in spring, feed through summer, and stop by early fall '
  + 'so the grass is not pushed into growth before cold weather.';

export const GRASSES: readonly Grass[] = [
  { id: 'kentucky-bluegrass', name: 'Kentucky bluegrass', season: 'cool', annual: [1, 4], months: COOL_MONTHS,
    note: `${COOL_NOTE} Low-care lawns need 1–2 lb a year, most lawns 2–3, and high-care lawns 3–4.`,
    rate: 1, intro: 'A cool-season grass that does most of its growing in spring and fall. Its fall feedings matter most.' },
  { id: 'tall-fescue', name: 'Tall fescue', season: 'cool', annual: [1, 4], months: COOL_MONTHS,
    note: `${COOL_NOTE} NC State's calendar adds up to 3 lb a year for tall fescue.`,
    rate: 1, intro: 'A deep-rooted cool-season grass, common across the transition zone. Feed it mainly in fall.' },
  { id: 'bermudagrass', name: 'Bermudagrass', season: 'warm', annual: [3, 5], months: WARM_MONTHS,
    note: `${WARM_NOTE} Bermudagrass is the heaviest feeder; Florida's guide goes up to 7 lb a year in the south of the state.`,
    rate: 1, intro: 'A sun-loving warm-season grass that grows hard in summer and uses the most nitrogen of the common lawn grasses.' },
  { id: 'st-augustinegrass', name: 'St. Augustinegrass', season: 'warm', annual: [2, 4], months: WARM_MONTHS,
    note: `${WARM_NOTE} Florida's guide allows up to 6 lb a year in South Florida.`,
    rate: 0.75, intro: 'A coarse, wide-bladed warm-season grass, common along the Gulf Coast and in Florida, that tolerates more shade than most.' },
  { id: 'zoysiagrass', name: 'Zoysiagrass', season: 'warm', annual: [2, 3], months: WARM_MONTHS,
    note: `${WARM_NOTE} Zoysia needs less than bermudagrass; Florida's guide goes up to 4.5 lb in the far south.`,
    rate: 0.75, intro: 'A dense, slow-growing warm-season grass that needs less nitrogen than bermudagrass.' },
  { id: 'centipedegrass', name: 'Centipedegrass', season: 'warm', annual: [0.4, 2], months: { 4: 'light', 5: 'main', 6: 'light' },
    note: 'Centipede does best on very little fertilizer: one or two light feedings in late spring to early summer, after green-up.',
    rate: 0.5, intro: 'A low-maintenance warm-season grass of the Southeast that does best on very little fertilizer.' },
];

/** How many feedings at this rate fit the grass's yearly range, rounded to whole feedings. */
export function feedingsPerYear(grass: Grass, rate: number): readonly [number, number] {
  return [Math.max(1, Math.floor(grass.annual[0] / rate + 1e-9)), Math.max(1, Math.floor(grass.annual[1] / rate + 1e-9))];
}

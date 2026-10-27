/** Every page on the site in one place, so the navigation, guide hub, related links and sitemap never drift apart. */
import { BAGS } from '../content/bags.ts';
import { RANGES } from '../content/ranges.ts';
import { SEASONS } from '../content/seasons.ts';
import { STATES } from '../content/states.ts';
import { GRASSES, type Grass } from './grasses.ts';
import { SIZES } from './sizes.ts';

export interface PageLink { path: string; title: string; blurb: string }

export const TOOL_GUIDES: readonly PageLink[] = [
  { path: '/guides/measure-your-lawn/', title: 'Measure your lawn',
    blurb: 'Add up rectangles, circles and triangles, take out the house and beds, and send the total to the calculator.' },
  { path: '/guides/fertilizer-numbers/', title: 'Read a fertilizer bag',
    blurb: 'What the three numbers mean, how many pounds of each nutrient are in the bag, and how far one bag goes.' },
  { path: '/guides/spreader-calibration/', title: 'Calibrate your spreader',
    blurb: 'Weigh, spread, weigh again. Find the setting that puts down exactly the amount you planned.' },
  { path: '/guides/grass-seed/', title: 'Grass seed calculator',
    blurb: 'How much seed for a new lawn or for overseeding, by grass type, with the best time to sow.' },
];

/** "Tall fescue" mid-sentence is "tall fescue", but "Kentucky" and "St." keep their capitals. */
export function inline(grass: Grass): string {
  return /^(Kentucky|St\.)/.test(grass.name) ? grass.name : grass.name[0].toLowerCase() + grass.name.slice(1);
}

export const GRASS_GUIDES: readonly PageLink[] = GRASSES.map((grass) => ({
  path: `/grass/${grass.id}/`, title: `${grass.name} fertilizer guide`, blurb: grass.intro,
}));

export const SIZE_GUIDES: readonly PageLink[] = SIZES.map((size) => ({
  path: `/lawn-size/${size.slug}/`, title: `Fertilizer for ${size.label}`,
  blurb: `Pounds, bags and yearly nitrogen for ${size.label} (${size.shape}).`,
}));

export const RANGE_GUIDES: readonly PageLink[] = RANGES.map((range) => ({
  path: `/lawn-size/${range.slug}/`, title: `Fertilizer for lawns ${range.label}`,
  blurb: range.lede,
}));

export const BAG_GUIDES: readonly PageLink[] = BAGS.map((bag) => ({
  path: `/bags/${bag.slug}/`, title: `How far a ${bag.label} goes`,
  blurb: bag.blurb,
}));

export const SEASON_GUIDES: readonly PageLink[] = SEASONS.map((season) => ({
  path: `/seasons/${season.slug}/`, title: season.title, blurb: season.lede,
}));

export const STATE_GUIDES: readonly PageLink[] = STATES.map((state) => ({
  path: `/states/${state.slug}/`, title: `${state.name} lawn fertilizer rules`, blurb: state.summary,
}));

export const SITE_PAGES: readonly PageLink[] = [
  { path: '/about/', title: 'About', blurb: 'Who runs Lawn Numbers, where the numbers come from, and how a correction gets onto the page.' },
  { path: '/contact/', title: 'Contact', blurb: 'How to send a correction or a question, and what a reply does and does not promise.' },
  { path: '/credits/', title: 'Photo credits', blurb: 'Photographer, source, and license for every grass photograph on the site.' },
  { path: '/method/', title: 'Method and sources', blurb: 'The formulas and the university extension sources behind the calculator.' },
  { path: '/privacy/', title: 'Privacy', blurb: 'What the site collects today, and what would have to be said before ads or analytics are added.' },
  { path: '/terms/', title: 'Terms and disclaimer', blurb: 'The label comes first. These are planning estimates, not professional advice.' },
];

export const ROUTES: readonly string[] = [
  '/', '/guides/', '/lawn-size/', '/bags/', '/seasons/', '/states/',
  ...TOOL_GUIDES.map((page) => page.path),
  ...GRASS_GUIDES.map((page) => page.path),
  ...SIZE_GUIDES.map((page) => page.path),
  ...RANGE_GUIDES.map((page) => page.path),
  ...BAG_GUIDES.map((page) => page.path),
  ...SEASON_GUIDES.map((page) => page.path),
  ...STATE_GUIDES.map((page) => page.path),
  ...SITE_PAGES.map((page) => page.path),
];

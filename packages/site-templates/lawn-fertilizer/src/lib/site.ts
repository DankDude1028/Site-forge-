/** Every page on the site in one place, so the navigation, guide hub, related links and sitemap never drift apart. */
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

export const ROUTES: readonly string[] = ['/', '/guides/', ...TOOL_GUIDES.map((page) => page.path),
  ...GRASS_GUIDES.map((page) => page.path), ...SIZE_GUIDES.map((page) => page.path), '/method/', '/privacy/', '/terms/'];

/** Seeding rates from NC State Extension AG-69, Carolina Lawns (2021), in lb of seed per 1,000 sq ft for a new lawn.
 * Seeding into an existing lawn uses a 25–50% lower rate. Grasses with no rate cannot be grown from seed. */

export type SeedSeason = 'late summer to early fall' | 'spring to early summer';

export interface SeedGrass {
  id: string;
  name: string;
  rate: readonly [number, number] | null; // lb per 1,000 sq ft, new lawn
  season: SeedSeason | null;
  note: string;
}

export const SEED_GRASSES: readonly SeedGrass[] = [
  { id: 'tall-fescue', name: 'Tall fescue', rate: [6, 6], season: 'late summer to early fall',
    note: 'The most common seeded lawn grass in the transition zone. Seed in late summer or early fall.' },
  { id: 'kentucky-bluegrass', name: 'Kentucky bluegrass', rate: [1, 2], season: 'late summer to early fall',
    note: 'Small seed, so it needs far fewer pounds than tall fescue. It is slow to come up.' },
  { id: 'bermudagrass', name: 'Bermudagrass', rate: [1, 2], season: 'spring to early summer',
    note: 'Common bermudagrass can be seeded. Hybrid bermudagrass cannot; it is planted as sod or sprigs.' },
  { id: 'zoysiagrass', name: 'Zoysiagrass', rate: [1, 2], season: 'spring to early summer',
    note: 'Only a few zoysia varieties are sold as seed; most zoysia lawns are planted from sod or plugs.' },
  { id: 'centipedegrass', name: 'Centipedegrass', rate: [0.25, 0.5], season: 'spring to early summer',
    note: 'Very small seed: a quarter to half a pound covers 1,000 sq ft.' },
  { id: 'st-augustinegrass', name: 'St. Augustinegrass', rate: null, season: null,
    note: 'Seed is not available. St. Augustinegrass is planted as sod or plugs.' },
];

export type SeedMode = 'new' | 'overseed';

export type SeedPlan =
  | { seedable: false }
  | { seedable: true; perThousand: readonly [number, number]; pounds: readonly [number, number];
      bags: readonly [number, number]; season: SeedSeason };

/** Pounds of seed and whole bags for an area. Overseeding uses 50–75% of the new-lawn rate (25–50% lower). */
export function seedPlan(area: number, grassId: string, mode: SeedMode, bagWeight: number): SeedPlan | null {
  const grass = SEED_GRASSES.find((item) => item.id === grassId);
  if (!grass || !Number.isFinite(area) || area < 1 || area > 1_000_000 || !Number.isFinite(bagWeight)
      || bagWeight <= 0 || bagWeight > 100) return null;
  if (!grass.rate || !grass.season) return { seedable: false };
  const perThousand: readonly [number, number] = mode === 'new' ? grass.rate : [grass.rate[0] * 0.5, grass.rate[1] * 0.75];
  const pounds = [perThousand[0] * area / 1000, perThousand[1] * area / 1000] as const;
  const bags = pounds.map((value) => Math.max(1, Math.ceil(value / bagWeight - 1e-9))) as [number, number];
  return { seedable: true, perThousand, pounds, bags, season: grass.season };
}

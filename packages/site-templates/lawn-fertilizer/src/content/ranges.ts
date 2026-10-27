/** Area bands that point at the exact size pages. Worked areas are not copies of those pages. */

export interface SizeRange {
  slug: string;
  label: string;
  title: string;
  low: number;
  high: number | null;
  exampleArea: number;
  exampleShape: string;
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  rate: number;
  productName: string;
  links: readonly string[];
  lede: string;
  story: readonly string[];
}

export const RANGES: readonly SizeRange[] = [
  {
    slug: 'under-2000-sq-ft', label: 'under 2,000 sq ft', title: 'Under 2,000 Sq Ft',
    low: 1, high: 2000, exampleArea: 1250, exampleShape: '25 by 50 ft, a side yard with the beds already taken out',
    nitrogen: 16, phosphorus: 4, potassium: 8, rate: 0.5, productName: '16-4-8',
    links: ['1000-sq-ft', '2500-sq-ft'],
    lede: 'Townhouse lawns and side yards live in this band. The pile of fertilizer is small, and a big bag is mostly leftover.',
    story: [
      'A 1,250 sq ft lawn is the example, not the 1,000 sq ft page and not a guess at “about a thousand.” Measure the rectangle and subtract the beds with the measuring tool if the shape is not a clean rectangle.',
      'The worked feeding is deliberately light: 0.5 lb of nitrogen per 1,000 sq ft from a 16-4-8, which is a complete fertilizer. On a lawn this small the phosphate in that bag is a reason to pause. If a soil test does not call for phosphorus, switch the calculator to a 29-0-4 or another low-phosphorus analysis. Virginia does not allow phosphorus in routine maintenance fertilizer at all.',
      'The exact 1,000 sq ft page is the next stop if you are near the bottom of this band. If you are closer to 2,000, look at 2,500 sq ft before you buy, because “under 2,000” and “2,500” are one mis-measured flower bed apart.',
    ],
  },
  {
    slug: '2000-5000-sq-ft', label: '2,000–5,000 sq ft', title: '2,000–5,000 Sq Ft',
    low: 2000, high: 5000, exampleArea: 3600, exampleShape: '40 by 90 ft',
    nitrogen: 29, phosphorus: 0, potassium: 4, rate: 1, productName: '29-0-4',
    links: ['2500-sq-ft', '5000-sq-ft'],
    lede: 'This is the ordinary front-and-back yard. One feeding is a partial bag or two, not a pallet.',
    story: [
      'The example is 3,600 sq ft, 40 by 90, which sits between the 2,500 and 5,000 sq ft pages on purpose so this page is not a reprint of either. At 1 lb of nitrogen per 1,000 sq ft, a 29-0-4 is the product in the worked line. There is no phosphate in that analysis. If your bag is a 10-10-10, the pounds jump because each pound carries less nitrogen, and you should ask whether the lawn needs the phosphate.',
      'One pound is the top of a normal quick-release feeding (Rutgers) and above Florida’s 0.7 lb cap on readily available nitrogen. If you are in Florida, rerun the example at 0.7 before you spread. The calculator on this page starts at 3,600 sq ft and 1 lb so you can drop the rate yourself.',
      'Near 2,000 sq ft, use the under-2,000 page. At 5,000 exactly, use the 5,000 sq ft page. The edges of the band are where people double-buy.',
    ],
  },
  {
    slug: '5000-10000-sq-ft', label: '5,000–10,000 sq ft', title: '5,000–10,000 Sq Ft',
    low: 5000, high: 10000, exampleArea: 7200, exampleShape: '60 by 120 ft, house and drive already removed',
    nitrogen: 10, phosphorus: 10, potassium: 10, rate: 0.75, productName: '10-10-10',
    links: ['5000-sq-ft', '10000-sq-ft'],
    lede: 'A large suburban lot. The example uses 10-10-10 on purpose, because this is where a “complete” bag gets expensive and often wrong.',
    story: [
      '7,200 sq ft is the worked lawn: bigger than the 5,000 sq ft page and smaller than the 10,000 sq ft page. The rate is 0.75 lb of nitrogen per 1,000 sq ft. The product is 10-10-10 so the phosphate problem is visible in the pounds, not hidden. Established lawns in Florida and Virginia are the clearest cases where that middle 10 does not belong. Other states still want a soil test before a high-phosphorus bag becomes the habit.',
      'Swap to 29-0-4 in the calculator if the soil test is fine for phosphorus. The nitrogen rate can stay. Only the product pounds change, because the first number changed. That is the whole formula: nitrogen rate divided by the nitrogen share, times the lawn.',
      'At this size, bag choice matters more than on a townhouse lawn. A 15 lb bag means many trips. A 50 lb bag may still be more than one feeding. The bag pages run those leftovers. The 5,000 and 10,000 sq ft pages are the exact tables if your measure lands on them.',
    ],
  },
  {
    slug: 'over-10000-sq-ft', label: 'over 10,000 sq ft', title: 'Over 10,000 Sq Ft',
    low: 10000, high: null, exampleArea: 15000, exampleShape: 'about a third of an acre (an acre is 43,560 sq ft)',
    nitrogen: 46, phosphorus: 0, potassium: 0, rate: 0.5, productName: 'urea, 46-0-0',
    links: ['10000-sq-ft', 'quarter-acre', 'half-acre', 'one-acre'],
    lede: 'Past 10,000 sq ft you are in acreage math. The example is 15,000 sq ft of urea at a light rate, split rather than dumped.',
    story: [
      '15,000 sq ft is not a quarter acre. A quarter acre is 10,890 sq ft, half an acre is 21,780, and a full acre is 43,560. Those three have their own pages. This example sits between a quarter acre and a half acre so the arithmetic is not a copy of either.',
      'Urea is 46-0-0 and it is quick-release. The worked rate is 0.5 lb of nitrogen per 1,000 sq ft, inside the light band, because a full 1 lb of quick-release urea on 15,000 sq ft is a large, hot application. Rutgers’ soluble limit is about 1 lb per 1,000 sq ft. You can type 1 into the calculator and see the pounds. You should not put that down in one pass if the label says to split it. Two passes at right angles, at half the setting, are the spreader habit on the home page, not a second dose.',
      'Yearly totals scale fast. A bermuda year of 3–5 lb of nitrogen is 45–75 lb of actual nitrogen on 15,000 sq ft, spread over the summer, not one Saturday. A centipede year of 0.4–2 lb is 6–30 lb of nitrogen on the same area. The grass page is what decides which of those years you are in. The acre pages are where to go once the tape measure crosses 10,890.',
    ],
  },
];

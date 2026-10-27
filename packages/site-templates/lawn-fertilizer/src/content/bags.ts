/** One worked lawn per bag weight. Areas and analyses differ so the pages are not the same table. */

export interface BagGuide {
  slug: string;
  weight: number;
  label: string;
  area: number;
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  rate: number;
  analysis: string;
  blurb: string;
  paragraphs: readonly string[];
}

export const BAGS: readonly BagGuide[] = [
  {
    slug: '15-lb', weight: 15, label: '15 lb bag', area: 1500,
    nitrogen: 29, phosphorus: 0, potassium: 4, rate: 0.5, analysis: '29-0-4',
    blurb: 'The carry-home size. On a small lawn at a light rate, most of the bag is still in the bag.',
    paragraphs: [
      'The example is a 1,500 sq ft lawn, a 29-0-4, and 0.5 lb of nitrogen per 1,000 sq ft. That is a light feeding on a lawn under 2,000 sq ft, with no phosphate in the analysis. It is not the 5,000 sq ft default the home calculator uses, and it is not the 15 lb default bag on a 10,000 sq ft lawn.',
      'Fifteen pounds is what you can carry in one hand and store on a shelf. The cost of that convenience is the number of bags once the lawn grows. A half-acre at a full 1 lb rate will not be a one-bag errand. Run the half-acre page before you buy six small bags out of habit, and run this page before you buy a 50 lb sack for a courtyard.',
      'Whatever is left stays in the opened bag, dry, with the label readable. The calculator’s “left over” line is that remainder. It is not a second feeding unless you meant to feed again at the same rate later in the year. Centipede and a light fescue program often never come back for it.',
    ],
  },
  {
    slug: '25-lb', weight: 25, label: '25 lb bag', area: 3200,
    nitrogen: 16, phosphorus: 4, potassium: 8, rate: 0.75, analysis: '16-4-8',
    blurb: 'A middle bag. The example is picked so you can see a clean leftover, not a coincidence of marketing.',
    paragraphs: [
      'The lawn is 3,200 sq ft. The bag is 16-4-8 at 0.75 lb of nitrogen per 1,000 sq ft. The 4 in the middle is phosphate. On an established lawn that is a choice, not a default. Florida caps phosphate applications unless a soil test shows a need. Virginia does not allow phosphorus in routine lawn-maintenance fertilizer. If that is you, change the calculator to a zero-phosphorus analysis. The nitrogen math is the same formula either way.',
      'Twenty-five pounds is the size that often finishes a normal yard in one or two bags without the bulk of a 50. It is still heavy enough to hurt a back. Split the carry. Do not split the rate in your head and then forget you already counted the nitrogen.',
      'This page does not claim 25 lb is a standard legal size. It is a common retail size. The label’s coverage number is the manufacturer’s rate. Use this calculation when you want a different rate than the bag assumed, which is the same reason the home calculator exists.',
    ],
  },
  {
    slug: '40-lb', weight: 40, label: '40 lb bag', area: 6400,
    nitrogen: 10, phosphorus: 10, potassium: 10, rate: 1, analysis: '10-10-10',
    blurb: 'A heavy bag of a heavy-phosphate analysis, on a lawn big enough that the pounds get serious.',
    paragraphs: [
      'The example is 6,400 sq ft of 10-10-10 at 1 lb of nitrogen per 1,000 sq ft. One pound is the top of the usual quick-release feeding, not a light touch. Ten percent nitrogen means you spread a lot of product to get that one pound: ten pounds of product per 1,000 sq ft before the lawn is even scaled. The phosphate matches the nitrogen, pound for pound of nutrient percentage. That is a starter pattern, or a soil-test pattern, not an every-month pattern.',
      'Forty pounds is awkward. It is more than a 25 and less than a 50, and it is easy to buy two when one and a partial would do, or one when the math says two. The whole-bag count always rounds up so you do not run out mid-lawn. The leftover is the reason not to open the second bag if you can finish from the first by tightening the spreader. You cannot finish from the first if the pounds say otherwise. Read the line, then the label.',
      'If 10-10-10 is simply what the store had, put a 29-0-4 or a 46-0-0 into the calculator and compare pounds before you load the spreader. Urea is quick-release and hotter per pound of product. A lower product weight is not a lower nitrogen rate. The first number tells you which is which.',
    ],
  },
  {
    slug: '50-lb', weight: 50, label: '50 lb bag', area: 8000,
    nitrogen: 46, phosphorus: 0, potassium: 0, rate: 0.75, analysis: 'urea, 46-0-0',
    blurb: 'The big bag. UF/IFAS says Florida’s urban-turf label rules are written for bags under 50 lb. Read the bag in front of you anyway.',
    paragraphs: [
      'The example is 8,000 sq ft of urea (46-0-0) at 0.75 lb of nitrogen per 1,000 sq ft. Urea is soluble nitrogen. There is no phosphate and no potash in a straight urea analysis. The rate is under the 1 lb soluble guidance from Rutgers and just above Florida’s 0.7 lb cap on readily available nitrogen. In Florida, use 0.7 or the label. Elsewhere, 0.75 is inside the standard band on this site. Do not raise it to 2 because the bag is large and you want to “get it done.”',
      'UF/IFAS EP353 says bags weighing less than 50 lb that are sold for home lawns carry directions that follow the urban turf limits. A 50 lb bag may be labeled for a different use, including agriculture. That sentence is about Florida labeling, not a promise that a 50 lb bag is unregulated, and not a promise that it is aimed at your lawn. If the label does not say lawn, do not invent a lawn rate for it.',
      'On a small lawn a 50 lb bag of urea is several feedings, and an opened bag of urea does not improve with humidity. Buy it when the lawn and the year’s plan will use it. The over-10,000 sq ft page and the acre pages are the lawns where 50 lb stops being absurd. The 15 lb page is the other end.',
    ],
  },
];

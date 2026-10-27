/** University extension sources, opened and checked on 26 October 2026. */
export const SOURCES = {
  iowa: { name: 'Iowa State University Extension: How to Calculate Fertilizer Rates for the Lawn (reviewed April 2026)',
    url: 'https://yardandgarden.extension.iastate.edu/how-to/how-calculate-fertilizer-rates-lawn' },
  rutgers: { name: 'Rutgers Cooperative Extension FS839: How to Calculate the Amount of Fertilizer Needed for Your Lawn',
    url: 'https://extension.rutgers.edu/fs839' },
  ncstate: { name: 'NC State Extension AG-931: Tall Fescue, Hard (Fine) Fescue, and Kentucky Bluegrass Home Lawn Calendar',
    url: 'https://content.ces.ncsu.edu/tall-fescue-hard-fine-fescue-and-kentucky-bluegrass-home-lawn-calendar' },
  ufRule: { name: 'University of Florida IFAS ENH1089/EP353: Urban Turf Fertilizer Rule for Home Lawn Fertilization',
    url: 'https://ask.ifas.ufl.edu/publication/ep353' },
  ufSpreader: { name: 'University of Florida IFAS ENH62/LH024: How to Calibrate Your Fertilizer Spreader',
    url: 'https://ask.ifas.ufl.edu/publication/LH024' },
  nebraska: { name: 'University of Nebraska–Lincoln Water: Nutritional Value for the Landscape',
    url: 'https://water.unl.edu/article/lawns-gardens-landscapes/nutritional-value-landscape/' },
} as const;

export type SourceKey = keyof typeof SOURCES;
export const CHECKED = '26 October 2026';

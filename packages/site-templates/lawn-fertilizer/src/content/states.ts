/** State notes use statutes and extension pages opened for this site. Unverified items stay labeled. */

export interface StateSource { name: string; url: string }
export interface StateSection { id: string; heading: string; paragraphs: string[] }
export interface StateGuide {
  slug: string;
  name: string;
  abbr: string;
  summary: string;
  grasses: readonly string[];
  sections: readonly StateSection[];
  sources: readonly StateSource[];
  /** Shown on the page and collected for the pull request. */
  unverified: readonly string[];
}

const a = (href: string, text: string) => `<a href="${href}">${text}</a>`;

export const STATES: readonly StateGuide[] = [
  {
    slug: 'alabama', name: 'Alabama', abbr: 'AL',
    summary: 'No statewide homeowner nitrogen cap or blackout was verified. Cities are generally barred from writing their own fertilizer rules, with a narrow pollution-permit exception.',
    grasses: ['bermudagrass', 'centipedegrass', 'zoysiagrass', 'st-augustinegrass', 'tall-fescue'],
    sections: [
      { id: 'law', heading: 'What the statute actually does', paragraphs: [
        `Alabama Code § 11-80-15 says a county or city may not adopt or keep an ordinance regulating the registration, packaging, labeling, sale, distribution, transportation, storage, or application of fertilizer. That subject belongs to the Department of Agriculture and Industries. Zoning and business licenses still exist, but not as a back door to regulate fertilizer itself.`,
        `The same section has a narrow exception: a local government is not bound by that preemption when its NPDES permit, or another Alabama Department of Environmental Management action, requires a fertilizer rule because of federal or state law for impaired, threatened, or exceptional waters. So the usual line, “your city can always be stricter,” is the wrong line for Alabama. Most cities cannot. A few may have a permit that says otherwise. Ask the city and read the permit rather than assuming either a ban or a free hand.`,
        `No statewide homeowner blackout calendar, and no statewide pound-per-thousand cap for lawns, was verified for this page. The Alabama fertilizer law on the Department of Agriculture site is about registration, labeling, and sale, not a June-to-September ban. ${a('/states/', 'Check your county extension office')} for the feeding calendar they hand out. That absence is listed under unverified items below.`,
      ] },
      { id: 'feed', heading: 'How to feed the grasses that actually grow here', paragraphs: [
        `Warm-season lawns are the default: ${a('/grass/bermudagrass/', 'bermudagrass')}, ${a('/grass/centipedegrass/', 'centipedegrass')}, ${a('/grass/zoysiagrass/', 'zoysiagrass')}, and ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} nearer the coast. ${a('/grass/tall-fescue/', 'Tall fescue')} shows up where summers are a little kinder, generally farther north. This page does not assign a county-by-county map. The Alabama Cooperative Extension lawn publications are the place to match a cultivar to a region.`,
        `Use the grass page for the yearly nitrogen band and the months. Bermuda is the heavy summer feeder (3–5 lb per 1,000 sq ft on this site’s north-Florida-based column, not a south-Florida 7 lb year carried into Alabama). Centipede stays at 0.4–2 lb and only in late spring to early summer. Fescue, if you have it, is a ${a('/seasons/fall/', 'fall')} grass, not a July grass. ${a('/seasons/spring/', 'Spring')} green-up is the start for the warm-season species, and you stop before cold weather. No Alabama statute found for this page names those months, so they stay extension practice, not law.`,
      ] },
    ],
    sources: [
      { name: 'Alabama Code § 11-80-15 (regulation of fertilizer)', url: 'https://law.justia.com/codes/alabama/title-11/title-3/chapter-80/section-11-80-15/' },
      { name: 'Alabama Department of Agriculture and Industries, fertilizer law booklet', url: 'https://agi.alabama.gov/agcompliance/wp-content/uploads/sites/7/2020/12/AlabamaFertilizerLawandRules.pdf' },
      { name: 'Alabama Cooperative Extension System', url: 'https://www.aces.edu/' },
    ],
    unverified: [
      'No statewide homeowner blackout dates were verified.',
      'No statewide lawn nitrogen or phosphorus rate cap, in pounds per 1,000 sq ft, was verified.',
      'Which cities currently have an NPDES-based fertilizer condition was not enumerated.',
    ],
  },
  {
    slug: 'mississippi', name: 'Mississippi', abbr: 'MS',
    summary: 'No statewide lawn blackout or phosphorus ban was verified. Use Mississippi State University Extension for rates, and check the county before you assume a city rule.',
    grasses: ['bermudagrass', 'centipedegrass', 'zoysiagrass', 'st-augustinegrass', 'tall-fescue'],
    sections: [
      { id: 'law', heading: 'What was and was not found', paragraphs: [
        `A statewide statute that sets homeowner nitrogen rates, bans phosphorus on established lawns, or names blackout dates was not verified for Mississippi while this page was written. That is not the same sentence as “Mississippi has no rules.” Sale and labeling of fertilizer sit with the state agriculture department. A county or city stormwater rule can still exist. Because it was not verified one way or the other, the honest instruction is: check your county.`,
        `Do not borrow Florida’s urban turf numbers or Virginia’s phosphorus sale ban and treat them as Mississippi law. They are linked from those states’ pages because they were read there. They do not travel.`,
      ] },
      { id: 'feed', heading: 'Extension practice, not a statute', paragraphs: [
        `The grasses are the Gulf and mid-South set: ${a('/grass/bermudagrass/', 'bermudagrass')} through the summer, ${a('/grass/centipedegrass/', 'centipedegrass')} on a short late-spring feeding, ${a('/grass/zoysiagrass/', 'zoysiagrass')} at a lower yearly total than bermuda, ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} toward the coast, and ${a('/grass/tall-fescue/', 'tall fescue')} where the lawn is managed as a cool-season stand. Mississippi State University Extension publishes the lawn calendars. Use those dates if they differ from the months on this site.`,
        `${a('/seasons/summer/', 'Summer')} carries the warm-season grasses. ${a('/seasons/fall/', 'Fall')} carries tall fescue. This site’s warm-season window starts after full green-up and stops by early fall. No Mississippi blackout was found to override that, and none is invented here. Phosphorus still waits on a soil test. The calculator will flag a middle bag number above zero. It will not tell you the Hinds County ordinance.`,
      ] },
    ],
    sources: [
      { name: 'Mississippi State University Extension', url: 'https://extension.msstate.edu/' },
      { name: 'Mississippi Department of Agriculture and Commerce', url: 'https://www.mdac.ms.gov/' },
    ],
    unverified: [
      'No statewide homeowner fertilizer blackout was verified.',
      'No statewide phosphorus ban or numerical lawn nitrogen cap was verified.',
      'Whether individual cities regulate lawn fertilizer was not surveyed.',
    ],
  },
  {
    slug: 'florida', name: 'Florida', abbr: 'FL',
    summary: 'The state rule limits nitrogen and phosphorus on lawn fertilizers and how much quick-release nitrogen goes down at once. Many counties add a rainy-season blackout the state rule does not set by itself.',
    grasses: ['st-augustinegrass', 'bermudagrass', 'zoysiagrass', 'centipedegrass'],
    sections: [
      { id: 'rates', heading: 'Nitrogen by grass and by region', paragraphs: [
        `UF/IFAS EP353 is the publication this site follows for Florida yearly totals. North Florida is north of Ocala, central Florida runs from Ocala to State Road 60, and south Florida is the rest. The current table, in pounds of nitrogen per 1,000 sq ft per year, with clippings left on the lawn: bermudagrass 3–5, 4–6, and 5–7; St. Augustinegrass 2–4, 2–5, and 4–6; zoysiagrass 2–3, 2–4, and 2.5–4.5; centipedegrass 0.4–2, 0.4–3, and 0.4–3. Bahiagrass is on that table too and does not have a page here.`,
        `An older printing of the same family of tables, including one reproduced with Rule 5E-1.003, lists zoysia higher (3–5 / 3–6 / 4–6) and centipede higher at the floor (1–2 in the north). The current EP353 page and that older table disagree. This site uses the current EP353 figures. Ask the county office if they still hand out the older sheet.`,
      ] },
      { id: 'rule', heading: 'The urban turf rule, and where the wording splits', paragraphs: [
        `Florida’s urban turf rule (Rule 5E-1.003, Florida Administrative Code) is a labeling and application rule for lawn fertilizer, adopted by the Department of Agriculture and Consumer Services. EP353 summarizes it this way: no more than 0.7 lb of readily available (quick-release) nitrogen per 1,000 sq ft at one time. Phosphate is summarized as no more than 0.25 lb of P₂O₅ per 1,000 sq ft per application and 0.50 lb per year unless a soil test shows a deficiency. A starter application is a separate, one-time case. EP353 says the directions on bags under 50 lb sold for home lawns have to follow these limits.`,
        `Two wordings of the single-application total do not match. EP353 says the rule allows up to 2 lb of nitrogen per 1,000 sq ft in spring or summer when at least 65% of the nitrogen is controlled-release. A task-force copy of the rule text says no more than 1 lb total nitrogen per 1,000 sq ft at one time, with the 0.7 lb quick-release cap. This site does not pick a winner. The label on the bag you are holding is the one you follow, and 0.7 lb is the quick-release figure both descriptions share.`,
        `The state rule, as EP353 explains it, does not itself publish one statewide “no fertilizer from June 1 to September 30” calendar. Many counties and cities adopted ordinances, often from a state model, that do ban nitrogen or phosphorus in the rainy season and that can be stricter than the state label rule. The University of Florida keeps a fertilizer-ordinance resource. Look up the county before you treat summer as automatically legal or automatically banned. ${a('/grass/st-augustinegrass/', 'St. Augustine')}, ${a('/grass/bermudagrass/', 'bermuda')}, ${a('/grass/zoysiagrass/', 'zoysia')}, and ${a('/grass/centipedegrass/', 'centipede')} pages carry the feeding months. Local blackouts override them.`,
      ] },
    ],
    sources: [
      { name: 'UF/IFAS EP353: Urban Turf Fertilizer Rule for Home Lawn Fertilization', url: 'https://ask.ifas.ufl.edu/publication/EP353' },
      { name: 'Florida Rule 5E-1.003 (Florida Administrative Code)', url: 'https://www.flrules.org/gateway/RuleNo.asp?id=5E-1.003' },
      { name: 'UF/IFAS fertilizer ordinance resources', url: 'https://ffl-apps.ifas.ufl.edu/fertilizer/Home/Resources' },
      { name: 'Florida Department of Agriculture and Consumer Services', url: 'https://www.fdacs.gov/' },
    ],
    unverified: [
      'Which counties are inside a rainy-season blackout this year was not listed one by one.',
      'The conflict between EP353’s “up to 2 lb if 65% slow-release” sentence and the older rule text’s “1 lb total” sentence was not resolved.',
    ],
  },
  {
    slug: 'georgia', name: 'Georgia', abbr: 'GA',
    summary: 'State law, as quoted by a University of Georgia publication, stops cities and counties from regulating fertilizer use. No statewide homeowner blackout was verified.',
    grasses: ['bermudagrass', 'centipedegrass', 'zoysiagrass', 'st-augustinegrass', 'tall-fescue'],
    sections: [
      { id: 'law', heading: 'Local fertilizer ordinances are preempted', paragraphs: [
        `A University of Georgia River Basin Center paper quotes O.C.G.A. § 2-12-21: no county, city, or other political subdivision may adopt or keep a rule regulating the registration, labeling, packaging, sale, storage, transportation, distribution, use, or application of fertilizer. Business licenses and zoning are not blocked. The paper is an older legal analysis (it discusses the statute as a 2005 law). It is not the Georgia Code itself. Confirm the current section before you rely on a city flyer that claims to ban lawn fertilizer.`,
        `If that statute is still in force as quoted, Georgia is in the same family as Alabama and Louisiana: a city generally cannot be “stricter” about fertilizer application. Education programs are a different thing from an application ordinance. The paper itself makes that distinction. No statewide homeowner nitrogen cap or blackout dates were verified on this page. Do not import Florida’s 0.7 lb quick-release cap as Georgia law.`,
      ] },
      { id: 'feed', heading: 'North Georgia is not south Georgia', paragraphs: [
        `${a('/grass/bermudagrass/', 'Bermudagrass')}, ${a('/grass/centipedegrass/', 'centipedegrass')}, and ${a('/grass/zoysiagrass/', 'zoysiagrass')} cover most of the state. ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} is a coastal and south-Georgia grass. ${a('/grass/tall-fescue/', 'Tall fescue')} is the cool-season lawn in the mountains and the upper Piedmont, fed in ${a('/seasons/fall/', 'fall')}, not in July. University of Georgia Extension publishes the calendars. Where UGA’s pounds differ from the Florida columns this site uses as a comparison, UGA wins inside Georgia.`,
        `Warm-season feeding still means after green-up and done by early fall, which is ${a('/seasons/spring/', 'spring')} and ${a('/seasons/summer/', 'summer')} on this site. That is practice from the grass pages, not a Georgia statute. Phosphorus belongs on a soil test. The ${a('/method/', 'method page')} says the calculator cannot see your soil.`,
      ] },
    ],
    sources: [
      { name: 'University of Georgia River Basin Center, Managing Fertilizer for Lawn Use (quotes O.C.G.A. § 2-12-21)', url: 'https://rivercenter.uga.edu/wp-content/uploads/2021/01/Managing-Fertilizer-for-Lawn-Use.pdf' },
      { name: 'University of Georgia Cooperative Extension', url: 'https://extension.uga.edu/' },
      { name: 'Georgia Department of Agriculture', url: 'https://agr.georgia.gov/' },
    ],
    unverified: [
      'The current official text of O.C.G.A. § 2-12-21 was not re-read on the legislature’s code site; the quotation is from the UGA paper.',
      'No statewide homeowner blackout or numerical lawn rate cap was verified.',
    ],
  },
  {
    slug: 'louisiana', name: 'Louisiana', abbr: 'LA',
    summary: 'Parishes cannot write their own fertilizer rules unless the commissioner of agriculture approves them. No statewide homeowner blackout was verified.',
    grasses: ['st-augustinegrass', 'centipedegrass', 'bermudagrass', 'zoysiagrass'],
    sections: [
      { id: 'law', heading: 'Preemption, with a petition path', paragraphs: [
        `Louisiana Revised Statutes 3:1423 says regulation of fertilizer is preempted. A municipality, parish, or other local authority shall not enact ordinances that affect the registration, sale, or application of fertilizer, except as that section allows. A parish that wants a local rule has to petition the commissioner. The commission holds a hearing. The commissioner approves or disapproves. Ordinances already in effect on July 1, 2008 had to be submitted by December 1, 2008, or they became void.`,
        `So “check your parish, it might be stricter” is only half right. A parish might have an approved ordinance. It may not simply pass one. This page did not inventory which parishes, if any, hold an approval. Ask the parish and the Louisiana Department of Agriculture and Forestry. No statewide blackout dates or homeowner pound caps were verified here. Florida’s rule is not Louisiana’s rule.`,
      ] },
      { id: 'feed', heading: 'Gulf grasses, warm-season timing', paragraphs: [
        `${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} and ${a('/grass/centipedegrass/', 'centipedegrass')} are the lawns people argue about in Louisiana, along with ${a('/grass/bermudagrass/', 'bermudagrass')} in full sun and ${a('/grass/zoysiagrass/', 'zoysiagrass')} where someone wanted a denser, slower grass. LSU AgCenter is the extension source for which one belongs on a given soil. Centipede still gets the short, small feeding on its own page. St. Augustine gets the middle budget, not bermuda’s south-Florida top rate, unless LSU says otherwise for your region.`,
        `Start after green-up (${a('/seasons/spring/', 'spring')}), feed through ${a('/seasons/summer/', 'summer')} only for the grasses whose pages say so, and do not give centipede a ${a('/seasons/fall/', 'fall')} “winterizer.” Tall fescue is not the default Louisiana lawn. If you have a patch of it, use the fescue page and expect summer to hurt it.`,
      ] },
    ],
    sources: [
      { name: 'Louisiana Revised Statutes 3:1423 (local regulations)', url: 'https://legis.la.gov/Legis/Law.aspx?d=726860' },
      { name: 'LSU AgCenter', url: 'https://www.lsuagcenter.com/' },
      { name: 'Louisiana Department of Agriculture and Forestry', url: 'https://www.ldaf.la.gov/' },
    ],
    unverified: [
      'No statewide homeowner blackout or numerical rate cap was verified.',
      'Which parishes have a commissioner-approved fertilizer ordinance was not listed.',
    ],
  },
  {
    slug: 'texas', name: 'Texas', abbr: 'TX',
    summary: 'No statewide homeowner blackout was verified. Texas is large enough that a Panhandle lawn and a Houston lawn are not on the same calendar. Check the city.',
    grasses: ['bermudagrass', 'st-augustinegrass', 'zoysiagrass', 'centipedegrass', 'tall-fescue'],
    sections: [
      { id: 'law', heading: 'State labeling is not a feeding calendar', paragraphs: [
        `No Texas statute was verified that sets a statewide date range when homeowners may not fertilize lawns, or that copies Florida’s 0.7 lb quick-release cap or Virginia’s phosphorus sale ban. The Texas Department of Agriculture regulates fertilizer products. That is not a month-by-month lawn schedule. Cities can and sometimes do pass nutrient rules for stormwater. Austin and San Antonio are often mentioned in conversation. This page does not describe those ordinances because their current text was not opened line by line. Check the city you pay taxes to.`,
        `Until you have read the city code, do not claim you are “following Texas law” by using or skipping a summer feeding. You are following extension practice and, if the city has an ordinance, that ordinance.`,
      ] },
      { id: 'feed', heading: 'East, central, south, west', paragraphs: [
        `${a('/grass/bermudagrass/', 'Bermudagrass')} is the common full-sun lawn across a lot of the state. ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} dominates shady Gulf and east-Texas yards. ${a('/grass/zoysiagrass/', 'Zoysiagrass')} is the slower, lower-nitrogen alternative. ${a('/grass/centipedegrass/', 'Centipedegrass')} appears in east Texas on acid soils and should stay on its small yearly budget. ${a('/grass/tall-fescue/', 'Tall fescue')} is a northern-Texas or shaded experiment more often than a statewide default; summer will punish it. Texas A&M AgriLife Extension is the source that splits the state into regions. A south-Florida bermuda rate does not belong in Amarillo, and a north-Florida centipede rate is not a reason to starve a College Station bermuda lawn.`,
        `Warm-season pages use ${a('/seasons/spring/', 'spring')} green-up through ${a('/seasons/summer/', 'summer')}, then stop. Fall is for fescue, not for pushing bermuda. Water rules and drought stage are separate from fertilizer law and were not catalogued here.`,
      ] },
    ],
    sources: [
      { name: 'Texas A&M AgriLife Extension', url: 'https://agrilifeextension.tamu.edu/' },
      { name: 'Texas Department of Agriculture', url: 'https://www.texasagriculture.gov/' },
    ],
    unverified: [
      'No statewide homeowner blackout or phosphorus ban was verified.',
      'Current text of city fertilizer ordinances (including any in Austin or San Antonio) was not verified page by page.',
      'Regional AgriLife nitrogen rates were not copied onto this page; use the AgriLife publication for your region.',
    ],
  },
  {
    slug: 'tennessee', name: 'Tennessee', abbr: 'TN',
    summary: 'No statewide lawn blackout was verified. Tennessee sits on the cool-season / warm-season line, so the grass decides the calendar.',
    grasses: ['tall-fescue', 'bermudagrass', 'zoysiagrass', 'kentucky-bluegrass'],
    sections: [
      { id: 'law', heading: 'Nothing statewide was verified as a blackout', paragraphs: [
        `No Tennessee statute was verified that bans lawn fertilizer on fixed dates or that sets a homeowner phosphorus limit like Virginia’s. The Department of Agriculture handles fertilizer as a product. Local stormwater rules were not surveyed. Check the county and the city. Do not treat silence on this page as proof that every city is silent.`,
      ] },
      { id: 'feed', heading: 'Two calendars in one state', paragraphs: [
        `${a('/grass/tall-fescue/', 'Tall fescue')} is the common lawn through much of Tennessee and is fed in ${a('/seasons/fall/', 'fall')} (September and November on the NC State calendar this site uses, with a light February in the transition zone). ${a('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} shares that cool-season shape where it is grown. ${a('/grass/bermudagrass/', 'Bermudagrass')} and ${a('/grass/zoysiagrass/', 'zoysiagrass')} are the warm-season lawns and take ${a('/seasons/spring/', 'spring')} and ${a('/seasons/summer/', 'summer')} after green-up, then stop. Using the fescue months on bermuda, or the bermuda months on fescue, is the mistake this state’s geography invites.`,
        `University of Tennessee Extension publishes the lawn maintenance calendars. A UT PDF (W160-B) could not be read when the seed rates on this site were checked, and it is not used as a source here either. If UT’s yearly nitrogen total differs from the bands on the grass pages, use UT for a Tennessee lawn. Centipede and St. Augustine are not the typical Tennessee lawn; if you have them, their pages still apply and the climate may be at the edge of what they like.`,
      ] },
    ],
    sources: [
      { name: 'University of Tennessee Extension', url: 'https://utextension.tennessee.edu/' },
      { name: 'Tennessee Department of Agriculture', url: 'https://www.tn.gov/agriculture.html' },
    ],
    unverified: [
      'No statewide homeowner blackout or phosphorus limit was verified.',
      'Local ordinances were not surveyed.',
      'UT publication W160-B was not readable and is not cited for rates.',
    ],
  },
  {
    slug: 'south-carolina', name: 'South Carolina', abbr: 'SC',
    summary: 'No statewide homeowner blackout was verified. Clemson Extension is the lawn authority; the grass still picks the season.',
    grasses: ['centipedegrass', 'bermudagrass', 'zoysiagrass', 'st-augustinegrass', 'tall-fescue'],
    sections: [
      { id: 'law', heading: 'No statewide date rule was verified', paragraphs: [
        `No South Carolina statute was verified that sets a homeowner fertilizer blackout or a numerical nitrogen cap for lawns. Fertilizer sales are a state agriculture matter. Cities and counties were not checked one by one, so a local stormwater rule remains possible. Check the county. Do not copy a North Carolina basin rule or a Florida county blackout across the state line.`,
      ] },
      { id: 'feed', heading: 'Centipede country, with company', paragraphs: [
        `South Carolina is where ${a('/grass/centipedegrass/', 'centipedegrass')} is a default rather than a curiosity. Keep it at 0.4–2 lb of nitrogen per 1,000 sq ft for the year and in late spring to early summer only. ${a('/grass/bermudagrass/', 'Bermudagrass')} in the sun gets the higher summer budget. ${a('/grass/zoysiagrass/', 'Zoysiagrass')} stays under bermuda. ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} is the coastal shade grass. ${a('/grass/tall-fescue/', 'Tall fescue')} is an upstate, cool-season lawn and belongs on the ${a('/seasons/fall/', 'fall')} calendar.`,
        `Clemson Cooperative Extension and the Home & Garden Information Center publish the species fact sheets. Their months and rates outrank this site inside South Carolina when they differ. ${a('/seasons/summer/', 'Summer')} feeding is for the warm-season grasses whose pages include summer, not for fescue and not for a second helping of centipede in August.`,
      ] },
    ],
    sources: [
      { name: 'Clemson Cooperative Extension Home & Garden Information Center', url: 'https://hgic.clemson.edu/' },
      { name: 'Clemson Cooperative Extension', url: 'https://www.clemson.edu/extension/' },
      { name: 'South Carolina Department of Agriculture', url: 'https://agriculture.sc.gov/' },
    ],
    unverified: [
      'No statewide homeowner blackout or rate cap was verified.',
      'City and county ordinances were not surveyed.',
      'Clemson’s own pound-per-year tables were not transcribed onto this page.',
    ],
  },
  {
    slug: 'north-carolina', name: 'North Carolina', abbr: 'NC',
    summary: 'Homeowners fertilizing their own lawns are largely outside the basin nutrient-training rules. Cities generally cannot invent a fertilizer ordinance unless the state environmental commission approves it.',
    grasses: ['tall-fescue', 'bermudagrass', 'zoysiagrass', 'centipedegrass', 'kentucky-bluegrass', 'st-augustinegrass'],
    sections: [
      { id: 'law', heading: 'Two basin rules, and a limit on city ordinances', paragraphs: [
        `North Carolina does not, on the pages read for this site, ban phosphorus in every homeowner lawn fertilizer the way Virginia does. What it does have are nutrient-strategy rules for the Neuse and Tar-Pamlico river basins (15A NCAC 02B .0239 and 02B .0257). They require training or a nutrient-management plan for people who apply fertilizer as a business, for many turf managers, and for applicators hired by homeowners. The Tar-Pamlico text expressly excepts residential landowners who apply fertilizer to their own property from the owner-and-manager list, while still covering applicators those landowners hire. The goal language in the Tar-Pamlico rule is a 30% cut in nitrogen loading from 1991 and a cap on phosphorus loading at 1991 levels for the estuary. That is a basin target, not a “0.7 lb on your lawn” number.`,
        `A North Carolina Department of Agriculture briefing states that G.S. 106-678 stops local governments from adopting fertilizer-use ordinances unless the Environmental Management Commission approves them as part of a water-quality strategy. The same briefing says residential fertilizer use is not regulated the way farms and wastewater plants are, because the state does not have the staff to police every yard. So a North Carolina city is not free to copy a Florida county blackout on its own. Whether any local rule has EMC approval was not catalogued here.`,
        `The statute page and the full Neuse text should be read before you advise anyone else. This summary is the part that was checked. It is not legal advice.`,
      ] },
      { id: 'feed', heading: 'The calendars this site already uses', paragraphs: [
        `NC State Extension is the source of the cool-season calendar on this site (AG-931: September, November, and February for tall fescue, fine fescue, and Kentucky bluegrass) and of the seed rates (AG-69). ${a('/grass/tall-fescue/', 'Tall fescue')} is the transition-zone workhorse and is a ${a('/seasons/fall/', 'fall')} grass, about 3 lb of nitrogen a year on that calendar. ${a('/grass/bermudagrass/', 'Bermudagrass')}, ${a('/grass/zoysiagrass/', 'zoysiagrass')}, ${a('/grass/centipedegrass/', 'centipedegrass')}, and coastal ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} follow the warm-season pages. Piedmont bermuda and coastal St. Augustine are not the same feeding year. Carolina Lawns (AG-69) is the overview.`,
      ] },
    ],
    sources: [
      { name: '15A NCAC 02B .0257, Tar-Pamlico nutrient management', url: 'https://ncrules.elaws.us/code/15ancac02b.0257' },
      { name: '15A NCAC 02B .0239, Neuse nutrient management', url: 'https://ncrules.elaws.us/code/15ancac02b.0239' },
      { name: 'NC DEQ, Tar-Pamlico nutrient strategy', url: 'https://www.deq.nc.gov/about/divisions/water-resources/water-planning/nonpoint-source-planning/tar-pamlico-nutrient-strategy' },
      { name: 'NC State Extension, Carolina Lawns (AG-69)', url: 'https://content.ces.ncsu.edu/carolina-lawns' },
      { name: 'NC Department of Agriculture and Consumer Services', url: 'https://www.ncagr.gov/' },
    ],
    unverified: [
      'The official text of G.S. 106-678 was not opened on ncleg.gov; the description comes from an NCDA briefing.',
      'No EMC-approved local fertilizer ordinance was individually verified.',
      'No statewide pound cap for homeowner lawns was verified outside the basin training rules.',
    ],
  },
  {
    slug: 'arkansas', name: 'Arkansas', abbr: 'AR',
    summary: 'Nutrient rules for turf apply in designated nutrient-surplus areas, not as a single statewide blackout. Outside those areas, this page did not verify a homeowner rate cap.',
    grasses: ['bermudagrass', 'zoysiagrass', 'tall-fescue', 'centipedegrass'],
    sections: [
      { id: 'law', heading: 'Nutrient surplus areas, not the whole map', paragraphs: [
        `University of Arkansas fact sheet FSA9532 explains rules that grew out of 2003 legislation on nutrient surplus areas, aimed first at northwest Arkansas waterways. Title XXI and Title XXII, as the fact sheet describes them, cover nutrient applications to turf, lawns, and landscaping in those designated areas. The fact sheet includes a map. This page does not redraw that map or guess which county you are in.`,
        `Inside those areas, the fact sheet says: poultry litter goes on only at the rates in a nutrient management plan; if there is no plan, commercial fertilizer may not exceed the protective rate in the fact sheet’s tables; nutrients are not applied when soil is saturated, frozen, or covered with ice or snow; and nutrients are not applied so that they enter state waters or run onto neighboring property. Records and certification requirements apply to applicators covered by the program. The protective-rate tables were not copied here. Open the PDF and read the table that matches your fertilizer. Those numbers are not statewide for every Arkansas county. Outside the mapped areas, no homeowner blackout was verified.`,
      ] },
      { id: 'feed', heading: 'Warm-season lawns, fescue in the cooler pockets', paragraphs: [
        `${a('/grass/bermudagrass/', 'Bermudagrass')} and ${a('/grass/zoysiagrass/', 'zoysiagrass')} are the common summer lawns. ${a('/grass/tall-fescue/', 'Tall fescue')} is the cool-season option and takes ${a('/seasons/fall/', 'fall')}. ${a('/grass/centipedegrass/', 'Centipedegrass')} stays on a small budget if you have it in the south. University of Arkansas Cooperative Extension is the rate source. The grass pages are the comparison. A nutrient-surplus protective rate, if it is lower than the grass page, wins inside that area because it is the rule the fact sheet describes, not a suggestion.`,
      ] },
    ],
    sources: [
      { name: 'University of Arkansas FSA9532: Understanding Nutrient Management Laws for Turf Grass, Lawn Care and Landscaping', url: 'https://www.uaex.uada.edu/publications/PDF/FSA-9532.pdf' },
      { name: 'University of Arkansas System Division of Agriculture, Cooperative Extension', url: 'https://www.uaex.uada.edu/' },
    ],
    unverified: [
      'Protective-rate numbers in the FSA9532 tables were not copied onto this page.',
      'The current boundary of each nutrient surplus area was not re-drawn; use the fact sheet’s map.',
      'No statewide rule outside those areas was verified.',
    ],
  },
  {
    slug: 'kentucky', name: 'Kentucky', abbr: 'KY',
    summary: 'No statewide homeowner blackout was verified. Kentucky lawns are mostly cool-season, so fall is the feeding season.',
    grasses: ['kentucky-bluegrass', 'tall-fescue'],
    sections: [
      { id: 'law', heading: 'No blackout was verified', paragraphs: [
        `No Kentucky statute was verified that sets dates when homeowners may not apply lawn fertilizer, or that bans phosphorus in maintenance fertilizer the way Virginia’s code does. The Department of Agriculture regulates products. Local ordinances were not surveyed. Check the county extension office and the city before you assume there is no stormwater rule. Also do not assume there is a hidden blackout and skip a September feeding that the University of Kentucky recommends.`,
      ] },
      { id: 'feed', heading: 'Cool-season first', paragraphs: [
        `${a('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} and ${a('/grass/tall-fescue/', 'tall fescue')} are the lawns this state is named for in practice. Both take the cool-season year: 1–4 lb of nitrogen per 1,000 sq ft, with the main feedings in ${a('/seasons/fall/', 'September and November')}, light dates in late spring, and summer left alone. University of Kentucky Cooperative Extension publishes the local calendar. If UK’s maintenance levels differ from Nebraska’s 1–2 / 2–3 / 3–4 bands that this site quotes, use UK.`,
        `${a('/grass/bermudagrass/', 'Bermudagrass')} is a special case in the warmer counties, not the default. If you have it, use the bermuda page and a UK warm-season note, and do not feed it in November just because the fescue next door is being fed. ${a('/seasons/winter/', 'Winter')} is not an extra feeding on top of November.`,
      ] },
    ],
    sources: [
      { name: 'University of Kentucky Cooperative Extension', url: 'https://extension.ca.uky.edu/' },
      { name: 'Kentucky Department of Agriculture', url: 'https://www.kyagr.com/' },
    ],
    unverified: [
      'No statewide homeowner blackout or phosphorus ban was verified.',
      'UK’s current pound-per-year table was not transcribed.',
      'Local ordinances were not surveyed.',
    ],
  },
  {
    slug: 'virginia', name: 'Virginia', abbr: 'VA',
    summary: 'Routine lawn-maintenance fertilizer may not contain phosphorus. Nitrogen rates on those products have to match Virginia’s nutrient-management standards. Commercial applicators are certified.',
    grasses: ['tall-fescue', 'kentucky-bluegrass', 'bermudagrass', 'zoysiagrass'],
    sections: [
      { id: 'law', heading: 'Phosphorus on maintenance fertilizer', paragraphs: [
        `Virginia Code § 3.2-3607(F) says that, beginning December 31, 2013, no lawn maintenance fertilizer containing more than zero percent phosphorus, or other phosphorus compounds such as phosphate, shall be registered or offered for sale, distribution, or use in the Commonwealth. The ban does not cover everything green. The section exempts lawn fertilizer (a defined category), manipulated manure, yard-waste compost, sewage-sludge products, soils that contain fertilizer, products meant primarily for gardens, trees, shrubs, and indoor plants, and reclaimed water. Retailers could sell stock they already had on that date.`,
        `The regulation 2VAC5-405 defines “lawn fertilizer” as fertilizer for newly established turf during the first growing season, turf being repaired or renovated, and turf where a soil test in the past three years shows a nutrient deficiency. “Lawn maintenance fertilizer” is the routine product. So a phosphorus-containing product can still be legal when it is truly a starter or a soil-test correction. It is not a legal default for “just greening up” an established lawn. Read the label. If it says maintenance and the middle number is above zero, it does not belong on a Virginia store shelf under this statute.`,
        `Section 3.2-3607(G) says that, beginning July 1, 2014, lawn maintenance fertilizer may be registered only when, applied as directed, its nitrogen rates match the rates recommended for turf in the Virginia Nutrient Management Standards and Criteria. This page does not reprint those criteria. They are the numerical cap. Do not substitute Florida’s table or this site’s 1 lb starting rate if the Virginia standard or the label is lower.`,
      ] },
      { id: 'who', heading: 'Who has to be certified', paragraphs: [
        `Virginia’s regulations for fertilizer on nonagricultural land require certification for contractor-applicators, licensees, and government employees who apply fertilizer commercially. The Virginia Department of Agriculture and Consumer Services runs the Certified Fertilizer Applicator program. Certification lasts four years, with coursework to renew. Applicators who treat more than 50 acres of nonagricultural land file an annual report by February 1. A homeowner spreading a bag on one yard is not that program. A lawn company is.`,
        `Contractors and licensees who comply with the state regulations are not subject to local ordinances governing lawn fertilizer, under § 3.2-3602.1(F). That sentence is about those businesses, not a promise that every homeowner is free of every city rule. Homeowners should still check the city. It is not a reason for a company to ignore the phosphorus ban; the ban is state law.`,
      ] },
      { id: 'feed', heading: 'Mostly a fescue state', paragraphs: [
        `${a('/grass/tall-fescue/', 'Tall fescue')} and ${a('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} take ${a('/seasons/fall/', 'fall')} feedings. ${a('/grass/bermudagrass/', 'Bermudagrass')} and ${a('/grass/zoysiagrass/', 'zoysiagrass')} are warm-season lawns in the warmer counties and follow spring and summer after green-up. Virginia Cooperative Extension and the nutrient-management standards are the rate authority. This site’s calculator will still compute a 1 lb feeding if you type 1. In Virginia, only do that when the label and the state standard allow it. A 10-10-10 maintenance feeding on an established lawn conflicts with the phosphorus ban regardless of what the math says.`,
      ] },
    ],
    sources: [
      { name: 'Virginia Code § 3.2-3607 (product registration, phosphorus, nitrogen)', url: 'https://law.lis.virginia.gov/vacode/title3.2/chapter36/section3.2-3607/' },
      { name: 'Virginia Code § 3.2-3602.1 (applicator regulations)', url: 'https://law.lis.virginia.gov/vacode/title3.2/chapter36/section3.2-3602.1/' },
      { name: '2VAC5-405, fertilizer on nonagricultural lands', url: 'https://law.lis.virginia.gov/admincode/title2/agency5/chapter405/' },
      { name: 'VDACS Certified Fertilizer Applicator program', url: 'https://www.vdacs.virginia.gov/plant-industry-services-certified-fertilizer-applicator-training.shtml' },
      { name: 'Virginia Cooperative Extension', url: 'https://ext.vt.edu/' },
    ],
    unverified: [
      'The numeric nitrogen rates inside the Virginia Nutrient Management Standards and Criteria were not copied onto this page.',
      'City rules that still apply to homeowners, as opposed to certified contractors, were not surveyed.',
    ],
  },
];

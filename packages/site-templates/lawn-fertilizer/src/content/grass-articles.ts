/** Unique copy for each grass page. Numbers are the ones already on the site or in the sources named in the text. */

export interface ArticleSection { id: string; heading: string; paragraphs: string[] }
export interface ArticleFaq { q: string; a: string }
export interface GrassArticle { sections: ArticleSection[]; faqs: ArticleFaq[] }

const link = (href: string, text: string) => `<a href="${href}">${text}</a>`;

export const GRASS_ARTICLES: Record<string, GrassArticle> = {
  'kentucky-bluegrass': {
    sections: [
      { id: 'habit', heading: 'A grass that grows when the weather cools', paragraphs: [
        `Kentucky bluegrass (<em>Poa pratensis</em>) is the lawn in the photograph on this page. It is a cool-season grass: the growing that matters happens in spring and again in fall, and the lawn slows down in summer heat. The feeding plan follows that shape. A summer-long schedule written for ${link('/grass/bermudagrass/', 'bermudagrass')} puts nitrogen down when bluegrass is least able to use it.`,
        `The photograph is a mowed stand, which is how most people meet this grass. This page does not quote a hours-of-sun figure. The extension pages behind the rates do not give one number that fits every cultivar. If the yard is shaded most of the day, ask the county office before you pick bluegrass over ${link('/grass/tall-fescue/', 'tall fescue')}. The rates below assume the grass is actually growing.`,
      ] },
      { id: 'nitrogen', heading: 'How much nitrogen, and how that differs', paragraphs: [
        `University of Nebraska–Lincoln sorts cool-season lawns by the level of care: about 1–2 lb of nitrogen per 1,000 sq ft a year for a low-care lawn, 2–3 lb for a typical lawn, and 3–4 lb for high care. That is the 1–4 lb yearly range this site uses. It is a year's total, spread across several feedings, not a single application.`,
        `Set beside the other grasses on this site, bluegrass sits with tall fescue in the cool-season band and well below bermudagrass. NC State's calendar for tall fescue adds up to about 3 lb a year, inside the same 1–4 lb Nebraska span. Bermudagrass in the University of Florida's current north-Florida column is 3–5 lb, and the south-Florida column goes to 5–7. ${link('/grass/centipedegrass/', 'Centipedegrass')} is the opposite case: 0.4–2 lb in north Florida on the current UF/IFAS table. Feeding bluegrass at a centipede rate leaves it thin. Feeding it at a south-Florida bermuda rate is too much for one year.`,
        `One feeding of quick-release nitrogen should stay around 1 lb per 1,000 sq ft or less. That is the limit Rutgers describes for soluble nitrogen. Florida's urban turf rule, summarized by UF/IFAS EP353, caps readily available nitrogen at 0.7 lb per 1,000 sq ft in a single application. Bluegrass is not a Florida lawn grass, but a bag labeled under that rule still has to be followed. The label wins over this page.`,
      ] },
      { id: 'when', heading: 'Fall carries the year', paragraphs: [
        `NC State Extension's calendar for Kentucky bluegrass and the fescues puts the main feedings in September and around November, while the grass is still green, and adds February in the transition zone. Nebraska adds lighter feedings in late April and early June. This site's calendar marks September and November as the main months and February, April, and June as light. Summer heat is left off on purpose.`,
        `${link('/seasons/fall/', 'Fall')} is the season to read first if this is your grass. ${link('/seasons/spring/', 'Spring')} is only a light feeding, if you feed at all. ${link('/seasons/summer/', 'Summer')} is the season to skip. ${link('/seasons/winter/', 'Winter')} is not a bonus feeding: the November application is already the late one, and February is the transition-zone feeding NC State lists, not a reason to fertilize a frozen northern lawn. This site does not add a separate "winterizer" rate on top of November.`,
        `At the 1 lb starting rate, the year's 1–4 lb works out to about one to four feedings. A low-care lawn may only need the two fall dates. A high-care lawn can use the light spring dates as well and still stay inside 4 lb. Your ${link('/states/', 'state page')} and the county office outrank this calendar when they name different months.`,
      ] },
      { id: 'example', heading: 'One feeding on 5,000 square feet', paragraphs: [
        `This page starts the calculator at 1 lb of nitrogen per 1,000 sq ft on a 5,000 sq ft lawn. For a 29-0-4 product that is 1 ÷ 0.29 = 3.4 lb of product per 1,000 sq ft, and 17.2 lb on the whole lawn. The table under the calculator repeats that step for 16-4-8, 10-10-10, and urea (46-0-0). The formula is the one Iowa State, Rutgers FS839, and NC State's shortcut (100 ÷ the first bag number) all use. It is not a guess about your soil.`,
        `If the lawn is not 5,000 sq ft, do not scale this in your head and then round the wrong way. Open the ${link('/lawn-size/5000-sq-ft/', '5,000 sq ft page')}, the ${link('/lawn-size/under-2000-sq-ft/', 'under 2,000 sq ft page')}, or the ${link('/lawn-size/', 'size guide')}, or type the area into the calculator. Bag weight changes how many bags you buy, not how many pounds the lawn needs. The ${link('/bags/', 'bag-size pages')} separate those two questions.`,
      ] },
      { id: 'mistakes', heading: 'Mistakes that show up on bluegrass', paragraphs: [
        `The usual miss is treating it like a summer grass: several feedings from May through August, then nothing in September. The nitrogen lands when the lawn is stressed, and the fall, when the roots actually use it, is skipped. The other miss is dumping the whole year's 3 or 4 lb in one or two spring applications. Split it. A quick-release product is not labeled to carry the year in a day.`,
        `Phosphorus is the middle number on the bag. Several states restrict it on established lawns unless a soil test, or a new planting, calls for it. Virginia's rule on routine lawn-maintenance fertilizer is the strict one on this site; Florida caps phosphate rates on bags covered by the urban turf rule. The calculator only notices that the middle number is above zero. It does not know your county. Read ${link('/states/virginia/', 'Virginia')} or ${link('/states/florida/', 'Florida')} if you live there, and the ${link('/method/', 'method page')} for what the math does not do.`,
        `New bluegrass is seeded, not sprigged. NC State Extension AG-69, the source for this site's ${link('/guides/grass-seed/', 'seed calculator')}, lists 1–2 lb of seed per 1,000 sq ft for a new lawn, in late summer to early fall. That is far fewer pounds than tall fescue because the seed is small. It is also slow to come up. Overseeding an existing lawn uses a lower rate, 25–50% less on this site's calculator. Do not invent a higher seeding rate to "make it thicker faster."`,
      ] },
    ],
    faqs: [
      { q: 'How much nitrogen does Kentucky bluegrass need in a year?',
        a: 'About 1–4 lb per 1,000 sq ft for the year, using University of Nebraska–Lincoln\'s low, typical, and high-care bands (1–2, 2–3, and 3–4). Spread that total over the feedings on the calendar. One feeding should stay near 1 lb of quick-release nitrogen or less.' },
      { q: 'When should I fertilize Kentucky bluegrass?',
        a: 'September and November are the main months on this site, from NC State\'s calendar, while the grass is still green. February, late April, and early June are light or regional. Skip summer heat. A state guide that names other months wins.' },
      { q: 'Can I grow Kentucky bluegrass from seed?',
        a: 'Yes. NC State lists 1–2 lb of seed per 1,000 sq ft for a new lawn, sown from late summer into early fall. The seed calculator on this site uses that rate and a lower one for overseeding.' },
      { q: 'Is a winterizer a separate feeding?',
        a: 'Not on this site. The late feeding is the November application while the grass is still green. There is no extra winter rate stacked on top of it.' },
    ],
  },
  'tall-fescue': {
    sections: [
      { id: 'habit', heading: 'The bunch grass of the transition zone', paragraphs: [
        `Tall fescue (<em>Festuca arundinacea</em>, also called <em>Lolium arundinaceum</em> and <em>Schedonorus arundinaceus</em> in newer names) is a cool-season grass with a deep root system and a bunch habit. The photograph is a nursery plant with the species name on the label, not a mowed yard, so you can see the plant the page is about. In a lawn it is usually a sod or a seeded stand, not a pot.`,
        `It is the common seeded lawn grass of the transition zone, the band where summers are too hot for an easy northern lawn and winters are too cold for bermudagrass to stay green. NC State treats it on the same home-lawn calendar as Kentucky bluegrass and the fine fescues. It is not a warm-season grass, and it should not be fed on a ${link('/grass/bermudagrass/', 'bermudagrass')} calendar.`,
      ] },
      { id: 'nitrogen', heading: 'A cool-season budget, with NC State\'s ceiling', paragraphs: [
        `The yearly range on this site is 1–4 lb of nitrogen per 1,000 sq ft, the same Nebraska low-to-high span used for ${link('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')}. NC State's tall-fescue calendar adds up to about 3 lb a year, which sits inside that span and is the practical ceiling this site points to for the transition zone. If a state guide says less, use the state guide.`,
        `That is less nitrogen than bermudagrass, which UF/IFAS lists at 3–5 lb in north Florida and up to 5–7 lb in the south. It is more than ${link('/grass/centipedegrass/', 'centipedegrass')}, at 0.4–2 lb in the current north-Florida column. Tall fescue does not want centipede's starvation diet, and it does not want bermuda's summer appetite. The difference is the season as much as the total: fescue takes its nitrogen in fall, bermuda takes it after spring green-up.`,
        `Keep a single quick-release feeding around 1 lb per 1,000 sq ft or less (Rutgers). The page starts the calculator at that 1 lb rate. Slow-release products may be labeled for more. Florida's 0.7 lb cap on readily available nitrogen applies to bags covered by the urban turf rule, which matters when the product in your hand was labeled for Florida even if the lawn itself is in North Carolina or Tennessee.`,
      ] },
      { id: 'when', heading: 'September, November, and a light February', paragraphs: [
        `NC State lists mid-September and November as the feedings, plus February in the transition zone. Nebraska's cool-season schedule adds light applications in late April and early June and tells you to skip summer heat. This site shows September and November as the main months and February, April, and June as light. July and August stay empty.`,
        `Read ${link('/seasons/fall/', 'fall')} before the other seasons. ${link('/seasons/spring/', 'Spring')} is optional and light. ${link('/seasons/summer/', 'Summer')} is when tall fescue struggles with heat and with diseases that like humidity; adding a heavy feeding then is the mistake, not the cure. ${link('/seasons/winter/', 'Winter')} does not get its own rate. November, while the grass is still green, is the late feeding. February is only the transition-zone date NC State adds, and only as a light feeding on this calendar.`,
        `At 1 lb per feeding, three feedings land near NC State's roughly 3 lb year, and four land at the top of the Nebraska high-care band. A low-care lawn can stop at one or two fall feedings and stay near 1–2 lb. Count the year before you add "just one more" in May.`,
      ] },
      { id: 'seed', heading: 'The seeding rate is the high one', paragraphs: [
        `Tall fescue is the grass people actually plant from a big bag of seed. NC State AG-69 lists 6 lb of seed per 1,000 sq ft for a new lawn, late summer to early fall. Kentucky bluegrass, on the same publication, is 1–2 lb, because the seed is so much smaller. The ${link('/guides/grass-seed/', 'seed calculator')} uses 6 lb and, for overseeding, 25–50% less. On 5,000 sq ft a new lawn is 30 lb of seed. That figure is seed, not fertilizer. Do not mix the two totals.`,
        `A 5,000 sq ft feeding at 1 lb of nitrogen from 29-0-4 is 17.2 lb of fertilizer, a different pile from the 30 lb of seed. The ${link('/lawn-size/5000-sq-ft/', '5,000 sq ft fertilizer page')} is the fertilizer side. If you are establishing a lawn, phosphorus may be justified as a starter where a soil test or your state allows it. On an established fescue lawn, do not keep buying a high-phosphorus "starter" out of habit. ${link('/states/virginia/', 'Virginia')} bars phosphorus in routine lawn-maintenance fertilizer. Other states vary. The ${link('/states/', 'state pages')} say what was verified.`,
      ] },
      { id: 'mistakes', heading: 'What goes wrong', paragraphs: [
        `Brown, hot-weather patches get an extra summer feeding because the lawn looks hungry. Heat-stressed tall fescue is a poor candidate for more quick-release nitrogen. The calendar is empty in summer for that reason. Water, mowing height, and patience belong there; the September feeding is the restart.`,
        `The other miss is seeding in late spring because the bag was on sale. NC State's window for this grass is late summer to early fall. Spring seedlings meet summer before the roots are down. And do not use a St. Augustine or centipede "low nitrogen" habit on a fescue lawn you are trying to keep dense. The yearly total is in the cool-season band, delivered in fall, not a single spring dump and not a summer drip.`,
      ] },
    ],
    faqs: [
      { q: 'How much nitrogen does tall fescue need in a year?',
        a: 'This site uses 1–4 lb per 1,000 sq ft a year from Nebraska\'s cool-season bands. NC State\'s calendar adds up to about 3 lb, which is the figure to plan around in the transition zone unless your state guide says otherwise.' },
      { q: 'When do I fertilize tall fescue?',
        a: 'September and November are the main months. February is a light transition-zone feeding on the NC State calendar. Late April and early June are light and northern. Do not feed in summer heat.' },
      { q: 'How much seed is a new tall fescue lawn?',
        a: '6 lb per 1,000 sq ft on NC State\'s Carolina Lawns guide, sown late summer to early fall. A 5,000 sq ft new lawn is 30 lb of seed. Overseeding uses less. Use the seed calculator so the number is not confused with fertilizer pounds.' },
      { q: 'Is tall fescue the same as Kentucky bluegrass for fertilizer?',
        a: 'The months match and the yearly band is the same 1–4 lb. NC State\'s fescue calendar is the one that points at about 3 lb. The seed rate does not match: fescue is 6 lb of seed per 1,000 sq ft and bluegrass is 1–2 lb.' },
    ],
  },
  bermudagrass: {
    sections: [
      { id: 'habit', heading: 'A summer grass that runs', paragraphs: [
        `Bermudagrass (<em>Cynodon dactylon</em>) is the lawn in the photograph, identified by the photographer as couch grass, <em>Cynodon dactylon</em>. It is a warm-season grass. It sleeps in cool weather, greens up in spring, and does its growing in the heat. It spreads by both stolons and rhizomes, which is why a few sprigs can take a bed and why it shows up in cracks and flower borders you did not plant.`,
        `It wants sun. This page does not quote a minimum hours-of-sun number; the rate tables do not include one. If the yard is shady, bermudagrass is usually the wrong choice and ${link('/grass/st-augustinegrass/', 'St. Augustinegrass')} or, farther north, ${link('/grass/tall-fescue/', 'tall fescue')} is the conversation to have with the county office. Feeding a thin, shaded bermuda lawn harder does not turn it into a shade grass.`,
      ] },
      { id: 'nitrogen', heading: 'The highest nitrogen budget of the six', paragraphs: [
        `On this site the yearly range is 3–5 lb of nitrogen per 1,000 sq ft, the north-Florida column of the current UF/IFAS table in EP353. The same table lists 4–6 lb for central Florida and 5–7 lb for south Florida (south of State Road 60 on that publication). Those higher columns are why the short note on this site says Florida's guide goes up to 7 lb in the south. North of Florida, your state extension rate wins if it is lower. Do not import the south-Florida 5–7 lb into Tennessee or Virginia because the grass has the same name.`,
        `Compare that with the others. ${link('/grass/zoysiagrass/', 'Zoysiagrass')} on the current EP353 table is 2–3 lb in north Florida and 2.5–4.5 lb in the south, not bermuda's 5–7. ${link('/grass/st-augustinegrass/', 'St. Augustinegrass')} is 2–4, 2–5, and 4–6 across those three regions. ${link('/grass/centipedegrass/', 'Centipedegrass')} is 0.4–2 in the north column. ${link('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} is a cool-season 1–4 lb year, mostly in fall. Bermudagrass is the heavy feeder, and it is fed in the warm months, not in September-and-November the way fescue is.`,
        `EP353 and the Florida urban turf rule also limit a single application: no more than 0.7 lb of readily available (quick-release) nitrogen per 1,000 sq ft at one time. Rutgers describes about 1 lb as the usual cap for soluble nitrogen. This page starts the calculator at 1 lb, which is inside the usual band and above Florida's quick-release cap. If you are in Florida, or the bag is labeled for Florida, use 0.7 lb of quick-release or whatever the label allows, not the 1 lb starting point. An older copy of the Florida rule text says no more than 1 lb total nitrogen at one time; EP353 describes up to 2 lb in spring or summer when at least 65% of the nitrogen is controlled-release. Those two wordings disagree. Follow the bag you bought.`,
      ] },
      { id: 'when', heading: 'After green-up, and stop before cold', paragraphs: [
        `The warm-season window on this site is a light feeding in April, main feedings from May through August, and a light feeding in September, then stop. The idea, from the general warm-season guidance this site cites, is to start only after the lawn has fully greened up and to quit early enough that you are not pushing soft growth into frost. Exact green-up week is local. A late spring in north Georgia is not south Florida.`,
        `${link('/seasons/spring/', 'Spring')} and ${link('/seasons/summer/', 'summer')} are the seasons that matter here. ${link('/seasons/fall/', 'Fall')} is when you stop, which is the reverse of a fescue lawn. ${link('/seasons/winter/', 'Winter')} feeding of dormant bermuda is not on this calendar. Many Florida counties add a rainy-season blackout that the statewide rule, as EP353 explains it, does not itself set. The ${link('/states/florida/', 'Florida page')} says that plainly. Other ${link('/states/', 'state pages')} say whether a statewide date was verified. If it was not, check the county before you assume summer is open.`,
      ] },
      { id: 'example', heading: 'Pounds, not vibes', paragraphs: [
        `At 1 lb of nitrogen per 1,000 sq ft, 5,000 sq ft of bermudagrass needs 5 lb of actual nitrogen. A 29-0-4 product is 1 ÷ 0.29 × 5 = 17.2 lb of fertilizer for that one feeding. A 16-4-8 product is heavier because each pound carries less nitrogen: 1 ÷ 0.16 × 5 = 31.3 lb. Urea, 46-0-0, is 1 ÷ 0.46 × 5 = 10.9 lb. The table uses those four analyses. The calculator on this page is already set to 5,000 sq ft and 1 lb. Change either number and the 17.2 moves.`,
        `A full year at the north-Florida 3–5 lb is 15–25 lb of nitrogen on that same 5,000 sq ft lawn, delivered over several feedings, not as one 17.2 lb dump repeated every month. Five monthly feedings at 1 lb would be 5 lb for the year, the top of the north column and the bottom of the south column. That is why the region matters. The ${link('/lawn-size/', 'lawn-size pages')} multiply the same rates by other areas. Common bermudagrass can be seeded; hybrid bermudagrass cannot. The ${link('/guides/grass-seed/', 'seed calculator')} says "no seed" for the hybrids and 1–2 lb per 1,000 sq ft for common bermuda, in spring to early summer, from NC State AG-69.`,
      ] },
      { id: 'mistakes', heading: 'Mistakes on bermuda', paragraphs: [
        `Feeding before it is green wastes the first application on a brown lawn that is not taking it up. Feeding after it should be hardening for cool weather gives you green growth and then frost damage. Copying a fescue "feed in November" habit onto bermuda is that second mistake.`,
        `The other one is shade. More nitrogen does not compensate for trees. And phosphorus: Florida limits phosphate on lawns covered by the urban turf rule to 0.25 lb of P₂O₅ per 1,000 sq ft per application and 0.50 lb per year unless a soil test shows a need, on the EP353 summary. A 10-10-10 bag is a lot of phosphorus for an established bermuda lawn. Soil-test first. The label and the county rule win.`,
      ] },
    ],
    faqs: [
      { q: 'How much nitrogen does bermudagrass need in a year?',
        a: '3–5 lb per 1,000 sq ft is the north-Florida column this site uses. UF/IFAS EP353 lists 4–6 lb for central Florida and 5–7 lb for south Florida. Outside Florida, use the state extension rate if it differs.' },
      { q: 'When should bermudagrass be fertilized?',
        a: 'After it has fully greened up in spring, through summer, and stop by early fall. This site shows April as light, May through August as the main months, and September as light. Do not use a cool-season fall-and-November schedule.' },
      { q: 'Can I seed bermudagrass?',
        a: 'Common bermudagrass can be seeded, at 1–2 lb per 1,000 sq ft in spring to early summer on NC State\'s guide. Hybrid bermudagrass is sod or sprigs, not seed. The seed calculator separates the two.' },
      { q: 'Why does the calculator start at 1 lb if Florida says 0.7?',
        a: '1 lb is the usual top of a quick-release feeding in the Rutgers guidance this site uses. Florida caps readily available nitrogen at 0.7 lb per 1,000 sq ft per application. In Florida, follow 0.7 lb or the label, whichever is stricter.' },
    ],
  },
  'st-augustinegrass': {
    sections: [
      { id: 'habit', heading: 'Wide blades and stolons', paragraphs: [
        `St. Augustinegrass (<em>Stenotaphrum secundatum</em>) is the grass in the photograph: wide blades and stolons creeping across a lawn. The file's scientific name is <em>Stenotaphrum secundatum</em>. The photographer's caption also says "centipede grass," which is a different plant. This page is only about St. Augustinegrass. ${link('/grass/centipedegrass/', 'Centipedegrass')} has its own rates and its own photograph.`,
        `It is a warm-season grass of the Gulf Coast and Florida. Among common warm-season lawn grasses it is the one extension guides describe as handling more shade. This page still does not quote an hours-of-sun minimum. "More shade than bermuda" is not "deep shade all day." If the lawn is failing under trees, fertilizer will not replace light. It is planted from sod or plugs. The ${link('/guides/grass-seed/', 'seed calculator')} returns no seed, because seed is not how this grass is sold, on NC State's Carolina Lawns guide.`,
      ] },
      { id: 'nitrogen', heading: 'A middle nitrogen budget, higher in south Florida', paragraphs: [
        `This site uses 2–4 lb of nitrogen per 1,000 sq ft a year, the north-Florida column of the current UF/IFAS EP353 table. That table lists 2–5 lb for central Florida and 4–6 lb for south Florida. The short note on the grass ("Florida's guide allows up to 6 lb in South Florida") is that south column. Do not use 4–6 lb in north Florida, and do not use the north column's 2 lb floor as a promise that south Florida lawns are fine at 2 lb. The publication says homeowner expectations and local shade, drought, and soil are why each cell is a range, and it assumes clippings are left on the lawn.`,
        `Set next to bermudagrass, St. Augustine needs less: bermuda is 3–5, 4–6, and 5–7 on the same three columns. Set next to centipede, it needs more: centipede is 0.4–2 in north Florida on the current table. ${link('/grass/zoysiagrass/', 'Zoysiagrass')} overlaps it in the north (2–3 lb) and stays lower in the far south (2.5–4.5 on the current table). An older printing of the Florida nitrogen table listed higher zoysia numbers; that disagreement is on the zoysia page, not a reason to raise St. Augustine.`,
        `The calculator starts at 0.75 lb of nitrogen per 1,000 sq ft, inside the 0.5–1 lb band and just above Florida's 0.7 lb cap on readily available nitrogen. In Florida, drop the rate to 0.7 lb of quick-release or follow the label. EP353 also describes a higher total in spring or summer when most of the nitrogen is controlled-release, while an older text of Rule 5E-1.003 says no more than 1 lb total nitrogen at one time. The sources disagree. The bag in your hand is the instruction.`,
      ] },
      { id: 'when', heading: 'Green-up to early fall, not a fescue autumn', paragraphs: [
        `Feed after the lawn is fully green, through the warm months, and stop by early fall so you are not forcing growth ahead of cold. This site's calendar marks April as light, May through August as main, and September as light. That is a warm-season shape. It is the wrong shape for ${link('/grass/tall-fescue/', 'tall fescue')}, which wants ${link('/seasons/fall/', 'fall')}. For St. Augustine, ${link('/seasons/spring/', 'spring')} and ${link('/seasons/summer/', 'summer')} are the working seasons, and fall is the stopping season.`,
        `Florida counties often add a blackout the state rule does not set as a single statewide calendar. Check the ${link('/states/florida/', 'Florida page')} and then the county. Gulf states that do not have a verified statewide date are marked that way on their ${link('/states/', 'state pages')}: the instruction there is to check the county rather than invent a blackout.`,
      ] },
      { id: 'example', heading: 'A 0.75 lb feeding, spelled out', paragraphs: [
        `On 5,000 sq ft at 0.75 lb of nitrogen per 1,000 sq ft, the lawn needs 3.75 lb of actual nitrogen. A 29-0-4 product supplies that with 0.75 ÷ 0.29 × 5 = 12.9 lb of fertilizer. A 16-4-8 product needs 0.75 ÷ 0.16 × 5 = 23.4 lb. Those are one feeding, not the year. A north-Florida year of 2–4 lb of nitrogen is 10–20 lb of nitrogen on 5,000 sq ft, which is several feedings at 0.75 lb (each 0.75 lb feeding on 5,000 sq ft is 3.75 lb of nitrogen). Four of them are 3 lb for the year, inside the 2–4 band. Six of them are 4.5 lb, over the north column and inside the central column. Count them.`,
        `Phosphate on the EP353 summary is capped at 0.25 lb of P₂O₅ per 1,000 sq ft per application and 0.50 lb per year unless a soil test shows a deficiency. A complete garden fertilizer is an easy way to overshoot that on an established St. Augustine lawn. The ${link('/lawn-size/', 'size pages')} and ${link('/bags/', 'bag pages')} scale other areas and bag weights with the same formula. The ${link('/method/', 'method page')} records the formula.`,
      ] },
      { id: 'problems', heading: 'Problems fertilizer will not fix', paragraphs: [
        `Chinch bugs, take-all root rot, gray leaf spot, large patch, and viral decline are the names extension clinics hear on this grass. This page does not diagnose them and does not give pesticide rates. Extra nitrogen on a diseased or insect-damaged lawn often makes it worse. If the lawn is yellow in patches rather than evenly hungry, get a diagnosis before you add a feeding. Iron chlorosis and a nitrogen shortage can look similar; a soil test or an extension clinic is the way to tell them apart, not another round of 29-0-4.`,
        `The maintenance mistake is using bermuda's yearly total. Six or seven pounds of nitrogen, the top of south-Florida bermuda, is above even south-Florida St. Augustine on the current table (4–6). The planting mistake is looking for seed. There isn't a seed rate because the grass is not grown that way. Buy sod or plugs, and do not "overseed with whatever the store has" and expect St. Augustine.`,
      ] },
    ],
    faqs: [
      { q: 'How much nitrogen does St. Augustinegrass need in a year?',
        a: '2–4 lb per 1,000 sq ft is the north-Florida figure this site uses. UF/IFAS EP353 lists 2–5 lb in central Florida and 4–6 lb in south Florida, assuming clippings stay on the lawn.' },
      { q: 'When do I fertilize St. Augustinegrass?',
        a: 'After spring green-up, through summer, stopping by early fall. This calendar shows May through August as the main months, with April and September light. It is not a September-and-November cool-season plan.' },
      { q: 'Can I plant St. Augustinegrass from seed?',
        a: 'No. NC State lists it as sod or plugs. The seed calculator on this site returns no seed for it.' },
      { q: 'Does it really tolerate shade?',
        a: 'It tolerates more shade than bermudagrass, which is the comparison extension guides make. This page does not claim a number of sun-hours. Deep shade still needs a different plant, not more fertilizer.' },
    ],
  },
  zoysiagrass: {
    sections: [
      { id: 'habit', heading: 'Dense, slow, and easy to overfeed', paragraphs: [
        `Zoysiagrass on this page is <em>Zoysia japonica</em>, the species in the photograph: a dense patch with a tired brown edge. Other species and hybrids (including <em>Zoysia matrella</em>) are also sold as zoysia. They are not identical. Where a source gives one lawn rate for "zoysiagrass," this page uses that rate and says so. Where cultivars differ, the bag and the supplier know more than a single statewide number.`,
        `It is a warm-season grass that spreads by stolons and rhizomes and fills in slowly. That slow habit is the reason it builds thatch and the reason people overfeed it, trying to make it hurry. It needs less nitrogen than bermudagrass. It handles some shade, better than bermuda and generally less than St. Augustine, but this page does not assign an hours rating. Most improved cultivars are sod or plugs. NC State notes that only a few varieties are sold as seed; the ${link('/guides/grass-seed/', 'seed calculator')} uses 1–2 lb per 1,000 sq ft for those, in spring to early summer, and you should not apply that rate to a cultivar that isn't sold as seed.`,
      ] },
      { id: 'nitrogen', heading: 'Less than bermuda, and the Florida tables disagree', paragraphs: [
        `This site's yearly range is 2–3 lb of nitrogen per 1,000 sq ft. That matches the north-Florida cell of the current UF/IFAS EP353 table. The same current table lists 2–4 lb for central Florida and 2.5–4.5 lb for south Florida. The note on this grass ("Florida's guide goes up to 4.5 lb in the far south") is that current south cell.`,
        `An older copy of the nitrogen table, including the one printed with Rule 5E-1.003 in a Florida fertilizer task-force packet and in older EDIS reprints, lists zoysia at 3–5 lb in the north, 3–6 in the center, and 4–6 in the south. Those are bermuda-like numbers, not the current EP353 numbers. The sources disagree. This site follows the current EP353 table and does not silently switch the calculator to the older, higher band. If your county office still hands out the older table, ask which one they want you to use before you pick the top of it.`,
        `Bermudagrass on the current table is 3–5 / 4–6 / 5–7. Zoysia's current 2–3 / 2–4 / 2.5–4.5 is a step down in every column. ${link('/grass/centipedegrass/', 'Centipedegrass')} is lower still. ${link('/grass/st-augustinegrass/', 'St. Augustinegrass')} is similar in north Florida (2–4) and higher in the south (4–6). Feeding zoysia on a bermuda year is the overfeed. The calculator starts at 0.75 lb per 1,000 sq ft so a single feeding stays in the 0.5–1 lb band. Florida's cap on readily available nitrogen is 0.7 lb per application. Use 0.7, or the label, in Florida.`,
      ] },
      { id: 'when', heading: 'Warm months, then leave it alone', paragraphs: [
        `Same warm-season shape as the other summer grasses on this site: a light April, main feedings May through August, a light September, then stop. Start after full green-up. Zoysia greens up later than bermuda in a lot of yards, so "April" on a chart can be early. Wait until it is actually green. Stop early enough that frost does not catch soft growth. ${link('/seasons/summer/', 'Summer')} is the working season. ${link('/seasons/fall/', 'Fall')} is not the main feeding the way it is for ${link('/grass/tall-fescue/', 'tall fescue')}. ${link('/seasons/winter/', 'Winter')} is dormancy, not a feeding window.`,
        `A 2–3 lb year at 0.75 lb per feeding is about two to four applications. Adding a fifth because the lawn looks brown in October is how you leave the band. Brown in October, on a warm-season grass, is often the lawn going dormant, not a nitrogen deficiency.`,
      ] },
      { id: 'example', heading: 'Why the lower rate changes the shopping', paragraphs: [
        `On 5,000 sq ft at 0.75 lb of nitrogen, you need 3.75 lb of nitrogen. Urea (46-0-0) supplies that in 0.75 ÷ 0.46 × 5 = 8.2 lb of product. A 29-0-4 needs 12.9 lb. A 10-10-10 needs 0.75 ÷ 0.10 × 5 = 37.5 lb, and it brings a matching load of phosphate, which an established zoysia lawn often does not need. The table under the calculator lists all four. Prefer the low-phosphorus bag unless a soil test says otherwise. Florida's EP353 summary caps phosphate at 0.25 lb of P₂O₅ per 1,000 sq ft per application and 0.50 lb per year without a soil test.`,
        `Scale the lawn on the ${link('/lawn-size/', 'size pages')} rather than multiplying 12.9 by a guess. A small zoysia lawn is an easy place to buy one ${link('/bags/50-lb/', '50 lb bag')} and then store most of it. The bag-size pages show the leftover on purpose. Thatch is the zoysia-specific storage problem in the lawn itself: dense growth plus extra nitrogen makes a layer that water and fertilizer sit on. If the lawn feels spongy, deal with thatch before you raise the rate. This page does not give a dethatching procedure.`,
      ] },
      { id: 'mistakes', heading: 'Mistakes that are specific to zoysia', paragraphs: [
        `Hurrying it. Zoysia is slow. A second feeding two weeks after the first, because you cannot see the difference yet, stacks nitrogen the grass has not asked for. Space the feedings across the summer and stop.`,
        `Seeding a hybrid that has no seed. The 1–2 lb rate is only for the seeded varieties NC State is talking about. Plugs and sod are the normal plant material. And using the old Florida 4–6 lb south column when the current publication says 2.5–4.5. If you cite a number, cite which table it came from. This site's calculator range stays at 2–3 unless you type a different rate yourself.`,
      ] },
    ],
    faqs: [
      { q: 'How much nitrogen does zoysiagrass need in a year?',
        a: '2–3 lb per 1,000 sq ft is the range on this site, matching current UF/IFAS EP353 for north Florida. That publication lists 2–4 lb in central Florida and 2.5–4.5 lb in south Florida. Older Florida tables list higher zoysia rates. They disagree; this site uses the current table.' },
      { q: 'When should I fertilize zoysia?',
        a: 'After it greens up, through summer, and stop by early fall. May through August are the main months on this calendar. Do not copy a cool-season September-and-November plan onto it.' },
      { q: 'Can I grow zoysia from seed?',
        a: 'Only some varieties. NC State\'s rate for those is 1–2 lb per 1,000 sq ft, spring to early summer. Most zoysia lawns are sod or plugs. Check the cultivar before you buy seed.' },
      { q: 'Does zoysia need as much fertilizer as bermudagrass?',
        a: 'No. On the current Florida table, zoysia is lower in every region: 2–3 versus 3–5 in the north, and 2.5–4.5 versus 5–7 in the south. Feeding it like bermuda is the overfeed.' },
    ],
  },
  centipedegrass: {
    sections: [
      { id: 'habit', heading: 'The lawn you ruin by being helpful', paragraphs: [
        `Centipedegrass (<em>Eremochloa ophiuroides</em>) is the pale-green lawn in the photograph. The file is titled "Centipedegrass" and filed under that scientific name; the description does not repeat the Latin. It is a warm-season grass of the Southeast, spread by stolons, and it is the low-maintenance choice: acid soils, modest fertility, and a habit of declining when people treat it like bermuda.`,
        `The yearly range on this site is 0.4–2 lb of nitrogen per 1,000 sq ft. The calendar is short on purpose: a light feeding in May, a main feeding in June, and a light feeding in July. One or two light applications after green-up, then stop. That is the opposite of a ${link('/grass/bermudagrass/', 'bermudagrass')} summer-long program and the opposite of a ${link('/grass/tall-fescue/', 'tall fescue')} fall program. If you want a grass you feed all summer, pick a different grass. Do not "fix" centipede by adopting bermuda's year.`,
      ] },
      { id: 'nitrogen', heading: 'The smallest nitrogen budget, and a table that moved', paragraphs: [
        `The current UF/IFAS EP353 table lists centipede at 0.4–2 lb in north Florida and 0.4–3 lb in central and south Florida, with clippings recycled. This site uses the 0.4–2 band. An older interim Florida table, still circulating in reprints, listed 1–2 lb in the north and 2–3 lb in the center and south. The floor moved. The current table allows a very small annual total, down at 0.4 lb, which is less than one full 0.5 lb feeding per 1,000 sq ft. A lawn that looks fine may not need the top of the range.`,
        `Put the six grasses in a line and centipede is at the bottom. Bluegrass and tall fescue are 1–4 lb, mostly in fall. St. Augustine is 2–4 lb in north Florida and up to 4–6 in the south. Zoysia is 2–3 lb on this site, up to 2.5–4.5 in south Florida on the current table. Bermuda is 3–5 and up to 5–7. Centipede at 2 lb is the top of its north-Florida cell and the bottom of bermuda's. Crossing that line is the classic way to get centipede decline: too much nitrogen, often with too much phosphorus, on a grass that yellows and thins when it is overfed.`,
        `The calculator starts at 0.5 lb of nitrogen per 1,000 sq ft, the bottom of the usual per-feeding band and a sane single dose for this grass. At that rate the year's 0.4–2 lb is about one feeding, maybe two, not five. Florida's 0.7 lb cap on readily available nitrogen is above this starting rate, so 0.5 lb of quick-release sits under both the Rutgers 1 lb guidance and the Florida cap. You do not need to push it up to 0.7 just because 0.7 is legal.`,
      ] },
      { id: 'when', heading: 'Late spring into early summer, then done', paragraphs: [
        `Green-up first. Then one feeding, or a light one followed by the main June feeding, and a possible light follow-up in July. After that the calendar is empty: no August main feeding, no September, no November. ${link('/seasons/spring/', 'Spring')} and early ${link('/seasons/summer/', 'summer')} are the whole program. ${link('/seasons/fall/', 'Fall')} fertilizer, the kind of bag marketed as a winterizer, is for cool-season grass. On centipede it is off the calendar. ${link('/seasons/winter/', 'Winter')} is dormancy. The grass turns brown or red-brown. That color is not a fertilizer bill.`,
        `Counties can be stricter than a state, except where state law actually preempts local fertilizer rules. The ${link('/states/', 'state pages')} separate those cases. Alabama, Georgia, and Louisiana are not "counties can always be stricter." Florida often is, through local ordinances. Read the state you live in. If this page and the county fact sheet disagree, the county fact sheet wins.`,
      ] },
      { id: 'example', heading: 'How small the pile is', paragraphs: [
        `On 5,000 sq ft at 0.5 lb of nitrogen per 1,000 sq ft, the lawn needs 2.5 lb of nitrogen. A 29-0-4 product is 0.5 ÷ 0.29 × 5 = 8.6 lb of fertilizer. Urea is 0.5 ÷ 0.46 × 5 = 5.4 lb. A 15 lb bag of 29-0-4 already holds more than that one feeding; you will not finish the bag. The ${link('/bags/15-lb/', '15 lb bag page')} is the one to read before you buy a 50 lb sack "to have on hand." A year at the top of the range, 2 lb of nitrogen per 1,000 sq ft, is 10 lb of nitrogen on 5,000 sq ft, about four feedings at 0.5 lb, which is more than this calendar recommends. The top of the range is not the goal.`,
        `Phosphorus is the other half of the decline story. Centipede is often cited by extension as needing little or none on established lawns, and a soil test is how you know. This page does not invent a phosphorus number the EP353 phosphate cap doesn't already state for Florida lawns generally: 0.25 lb of P₂O₅ per 1,000 sq ft per application and 0.50 lb per year unless a soil test shows a need. A 10-10-10 bag on centipede is a poor default. Iron deficiency on high-pH soil can look like hunger. Lime, which people add because other grasses want it, can make centipede worse if the soil is already near neutral. Do not lime because a neighbor limed a fescue lawn. Test.`,
      ] },
      { id: 'seed', heading: 'Seed is possible, and it is a tiny amount', paragraphs: [
        `NC State AG-69 lists 0.25–0.5 lb of seed per 1,000 sq ft for a new centipede lawn, spring to early summer. The seed is very small. A pound covers a lot of ground. The ${link('/guides/grass-seed/', 'seed calculator')} uses that rate. Do not sow it at the tall-fescue rate of 6 lb. You would be planting an expensive mat and most of it would be wasted. Overseeding uses less still.`,
        `Established centipede does not need a yearly "overseeding like fescue" habit. If the stand is dying back, find out whether it was overfertilized, buried in thatch, or sitting on soil that was limed too far, before you buy more seed and more nitrogen. The ${link('/method/', 'method page')} lists what the fertilizer calculator refuses to pretend it knows: soil tests, spreader dials, and your city's rule.`,
      ] },
    ],
    faqs: [
      { q: 'How much nitrogen does centipedegrass need in a year?',
        a: '0.4–2 lb per 1,000 sq ft is the range on this site. Current UF/IFAS EP353 lists 0.4–2 lb in north Florida and 0.4–3 lb in central and south Florida. Older Florida tables started higher, at 1–2 lb in the north. One light feeding is often enough.' },
      { q: 'When should I fertilize centipedegrass?',
        a: 'After green-up, once or twice, in late spring to early summer. This calendar shows May as light, June as the main feeding, and July as light. It does not show fall or winter feedings.' },
      { q: 'Why does centipede decline when I fertilize it more?',
        a: 'The yearly budget is small. Pushing it toward bermuda rates, or adding phosphorus and lime it does not need, is a standard way to thin it. Stay at or under 2 lb of nitrogen per 1,000 sq ft for the year unless your state guide says otherwise, and soil-test before you add phosphorus or lime.' },
      { q: 'Can centipedegrass be seeded?',
        a: 'Yes. NC State lists 0.25–0.5 lb of seed per 1,000 sq ft for a new lawn, in spring to early summer. That is a small bag, not a fescue-sized one.' },
    ],
  },
};

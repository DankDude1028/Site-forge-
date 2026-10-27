/** Seasonal guides. Months follow the grass pages. Regions differ; the state pages say where a law was verified. */

export interface SeasonSection { id: string; heading: string; paragraphs: string[] }
export interface SeasonGuide {
  slug: string;
  name: string;
  title: string;
  kicker: string;
  lede: string;
  sections: readonly SeasonSection[];
  faqs: readonly { q: string; a: string }[];
}

const a = (href: string, text: string) => `<a href="${href}">${text}</a>`;

export const SEASONS: readonly SeasonGuide[] = [
  {
    slug: 'spring', name: 'Spring', title: 'Spring lawn fertilizer',
    kicker: 'Warm-season green-up',
    lede: 'Spring is the start for bermudagrass, St. Augustine, zoysia, and centipede, and only a light optional feeding for tall fescue and Kentucky bluegrass.',
    sections: [
      { id: 'who', heading: 'Who spring is actually for', paragraphs: [
        `Spring fertilizer is a warm-season event. ${a('/grass/bermudagrass/', 'Bermudagrass')}, ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')}, ${a('/grass/zoysiagrass/', 'zoysiagrass')}, and ${a('/grass/centipedegrass/', 'centipedegrass')} are fed after they have fully greened up, not on the first warm Saturday. A brown lawn is not taking nitrogen up yet. This site marks April as a light month for bermuda, St. Augustine, and zoysia, and May as light for centipede, with the main centipede feeding in June. Those are typical windows. A late spring moves them.`,
        `${a('/grass/tall-fescue/', 'Tall fescue')} and ${a('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} can take a light feeding in late April on the Nebraska schedule this site uses. It is not the feeding that makes their year. That one is ${a('/seasons/fall/', 'fall')}. A heavy spring dose, meant to “get ahead of summer,” spends nitrogen the cool-season lawn will wish it had in September.`,
      ] },
      { id: 'howmuch', heading: 'How much, once it is green', paragraphs: [
        `One feeding stays around 0.5–1 lb of quick-release nitrogen per 1,000 sq ft. Rutgers describes about 1 lb as the soluble-nitrogen limit. Florida’s urban turf rule, via UF/IFAS EP353, caps readily available nitrogen at 0.7 lb per 1,000 sq ft per application. Centipede starts at 0.5 lb on its page because its whole year may only be 0.4–2 lb. Bermuda’s page starts at 1 lb, which is too high for a Florida quick-release application. The label and the ${a('/states/florida/', 'Florida page')} win there.`,
        `Do not put the year’s total down in April. Bermuda’s north-Florida year is 3–5 lb, delivered across summer. Four or five feedings, not one. The calculator on each grass page is set to a single feeding. Change the rate before you spread.`,
      ] },
      { id: 'region', heading: 'The same month is not the same lawn', paragraphs: [
        `Green-up in south Florida is not green-up in Kentucky. ${a('/states/kentucky/', 'Kentucky')} and ${a('/states/tennessee/', 'Tennessee')} are mostly cool-season in spring: light or nothing, then wait for fall. ${a('/states/florida/', 'Florida')}, ${a('/states/louisiana/', 'Louisiana')}, and the Gulf Coast are waiting on warm-season grass to wake up, and Florida counties may block part of the warm season entirely. ${a('/states/georgia/', 'Georgia')} and ${a('/states/north-carolina/', 'North Carolina')} have both calendars in one state. Read the state page, then the grass page. If neither verified a legal date, check the county. This page does not invent one.`,
      ] },
    ],
    faqs: [
      { q: 'Should I fertilize tall fescue in spring?', a: 'Only lightly, if at all. Late April is a light month on this site. September and November do the real work. Skip a heavy spring feeding.' },
      { q: 'When does bermudagrass get its first feeding?', a: 'After it has fully greened up. April is marked light on this site and May through August are the main months. A still-brown lawn can wait.' },
      { q: 'Is spring a good time to seed?', a: 'Warm-season seed (common bermuda, zoysia varieties that have seed, centipede) is a spring to early-summer planting on NC State’s guide. Tall fescue and Kentucky bluegrass are late summer to early fall, not spring.' },
    ],
  },
  {
    slug: 'summer', name: 'Summer', title: 'Summer lawn fertilizer',
    kicker: 'The warm-season season',
    lede: 'Summer is when bermudagrass, St. Augustine, and zoysia do their growing. It is when tall fescue and Kentucky bluegrass should be left alone, and when centipede is nearly done.',
    sections: [
      { id: 'warm', heading: 'The grasses that are working', paragraphs: [
        `${a('/grass/bermudagrass/', 'Bermudagrass')} carries main feedings from May through August on this site, inside a yearly 3–5 lb of nitrogen per 1,000 sq ft in the north-Florida column and up to 5–7 lb only in south Florida on the current UF table. ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')} uses the same months at a lower year: 2–4 lb in north Florida, up to 4–6 in the south. ${a('/grass/zoysiagrass/', 'Zoysiagrass')} uses the months and a still lower year, 2–3 lb on this site. Spacing those feedings across summer is the job. Stacking them two weeks apart is how you overshoot.`,
        `${a('/grass/centipedegrass/', 'Centipedegrass')} is the exception inside the warm-season group. Its main month is June, with July only light, and then it stops. An August feeding because the lawn looks pale is the usual way to overfeed it. Its year is 0.4–2 lb, not bermuda’s summer budget.`,
      ] },
      { id: 'cool', heading: 'The grasses that are enduring', paragraphs: [
        `${a('/grass/tall-fescue/', 'Tall fescue')} and ${a('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} are not summer grasses. Nebraska’s guidance, which this site follows for the cool-season band, says to skip feeding in summer heat. A light early-June feeding exists on the calendar for northern schedules. July and August do not. A brown fescue lawn in August is heat. More quick-release nitrogen is the wrong remedy. The restart is ${a('/seasons/fall/', 'September')}.`,
        `One quick-release feeding still tops out around 1 lb per 1,000 sq ft (Rutgers) and at 0.7 lb of readily available nitrogen in Florida (EP353). Summer thunderstorms and irrigation move whatever the lawn does not take up. Sweep granules off pavement. The label’s “do not apply before heavy rain” line is there for this season.`,
      ] },
      { id: 'blackout', heading: 'Where summer feeding may be illegal', paragraphs: [
        `Florida’s statewide urban turf rule limits rates and phosphorus. It does not, in the EP353 summary, set one statewide June-to-September blackout. Many Florida counties do. The ${a('/states/florida/', 'Florida page')} says to look the county up. ${a('/states/alabama/', 'Alabama')}, ${a('/states/georgia/', 'Georgia')}, and ${a('/states/louisiana/', 'Louisiana')} generally preempt local fertilizer ordinances, with narrow exceptions, so a city flyer is not automatically the law. ${a('/states/arkansas/', 'Arkansas')} restricts nutrient applications in mapped nutrient-surplus areas, including a ban on applying to saturated or frozen soil, which is a condition, not a summer calendar. Other state pages say “not verified” where no statute was found. Unverified means check the county, not “summer is always fine.”`,
      ] },
    ],
    faqs: [
      { q: 'Can I fertilize fescue in July?', a: 'No. This site leaves summer heat off the tall fescue and Kentucky bluegrass calendars. Wait for September.' },
      { q: 'How many summer feedings does bermuda get?', a: 'May, June, July, and August are marked main, with April and September light. At about 1 lb of quick-release nitrogen each, count them against the yearly total for your region so you do not pass 5 lb where the guide says 3–5, or 7 lb only where south Florida actually applies.' },
      { q: 'Should centipede be fed all summer?', a: 'No. One or two light feedings after green-up, centered on June. August is not on its calendar.' },
    ],
  },
  {
    slug: 'fall', name: 'Fall', title: 'Fall lawn fertilizer',
    kicker: 'The cool-season season',
    lede: 'Fall is the main feeding season for tall fescue and Kentucky bluegrass. For bermudagrass, St. Augustine, zoysia, and centipede, fall is when you stop.',
    sections: [
      { id: 'cool', heading: 'September and November', paragraphs: [
        `NC State Extension’s calendar for ${a('/grass/tall-fescue/', 'tall fescue')}, fine fescue, and ${a('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} puts the important feedings in September and November, while the grass is still green. This site marks both as main months. A light February feeding is the transition-zone addition, not a third fall feeding. Nebraska’s cool-season bands are 1–2, 2–3, or 3–4 lb of nitrogen per 1,000 sq ft for the whole year depending on how much lawn you want to maintain. Two fall feedings at about 1 lb each already cover a low-care to typical year. Spring light feedings are optional on top of that, not a substitute for September.`,
        `This is the page to start from if the lawn is fescue or bluegrass. ${a('/seasons/spring/', 'Spring')} is secondary. ${a('/seasons/summer/', 'Summer')} is a skip. ${a('/seasons/winter/', 'Winter')} does not add a separate “winterizer” rate on top of November. The November application, while the grass is green, is the late one. If the lawn has already gone dormant and brown, you missed the window. Do not fertilize a frozen, brown cool-season lawn in December because the bag says winterizer.`,
      ] },
      { id: 'warm', heading: 'Warm-season lawns are finishing, not starting', paragraphs: [
        `${a('/grass/bermudagrass/', 'Bermudagrass')}, ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')}, and ${a('/grass/zoysiagrass/', 'zoysiagrass')} show September as a light month and then nothing. The point is to stop early enough that frost does not catch soft new growth. ${a('/grass/centipedegrass/', 'Centipedegrass')} is already finished; its calendar does not include September. A fall feeding sold for “all lawns” is a cool-season product being aimed at the wrong grass.`,
        `People with both a fescue backyard and a bermuda front yard, common in ${a('/states/tennessee/', 'Tennessee')}, ${a('/states/north-carolina/', 'North Carolina')}, and ${a('/states/georgia/', 'Georgia')}, have to run two calendars. September is right for one and nearly over for the other. The grass pages are the split. The state pages say whether any of this is a legal date or only extension practice. For most of these states, the months are practice. ${a('/states/virginia/', 'Virginia')} adds a real phosphorus rule: routine maintenance fertilizer may not contain phosphorus, in fall or any other month.`,
      ] },
      { id: 'shop', heading: 'Buying for a fall feeding', paragraphs: [
        `At 1 lb of nitrogen per 1,000 sq ft, the pounds of product are 100 ÷ the first bag number, then scaled to the lawn. A 5,000 sq ft fescue lawn and a 29-0-4 bag is 17.2 lb for one feeding, which is one ${a('/bags/25-lb/', '25 lb bag')} with some left, or two ${a('/bags/15-lb/', '15 lb bags')} with more left. The ${a('/lawn-size/5000-sq-ft/', '5,000 sq ft page')} and the ${a('/lawn-size/', 'size guide')} do the other areas. Use a low- or no-phosphorus analysis on an established lawn unless a soil test says otherwise. Seed, if you are planting fescue, is a different pile: 6 lb of seed per 1,000 sq ft on NC State’s guide, in this same late-summer to early-fall window. The ${a('/guides/grass-seed/', 'seed calculator')} keeps that number off the fertilizer total.`,
      ] },
    ],
    faqs: [
      { q: 'Is fall the most important time to fertilize?', a: 'For tall fescue and Kentucky bluegrass, yes. September and November are the main months. For bermudagrass, St. Augustine, zoysia, and centipede, no. Those grasses are fed in the warm months and should be stopping by early fall.' },
      { q: 'What is a winterizer?', a: 'A marketing name for a late-fall feeding. On this site the late feeding is the November application while cool-season grass is still green. There is no extra rate stacked on top, and it is not for dormant bermudagrass.' },
      { q: 'Can I fertilize centipede in the fall?', a: 'Not on this calendar. Centipede is fed once or twice after green-up, in late spring to early summer, and then left alone.' },
    ],
  },
  {
    slug: 'winter', name: 'Winter', title: 'Winter lawn fertilizer',
    kicker: 'Mostly do not',
    lede: 'Winter is not a feeding season for warm-season grass, and it is not a second chance after November for cool-season grass. February is only a light transition-zone date.',
    sections: [
      { id: 'dormant', heading: 'Dormant grass is not hungry', paragraphs: [
        `${a('/grass/bermudagrass/', 'Bermudagrass')}, ${a('/grass/zoysiagrass/', 'zoysiagrass')}, ${a('/grass/st-augustinegrass/', 'St. Augustinegrass')}, and ${a('/grass/centipedegrass/', 'centipedegrass')} go dormant when it is cold. The lawn turns tan or brown. That color is the season, not a nitrogen deficiency. None of their calendars on this site include December or January. A winter application sits on a lawn that is not growing and is one rain away from the storm drain. ${a('/seasons/spring/', 'Spring')}, after full green-up, is the restart.`,
        `${a('/states/florida/', 'South Florida')} is the exception people mean when they say the grass never really stops. Even there, EP353’s yearly totals still cap the year, and county blackouts may cover part of it. “It stays green” is not a reason to feed every month. The regional column (up to 5–7 lb for bermuda, 4–6 for St. Augustine) is the year, not a monthly rate.`,
      ] },
      { id: 'february', heading: 'The February exception is small', paragraphs: [
        `NC State’s cool-season calendar adds February for ${a('/grass/tall-fescue/', 'tall fescue')} and ${a('/grass/kentucky-bluegrass/', 'Kentucky bluegrass')} in the transition zone. This site marks it light, not main. It is not a feeding for a lawn under snow, and it is not an excuse to fertilize in December because you missed November. The main cool-season dates remain ${a('/seasons/fall/', 'September and November')}, while the grass is green. If November already went down at about 1 lb of nitrogen per 1,000 sq ft, February is optional and light, and it still counts toward the year’s 1–4 lb (or toward NC State’s roughly 3 lb fescue year).`,
        `${a('/states/arkansas/', 'Arkansas')} nutrient-surplus areas, where those rules apply, forbid nutrient application when the soil is saturated, frozen, or covered with ice or snow. That is the one winter rule verified on this site, and it is regional. Other states: no statewide winter blackout was verified, which does not mean frozen-ground applications are a good idea. The extension practice is still “don’t.”`,
      ] },
      { id: 'instead', heading: 'What to do instead of spreading', paragraphs: [
        `Winter is for the soil test you did not run in summer, for reading the bag you already own, and for measuring the lawn so spring’s first feeding is not a guess. The ${a('/guides/measure-your-lawn/', 'measuring tool')}, the ${a('/guides/fertilizer-numbers/', 'bag reader')}, and the ${a('/lawn-size/', 'size pages')} do not care what month it is. Mower blades and spreader cleanup are not fertilizer math, but they beat a wasted bag.`,
        `If you are in ${a('/states/virginia/', 'Virginia')}, winter is also a fine time to notice that a maintenance bag with a middle number above zero should not have been on the shelf. The phosphorus rule is not seasonal. ${a('/states/kentucky/', 'Kentucky')} and ${a('/states/tennessee/', 'Tennessee')} fescue lawns wait for the next September if they missed this one. They do not get a January makeup.`,
      ] },
    ],
    faqs: [
      { q: 'Should I fertilize a brown bermudagrass lawn in January?', a: 'No. It is dormant. Wait until it greens up in spring. Winter color is not a hunger signal.' },
      { q: 'What is the February feeding?', a: 'A light transition-zone feeding on NC State’s calendar for tall fescue and Kentucky bluegrass. It is not a main feeding, and it is not for warm-season grasses or for lawns under snow.' },
      { q: 'Is a winterizer the same as fertilizing in winter?', a: 'On this site, no. The late cool-season feeding is November, while the grass is still green. December and January are not on the calendar.' },
    ],
  },
];

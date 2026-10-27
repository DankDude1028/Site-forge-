# Lawn fertilizer calculator (Lawn Numbers, lawnnumbers.com)

SiteForge's first real launch candidate, chosen on 2026-10-26. A browser-local calculator turns the lawn area, the
three numbers on the bag, the bag weight and a nitrogen rate into:
- pounds of product to spread;
- whole bags to buy;
- the spreader target per 1,000 sq ft.

A feeding calendar shows typical yearly nitrogen and feeding months for six grasses. Every formula and range comes
from the university extension guides listed on `/method/`. Calculator inputs stay in the browser. The site does not
run analytics or show ads today; `/privacy/` says what has to be disclosed before either is added. The contact
address is `hello@lawnnumbers.com` (see `contact.mjs`). That mailbox has to exist before the site is published with it.

The design is interactive by intent. As the inputs change:
- the lawn drawing grows tile by tile;
- its color follows the feeding rate (pale, lush, then scorched);
- bags drop in and the gauge swings;
- the bag label and the worked math update live.

Motion switches off for visitors who ask for reduced motion.

Pages: the calculator (`/`); guides for six grasses, seven exact lawn sizes, four size bands, and four bag weights;
season and state hubs; about, contact, and photo credits; method and sources (`/method/`); privacy (`/privacy/`) and
terms (`/terms/`). Preview builds are noindex. A production build needs `SITEFORGE_SITE_URL`, `SITEFORGE_HOST_NAME`,
`SITEFORGE_HOST_PRIVACY_URL` and `SITEFORGE_CONTACT_EMAIL`, and fails without them. The contact email must match
`contact.mjs`. Publishing remains a separately approved action.

Use Node 22.23.4 or newer, then run:
- `npm ci`
- `npm run typecheck`
- `npm test`
- `npm run build`
- `npm run e2e`
- `npm audit`

The unit tests check every formula against the extension guides' own worked examples and edge cases. The build test
checks each page's SEO contract in both build modes. The browser tests cover live updates, field errors, no outside
requests, axe accessibility on every page, phone width and reduced motion.

Still open before launch of this revision:
- create the `hello@lawnnumbers.com` mailbox (domain forwarding is enough) before merge;
- owner approval before any push to `live/lawnnumbers`;
- state rules the pages mark as unverified still need a county check;
- analytics or ads, if added later, need the privacy page updated first.

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { getSiteConfig } from '../site-config.mjs';

const config = getSiteConfig();

/** Wait for time-based entry animations, so checks see the settled page a reader sees. */
const settle = (page) => page.evaluate(() => Promise.all(document.getAnimations()
  .filter((animation) => animation.timeline === document.timeline
    && animation.effect?.getComputedTiming().iterations !== Infinity)
  .map((animation) => animation.finished)));

test('calculator updates live, flags the exact invalid field, and sends no inputs', async ({ page }, testInfo) => {
  const outside = [];
  page.on('request', (request) => { if (new URL(request.url()).hostname !== '127.0.0.1') outside.push(request.url()); });
  await page.goto('/');
  await expect(page).toHaveTitle(/Lawn Fertilizer Calculator/);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', config.robots);
  await expect(page.locator('#total')).toHaveText('25.9');
  await expect(page.locator('#bags-count')).toHaveText('2 bags');
  await expect(page.locator('#tiles .tile')).toHaveCount(10);
  await settle(page);
  await page.screenshot({ path: testInfo.outputPath('planner.png'), fullPage: true });

  // 5,000 sq ft of a 20-0-5 product at 1 lb of nitrogen: 25 lb, two 15 lb bags (the extension example).
  await page.getByLabel('Lawn size', { exact: true }).fill('5,000');
  await page.getByLabel('Nitrogen %').fill('20');
  await page.getByLabel('Potash %').fill('5');
  await page.getByRole('button', { name: /Full/ }).click();
  await expect(page.locator('#total')).toHaveText('25.0');
  await expect(page.locator('#per1000')).toHaveText('5.00');
  await expect(page.locator('#bags-count')).toHaveText('2 bags');
  await expect(page.locator('#leftover')).toHaveText('5.0 lb');
  await expect(page.locator('#m-per')).toHaveText('5.00');
  await expect(page.locator('#sack-n')).toHaveText('20');
  await expect(page.locator('#tiles .tile')).toHaveCount(5);
  await expect(page.locator('#announce')).toHaveText(/Spread 25.0 pounds/);

  // Length × width fills in the area.
  await page.getByText('Measure it: length × width').click();
  await page.getByLabel('Length').fill('40');
  await page.getByLabel('Width').fill('25');
  await page.getByRole('button', { name: 'Use area' }).click();
  await expect(page.getByLabel('Lawn size', { exact: true })).toHaveValue('1,000');
  await expect(page.locator('#total')).toHaveText('5.0');

  // A heavy rate warns; phosphorus shows the state-rules note.
  await page.getByLabel('Nitrogen this feeding, lb per 1,000 sq ft').fill('1.5');
  await expect(page.locator('#band')).toHaveAttribute('data-band', 'heavy');
  await expect(page.locator('#tiles')).toHaveAttribute('data-band', 'heavy');
  await page.getByLabel('Phosphate %').fill('10');
  await expect(page.locator('#p-note')).toBeVisible();

  // Invalid input names its own field and hides the purchase line.
  await page.getByLabel('Bag weight').fill('');
  await expect(page.locator('#bag')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.locator('#bag-error')).toHaveText(/bag weight in pounds/);
  await expect(page.locator('#buy')).toBeHidden();
  await expect(page.locator('#invalid-note')).toBeVisible();
  await page.getByLabel('Bag weight').fill('12.5');
  await expect(page.locator('#buy')).toBeVisible();
  await page.getByLabel('Nitrogen %').fill('80');
  await expect(page.locator('#npk-error')).toHaveText(/1 to 46/);

  // The feeding calendar follows the grass picker.
  await page.getByRole('radio', { name: 'Bermudagrass' }).check();
  await expect(page.locator('#annual')).toHaveText('3–5');
  await expect(page.locator('#season')).toHaveText('Warm-season grass');
  await expect(page.locator('.ring .seg[data-month="5"]')).toHaveAttribute('data-feed', 'main');
  await expect(page.locator('#next')).toBeVisible();

  expect(outside).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('every page passes automated accessibility and its configured crawl controls', async ({ page, request }) => {
  test.setTimeout(150_000); // axe on every page in the sitemap
  // The sitemap is the list of pages, so a page missing from it fails here too.
  const sitemap = await (await request.get('/sitemap.xml')).text();
  const paths = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => new URL(match[1]).pathname);
  expect(paths.length).toBe(22);
  for (const path of paths) {
    await page.goto(path);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', config.robots);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', config.origin + path);
    await settle(page);
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(result.violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  const robots = await request.get('/robots.txt');
  expect(await robots.text()).toContain(config.mode === 'production' ? 'Allow: /' : 'Disallow: /');
  expect(sitemap).toContain(`<loc>${config.origin}/method/</loc>`);
});

test('reduced motion still shows a complete, correct page', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto('/');
  await page.getByLabel('Lawn size', { exact: true }).fill('2,000');
  await expect(page.locator('#total')).toHaveText('5.2');
  expect(await page.evaluate(() => document.getAnimations().filter((animation) => animation.playState === 'running').length)).toBe(0);
  await context.close();
});

test('grass pages start the calculator and the calendar on their own grass', async ({ page }) => {
  await page.goto('/grass/bermudagrass/');
  await expect(page.locator('h1')).toHaveText('How to fertilize bermudagrass');
  await expect(page.locator('#rate-value')).toHaveText('1.00');
  await expect(page.locator('#total')).toHaveText('17.2'); // 5,000 sq ft, 29% N, 1 lb N: 1 / 0.29 × 5
  await expect(page.locator('#annual')).toHaveText('3–5');
  await expect(page.locator('.grass-picker')).toBeHidden();
  await expect(page.locator('#next')).toContainText('bermudagrass');
  await page.goto('/grass/kentucky-bluegrass/');
  await expect(page.locator('#next')).toContainText('Kentucky bluegrass');
});

test('the lawn measuring tool adds, cuts out and hands the area to the calculator', async ({ page }) => {
  await page.goto('/guides/measure-your-lawn/');
  await expect(page.locator('#area-total')).toHaveText('7,487'); // 9,600 − 2,000 − 113.1
  await page.getByRole('button', { name: '+ Rectangle' }).click();
  const added = page.locator('.shape-row').nth(3);
  await added.getByLabel('Length').fill('10');
  await added.getByLabel('Width').fill('10');
  await expect(page.locator('#area-total')).toHaveText('7,587');
  await page.locator('.shape-row').nth(2).getByLabel('Cut out').uncheck();
  await expect(page.locator('#area-total')).toHaveText('7,813'); // the 113 sq ft bed now counts as lawn
  await page.getByRole('button', { name: 'Remove House' }).click();
  await expect(page.locator('.shape-row')).toHaveCount(3);
  await expect(page.locator('#area-total')).toHaveText('9,813');
  await page.getByRole('link', { name: /in the calculator/ }).click();
  await expect(page).toHaveURL(/\/#area=9813$/);
  await expect(page.getByLabel('Lawn size', { exact: true })).toHaveValue('9,813');
});

test('the bag reader shows what is inside and hands the bag to the calculator', async ({ page }) => {
  await page.goto('/guides/fertilizer-numbers/');
  await expect(page.locator('#o-n')).toHaveText('14.5');
  await expect(page.locator('#o-cover')).toHaveText('14,500');
  await page.getByLabel('Bag weight').fill('10');
  await page.getByLabel('Nitrogen %').fill('20');
  await expect(page.locator('#o-n')).toHaveText('2.0');
  await expect(page.locator('#o-per')).toHaveText('5.00');
  await page.getByRole('button', { name: /Light/ }).click();
  await expect(page.locator('#o-cover')).toHaveText('4,000');
  await page.getByLabel('Nitrogen %').fill('70');
  await expect(page.locator('#b-error')).toHaveText(/from 1 to 46/);
  await page.getByLabel('Nitrogen %').fill('46');
  await page.getByLabel('Phosphate %').fill('40');
  await page.getByLabel('Potash %').fill('20');
  await expect(page.locator('#b-error')).toHaveText(/cannot pass 100/);
  await page.getByLabel('Phosphate %').fill('0');
  await page.getByLabel('Potash %').fill('4');
  await page.getByLabel('Nitrogen %').fill('20');
  await page.getByRole('link', { name: /Use this bag/ }).click();
  await expect(page.getByLabel('Nitrogen %')).toHaveValue('20');
  await expect(page.getByLabel('Bag weight')).toHaveValue('10');
});

test('the spreader checker judges a pass against the target', async ({ page }) => {
  await page.goto('/guides/spreader-calibration/');
  await expect(page.locator('#c-verdict')).toHaveText(/On target/);
  await page.getByLabel('Left after').fill('13');
  await expect(page.locator('#c-actual')).toHaveText('7.0');
  await expect(page.locator('#c-verdict')).toHaveText('40% too heavy. Close the setting a step and test again.');
  await page.getByRole('radio', { name: /swept up/ }).check();
  await page.getByRole('button', { name: '100', exact: true }).click();
  await expect(page.locator('#c-after-label')).toHaveText('Swept up');
  await page.locator('#c-after').fill('0.4');
  await expect(page.locator('#c-verdict')).toHaveText('20% too light. Open the setting a step and test again.');
});

test('lawn size pages show the worked amounts and start the calculator at their size', async ({ page }) => {
  await page.goto('/lawn-size/5000-sq-ft/');
  await expect(page.locator('h1')).toHaveText('How much fertilizer for 5,000 sq ft?');
  await expect(page.locator('.glance-card').first()).toContainText('17.2 lb'); // 1 ÷ 0.29 × 5
  await expect(page.getByLabel('Lawn size', { exact: true })).toHaveValue('5,000');
  await expect(page.locator('#total')).toHaveText('12.9'); // 0.75 ÷ 0.29 × 5
  await page.goto('/lawn-size/one-acre/');
  await expect(page.locator('.glance-card').last()).toContainText('94.7 lb'); // urea: 1 ÷ 0.46 × 43.56
  await expect(page.locator('.size-chip.is-current')).toHaveText('one acre');
});

test('the grass seed calculator follows the NC State rates', async ({ page }) => {
  await page.goto('/guides/grass-seed/');
  await expect(page.locator('#s-total')).toHaveText('30'); // tall fescue, 6 lb per 1,000 sq ft, 5,000 sq ft
  await page.getByRole('radio', { name: 'Overseed an existing lawn' }).check();
  await expect(page.locator('#s-total')).toHaveText('15–22.5');
  await page.getByRole('radio', { name: 'New lawn or bare soil' }).check();
  await page.getByRole('radio', { name: 'Centipedegrass' }).check();
  await expect(page.locator('#s-total')).toHaveText('1.25–2.5');
  await expect(page.locator('#s-season')).toContainText('spring to early summer');
  await page.getByRole('radio', { name: 'St. Augustinegrass' }).check();
  await expect(page.locator('#s-total')).toHaveText('No seed');
  await expect(page.locator('#s-detail')).toContainText('sod or plugs');
  await page.getByLabel('Lawn size', { exact: true }).fill('');
  await expect(page.locator('#s-error')).toContainText('lawn size');
});

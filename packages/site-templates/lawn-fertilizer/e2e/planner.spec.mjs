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
  for (const path of ['/', '/method/', '/privacy/', '/terms/']) {
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
  const sitemap = await request.get('/sitemap.xml');
  expect(sitemap.ok()).toBe(true);
  expect(await sitemap.text()).toContain(`<loc>${config.origin}/method/</loc>`);
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

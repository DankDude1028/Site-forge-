import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('calculator updates useful quantities, rejects invalid input, and sends no inputs', async ({ page }, testInfo) => {
  const outside = [];
  page.on('request', request => { if (new URL(request.url()).hostname !== '127.0.0.1') outside.push(request.url()); });
  await page.goto('/');
  await expect(page).toHaveTitle(/Label Roll Planner/);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow');
  await expect(page.locator('#order')).toHaveText('1');
  await page.screenshot({ path: testInfo.outputPath('planner.png'), fullPage: true });
  await page.getByLabel('Items in this batch').fill('1000');
  await expect(page.locator('#result')).toBeHidden();
  await page.getByRole('button', { name: /Calculate my rolls/ }).click();
  await expect(page.locator('#order')).toHaveText('4');
  await expect(page.locator('#needed')).toHaveText('2,100');
  await page.getByLabel('Items in this batch').fill('');
  await page.getByRole('button', { name: /Calculate my rolls/ }).click();
  expect(await page.locator('#planner').evaluate(form => form.checkValidity())).toBe(false);
  await expect(page.locator('#result')).toBeHidden();
  await page.getByLabel('Items in this batch').fill('100');
  await page.getByLabel('Labels per item').fill('1');
  await page.getByLabel('Extra allowance (%)').fill('0');
  await page.getByRole('button', { name: /Calculate my rolls/ }).click();
  await expect(page.locator('#order')).toHaveText('0');
  expect(outside).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('both pages pass automated accessibility and preview crawl controls', async ({ page, request }) => {
  for (const path of ['/', '/privacy/']) {
    await page.goto(path);
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(result.violations).toEqual([]);
  }
  const robots = await request.get('/robots.txt');
  expect(await robots.text()).toContain('Disallow: /');
  const sitemap = await request.get('/sitemap.xml');
  expect(sitemap.ok()).toBe(true);
  expect(await sitemap.text()).toContain('<loc>https://preview.invalid/</loc>');
});

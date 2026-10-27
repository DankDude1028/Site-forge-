import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getSiteConfig } from '../site-config.mjs';

test('preview is the closed default and production requires a real canonical origin', () => {
  assert.deepEqual(getSiteConfig({}), { mode: 'preview', origin: 'https://preview.invalid', robots: 'noindex, nofollow' });
  assert.deepEqual(getSiteConfig({ SITEFORGE_BUILD_MODE: 'production', SITEFORGE_SITE_URL: 'https://lawnnumbers.com/' }),
    { mode: 'production', origin: 'https://lawnnumbers.com', robots: 'index, follow' });
  assert.throws(() => getSiteConfig({ SITEFORGE_BUILD_MODE: 'production' }), /requires SITEFORGE_SITE_URL/);
  assert.throws(() => getSiteConfig({ SITEFORGE_BUILD_MODE: 'public' }), /preview or production/);
});

test('production rejects credentials, non-HTTPS, subpaths, and placeholder/local origins', () => {
  for (const value of ['http://lawnnumbers.com', 'https://u:p@lawnnumbers.com', 'https://lawnnumbers.com/path',
    'https://lawnnumbers.com?token=value', 'https://lawnnumbers.com/#fragment', 'https://localhost',
    'https://127.0.0.1', 'https://[::1]', 'https://preview.invalid', 'https://example.com',
    'https://demo.test', 'https://demo.local', 'https://intranet', 'https://lawnnumbers.com:444', 'not a URL']) {
    assert.throws(() => getSiteConfig({ SITEFORGE_BUILD_MODE: 'production', SITEFORGE_SITE_URL: value }), value);
  }
});

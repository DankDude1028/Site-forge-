import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getSiteConfig } from '../site-config.mjs';

test('preview is the closed default and production requires a real canonical origin', () => {
  assert.deepEqual(getSiteConfig({}), { mode: 'preview', origin: 'https://preview.invalid', robots: 'noindex, nofollow' });
  assert.deepEqual(getSiteConfig({ SITEFORGE_BUILD_MODE: 'production', SITEFORGE_SITE_URL: 'https://turfwise.net/' }),
    { mode: 'production', origin: 'https://turfwise.net', robots: 'index, follow' });
  assert.throws(() => getSiteConfig({ SITEFORGE_BUILD_MODE: 'production' }), /requires SITEFORGE_SITE_URL/);
  assert.throws(() => getSiteConfig({ SITEFORGE_BUILD_MODE: 'public' }), /preview or production/);
});

test('production rejects credentials, non-HTTPS, subpaths, and placeholder/local origins', () => {
  for (const value of ['http://turfwise.net', 'https://u:p@turfwise.net', 'https://turfwise.net/path',
    'https://turfwise.net?token=value', 'https://turfwise.net/#fragment', 'https://localhost',
    'https://127.0.0.1', 'https://[::1]', 'https://preview.invalid', 'https://example.com',
    'https://demo.test', 'https://demo.local', 'https://intranet', 'https://turfwise.net:444', 'not a URL']) {
    assert.throws(() => getSiteConfig({ SITEFORGE_BUILD_MODE: 'production', SITEFORGE_SITE_URL: value }), value);
  }
});

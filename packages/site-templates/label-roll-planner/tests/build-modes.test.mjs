import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, realpath, rm } from 'node:fs/promises';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
test('actual Astro preview and production outputs have separate complete SEO contracts', async () => {
  // Astro renames prerendered assets, so output must share the template filesystem.
  const temporaryParent = join(await realpath(root), 'test-results');
  await mkdir(temporaryParent, { recursive: true });
  assert.equal(await realpath(temporaryParent), temporaryParent, 'Build output parent must not be redirected');
  const temporary = await mkdtemp(join(temporaryParent, 'astro-build-'));
  try {
    for (const mode of ['preview', 'production']) {
      const origin = mode === 'production' ? 'https://rollwise.net' : 'https://preview.invalid';
      const out = join(temporary, mode);
      const details = mode === 'production' ? { SITEFORGE_HOST_NAME: 'Netlify',
        SITEFORGE_HOST_PRIVACY_URL: 'https://www.netlify.com/privacy/', SITEFORGE_CONTACT_EMAIL: 'hello@rollwise.net' }
        : { SITEFORGE_HOST_NAME: '', SITEFORGE_HOST_PRIVACY_URL: '', SITEFORGE_CONTACT_EMAIL: '' };
      const build = spawnSync(process.execPath, ['node_modules/astro/bin/astro.mjs', 'build', '--outDir', out],
        { cwd: root, env: { ...process.env, SITEFORGE_BUILD_MODE: mode, SITEFORGE_SITE_URL: origin, ...details }, encoding: 'utf8', timeout: 60_000 });
      assert.equal(build.status, 0, build.stderr + build.stdout);
      const privacy = await readFile(join(out, 'privacy/index.html'), 'utf8');
      assert.ok(!privacy.includes('synthetic research'), 'Internal research notes never reach visitors');
      if (mode === 'production') {
        assert.ok(privacy.includes('href="mailto:hello@rollwise.net"') && privacy.includes('href="https://www.netlify.com/privacy/"'));
        assert.ok(!privacy.includes('added before launch'));
      } else {
        assert.ok(privacy.includes('added before launch'));
      }
      for (const [path, route] of [['index.html', '/'], ['privacy/index.html', '/privacy/']]) {
        const html = await readFile(join(out, path), 'utf8');
        assert.ok(html.includes(`name="robots" content="${mode === 'production' ? 'index, follow' : 'noindex, nofollow'}"`));
        assert.ok(html.includes(`rel="canonical" href="${origin}${route}"`));
        assert.ok(!html.includes(mode === 'production' ? 'noindex' : 'content="index, follow"'));
      }
      const robots = await readFile(join(out, 'robots.txt'), 'utf8');
      assert.equal(robots, mode === 'production'
        ? `User-agent: *\nAllow: /\nSitemap: ${origin}/sitemap.xml\n` : 'User-agent: *\nDisallow: /\n');
      const sitemap = await readFile(join(out, 'sitemap.xml'), 'utf8');
      assert.ok(sitemap.includes(`<loc>${origin}/</loc>`));
      assert.ok(sitemap.includes(`<loc>${origin}/privacy/</loc>`));
    }
    const missing = spawnSync(process.execPath, ['node_modules/astro/bin/astro.mjs', 'build', '--outDir', join(temporary, 'missing')],
      { cwd: root, env: { ...process.env, SITEFORGE_BUILD_MODE: 'production', SITEFORGE_SITE_URL: 'https://rollwise.net',
        SITEFORGE_HOST_NAME: '', SITEFORGE_HOST_PRIVACY_URL: '', SITEFORGE_CONTACT_EMAIL: '' }, encoding: 'utf8', timeout: 60_000 });
    assert.notEqual(missing.status, 0, 'A production build without host and contact details must fail');
  } finally {
    // Resolve and verify the exact fresh direct child before any recursive deletion.
    const resolvedTemporary = await realpath(temporary);
    assert.equal(dirname(resolvedTemporary), temporaryParent, 'Cleanup must stay inside the build test parent');
    assert.ok(basename(resolvedTemporary).startsWith('astro-build-'), 'Cleanup requires the generated test prefix');
    await rm(resolvedTemporary, { recursive: true, force: true });
  }
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
test('actual Astro preview and production outputs have separate complete SEO contracts', async () => {
  const temporary = await mkdtemp(join(tmpdir(), 'siteforge-build-'));
  try {
    for (const mode of ['preview', 'production']) {
      const origin = mode === 'production' ? 'https://rollwise.net' : 'https://preview.invalid';
      const out = join(temporary, mode);
      const build = spawnSync(process.execPath, ['node_modules/astro/bin/astro.mjs', 'build', '--outDir', out],
        { cwd: root, env: { ...process.env, SITEFORGE_BUILD_MODE: mode, SITEFORGE_SITE_URL: origin }, encoding: 'utf8', timeout: 60_000 });
      assert.equal(build.status, 0, build.stderr + build.stdout);
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
  } finally {
    // Only the fresh mkdtemp directory created above is removed; never a configured artifact root.
    await rm(temporary, { recursive: true, force: true });
  }
});

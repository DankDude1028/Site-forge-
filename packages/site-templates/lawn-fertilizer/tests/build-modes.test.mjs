import { test } from 'node:test';
import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readFile, realpath, rm } from 'node:fs/promises';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
import { ROUTES } from '../src/lib/site.ts';

const pages = ROUTES.map((route) => [route === '/' ? 'index.html' : `${route.slice(1)}index.html`, route]);

test('actual Astro preview and production outputs have separate complete SEO contracts', async () => {
  // Astro renames prerendered assets, so output must share the template filesystem.
  const temporaryParent = join(await realpath(root), 'test-results');
  await mkdir(temporaryParent, { recursive: true });
  assert.equal(await realpath(temporaryParent), temporaryParent, 'Build output parent must not be redirected');
  const temporary = await mkdtemp(join(temporaryParent, 'astro-build-'));
  try {
    for (const mode of ['preview', 'production']) {
      const origin = mode === 'production' ? 'https://lawnnumbers.com' : 'https://preview.invalid';
      const out = join(temporary, mode);
      const details = mode === 'production' ? { SITEFORGE_HOST_NAME: 'Netlify',
        SITEFORGE_HOST_PRIVACY_URL: 'https://www.netlify.com/privacy/', SITEFORGE_CONTACT_EMAIL: 'hello@lawnnumbers.com' }
        : { SITEFORGE_HOST_NAME: '', SITEFORGE_HOST_PRIVACY_URL: '', SITEFORGE_CONTACT_EMAIL: '' };
      const build = spawnSync(process.execPath, ['node_modules/astro/bin/astro.mjs', 'build', '--outDir', out],
        { cwd: root, env: { ...process.env, SITEFORGE_BUILD_MODE: mode, SITEFORGE_SITE_URL: origin, ...details }, encoding: 'utf8', timeout: 180_000 });
      assert.equal(build.status, 0, build.stderr + build.stdout);
      const privacy = await readFile(join(out, 'privacy/index.html'), 'utf8');
      if (mode === 'production') {
        assert.ok(privacy.includes('href="mailto:hello@lawnnumbers.com"') && privacy.includes('href="https://www.netlify.com/privacy/"'));
        assert.ok(!privacy.includes('added before launch'));
      } else {
        assert.ok(privacy.includes('added before launch'));
      }
      for (const [path, route] of pages) {
        const html = await readFile(join(out, path), 'utf8');
        assert.ok(html.includes(`name="robots" content="${mode === 'production' ? 'index, follow' : 'noindex, nofollow'}"`), path);
        assert.ok(html.includes(`rel="canonical" href="${origin}${route}"`), path);
        assert.ok(!html.includes(mode === 'production' ? 'noindex' : 'content="index, follow"'), path);
        assert.equal((html.match(/<h1[\s>]/g) ?? []).length, 1, `${path} has exactly one h1`);
        assert.ok(/<title>[^<]+\| Lawn Numbers<\/title>/.test(html) && html.includes('name="description"'), path);
        assert.equal(html.includes('Proof · not published'), mode === 'preview', `${path} marks only previews as proofs`);
        for (const property of ['og:title', 'og:description', 'og:url', 'og:type', 'og:site_name', 'og:image']) {
          assert.ok(html.includes(`property="${property}"`), `${path} ${property}`);
        }
        assert.ok(html.includes('name="twitter:card" content="summary_large_image"'), path);
        assert.ok(!html.includes('debrisdash.app@gmail.com') && !html.includes('shows no ads'), path);
        const locals = new Set();
        for (const match of html.matchAll(/(?:href|src)="(\/[^"]*)"/g)) locals.add(match[1]);
        for (const match of html.matchAll(/srcset="([^"]+)"/g)) {
          for (const part of match[1].split(',')) locals.add(part.trim().split(/\s+/)[0]);
        }
        for (const url of locals) {
          if (!url.startsWith('/') || url.startsWith('//')) continue;
          const pathOnly = url.split('#')[0].split('?')[0];
          if (pathOnly === '' || ROUTES.includes(pathOnly)) continue;
          try {
            await access(join(out, pathOnly.slice(1)));
          } catch {
            assert.fail(`${path} links to missing ${pathOnly}`);
          }
        }
        for (const tag of html.match(/<img\b[^>]*>/g) ?? []) {
          assert.ok(tag.includes('alt="'), `${path} img missing alt`);
          assert.ok(/width="\d+"/.test(tag) && /height="\d+"/.test(tag), `${path} img missing size: ${tag.slice(0, 180)}`);
        }
      }
      const home = await readFile(join(out, 'index.html'), 'utf8');
      assert.ok(home.includes('"@type":"WebApplication"') && home.includes('"@type":"FAQPage"'), 'home carries structured data');
      assert.ok(home.includes('id="total">25.9<'), 'the default result is in the server-rendered HTML');
      assert.equal(pages.length, 53, '22 existing pages plus hubs, bands, bags, seasons, 12 states, about, contact, credits');
      const bermuda = await readFile(join(out, 'grass/bermudagrass/index.html'), 'utf8');
      assert.ok(bermuda.includes('id="total">17.2<') && bermuda.includes('data-grass="bermudagrass"'), 'grass pages start the calculator and calendar on their own grass');
      const robots = await readFile(join(out, 'robots.txt'), 'utf8');
      assert.equal(robots, mode === 'production'
        ? `User-agent: *\nAllow: /\nSitemap: ${origin}/sitemap.xml\n` : 'User-agent: *\nDisallow: /\n');
      const sitemap = await readFile(join(out, 'sitemap.xml'), 'utf8');
      for (const [, route] of pages) assert.ok(sitemap.includes(`<loc>${origin}${route}</loc>`), route);
      assert.equal((sitemap.match(/<lastmod>\d{4}-\d{2}-\d{2}<\/lastmod>/g) ?? []).length, pages.length);
    }
    const missing = spawnSync(process.execPath, ['node_modules/astro/bin/astro.mjs', 'build', '--outDir', join(temporary, 'missing')],
      { cwd: root, env: { ...process.env, SITEFORGE_BUILD_MODE: 'production', SITEFORGE_SITE_URL: 'https://lawnnumbers.com',
        SITEFORGE_HOST_NAME: '', SITEFORGE_HOST_PRIVACY_URL: '', SITEFORGE_CONTACT_EMAIL: '' }, encoding: 'utf8', timeout: 180_000 });
    assert.notEqual(missing.status, 0, 'A production build without host and contact details must fail');
  } finally {
    // Resolve and verify the exact fresh direct child before any recursive deletion.
    const resolvedTemporary = await realpath(temporary);
    assert.equal(dirname(resolvedTemporary), temporaryParent, 'Cleanup must stay inside the build test parent');
    assert.ok(basename(resolvedTemporary).startsWith('astro-build-'), 'Cleanup requires the generated test prefix');
    await rm(resolvedTemporary, { recursive: true, force: true });
  }
});

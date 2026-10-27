import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { BAGS } from '../src/content/bags.ts';
import { GRASS_ARTICLES } from '../src/content/grass-articles.ts';
import { RANGES } from '../src/content/ranges.ts';
import { GRASSES } from '../src/lib/grasses.ts';
import { bagsFor, productPounds } from '../src/lib/sizes.ts';

const root = fileURLToPath(new URL('../', import.meta.url));

async function files(dir: string): Promise<string[]> {
  const found: string[] = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (['node_modules', 'dist', 'test-results', '.astro', 'tests', 'e2e'].includes(entry.name)) continue;
    const path = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...await files(path));
    else found.push(path);
  }
  return found;
}

function words(html: string): number {
  return html.replace(/<[^>]+>/g, ' ').replace(/&[a-z#0-9]+;/gi, ' ').split(/\s+/).filter(Boolean).length;
}

test('contact address is one constant and the DebrisDash mailbox is gone', async () => {
  const contact = await readFile(join(root, 'contact.mjs'), 'utf8');
  assert.match(contact, /CONTACT_EMAIL = 'hello@lawnnumbers.com'/);
  const toml = await readFile(join(root, 'netlify.toml'), 'utf8');
  assert.ok(toml.includes('SITEFORGE_CONTACT_EMAIL = "hello@lawnnumbers.com"'));
  const banned = ['debrisdash.app@gmail.com', 'shows no ads', 'no ads and no tracking', 'runs no analytics', 'sets no cookies'];
  for (const path of await files(root)) {
    if (!/\.(astro|ts|mjs|md|css|toml|txt)$/.test(path)) continue;
    const text = await readFile(path, 'utf8');
    for (const phrase of banned) {
      assert.equal(text.includes(phrase), false, `${relative(root, path)} still says “${phrase}”`);
    }
  }
});

test('grass guides are long and do not share paragraphs', () => {
  const paragraphs: string[] = [];
  for (const grass of GRASSES) {
    const article = GRASS_ARTICLES[grass.id];
    assert.ok(article, grass.id);
    assert.ok(article.sections.length >= 4, grass.id);
    assert.ok(article.faqs.length >= 3, grass.id);
    const text = [
      ...article.sections.flatMap((section) => [section.heading, ...section.paragraphs]),
      ...article.faqs.flatMap((item) => [item.q, item.a]),
    ].join(' ');
    const count = words(text);
    assert.ok(count >= 800, `${grass.id} is ${count} words`);
    paragraphs.push(...article.sections.flatMap((section) => section.paragraphs));
  }
  assert.equal(new Set(paragraphs).size, paragraphs.length, 'a paragraph is copied between grass pages');
});

test('bag and size-band examples match the calculator formula', () => {
  for (const bag of BAGS) {
    const product = productPounds(bag.area, bag.nitrogen, bag.rate);
    const bags = bagsFor(product, bag.weight);
    assert.ok(bags >= 1);
    assert.ok(bags * bag.weight + 1e-9 >= product, bag.slug);
    assert.ok((bags - 1) * bag.weight < product, bag.slug);
  }
  for (const range of RANGES) {
    const product = productPounds(range.exampleArea, range.nitrogen, range.rate);
    const bags = bagsFor(product, 25);
    assert.ok(bags * 25 + 1e-9 >= product, range.slug);
    assert.ok((bags - 1) * 25 < product, range.slug);
    assert.ok(range.high === null || range.exampleArea <= range.high, range.slug);
    assert.ok(range.exampleArea >= range.low, range.slug);
  }
});

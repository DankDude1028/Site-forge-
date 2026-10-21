import { defineConfig } from 'astro/config';

const site = process.env.SITEFORGE_SITE_URL || 'https://preview.invalid';
const parsed = new URL(site);
if (parsed.protocol !== 'https:' && parsed.hostname !== 'localhost' && parsed.hostname !== '127.0.0.1') {
  throw new Error('Site origin must use HTTPS or loopback');
}
export default defineConfig({ site, output: 'static', devToolbar: { enabled: false } });

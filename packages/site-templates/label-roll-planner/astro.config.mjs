import { defineConfig } from 'astro/config';
import { getSiteConfig } from './site-config.mjs';
export default defineConfig({ site: getSiteConfig().origin, output: 'static', devToolbar: { enabled: false } });

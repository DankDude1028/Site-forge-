import type { APIRoute } from 'astro';
import { getSiteConfig } from '../../site-config.mjs';

export const GET: APIRoute = () => {
  const config = getSiteConfig();
  const content = config.mode === 'production'
    ? `User-agent: *\nAllow: /\nSitemap: ${config.origin}/sitemap.xml\n`
    : 'User-agent: *\nDisallow: /\n';
  return new Response(content, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};

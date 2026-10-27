import type { APIRoute } from 'astro';
import { lastmod, routeSources } from '../lib/lastmod.ts';
import { ROUTES } from '../lib/site.ts';

export const GET: APIRoute = ({ site }) => new Response(
  `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${
    ROUTES.map((route) => `<url><loc>${new URL(route, site).href}</loc><lastmod>${lastmod(routeSources(route))}</lastmod></url>`).join('')
  }</urlset>`,
  { headers: { 'Content-Type': 'application/xml' } },
);

/** Build settings are operator inputs. A production build never deploys itself. */
export function getSiteConfig(environment = process.env) {
  const mode = environment.SITEFORGE_BUILD_MODE || 'preview';
  if (!['preview', 'production'].includes(mode)) throw new Error('SITEFORGE_BUILD_MODE must be preview or production');
  if (mode === 'production' && !environment.SITEFORGE_SITE_URL) throw new Error('Production requires SITEFORGE_SITE_URL');
  const raw = environment.SITEFORGE_SITE_URL || 'https://preview.invalid';
  let parsed;
  try { parsed = new URL(raw); } catch { throw new Error('Site URL must be a canonical origin'); }
  const loopback = ['localhost', '127.0.0.1'].includes(parsed.hostname);
  if (parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== '/' ||
      (parsed.port && parsed.port !== '443') || (parsed.protocol !== 'https:' && !(mode === 'preview' && loopback && parsed.protocol === 'http:'))) {
    throw new Error('Site URL must be an HTTPS canonical origin without credentials, path, query, or fragment');
  }
  if (mode === 'production' && (loopback || !parsed.hostname.includes('.') ||
      /^[\d.]+$/.test(parsed.hostname) || parsed.hostname.includes(':') ||
      /\.(invalid|test|example|local|localhost)$/.test(parsed.hostname) || parsed.hostname === 'example.com')) {
    throw new Error('Production requires a real configured HTTPS canonical origin');
  }
  return { mode, origin: parsed.origin, robots: mode === 'production' ? 'index, follow' : 'noindex, nofollow' };
}

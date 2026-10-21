export interface SiteConfig { mode: 'preview' | 'production'; origin: string; robots: string }
export function getSiteConfig(environment?: Record<string, string | undefined>): SiteConfig;

/** Sitemap dates: git's last commit day, or the build day when a source file is uncommitted. */
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../../../../../', import.meta.url));
const buildDay = new Date().toISOString().slice(0, 10);

let dirty = new Set<string>();
try {
  const porcelain = execFileSync('git', ['status', '--porcelain', '--untracked-files=all'], { cwd: repo, encoding: 'utf8' });
  dirty = new Set(porcelain.split('\n').map((line) => line.slice(3).trim()).filter(Boolean));
} catch {
  dirty = new Set();
}

const commitDay = new Map<string, string>();

function committed(path: string): string | null {
  if (commitDay.has(path)) return commitDay.get(path) ?? null;
  try {
    const day = execFileSync('git', ['log', '-1', '--format=%cs', '--', path], { cwd: repo, encoding: 'utf8' }).trim();
    commitDay.set(path, day);
    return day || null;
  } catch {
    commitDay.set(path, '');
    return null;
  }
}

export function lastmod(paths: readonly string[]): string {
  let newest = '';
  for (const path of paths) {
    const changed = [...dirty].some((file) => file === path || file.endsWith(`/${path}`) || path.endsWith(file));
    const day = changed ? buildDay : (committed(path) ?? buildDay);
    if (day > newest) newest = day;
  }
  return newest || buildDay;
}

const ROOT = 'packages/site-templates/lawn-fertilizer/';

/** Page and content files that can change one route, plus the shared layout files. */
export function routeSources(route: string): string[] {
  const files: string[] = [];
  const add = (relative: string) => files.push(`${ROOT}${relative}`);
  if (route === '/') add('src/pages/index.astro');
  else if (route === '/guides/') add('src/pages/guides/index.astro');
  else if (route.startsWith('/guides/')) add(`src/pages${route.slice(0, -1)}.astro`);
  else if (route === '/lawn-size/') {
    add('src/pages/lawn-size/index.astro');
    add('src/content/ranges.ts');
  } else if (route.startsWith('/lawn-size/')) {
    add('src/pages/lawn-size/[size].astro');
    add('src/components/ExactSize.astro');
    add('src/components/RangeSize.astro');
    add('src/content/ranges.ts');
    add('src/lib/sizes.ts');
  } else if (route === '/bags/') add('src/pages/bags/index.astro');
  else if (route.startsWith('/bags/')) {
    add('src/pages/bags/[bag].astro');
    add('src/content/bags.ts');
  } else if (route === '/seasons/') add('src/pages/seasons/index.astro');
  else if (route.startsWith('/seasons/')) {
    add('src/pages/seasons/[season].astro');
    add('src/content/seasons.ts');
  } else if (route === '/states/') add('src/pages/states/index.astro');
  else if (route.startsWith('/states/')) {
    add('src/pages/states/[state].astro');
    add('src/content/states.ts');
  } else if (route.startsWith('/grass/')) {
    add('src/pages/grass/[grass].astro');
    add('src/content/grass-articles.ts');
    add('src/lib/photos.ts');
  } else add(`src/pages${route.slice(0, -1)}.astro`);
  return [...files, ...SHARED_SOURCES];
}

/** Shared files that change every page's HTML. */
export const SHARED_SOURCES = [
  'packages/site-templates/lawn-fertilizer/src/layouts/Base.astro',
  'packages/site-templates/lawn-fertilizer/src/components/SiteHeader.astro',
  'packages/site-templates/lawn-fertilizer/src/components/SiteFooter.astro',
  'packages/site-templates/lawn-fertilizer/src/styles/site.css',
] as const;

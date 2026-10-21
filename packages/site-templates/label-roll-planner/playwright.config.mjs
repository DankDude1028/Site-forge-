import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', workers: 1,
  use: { baseURL: 'http://127.0.0.1:4327', headless: true },
  projects: [{ name: 'desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 393, height: 852 }, isMobile: true } }],
  webServer: { command: `"${process.execPath}" ./node_modules/astro/bin/astro.mjs preview --host 127.0.0.1 --port 4327`, url: 'http://127.0.0.1:4327',
    reuseExistingServer: false },
});

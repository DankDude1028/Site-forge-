# Label roll planner

A browser-local utility for small batch print planning. Inputs are items, labels per item, labels per full roll, full rolls already on hand, and an additional stock allowance. It rounds allowance to whole labels and capacity to whole rolls, and explains those assumptions. It uses no third-party datasets, ad scripts, cookies, or analytics. No user input is transmitted.

With Node 22.12+ run `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`. The current repository Node is 22.23.2; Astro is deliberately pinned to compatible 6.4.8. The latest 7.4.2 requires Node 22.23.4+. `npm run dev` binds to loopback only. Automated unit tests cover edge cases, invalid/nonfinite inputs, available stock, fractional buffers, monotonicity and sufficient roll capacity.

This is a **private preview**: noindex metadata and `robots.txt` disallow crawling. `SITEFORGE_SITE_URL` configures canonical and sitemap origin; its default `https://preview.invalid` is a placeholder, not a public deployment. Public production needs real evidence, reviewed content/hosting privacy terms, an exact-commit approval, appropriate robots/canonical configuration, and a separately gated release. Build success does not establish browser accessibility or 72-hour acceptance.

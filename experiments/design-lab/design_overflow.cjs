// Usage: node design_overflow.cjs <templateDir> <baseUrl>
// Prints JSON: the outermost elements that stick out past the screen edge and make the page scroll sideways, each
// with the outermost on-screen container that could clip it.
const [templateDir, base] = process.argv.slice(2);
const { chromium } = require(templateDir + "/node_modules/playwright");

(async () => {
  const browser = await chromium.launch({ channel: "msedge" });
  const out = [];
  for (const [label, viewport] of [["desktop 1280px", { width: 1280, height: 900 }], ["phone 393px", { width: 393, height: 852 }]]) {
    const page = await browser.newPage({ viewport });
    for (const path of ["/", "/privacy/"]) {
      await page.goto(base + path, { waitUntil: "networkidle" });
      const found = await page.evaluate(() => {
        const width = document.documentElement.clientWidth;
        if (document.documentElement.scrollWidth <= innerWidth) return [];
        const outside = el => { const box = el.getBoundingClientRect(); return box.width > 0 && (box.right > width + 1 || box.left < -1); };
        const clipped = el => { for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
          if (getComputedStyle(a).overflowX !== "visible") return true; } return false; };
        const name = el => el.tagName.toLowerCase() + (el.id ? "#" + CSS.escape(el.id) : "")
          + (typeof el.className === "string" && el.className.trim()
             ? el.className.trim().split(/\s+/).map(c => "." + CSS.escape(c)).join("") : "");
        const hits = [];
        for (const el of document.querySelectorAll("body *")) {
          if (!outside(el) || clipped(el) || (el.parentElement && el.parentElement !== document.body && outside(el.parentElement))) continue;
          // The topmost ancestor below body that still fits the screen clips the least.
          let clip = null;
          for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) if (!outside(a)) clip = a;
          const box = el.getBoundingClientRect();
          hits.push({ element: name(el), left: Math.round(box.left), right: Math.round(box.right), width,
                      clip: clip ? name(clip) : null });
        }
        return hits.slice(0, 6);
      });
      for (const hit of found) out.push({ label, path, ...hit });
    }
    await page.close();
  }
  console.log(JSON.stringify(out));
  await browser.close();
})().catch(error => { console.error(error.message); process.exit(1); });

// Usage: node design_capture.cjs <templateDir> <outDir> <baseUrl>
const [templateDir, out, base] = process.argv.slice(2);
const { chromium } = require(templateDir + "/node_modules/playwright");
const fs = require("fs");
const MAX_HEIGHT = 7600;

(async () => {
  const browser = await chromium.launch({ channel: "msedge" });
  const shots = [["desktop-fold.png", { width: 1280, height: 900 }, false],
                 ["desktop-full.png", { width: 1280, height: 900 }, true],
                 ["mobile-full.png", { width: 393, height: 852 }, true],
                 ["mobile-fold.png", { width: 393, height: 852 }, false]];  // a readable first screen for vision models
  let text = "";
  const lint = [];
  for (const [name, viewport, full] of shots) {
    const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
    const page = await context.newPage();
    await page.goto(base + "/", { waitUntil: "networkidle" });
    await page.waitForTimeout(2600); // let the load sequence finish
    if (name !== "desktop-full.png" && name !== "mobile-fold.png") lint.push(...(await page.evaluate(label => {
      // Free checks for designs that build but render broken, before any paid review.
      const issues = [];
      const font = getComputedStyle(document.body).fontFamily;
      if (!font || /times/i.test(font)) issues.push(`${label}: body text renders in the browser default font (${font || "none"}); a font token or the font shorthand is broken.`);
      const defined = new Set(["--used"]), used = new Map(), classes = new Map();
      const walk = list => { for (const rule of list) {
        if (rule.cssRules) walk(rule.cssRules);
        if (!rule.style) continue;
        for (const property of rule.style) if (property.startsWith("--")) defined.add(property);
        for (const match of rule.style.cssText.matchAll(/var\(\s*(--[\w-]+)\s*\)/g)) used.set(match[1], rule.selectorText || "");
        for (const match of (rule.selectorText || "").matchAll(/\.([A-Za-z_][\w-]*)/g)) classes.set(match[1], rule.selectorText);
      } };
      for (const sheet of document.styleSheets) { try { walk(sheet.cssRules); } catch (error) { /* cross-origin */ } }
      const undefinedVars = [...used.keys()].filter(name => !defined.has(name));
      if (undefinedVars.length) issues.push(`${label}: CSS uses variables that are never defined: ${undefinedVars.join(", ")}.`);
      const dynamic = new Set(["roll", "order", "have", "partial", "more", "skip"]);
      const missing = [...classes.keys()].filter(name => !dynamic.has(name) && !document.getElementsByClassName(name).length);
      if (missing.length >= 4) issues.push(`${label}: CSS styles ${missing.length} classes that are not in the page: ${missing.slice(0, 15).join(", ")}. Add those elements to the markup or style the classes that exist.`);
      for (const element of document.querySelectorAll("body *")) {
        const box = element.getBoundingClientRect();
        if ((element.tagName === "svg" || element.tagName === "IMG") && box.height > innerHeight * 0.9 && box.width > innerWidth * 0.6) {
          const cls = (element.getAttribute("class") || "").trim().split(/\s+/)[0];
          const rule = cls ? ` For example add \`.${cls} { width: 2.5rem; height: 2.5rem; }\` for an icon, or a width and max-height that suit an illustration.` : "";
          issues.push(`${label}: a ${element.tagName.toLowerCase()} (${cls || "no class"}) renders ${Math.round(box.width)}x${Math.round(box.height)}px, filling the screen; give it an explicit size.${rule}`);
          break;
        }
      }
      // On desktop a grid can crush the calculator into a narrow column, which passes every test.
      const form = document.querySelector("form");
      if (innerWidth >= 1000 && form && form.getBoundingClientRect().width < 380)
        issues.push(`${label}: the calculator form is squeezed into a ${Math.round(form.getBoundingClientRect().width)}px column on a ${innerWidth}px screen. Give the calculator column at least 440px (for example grid-template-columns: minmax(0, 1fr) minmax(440px, 1.1fr)).`);
      // A phone layout that never collapses squeezes the headline and pushes content past a clipped edge.
      if (innerWidth < 500) {
        const h1 = document.querySelector("h1");
        if (h1 && h1.getBoundingClientRect().width < innerWidth * 0.6) {
          // Name the grid or flex row that squeezes it, so the fix targets the right rule.
          const name = el => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "")
            + (typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\s+/).join(".") : "");
          let cause = "";
          for (let el = h1; el && el.parentElement && el !== document.body; el = el.parentElement) {
            const parent = el.parentElement, s = getComputedStyle(el), ps = getComputedStyle(parent);
            const w = el.getBoundingClientRect().width, pw = parent.getBoundingClientRect().width;
            if (ps.display.includes("grid") && ps.gridTemplateColumns.split(" ").length > 1) {
              cause = ` It sits in ${name(parent)}, a grid with grid-template-columns: ${ps.gridTemplateColumns} at this width; inside @media (max-width: 768px) give ${name(parent)} grid-template-columns: 1fr.`;
              break;
            }
            if (ps.display.includes("flex") && !ps.flexDirection.startsWith("column") && w < pw * 0.7) {
              cause = ` It sits in ${name(parent)}, a flex row; inside @media (max-width: 768px) give ${name(parent)} flex-direction: column.`;
              break;
            }
            if (w < pw * 0.7) {
              const rule = s.maxWidth !== "none" ? `max-width: ${s.maxWidth}` : `width: ${s.width}`;
              cause = ` ${name(el)} is only ${Math.round(w)}px wide inside ${name(parent)} (${Math.round(pw)}px) because of ${rule}; inside @media (max-width: 768px) set ${name(el)} { max-width: none; width: auto; }.`;
              break;
            }
          }
          issues.push(`${label}: the headline is squeezed into a ${Math.round(h1.getBoundingClientRect().width)}px column on a ${innerWidth}px phone.${cause || " Collapse the layout to one column below 768px so text and inputs use the full width."}`);
        }
        const cut = [...document.querySelectorAll("h1, h2, p, label, input, button, select")].filter(el => {
          const b = el.getBoundingClientRect(); return b.width > 0 && (b.right > innerWidth + 2 || b.left < -2); });
        if (cut.length) issues.push(`${label}: ${cut.length} text or form elements run past the screen edge on the phone, for example <${cut[0].tagName.toLowerCase()}> "${(cut[0].innerText || cut[0].value || "").trim().slice(0, 40)}". Make the phone layout one column with full-width inputs.`);
      }
      // Valid CSS can still leave a page unstyled at one width: a media query that wraps most rules.
      let active = 0, inactive = 0; const conditions = new Map();
      const count = (list, on, condition) => { for (const rule of list) {
        if (rule.media && rule.cssRules) { const live = on && matchMedia(rule.conditionText || rule.media.mediaText).matches;
          count(rule.cssRules, live, rule.conditionText || rule.media.mediaText); continue; }
        if (!rule.selectorText) continue;
        if (on) active++; else { inactive++; conditions.set(condition, (conditions.get(condition) || 0) + 1); } } };
      for (const sheet of document.styleSheets) { try { count(sheet.cssRules, true, ""); } catch (error) { /* cross-origin */ } }
      if (active < 30) issues.push(`${label}: the page is nearly unstyled: only ${active} CSS rules apply. Check that index.astro still has import '../styles/site.css'; and that site.css has no unclosed comment or block that swallows the rules after it.`);
      else if (inactive > active && inactive > 20) {
        const [condition, rules] = [...conditions.entries()].sort((x, y) => y[1] - x[1])[0];
        issues.push(`${label}: most of the page's CSS does not apply at this width: ${inactive} style rules are switched off and only ${active} apply. ${rules} of them sit inside @media ${condition}. Close that media block right after the rules that belong to it, so the main styles apply at every width.`);
      }
      // The roll strip is the page's signature visual; a style that collapses or blanks it passes every test.
      const rolls = [...document.querySelectorAll(".roll")];
      const paints = s => s.backgroundColor !== "rgba(0, 0, 0, 0)" || s.backgroundImage !== "none"
        || (parseFloat(s.borderTopWidth) > 0 && s.borderTopColor !== "rgba(0, 0, 0, 0)") || s.boxShadow !== "none";
      const pseudoPaints = (el, which) => { const s = getComputedStyle(el, which); return s.content !== "none" && paints(s); };
      const blank = el => { const b = el.getBoundingClientRect(), s = getComputedStyle(el);
        const painted = paints(s) || pseudoPaints(el, "::before") || pseudoPaints(el, "::after")
          || [...el.querySelectorAll("*")].some(child => paints(getComputedStyle(child)));
        return b.width < 6 || b.height < 6 || s.visibility === "hidden" || parseFloat(s.opacity) === 0 || !painted; };
      if (!rolls.length) issues.push(`${label}: the roll strip shows no rolls at all; keep the .roll elements the calculator draws visible.`);
      else if (rolls.every(blank)) {
        const b = rolls[0].getBoundingClientRect();
        issues.push(`${label}: the roll strip is blank: its ${rolls.length} .roll elements render ${Math.round(b.width)}x${Math.round(b.height)}px with no visible fill or border. Give .roll a visible size (for example width and height of 40px or more) and a fill or border colour, and keep .roll.order, .roll.have and .roll.partial distinct.`);
      }
      // Template code that renders as visible text means a broken or duplicated --- frontmatter block.
      const leak = document.body.innerText.split("\n").find(line => /^\s*---|Astro\.props|^\s*(const|import) /.test(line));
      if (leak) issues.push(`${label}: template code shows as text on the page ("${leak.trim().slice(0, 80)}"). A component has a broken or duplicated --- frontmatter block; keep exactly one block at the very top of each .astro file.`);
      return issues;
    }, name.replace(".png", ""))));
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const options = { path: `${out}/${name}` };
    if (full) Object.assign(options, height > MAX_HEIGHT ? { clip: { x: 0, y: 0, width: viewport.width, height: MAX_HEIGHT } }
                                                          : { fullPage: true });
    await page.screenshot(options);
    if (!text) text = await page.innerText("body");
    await context.close();
  }
  fs.writeFileSync(`${out}/page-text.txt`, text);
  fs.writeFileSync(`${out}/lint.json`, JSON.stringify(lint, null, 2));
  await browser.close();
})().catch(error => { console.error(error.message); process.exit(1); });

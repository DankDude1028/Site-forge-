// Usage: node collab_capture.cjs <templateDir> <outDir> <baseUrl>
const [templateDir, out, base] = process.argv.slice(2);
const { chromium } = require(templateDir + "/node_modules/playwright");
const fs = require("fs");

const custom = [["Items in this batch", "1000"], ["Labels per item", "3"], ["Labels on each roll", "750"],
  ["Full rolls you already have", "0"], ["Extra allowance (%)", "10"]];
const enough = [["Items in this batch", "100"], ["Labels per item", "1"], ["Labels on each roll", "500"],
  ["Full rolls you already have", "10"], ["Extra allowance (%)", "5"]];

async function fill(page, values) {
  for (const [label, value] of values) await page.getByLabel(label).fill(value);
}

(async () => {
  const browser = await chromium.launch({ channel: "msedge" });
  const notes = [];
  const shoot = async (name, viewport, act, fullPage = true) => {
    const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
    const page = await context.newPage();
    await page.goto(base + "/", { waitUntil: "networkidle" });
    const note = await act(page);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${out}/${name}`, fullPage });
    if (note) notes.push(`=== ${name}: ${note}\n` + (await page.innerText("body")));
    await context.close();
  };
  await shoot("desktop-custom.png", { width: 1280, height: 900 }, async page => {
    await fill(page, custom);
    await page.getByRole("button", { name: /Calculate my rolls/ }).click();
    return "custom batch (1000 items, 3 labels, 750 per roll, 0 owned, 10%)";
  });
  await shoot("mobile-custom.png", { width: 393, height: 852 }, async page => {
    await fill(page, custom);
    await page.getByRole("button", { name: /Calculate my rolls/ }).click();
  });
  await shoot("desktop-error-focus.png", { width: 1280, height: 900 }, async page => {
    await page.getByLabel("Labels on each roll").fill("");
    await page.getByRole("button", { name: /Calculate my rolls/ }).click();
    return "blank 'Labels on each roll' then Calculate (focus moves to the invalid field)";
  }, false);
  await shoot("desktop-enough.png", { width: 1280, height: 900 }, async page => {
    await fill(page, enough);
    await page.getByRole("button", { name: /Calculate my rolls/ }).click();
    return "owned rolls exceed need (100 items, 1 label, 500 per roll, 10 owned, 5%)";
  });
  fs.writeFileSync(`${out}/page-text.txt`, notes.join("\n\n"));
  await browser.close();
})().catch(error => { console.error(error.message); process.exit(1); });

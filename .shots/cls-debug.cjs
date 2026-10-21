const { chromium, devices } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    ...devices["Pixel 5"],
    storageState: { cookies: [{ name: "tk_session", value: "shot", domain: "localhost", path: "/" }] },
  });
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    window.__cls = [];
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (e.hadRecentInput) continue;
        const sources = (e.sources || []).map((s) => {
          const n = s.node;
          return {
            tag: n && n.nodeName,
            id: n && n.id,
            cls: n && n.className && String(n.className).slice(0, 80),
            prev: s.previousRect ? { x: s.previousRect.x, y: s.previousRect.y, w: s.previousRect.width, h: s.previousRect.height } : null,
            cur: s.currentRect ? { x: s.currentRect.x, y: s.currentRect.y, w: s.currentRect.width, h: s.currentRect.height } : null,
          };
        });
        window.__cls.push({ value: e.value, sources });
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
  await page.goto("http://localhost:4400/digest", { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(7000);
  const cls = await page.evaluate(() => window.__cls);
  let total = 0;
  for (const s of cls) {
    total += s.value;
    console.log("shift", s.value.toFixed(4), JSON.stringify(s.sources, null, 1));
  }
  console.log("TOTAL", total.toFixed(4));
  await browser.close();
})();

// Start Vite on port 5178, then run: node src/test/evidence-map.browser.cjs
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const base = process.env.BASE_URL || 'http://127.0.0.1:5178';

(async () => {
  const browser = await chromium.launch({headless: true});
  const artifacts = await fs.mkdtemp('/private/tmp/emberline-map-');
  try {
    for (const width of [1440, 1024, 768, 390, 320]) {
      const page = await browser.newPage({viewport: {width, height: 1000}, serviceWorkers: 'block'});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      if (base.startsWith('http://127.0.0.1')) {
        // Read-only public fixture; no account, checkout or real Hub invocation.
        await page.route('**/api/public/**', async route => {
          const url = new URL(route.request().url());
          const response = await page.request.get(`https://emberlinedesk.com${url.pathname}${url.search}`);
          await route.fulfill({response});
        });
      }
      await page.goto(`${base}/sample`);
      const map = page.locator('svg.map-frame');
      await map.waitFor({state: 'visible'});
      await map.scrollIntoViewIfNeeded();
      await page.screenshot({path: `${artifacts}/sample-${width}.png`});
      const size = await map.evaluate(svg => {
        const container = svg.parentElement;
        const paper = svg.closest('.paper');
        const style = getComputedStyle(paper);
        return {
          map: svg.clientWidth,
          height: svg.clientHeight,
          container: container.clientWidth,
          content: paper.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
          detections: svg.querySelectorAll('g circle').length,
          viewBox: svg.getAttribute('viewBox'),
        };
      });
      assert.ok(size.map <= size.container, `${width}px: map overflows its container: ${JSON.stringify(size)}`);
      assert.ok(size.container <= size.content + 1, `${width}px: map extends into the paper margins`);
      assert.ok(Math.abs(size.map / size.height - 720 / 460) < 0.02, `${width}px: map aspect ratio changed`);
      assert.ok(size.detections > 0, 'Fixture detection points must remain visible');
      assert.equal(size.viewBox, '0 0 720 460');
      // Leaflet sizing is a separate contract, unaffected by the responsive SVG rule.
      const minimum = await page.evaluate(() => {
        const div = document.createElement('div');
        div.className = 'map-frame';
        document.body.append(div);
        const value = getComputedStyle(div).minHeight;
        div.remove();
        return value;
      });
      assert.equal(minimum, '420px');
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(JSON.stringify({status: 'passed', base, widths: [1440,1024,768,390,320], artifacts}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

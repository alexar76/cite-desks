import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const desksRoot = resolve(scriptDir, "..");

const targets = {
  family: {
    url: "http://127.0.0.1:8099/",
    output: resolve(desksRoot, "docs/screenshots/family-hero.jpg"),
    ready: ".hero h1",
  },
  emberline: {
    url: "http://127.0.0.1:5173/",
    output: resolve(desksRoot, "emberline/docs/screenshots"),
    ready: ".hero-cinematic h1",
    sample: "/sample",
    sampleReady: ".brief-stage",
    pricing: "#pricing",
  },
  tideline: {
    url: "http://127.0.0.1:8090/",
    api: "http://127.0.0.1:8101/",
    output: resolve(desksRoot, "tideline/docs/screenshots"),
    ready: "#hero-title",
    sample: "/sample",
    sampleReady: "#sample-page h3",
    pricing: "#buy",
  },
  solrecord: {
    url: "http://127.0.0.1:8090/",
    api: "http://127.0.0.1:8102/",
    output: resolve(desksRoot, "solrecord/docs/screenshots"),
    ready: "#hero-title",
    sample: "/sample",
    sampleReady: "#sample-page h3",
    pricing: "#buy",
  },
  seamark: {
    url: "http://127.0.0.1:8090/",
    api: "http://127.0.0.1:8103/",
    output: resolve(desksRoot, "seamark/docs/screenshots"),
    ready: "#hero-title",
    sample: "/sample",
    sampleReady: "#sample-page h3",
    pricing: "#buy",
  },
  plinth: {
    url: "http://127.0.0.1:8090/",
    api: "http://127.0.0.1:8104/",
    output: resolve(desksRoot, "plinth/docs/screenshots"),
    ready: "#hero-title",
    sample: "/sample",
    sampleReady: "#sample-page h3",
    pricing: "#buy",
  },
};

const heroOnly = process.argv.includes("--hero-only");
const requested = process.argv.slice(2).filter((arg) => arg !== "--hero-only");
const names = requested.length ? requested : Object.keys(targets);
for (const name of names) {
  if (!targets[name]) throw new Error(`Unknown target: ${name}`);
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  colorScheme: "dark",
  locale: "en-US",
});

async function settle(page, target, readySelector) {
  await page.waitForTimeout(6_000);
  if ((await page.locator("canvas").count()) > 0) {
    await page.waitForTimeout(10_000);
  }
  await page.evaluate(() => {
    window.requestAnimationFrame = () => 0;
  });
  if ((await page.locator(readySelector).count()) === 0) {
    throw new Error(`Ready selector not found: ${readySelector} at ${page.url()}`);
  }
  if (target.ready === "#hero-title") {
    const title = (await page.locator("#hero-title").textContent())?.trim();
    const brand = (await page.locator("#brand-name").textContent())?.trim();
    if (!title || !brand || brand === "Cite desk") {
      throw new Error(`Desk data did not load at ${page.url()}`);
    }
  }
  await page.addStyleTag({
    content: `
      .hero-copy > *, .section, main, [style*="opacity"] {
        opacity: 1 !important;
        transform: none !important;
      }
    `,
  });
  await page.waitForTimeout(1_600);
}

async function screenshot(page, path) {
  await mkdir(dirname(path), { recursive: true });
  await page.screenshot({ path, type: "jpeg", quality: 90, fullPage: false });
  process.stdout.write(`${path}\n`);
}

try {
  for (const name of names) {
    const target = targets[name];
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    if (target.api) {
      await page.route("**/api/**", async (route) => {
        const incoming = new URL(route.request().url());
        const upstream = new URL(`${incoming.pathname}${incoming.search}`, target.api).href;
        const response = await route.fetch({ url: upstream });
        await route.fulfill({ response });
      });
    }

    await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await settle(page, target, target.ready);

    if (name === "family") {
      await screenshot(page, target.output);
      await page.close();
      continue;
    }

    await page.locator(".demo-banner, .rails-banner").evaluateAll((elements) => elements.forEach((element) => element.remove()));
    await screenshot(page, resolve(target.output, "hero.jpg"));
    if (heroOnly) {
      await page.close();
      continue;
    }

    if (target.api) {
      await page.locator('a[href="/sample"]').first().click();
    } else {
      await page.goto(new URL(target.sample, target.url).href, { waitUntil: "domcontentloaded", timeout: 60_000 });
    }
    await settle(page, target, target.sampleReady);
    await page.locator(".demo-banner, .rails-banner").evaluateAll((elements) => elements.forEach((element) => element.remove()));
    await screenshot(page, resolve(target.output, "sample.jpg"));

    await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await settle(page, target, target.ready);
    await page.locator(".demo-banner, .rails-banner").evaluateAll((elements) => elements.forEach((element) => element.remove()));
    await page.locator(target.pricing).scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await screenshot(page, resolve(target.output, "pricing.jpg"));

    if (errors.length) {
      throw new Error(`${name} page errors: ${errors.join(" | ")}`);
    }
    await page.close();
  }
} finally {
  await browser.close();
}

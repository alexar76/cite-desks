// @vitest-environment node
import { renderToStaticMarkup } from "react-dom/server";
import { StaticRouter } from "react-router-dom/server";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/I18nProvider";
import { Landing } from "../pages/Landing";
import { RequestKey } from "../pages/RequestKey";
import { useDeskMode } from "../lib/useDeskMode";

vi.mock("../lib/useDeskMode", () => ({ useDeskMode: vi.fn() }));
vi.mock("../components/Globe", () => ({ Globe: () => null }));
vi.mock("../components/Nav", () => ({ SiteNav: () => null }));
vi.mock("../components/SiteFooter", () => ({ SiteFooter: () => null }));
vi.mock("../components/PageMeta", () => ({ PageMeta: () => null }));

describe.each([Landing, RequestKey])("commercial demonstration", (Page) => {
  it.each(["demo", "loading", "unavailable", "live"] as const)("keeps prices in %s mode", (mode) => {
    vi.mocked(useDeskMode).mockReturnValue(mode);
    const html = renderToStaticMarkup(<StaticRouter location="/"><I18nProvider><Page /></I18nProvider></StaticRouter>);
    for (const price of ["$49", "$149", "$499"]) expect(html).toContain(price);
    if (mode === "live") expect(html).toContain('href="/pay');
    else {
      expect(html).not.toContain('href="/pay');
      expect(html).toContain("https://github.com/alexar76/cite-desks");
      expect(html).toContain("Launch your own desk");
    }
  });
});

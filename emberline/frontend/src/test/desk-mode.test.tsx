// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDeskMode } from "../lib/useDeskMode";
import { DemoNextSteps } from "../components/DemoNextSteps";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({ api: { health: vi.fn() } }));
vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
let root: Root | undefined;
let element: HTMLDivElement;

function Probe() {
  const mode = useDeskMode();
  return mode === "live" ? <a href="/pay">Checkout</a> : <DemoNextSteps mode={mode} />;
}

async function mount() {
  element = document.createElement("div");
  document.body.append(element);
  root = createRoot(element);
  await act(async () => root!.render(<Probe />));
}

afterEach(async () => {
  await act(async () => root?.unmount());
  element?.remove();
  vi.resetAllMocks();
});

describe("checkout fails closed", () => {
  it.each([true, undefined])("does not sell when demo=%s", async (demo) => {
    vi.mocked(api.health).mockResolvedValue({ ok: true, hub_mode: "fixture", demo });
    await mount();
    expect(element.querySelector('[href="/pay"]')).toBeNull();
    expect(element.textContent).toContain("Launch your own desk");
  });
  it("does not sell on network failure", async () => {
    vi.mocked(api.health).mockRejectedValue(new Error("offline"));
    await mount();
    expect(element.textContent).toContain("could not be verified");
    expect(element.querySelector('[href="/pay"]')).toBeNull();
  });
  it("does not sell while loading", async () => {
    vi.mocked(api.health).mockReturnValue(new Promise(() => {}));
    await mount();
    expect(element.textContent).toContain("Checking service availability");
    expect(element.querySelector('[href="/pay"]')).toBeNull();
  });
  it("permits checkout only for explicit live mode", async () => {
    vi.mocked(api.health).mockResolvedValue({ ok: true, hub_mode: "live", demo: false });
    await mount();
    expect(element.querySelector('[href="/pay"]')).not.toBeNull();
  });
});

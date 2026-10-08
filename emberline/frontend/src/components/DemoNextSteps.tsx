import type { DeskMode } from "../lib/useDeskMode";

export function DemoNextSteps({ mode }: { mode: DeskMode }) {
  return (
    <div>
      <h3>{mode === "demo" ? "Launch your own evidence desk" : "Checkout unavailable"}</h3>
      <p role="status">{mode === "demo"
        ? "Fork Emberline, set your own subscription prices, and sell evidence briefs to your customers. Explore the sample and pricing model here; deploy your own desk to serve paying customers. Checkout on this demo host is closed."
        : mode === "loading"
          ? "Checking service availability. The sample and source are available without payment."
          : "The service mode could not be verified. Checkout stays closed. You can still inspect the sample and source."}</p>
      <div className="hero-actions" style={{ marginTop: 12 }}>
        <a className="btn" href="/sample">Sample brief</a>
        <a className="btn btn-ember" href="https://github.com/alexar76/cite-desks">Launch your own desk</a>
        <a className="btn" href="/#pricing">Pricing model</a>
      </div>
    </div>
  );
}

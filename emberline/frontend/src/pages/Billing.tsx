import { useEffect, useState } from "react";
import { SideNav } from "../components/Nav";
import { api } from "../lib/api";
import { money } from "../lib/format";

type Usage = {
  plan?: string;
  plan_meta?: { name: string; price_usd: number; watches: number; runs: number; retention_days: number };
  watches?: number;
  runs?: number;
  cogs_usd?: number;
  by_sku?: { sku: string; count: number; cogs_usd: number }[];
  overage?: Record<string, number>;
};

export function Billing() {
  const [usage, setUsage] = useState<Usage | null>(null);
  useEffect(() => {
    api.usage().then(setUsage).catch(() => setUsage(null));
  }, []);

  return (
    <div className="app-shell">
      <SideNav />
      <main className="main">
        <div className="kicker">Honest metering</div>
        <h2 className="serif">Billing</h2>
        <p className="muted">
          You pay Emberline. Emberline pays Hub. Prepaid desk keys are minted with{" "}
          <span className="mono">PAY_MINT_SECRET</span> and redeemed on the login page. Margin is
          UX, reliability, and archive — not invented polygons.
        </p>
        <div className="grid-3">
          <div className="card">
            <div className="kicker">Plan</div>
            <h3>{usage?.plan_meta?.name || usage?.plan}</h3>
            <p>{usage?.plan_meta ? `${money(usage.plan_meta.price_usd)} / mo illustration` : ""}</p>
          </div>
          <div className="card">
            <div className="kicker">This workspace</div>
            <h3>
              {usage?.watches} watches · {usage?.runs} runs
            </h3>
            <p>Hub COGS {money(usage?.cogs_usd || 0)}</p>
          </div>
          <div className="card">
            <div className="kicker">Overage list</div>
            <p className="mono">
              fire.weather {money(usage?.overage?.["atlas.fire.weather@v1"] || 0.12)}
              <br />
              watchbox {money(usage?.overage?.["atlas.watchbox.check@v1"] || 0.04)}
            </p>
          </div>
        </div>
        <table className="table" style={{ marginTop: 24 }}>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Invokes</th>
              <th>COGS</th>
            </tr>
          </thead>
          <tbody>
            {(usage?.by_sku || []).map((row) => (
              <tr key={row.sku}>
                <td className="mono">{row.sku}</td>
                <td>{row.count}</td>
                <td>{money(row.cogs_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}

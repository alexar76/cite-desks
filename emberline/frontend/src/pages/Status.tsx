import { useEffect, useState } from "react";
import { SiteNav } from "../components/Nav";
import { PageMeta } from "../components/PageMeta";
import { SiteFooter } from "../components/SiteFooter";
import { api } from "../lib/api";
import { when } from "../lib/format";

export function Status() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
    api.status().then(setStatus).catch(() => setStatus(null));
  }, []);

  const hubMode = String(health?.hub_mode || status?.hub_mode || "—");
  const payMode = String(health?.pay_mode || status?.pay_mode || "—");
  const lastRun = status?.last_completed_run_at ? when(String(status.last_completed_run_at)) : "none yet";

  return (
    <>
      <PageMeta
        title="Status — Emberline"
        description="Emberline status. Hub mode and pay mode without invoking Hub. Not a perimeter or forecast product."
      />
      <SiteNav />
      <section className="section">
        <div className="kicker">Honesty admin</div>
        <h2>Status</h2>
        <p className="sub">{String(status?.copy || "This page does not invoke Hub.")}</p>
        <div className="grid-2">
          <div className="card">
            <h3>Hub rails</h3>
            <p className="mono">
              api {health?.ok ? "ok" : "down"} · hub_mode {hubMode}
            </p>
            <p className="muted" style={{ marginTop: 8 }}>
              {hubMode === "fixture"
                ? "Fixture snapshots. Hub is not charged. Not a live detection."
                : "Live Hub invokes on scheduled watches. This status page still does not invoke Hub."}
            </p>
          </div>
          <div className="card">
            <h3>Pay rail</h3>
            <p className="mono">
              pay_mode {payMode} · {(status?.pay as { enabled?: boolean } | undefined)?.enabled ? "rail on" : "rail off"}
            </p>
            <p className="muted" style={{ marginTop: 8 }}>
              Fixture pay is a test rail. Live pay watches USDC on Base. Different from hub_mode.
            </p>
          </div>
          <div className="card">
            <h3>Last completed run</h3>
            <p className="mono">{lastRun}</p>
            <p className="muted" style={{ marginTop: 8 }}>
              Timestamp only. This page does not buy SKUs.
            </p>
          </div>
          <div className="card">
            <h3>Independent brand</h3>
            <p>Emberline is a third-party consumer of the rails. It is not a Hub wrapper and not an AIMarket product page.</p>
          </div>
        </div>
        <div className="honesty" style={{ justifyContent: "flex-start", padding: "28px 0" }}>
          {(status?.not as string[] | undefined)?.map((item) => (
            <span className="badge" key={item}>
              NOT {item.toUpperCase()}
            </span>
          ))}
        </div>
      </section>
      <SiteFooter />
    </>
  );
}

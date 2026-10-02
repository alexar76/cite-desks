import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type OpsDashboard, type OpsFunnelStep } from "../lib/api";
import { money, when } from "../lib/format";

export function Ops() {
  const [ready, setReady] = useState<boolean | null>(null);
  const [dash, setDash] = useState<OpsDashboard | null>(null);
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await api.opsDashboard();
    setDash(data);
    setReady(true);
  }

  useEffect(() => {
    api.opsMe()
      .then(() => load())
      .catch(() => setReady(false));
  }, []);

  async function onLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.opsLogin(secret.trim());
      setSecret("");
      await load();
    } catch {
      setError("Invalid operator secret.");
      setReady(false);
    } finally {
      setBusy(false);
    }
  }

  async function onLogout() {
    await api.opsLogout().catch(() => undefined);
    setDash(null);
    setReady(false);
  }

  if (ready === null) return <main className="main">Checking ops session…</main>;

  if (!ready || !dash) {
    return (
      <>
        <nav className="site-nav">
          <Link className="brand" to="/">
            <span className="brand-mark" />
            Emberline
          </Link>
        </nav>
        <form className="auth-card" onSubmit={(event) => void onLogin(event)}>
          <div className="kicker">Operator surface</div>
          <h2 className="serif" style={{ marginTop: 8 }}>
            Desk ops
          </h2>
          <p className="muted">
            Cross-tenant meters, pay funnel, and Hub COGS. Not a desk seat. Same secret as mint unless{" "}
            <span className="mono">OPS_SECRET</span> is set.
          </p>
          <label className="field" style={{ marginTop: 18 }}>
            Operator secret
            <input
              type="password"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error && <p className="err">{error}</p>}
          <button className="btn btn-ember" style={{ marginTop: 18, width: "100%" }} type="submit" disabled={busy}>
            Open ops
          </button>
        </form>
      </>
    );
  }

  const k = dash.kpis;
  return (
    <div className="ops">
      <nav className="site-nav">
        <Link className="brand" to="/ops">
          <span className="brand-mark" />
          Emberline ops
        </Link>
        <div className="nav-links">
          <span className="muted mono">{dash.window_days}d window</span>
          <Link to="/desk">Desk</Link>
          <button className="btn" type="button" onClick={() => void onLogout()}>
            Sign out
          </button>
        </div>
      </nav>

      <main className="ops-main">
        <div className="kicker">All seats · not a perimeter</div>
        <h2 className="serif" style={{ margin: "8px 0 12px" }}>
          How the desk is used
        </h2>
        <p className="muted" style={{ maxWidth: 720 }}>
          Live counts from Postgres. Request-a-key mail is not in this funnel. USDC is what settled on Base,
          not list price.
        </p>

        <div className="ops-kpis">
          <Kpi label="Workspaces" value={String(k.workspaces)} hint={`${k.users} users`} spark={dash.series.runs} />
          <Kpi label="Runs · 30d" value={String(k.runs_completed_30d)} hint={`${k.runs_completed} all-time`} spark={dash.series.runs} />
          <Kpi label="USDC in · 30d" value={money(k.usdc_paid_30d)} hint={`${money(k.usdc_paid)} all-time`} spark={dash.series.paid} />
          <Kpi label="Hub COGS · 30d" value={money(k.cogs_usd_30d)} hint={`${k.briefs} briefs`} spark={dash.series.cogs_usd} />
          <Kpi label="Pending invoices" value={String(k.invoices_pending)} hint={`${k.grants_unredeemed} keys waiting`} />
          <Kpi label="Push devices" value={String(k.push_devices)} hint={`${k.watches_active} active watches`} />
        </div>

        <div className="ops-grid">
          <section className="ops-panel">
            <div className="kicker">Pay → evidence funnel</div>
            <h3 className="serif">Where seats stall</h3>
            <Funnel steps={dash.funnel} />
          </section>
          <section className="ops-panel">
            <div className="kicker">Last {dash.window_days} days</div>
            <h3 className="serif">Runs vs settled invoices</h3>
            <LineChart
              days={dash.series.days}
              series={[
                { name: "Completed runs", color: "#e85d04", values: dash.series.runs },
                { name: "Paid invoices", color: "#f0b429", values: dash.series.paid },
              ]}
            />
          </section>
        </div>

        <div className="ops-grid">
          <section className="ops-panel">
            <div className="kicker">Plan mix</div>
            <h3 className="serif">Workspaces by plan</h3>
            <Bars
              rows={dash.plans.map((row) => ({ label: row.plan, value: row.workspaces }))}
              color="#3dd6c6"
            />
          </section>
          <section className="ops-panel">
            <div className="kicker">Evidence · 30d</div>
            <h3 className="serif">Completed run outcomes</h3>
            <Bars
              rows={dash.evidence.map((row) => ({ label: row.status, value: row.count }))}
              color="#7dce8a"
            />
            <div className="ops-sku" style={{ marginTop: 18 }}>
              {dash.by_sku.map((row) => (
                <div key={row.sku} className="ops-sku-row">
                  <span className="mono">{row.sku}</span>
                  <span>
                    {row.count} · {money(row.cogs_usd)}
                  </span>
                </div>
              ))}
            </div>
          </section>
          <section className="ops-panel">
            <div className="kicker">Delivery</div>
            <h3 className="serif">Alert channels</h3>
            {dash.delivery.length === 0 ? (
              <p className="muted">No delivery logs yet.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Channel</th>
                    <th>Ok</th>
                    <th>Fail</th>
                  </tr>
                </thead>
                <tbody>
                  {dash.delivery.map((row) => (
                    <tr key={row.channel}>
                      <td className="mono">{row.channel}</td>
                      <td className="ok">{row.ok}</td>
                      <td className={row.fail ? "err" : ""}>{row.fail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>

        <section className="ops-panel">
          <div className="kicker">Seats</div>
          <h3 className="serif">Every workspace</h3>
          <div className="ops-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Workspace</th>
                  <th>Plan</th>
                  <th>Owner</th>
                  <th>Watches</th>
                  <th>Runs</th>
                  <th>COGS</th>
                  <th>Push</th>
                  <th>Last run</th>
                </tr>
              </thead>
              <tbody>
                {dash.workspaces.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {row.name}
                      <div className="muted mono">{row.id}</div>
                    </td>
                    <td>
                      {row.plan}
                      {row.expired ? <span className="pill quiet"> expired</span> : ""}
                    </td>
                    <td className="mono">{row.email}</td>
                    <td>
                      {row.watches}
                      <span className="muted"> · {row.users} users</span>
                    </td>
                    <td>{row.runs}</td>
                    <td>{money(row.cogs_usd)}</td>
                    <td>{row.push_devices}</td>
                    <td>{when(row.last_run_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <div className="ops-grid">
          <section className="ops-panel">
            <div className="kicker">Recent runs</div>
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Seat</th>
                  <th>Evidence</th>
                  <th>COGS</th>
                </tr>
              </thead>
              <tbody>
                {dash.recent_runs.map((row) => (
                  <tr key={row.id}>
                    <td>{when(row.started_at)}</td>
                    <td>{row.workspace}</td>
                    <td>
                      <span className={`pill ${row.evidence_status === "live_evidence" ? "live" : "quiet"}`}>
                        {row.evidence_status}
                      </span>
                      {row.alerted ? " · alerted" : ""}
                    </td>
                    <td>{money(row.cogs_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section className="ops-panel">
            <div className="kicker">Recent invoices</div>
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Plan</th>
                  <th>Status</th>
                  <th>USDC</th>
                </tr>
              </thead>
              <tbody>
                {dash.recent_invoices.map((row) => (
                  <tr key={row.id}>
                    <td>{when(row.created_at)}</td>
                    <td>{row.plan}</td>
                    <td>{row.status}</td>
                    <td className="mono">{row.amount_usdc.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </main>
    </div>
  );
}

function Kpi({
  label,
  value,
  hint,
  spark,
}: {
  label: string;
  value: string;
  hint: string;
  spark?: number[];
}) {
  return (
    <div className="ops-kpi">
      <div className="kicker">{label}</div>
      <div className="ops-kpi-value">{value}</div>
      <p className="muted">{hint}</p>
      {spark && spark.some((n) => n > 0) ? <Spark values={spark} /> : null}
    </div>
  );
}

function Funnel({ steps }: { steps: OpsFunnelStep[] }) {
  const max = Math.max(...steps.map((step) => step.count), 1);
  return (
    <div className="ops-funnel">
      {steps.map((step, i) => (
        <div key={step.id} className="ops-funnel-row">
          <div className="ops-funnel-meta">
            <span>{step.label}</span>
            <span className="mono">
              {step.count}
              {i > 0 ? ` · ${step.of_prev_pct}%` : ""}
            </span>
          </div>
          <div className="ops-funnel-track">
            <div className="ops-funnel-fill" style={{ width: `${(step.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Bars({ rows, color }: { rows: { label: string; value: number }[]; color: string }) {
  if (rows.length === 0) return <p className="muted">Nothing in this window.</p>;
  const max = Math.max(...rows.map((row) => row.value), 1);
  return (
    <div className="ops-funnel">
      {rows.map((row) => (
        <div key={row.label} className="ops-funnel-row">
          <div className="ops-funnel-meta">
            <span className="mono">{row.label}</span>
            <span className="mono">{row.value}</span>
          </div>
          <div className="ops-funnel-track">
            <div className="ops-funnel-fill" style={{ width: `${(row.value / max) * 100}%`, background: color }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Spark({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  const d = values
    .map((value, i) => {
      const x = values.length === 1 ? 0 : (i / (values.length - 1)) * 100;
      const y = 18 - (value / max) * 16;
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg className="ops-spark" viewBox="0 0 100 20" preserveAspectRatio="none" aria-hidden>
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function LineChart({
  days,
  series,
}: {
  days: string[];
  series: { name: string; color: string; values: number[] }[];
}) {
  const width = 640;
  const height = 200;
  const pad = { l: 28, r: 8, t: 12, b: 28 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const max = Math.max(...series.flatMap((row) => row.values), 1);
  const points = (values: number[]) =>
    values
      .map((value, i) => {
        const x = pad.l + (values.length === 1 ? 0 : (i / (values.length - 1)) * innerW);
        const y = pad.t + innerH - (value / max) * innerH;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  const ticks = useMemo(() => [days[0], days[Math.floor(days.length / 2)], days[days.length - 1]], [days]);

  return (
    <div>
      <svg className="ops-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Runs and paid invoices over time">
        {[0.25, 0.5, 0.75, 1].map((frac) => {
          const y = pad.t + innerH - frac * innerH;
          return <line key={frac} x1={pad.l} x2={width - pad.r} y1={y} y2={y} stroke="rgba(244,236,224,0.08)" />;
        })}
        {series.map((row) => (
          <polyline key={row.name} fill="none" stroke={row.color} strokeWidth="2.2" points={points(row.values)} />
        ))}
        {ticks.map((label, i) => (
          <text key={label} x={pad.l + (i / 2) * innerW} y={height - 8} fill="#8a7b6d" fontSize="11">
            {label.slice(5)}
          </text>
        ))}
      </svg>
      <div className="ops-legend">
        {series.map((row) => (
          <span key={row.name}>
            <i style={{ background: row.color }} />
            {row.name}
          </span>
        ))}
      </div>
    </div>
  );
}

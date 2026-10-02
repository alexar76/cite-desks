import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { SideNav } from "../components/Nav";
import { api } from "../lib/api";
import { when } from "../lib/format";
import type { SessionUser, Watch } from "../lib/types";

export function Desk() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [me, setMe] = useState<SessionUser | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    const [user, list] = await Promise.all([api.me(), api.watches()]);
    setMe(user);
    setWatches(list);
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  async function run(id: string) {
    setBusy(id);
    try {
      const result = await api.runWatch(id);
      await load();
      if (result.brief_id) window.location.href = `/briefs/${result.brief_id}`;
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="app-shell">
      <SideNav />
      <main className="main">
        <div className="topbar">
          <div>
            <div className="kicker">{me?.workspace.name} · {me?.workspace.plan}</div>
            <h2 className="serif" style={{ margin: "6px 0" }}>
              Watches
            </h2>
            <p className="muted">Each watch is a named box. Emberline does not interpolate a fire shape between points.</p>
          </div>
          <Link className="btn btn-ember" to="/watches/new">
            New watch
          </Link>
        </div>
        {watches.length === 0 ? (
          <div className="card" style={{ maxWidth: 640 }}>
            <div className="kicker">First ten minutes</div>
            <h3>Name a box. Run once. Download the pack.</h3>
            <p>Delivery is optional. Slack, HTTPS webhooks, and desk push on an installed PWA. Emberline does not email alerts.</p>
            <ol className="onboard-steps">
              <li>Draw a bbox (max 40° × 30°). Numbers still work if you already have them.</li>
              <li>Save the watch, copy the webhook secret if you will use HMAC, then Run now.</li>
              <li>Open the brief and download the cite pack. That archive is the product.</li>
            </ol>
            <Link className="btn btn-ember" to="/watches/new">
              Draw the box
            </Link>
          </div>
        ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Box</th>
              <th>Cadence</th>
              <th>Last run</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {watches.map((w) => (
              <tr key={w.id}>
                <td>
                  <Link to={`/watches/${w.id}`}>{w.name}</Link>
                  <div className="muted mono">{w.status} · {w.policy}</div>
                </td>
                <td className="mono">
                  {w.west}, {w.south} → {w.east}, {w.north}
                </td>
                <td>{w.schedule}</td>
                <td>{when(w.last_run_at)}</td>
                <td>
                  <button className="btn" disabled={busy === w.id} onClick={() => run(w.id)}>
                    {busy === w.id ? "Running…" : "Run now"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </main>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { SideNav } from "../components/Nav";
import { api } from "../lib/api";
import { money, when } from "../lib/format";
import type { ArchiveRow } from "../lib/types";

export function Archive() {
  const [rows, setRows] = useState<ArchiveRow[]>([]);
  useEffect(() => {
    api.archive().then(setRows).catch(() => setRows([]));
  }, []);

  return (
    <div className="app-shell">
      <SideNav />
      <main className="main">
        <div className="kicker">Retention is the product</div>
        <h2 className="serif">Archive</h2>
        <p className="muted">Alerts fade. The signed brief is what you cite in intake, news, and audit.</p>
        <table className="table">
          <thead>
            <tr>
              <th>When</th>
              <th>Watch</th>
              <th>Evidence</th>
              <th>Alert</th>
              <th>COGS</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="mono">{when(row.started_at)}</td>
                <td>{row.watch_name}</td>
                <td>
                  <span className={`pill ${row.evidence_status === "live_evidence" ? "live" : "quiet"}`}>
                    {row.evidence_status}
                  </span>
                </td>
                <td>{row.alerted ? "yes" : "—"}</td>
                <td>{money(row.cogs_usd)}</td>
                <td>{row.brief_id ? <Link to={`/briefs/${row.brief_id}`}>Open brief</Link> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}

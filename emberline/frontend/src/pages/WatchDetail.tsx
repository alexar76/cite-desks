import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EvidenceMap } from "../components/EvidenceMap";
import { SideNav } from "../components/Nav";
import { api } from "../lib/api";
import { money, when } from "../lib/format";
import type { ArchiveRow, Watch } from "../lib/types";

export function WatchDetail() {
  const { id } = useParams();
  const [watch, setWatch] = useState<Watch | null>(null);
  const [runs, setRuns] = useState<ArchiveRow[]>([]);

  useEffect(() => {
    if (!id) return;
    api.watch(id).then(setWatch).catch(() => setWatch(null));
    api.watchRuns(id).then(setRuns).catch(() => setRuns([]));
  }, [id]);

  if (!watch) {
    return (
      <div className="app-shell">
        <SideNav />
        <main className="main">Loading watch…</main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <SideNav />
      <main className="main">
        <div className="topbar">
          <div>
            <div className="kicker">{watch.id}</div>
            <h2 className="serif" style={{ margin: "6px 0" }}>
              {watch.name}
            </h2>
          </div>
          <Link className="btn" to="/desk">
            All watches
          </Link>
        </div>
        <EvidenceMap bbox={watch} hotspots={[]} />
        <table className="table" style={{ marginTop: 24 }}>
          <thead>
            <tr>
              <th>Run</th>
              <th>Status</th>
              <th>Evidence</th>
              <th>COGS</th>
              <th>Brief</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td className="mono">{when(run.started_at)}</td>
                <td>{run.status}{run.alerted ? " · alerted" : ""}</td>
                <td>
                  <span className={`pill ${run.evidence_status === "live_evidence" ? "live" : "quiet"}`}>
                    {run.evidence_status}
                  </span>
                </td>
                <td>{money(run.cogs_usd)}</td>
                <td>{run.brief_id ? <Link to={`/briefs/${run.brief_id}`}>Open</Link> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}

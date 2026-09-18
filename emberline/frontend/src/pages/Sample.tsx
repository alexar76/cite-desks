import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BriefDocument } from "../components/BriefDocument";
import { PageMeta } from "../components/PageMeta";
import { SiteFooter } from "../components/SiteFooter";
import { SiteNav } from "../components/Nav";
import { api } from "../lib/api";
import { isBrief, type Brief } from "../lib/types";

const READ = [
  [
    "Badges",
    "Every brief stamps NOT A PERIMETER / NOT A FORECAST / NOT AN EVACUATION ORDER. If a vendor map drew a red shape Emberline did not store, that shape is not ours.",
  ],
  [
    "evidence_status",
    "live_evidence means LIVE thermal points existed on this run. no_live_evidence means the LIVE feed was empty — not that the ground is safe, and not a license to paste SIM detections.",
  ],
  [
    "Points, not outlines",
    "Hotspots are lat/lon + brightness. Cloud, revisit, and sensor limits apply. A disappeared point is not containment.",
  ],
  [
    "Run delta",
    "Appeared / disappeared / brightened / dimmed versus the prior completed brief on the same watch. Explicitly not a spread model.",
  ],
];

const PACK = [
  ["00-README.txt", "How to cite: brief id, time, evidence_status, receipt digest"],
  ["01-cover.pdf", "Human cover plus LIVE table and delta"],
  ["02-brief.json", "Normalized Emberline brief"],
  ["03-delta.json", "Run-to-run comparison (not a spread model)"],
  ["04-receipt.json", "ATLAS receipt panel as stored"],
  ["raw/", "Hub payloads exactly as received"],
  ["SHA256SUMS", "Hashes of every other file; re-download of the same brief is byte-identical"],
];

export function Sample() {
  const [brief, setBrief] = useState<Brief | null>(null);
  useEffect(() => {
    api.sampleBrief().then((payload) => setBrief(isBrief(payload) ? payload : null)).catch(() => setBrief(null));
  }, []);
  return (
    <>
      <PageMeta
        title="Sample brief — Emberline"
        description="Read a fixture Emberline evidence brief and download the cite pack. Detections you can cite — not perimeters we invent."
      />
      <SiteNav />
      <section className="section">
        <div className="kicker">Sample artifact</div>
        <h2 className="serif">A brief you can cite.</h2>
        <p className="sub">
          Fixture tape for a named box (CA Transmission Corridor). This is not a live Hub invoke.
          Download the pack, then request a desk key if you want your own box on a schedule.
        </p>
        <div className="brief-stage" style={{ marginTop: 28 }}>
          {brief ? (
            <BriefDocument brief={brief} sample publicView />
          ) : (
            <div className="paper">Loading sample brief…</div>
          )}
          <div>
            <div className="card">
              <h3>Cite pack</h3>
              <p>The object you hand to intake: cover PDF, brief, delta, receipt, raw Hub payloads, SHA256SUMS.</p>
              <a className="btn btn-ember" href="/api/public/sample-cite-pack">
                Download sample pack
              </a>
            </div>
            <div className="card" style={{ marginTop: 16 }}>
              <h3>Next</h3>
              <p>No self-serve signup. Request a key, or open the desk if you already have one.</p>
              <div className="hero-actions" style={{ marginTop: 12 }}>
                <Link className="btn btn-ember" to="/request">
                  Request a desk key
                </Link>
                <Link className="btn" to="/login">
                  Open the desk
                </Link>
              </div>
            </div>
            <div className="card" style={{ marginTop: 16 }}>
              <h3>Who this is for</h3>
              <p>
                Utility / ROW desks, municipal planning (not 911), insurer or MGA intake, local
                news and OSINT wildfire desks. Not a consumer panic map.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="kicker">How to read it</div>
        <h2>What survives an audit.</h2>
        <div className="grid-2" style={{ marginTop: 28 }}>
          {READ.map(([title, copy]) => (
            <div className="card" key={title}>
              <h3>{title}</h3>
              <p>{copy}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="kicker">Versus a dashboard</div>
        <h2>Points stay points.</h2>
        <p className="sub">We do not name other vendors. This is the failure mode Emberline was built to refuse.</p>
        <div className="table-wrap" style={{ marginTop: 28 }}>
          <table className="table compare-table">
            <thead>
              <tr>
                <th></th>
                <th>Typical wildfire dashboard</th>
                <th>Emberline brief</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Geometry", "Thermal hits upgraded into a red polygon", "Lat/lon points only; no invented outline"],
                ["Empty feed", "Often filled with demo or SIM fire", "no_live_evidence. SIM never rides a LIVE brief"],
                ["Time", "A pretty now", "Run tape plus delta versus the prior brief"],
                ["Hand-off", "A screenshot in Slack", "Cite pack with SHA256, receipt, raw payloads"],
                ["Legal strip", "Rarely printed on the artifact", "Stamped on every brief"],
              ].map(([label, left, right]) => (
                <tr key={label}>
                  <th>{label}</th>
                  <td>{left}</td>
                  <td>{right}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="kicker">Inside the zip</div>
        <h2>What you download.</h2>
        <table className="table" style={{ marginTop: 28 }}>
          <tbody>
            {PACK.map(([file, copy]) => (
              <tr key={file}>
                <th className="mono">{file}</th>
                <td>{copy}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted" style={{ marginTop: 16 }}>
          Quote the brief id, generated_at, evidence_status, and receipt digest. Do not re-draw
          geometry Emberline did not store.
        </p>
      </section>
      <SiteFooter />
    </>
  );
}

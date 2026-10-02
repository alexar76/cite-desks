import { Link } from "react-router-dom";
import { PageMeta } from "../components/PageMeta";
import { SiteFooter } from "../components/SiteFooter";
import { SiteNav } from "../components/Nav";
import { DESK_MAIL } from "../lib/site";

const BOILERPLATE = `Emberline is an independent fire evidence desk. On a schedule it buys attested thermal-detection and bounded-weather artifacts, writes a fail-closed brief, and files a citeable archive. It keeps NASA FIRMS-class detections as points. It does not draw a fire perimeter, forecast spread, score risk 0–100, or issue evacuation orders. Empty LIVE stays empty: simulation detections never appear on a LIVE brief. The commercial product is the watch, the tape, and the receipt — not invented geometry.`;

export function Press() {
  return (
    <>
      <PageMeta
        title="Press kit — Emberline"
        description="Boilerplate, facts, and assets for Emberline, the fire evidence desk. Not a perimeter, forecast, or evacuation product."
      />
      <SiteNav />
      <article className="legal">
        <div className="kicker">Press kit</div>
        <h1 className="serif">Emberline in one paragraph</h1>
        <p>{BOILERPLATE}</p>
        <p>
          Public origin <a href="https://emberlinedesk.com">emberlinedesk.com</a>. Desk mail{" "}
          <a href={`mailto:${DESK_MAIL}`}>{DESK_MAIL}</a>. Sample artifact{" "}
          <Link to="/sample">/sample</Link>. Cite pack{" "}
          <a href="/api/public/sample-cite-pack">emberline_sample_cite.zip</a>.
        </p>

        <h2 className="serif">Facts</h2>
        <table className="table">
          <tbody>
            {[
              ["Product", "Fire Evidence Desk (B2B monitoring aid)"],
              ["Unit of work", "A named bbox a person owns, on a 15/30/60 cadence"],
              ["Artifact", "Brief + run delta + cite pack (PDF, JSON, raw Hub, SHA256)"],
              ["Rails", "atlas.watchbox.check@v1 · atlas.fire.weather@v1"],
              ["Checkout", "USDC on Base, or wire that mints the same prepaid desk key"],
              ["Not", "Perimeter, forecast, insurer, satellite operator, 911, consumer panic map"],
            ].map(([k, v]) => (
              <tr key={k}>
                <th>{k}</th>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h2 className="serif">Do / do not</h2>
        <div className="grid-2" style={{ margin: "24px 0 8px" }}>
          <div className="card">
            <h3>Do say</h3>
            <p>
              Citeable thermal detections. Fail-closed LIVE vs SIM. Signed receipt. Archive you can
              hand to intake. Independent brand on ATLAS/GAIA rails.
            </p>
          </div>
          <div className="card">
            <h3>Do not say</h3>
            <p>
              “Detects every fire.” “Shows the burn perimeter.” “Predicts spread.” “Tells you when
              to evacuate.” “AIMarket product.” Invented quotes or logos we did not supply.
            </p>
          </div>
        </div>

        <h2 className="serif">Assets</h2>
        <p>
          Wordmark is the site nav. Do not redraw points into a polygon for a story graphic and
          attribute it to Emberline.
        </p>
        <div className="hero-actions" style={{ marginTop: 8 }}>
          <a className="btn" href="/og.png">
            Open Graph 1200×630
          </a>
          <a className="btn" href="/favicon.svg">
            Mark (SVG)
          </a>
          <Link className="btn btn-ember" to="/sample">
            Sample brief
          </Link>
        </div>
      </article>
      <SiteFooter />
    </>
  );
}

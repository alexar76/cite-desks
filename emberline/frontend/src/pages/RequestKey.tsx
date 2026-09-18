import { useEffect, useState } from "react";
import { SiteNav } from "../components/Nav";
import { PageMeta } from "../components/PageMeta";
import { SiteFooter } from "../components/SiteFooter";
import { api } from "../lib/api";
import { DESK_MAIL } from "../lib/site";

const MAIL = DESK_MAIL;
const SUBJECT = encodeURIComponent("Emberline desk key request");
const BODY = encodeURIComponent(
  "Plan (Solo / Team / Desk):\nOrganization:\nBilling contact:\nNamed bbox (optional):\n",
);

export function RequestKey() {
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    api.health().then((h) => setDemo(Boolean(h.demo))).catch(() => setDemo(false));
  }, []);
  return (
    <>
      <PageMeta
        title="Request a desk key — Emberline"
        description="Request a prepaid Emberline desk key. No self-serve signup. Wire, invoice, or USDC on Base."
      />
      <SiteNav />
      <section className="section" style={{ maxWidth: 720 }}>
        <div className="kicker">Concierge</div>
        <h2 className="serif">Request a desk key</h2>
        <p className="sub">
          There is no self-serve signup. We mint a prepaid <span className="mono">emb_…</span> key
          after wire or invoice. USDC on Base remains available if you already have a wallet.
        </p>
        <div className="card" style={{ marginTop: 28 }}>
          <h3>What to send</h3>
          <p>
            Plan (Solo $49 / Team $149 / Desk $499), organization, billing contact, and the box you
            intend to watch. We do not open Hub spend until the key exists.
          </p>
          <div className="hero-actions" style={{ marginTop: 16 }}>
            {demo ? (
              <p className="muted">DEMO · checkout closed. This host is not a merchant.</p>
            ) : (
              <>
                <a className="btn btn-ember" href={`mailto:${MAIL}?subject=${SUBJECT}&body=${BODY}`}>
                  Email the desk
                </a>
                <a className="btn" href="/pay">
                  Pay USDC on Base
                </a>
              </>
            )}
          </div>
          <p className="muted" style={{ marginTop: 16 }}>
            {MAIL}
          </p>
        </div>
      </section>
      <SiteFooter />
    </>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { BriefDocument } from "../components/BriefDocument";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { Globe } from "../components/Globe";
import { PageMeta } from "../components/PageMeta";
import { SiteFooter } from "../components/SiteFooter";
import { SiteNav } from "../components/Nav";
import { api } from "../lib/api";
import { isBrief, type Brief } from "../lib/types";
import { useI18n } from "../lib/I18nProvider";

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.7, delay, ease: [0.22, 1, 0.36, 1] },
});

const reveal = {
  initial: { opacity: 0, y: 34 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, amount: 0.1 },
  transition: { duration: 0.75, ease: [0.22, 1, 0.36, 1] },
} as const;

export function Landing() {
  const { t } = useI18n();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    api.sampleBrief().then((payload) => setBrief(isBrief(payload) ? payload : null)).catch(() => setBrief(null));
    api.health().then((h) => setDemo(Boolean(h.demo))).catch(() => setDemo(false));
  }, []);

  return (
    <>
      <PageMeta
        title="Emberline — Evidence for the box you watch"
        description="B2B fire evidence desk. Scheduled LIVE thermal detections, bounded weather, signed receipts, and a citeable archive. Not a perimeter. Not a forecast."
      />
      <SiteNav />
      <header className="hero-cinematic">
        <div className="hero-copy">
          <motion.div className="kicker" {...fade(0)}>
            {t.kicker}
          </motion.div>
          <motion.h1 {...fade(0.08)}>{t.hero_title}</motion.h1>
          <motion.p className="lede" {...fade(0.16)}>
            {t.lede}
          </motion.p>
          <motion.div className="hero-actions" {...fade(0.24)}>
            <Link className="btn btn-ember" to="/sample">
              {t.cta_sample}
            </Link>
            <Link className="btn" to="/login">
              {t.cta_desk}
            </Link>
          </motion.div>
          <motion.div className="hero-meta" {...fade(0.32)}>
            <div>
              <b>Fail-closed</b>
              empty LIVE stays empty
            </div>
            <div>
              <b>Cite pack</b>
              PDF · JSON · SHA256
            </div>
            <div>
              <b>Named box</b>
              a person owns it
            </div>
          </motion.div>
        </div>
        <div className="globe-stage">
          <ErrorBoundary>
            <Globe />
          </ErrorBoundary>
        </div>
      </header>

      <div className="ticker" aria-hidden>
        <div className="ticker-track">
          {[...t.ticker, ...t.ticker].map((item, i) => (
            <span key={`${item}-${i}`} className={item.includes("SIGNED") ? "cyan" : item.includes("AID") ? "quiet" : ""}>
              {item}
            </span>
          ))}
        </div>
      </div>

      <motion.section className="section" id="beyond" {...reveal}>
        <div className="kicker">{t.beyond_kicker}</div>
        <h2>{t.beyond_h2}</h2>
        <p className="sub">{t.beyond_sub}</p>
        <div className="grid-3" style={{ marginTop: 36 }}>
          {[
            [t.b1_t, t.b1_p],
            [t.b2_t, t.b2_p],
            [t.b3_t, t.b3_p],
          ].map(([title, copy]) => (
            <div className="card" key={title}>
              <h3>{title}</h3>
              <p>{copy}</p>
            </div>
          ))}
        </div>
      </motion.section>

      <motion.section className="section" id="product" {...reveal}>
        <div className="kicker">{t.product_kicker}</div>
        <h2>
          {t.product_h2_a}
          <br />
          {t.product_h2_b}
        </h2>
        <p className="sub">{t.product_sub}</p>
        <div className="grid-3" style={{ marginTop: 36 }}>
          {[
            ["01", t.p1_t, t.p1_p],
            ["02", t.p2_t, t.p2_p],
            ["03", t.p3_t, t.p3_p],
          ].map(([idx, title, copy]) => (
            <div className="card" key={idx}>
              <div className="idx">{idx}</div>
              <h3>{title}</h3>
              <p>{copy}</p>
            </div>
          ))}
        </div>
      </motion.section>

      <motion.section className="section" id="evidence" {...reveal}>
        <div className="kicker">{t.evidence_kicker}</div>
        <h2>{t.evidence_h2}</h2>
        <div className="brief-stage">
          {brief ? (
            <ErrorBoundary fallback={<div className="paper">{t.sample_unavailable}</div>}>
              <BriefDocument brief={brief} compact sample publicView />
            </ErrorBoundary>
          ) : (
            <div className="paper">{t.sample_loading}</div>
          )}
          <div>
            <div className="card">
              <h3>{t.e1_t}</h3>
              <p>{t.e1_p}</p>
            </div>
            <div className="card" style={{ marginTop: 16 }}>
              <h3>{t.e2_t}</h3>
              <p>{t.e2_p}</p>
            </div>
            <div className="card" style={{ marginTop: 16 }}>
              <h3>{t.e3_t}</h3>
              <p>{t.e3_p}</p>
              <a className="btn btn-ember" href="/api/public/sample-cite-pack">
                {t.e3_btn}
              </a>
            </div>
            <div className="card" style={{ marginTop: 16 }}>
              <h3>{t.e4_t}</h3>
              <p>
                {t.e4_p_a} <span className="mono">atlas.fire.weather@v1</span> +{" "}
                <span className="mono">atlas.watchbox.check@v1</span>. {t.e4_p_b}
              </p>
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section className="section" id="pricing" {...reveal}>
        <div className="kicker">{t.pricing_kicker}</div>
        <h2>{t.pricing_h2}</h2>
        <p className="sub">{t.pricing_sub}</p>
        <div className="grid-3" style={{ marginTop: 36 }}>
          {[
            ["solo", "Solo", "$49", t.plan_solo_copy, false],
            ["team", "Team", "$149", t.plan_team_copy, true],
            ["desk", "Desk", "$499", t.plan_desk_copy, false],
          ].map(([code, name, price, copy, featured]) => (
            <div className={`price-card ${featured ? "featured" : ""}`} key={String(name)}>
              <div className="kicker">{String(name)}</div>
              <div className="price">
                {String(price)}
                <span>{t.per_mo}</span>
              </div>
              <p className="muted">{String(copy)}</p>
              <ul>
                <li>{t.pricing_b1}</li>
                <li>{t.pricing_b2}</li>
                <li>{t.pricing_b3}</li>
              </ul>
              <div className="hero-actions" style={{ marginTop: 16 }}>
                {demo ? (
                  <span className="muted">DEMO · checkout closed</span>
                ) : (
                  <>
                    <Link className="btn btn-ember" to="/request">
                      {t.cta_request}
                    </Link>
                    <Link className="btn" to={`/pay?plan=${code}`}>
                      {t.cta_pay}
                    </Link>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </motion.section>

      <SiteFooter />
    </>
  );
}

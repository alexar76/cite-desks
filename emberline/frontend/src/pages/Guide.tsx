import { Link } from "react-router-dom";
import { SiteNav } from "../components/Nav";
import { PageMeta } from "../components/PageMeta";
import { SiteFooter } from "../components/SiteFooter";
import { useI18n } from "../lib/I18nProvider";

export function Guide() {
  const { t } = useI18n();
  return (
    <>
      <PageMeta title={`${t.guide_title} — Emberline`} description={t.guide_lede} />
      <SiteNav />
      <article className="legal">
        <div className="kicker">{t.guide_kicker}</div>
        <h1 className="serif">{t.guide_title}</h1>
        <p>{t.guide_lede}</p>
        {t.guide.map((sec) => (
          <section key={sec.id} id={sec.id}>
            <h2>{sec.title}</h2>
            {sec.body.map((p) => (
              <p key={p.slice(0, 24)}>{p}</p>
            ))}
          </section>
        ))}
        <p>
          <Link to="/legal">{t.legal_h1}</Link>
        </p>
      </article>
      <SiteFooter />
    </>
  );
}

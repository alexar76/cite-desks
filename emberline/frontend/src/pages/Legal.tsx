import { SiteNav } from "../components/Nav";
import { PageMeta } from "../components/PageMeta";
import { SiteFooter } from "../components/SiteFooter";
import { CANONICAL_HOST, CANONICAL_ORIGIN, DESK_MAIL } from "../lib/site";
import { useI18n } from "../lib/I18nProvider";

export function Legal() {
  const { t } = useI18n();
  return (
    <>
      <PageMeta
        title={`${t.legal_h1} — Emberline`}
        description={t.legal_p1}
      />
      <SiteNav />
      <article className="legal">
        <div className="kicker">{t.legal_kicker}</div>
        <h1 className="serif">{t.legal_h1}</h1>
        <p>{t.legal_p1}</p>
        <p>{t.legal_p2}</p>
        <p>
          Emberline does not guarantee detection completeness, does not pay claims, and does not
          instruct evacuation. Use in regulated insurance workflows requires your own compliance
          review. Demo mode may replay fixtures; live mode invokes Hub SKUs and incurs COGS.
        </p>
        <p>
          Prepaid desk keys are anonymous entitlements: Emberline stores a key hash, not a legal
          name. Named seats use email/password. Public checkout is USDC on Base only. The exact
          micro-amount is the invoice identifier; a rounded transfer will not settle. After the
          configured confirmations a desk key is shown on the invoice URL. There is no automated
          refund. Design-partner wire still mints through <code>PAY_MINT_SECRET</code>. These terms
          are a product draft.
        </p>
        <p>
          Implementation and operator manuals: <a href="/docs/enterprise/">enterprise documentation</a>.
          Online guide: <a href="/guide">/guide</a>.
          Contact: <a href={`mailto:${DESK_MAIL}`}>{DESK_MAIL}</a>.
          Public origin: <a href={CANONICAL_ORIGIN}>{CANONICAL_HOST}</a>.
        </p>
      </article>
      <SiteFooter />
    </>
  );
}

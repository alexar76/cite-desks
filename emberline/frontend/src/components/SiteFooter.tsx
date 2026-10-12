import { Link } from "react-router-dom";
import { CANONICAL_HOST, CANONICAL_ORIGIN, DESK_MAIL } from "../lib/site";
import { useI18n } from "../lib/I18nProvider";

export function SiteFooter() {
  const { t } = useI18n();
  return (
    <footer className="site-footer">
      <div>{t.footer}</div>
      <div className="row">
        <a href={CANONICAL_ORIGIN}>{CANONICAL_HOST}</a>
        <a href={`mailto:${DESK_MAIL}`}>{DESK_MAIL}</a>
        <Link to="/guide">{t.nav_guide}</Link>
        <Link to="/sample">{t.nav_sample}</Link>
        <Link to="/legal">{t.legal_h1}</Link>
        <Link to="/status">{t.nav_status}</Link>
        <a href="/docs/enterprise/">Enterprise docs</a>
        <Link to="/login">{t.nav_open}</Link>
      </div>
    </footer>
  );
}

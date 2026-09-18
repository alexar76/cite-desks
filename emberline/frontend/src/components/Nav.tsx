import { Link, NavLink } from "react-router-dom";
import { api } from "../lib/api";
import { useI18n } from "../lib/I18nProvider";
import { DeskPwa } from "./DeskPwa";
import { RailsBanner } from "./RailsBanner";

export function SiteNav() {
  const { t, locale, setLocale, locales } = useI18n();
  return (
    <>
      <RailsBanner />
      <nav className="site-nav">
        <Link className="brand" to="/">
          <span className="brand-mark" />
          Emberline
        </Link>
        <div className="nav-links">
          <a href="/#beyond">{t.nav_desk}</a>
          <a href="/#product">{t.nav_product}</a>
          <Link to="/sample">{t.nav_sample}</Link>
          <Link to="/guide">{t.nav_guide}</Link>
          <a href="/#pricing">{t.nav_pricing}</a>
          <Link to="/status">{t.nav_status}</Link>
          <label className="lang-switch">
            <select value={locale} onChange={(e) => setLocale(e.target.value as typeof locale)} aria-label={t.nav_language}>
              {locales.map((loc) => (
                <option key={loc.code} value={loc.code}>
                  {loc.name}
                </option>
              ))}
            </select>
          </label>
          <Link className="btn btn-ember" to="/login">
            {t.nav_open}
          </Link>
        </div>
      </nav>
    </>
  );
}

export function SideNav() {
  const { t } = useI18n();
  const items = [
    ["/desk", t.nav_desk],
    ["/archive", t.nav_archive],
    ["/billing", t.nav_billing],
    ["/status", t.nav_status],
    ["/guide", t.nav_guide],
  ];
  return (
    <aside className="side">
      <RailsBanner />
      <Link className="brand" to="/desk" style={{ marginBottom: 28 }}>
        <span className="brand-mark" />
        Emberline
      </Link>
      {items.map(([to, label]) => (
        <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>
          {label}
        </NavLink>
      ))}
      <div style={{ marginTop: 28, display: "grid", gap: 8 }}>
        <Link className="btn" to="/">
          {t.nav_marketing}
        </Link>
        <DeskPwa />
        <button
          className="btn"
          type="button"
          onClick={() => {
            void api.logout().finally(() => {
              window.location.href = "/login";
            });
          }}
        >
          {t.nav_sign_out}
        </button>
      </div>
    </aside>
  );
}

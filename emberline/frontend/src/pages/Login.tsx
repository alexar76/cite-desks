import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { SiteNav } from "../components/Nav";
import { useI18n } from "../lib/I18nProvider";

export function Login() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"password" | "key">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [deskKey, setDeskKey] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      if (mode === "key") {
        await api.redeem(deskKey.trim());
      } else {
        await api.login(email.trim(), password);
      }
      navigate("/desk");
    } catch {
      setError(mode === "key" ? t.login_key_err : t.login_err);
    }
  }

  return (
    <>
      <SiteNav />
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="kicker">{t.login_kicker}</div>
        <h2 className="serif" style={{ marginTop: 8 }}>
          {t.login_h2}
        </h2>
        <p className="muted">{t.login_lede}</p>
        <div className="hero-actions" style={{ marginTop: 16 }}>
          <button type="button" className={`btn ${mode === "password" ? "btn-ember" : ""}`} onClick={() => setMode("password")}>
            {t.login_password}
          </button>
          <button type="button" className={`btn ${mode === "key" ? "btn-ember" : ""}`} onClick={() => setMode("key")}>
            {t.login_key}
          </button>
        </div>
        {mode === "password" ? (
          <>
            <label className="field" style={{ marginTop: 18 }}>
              {t.login_email}
              <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
            </label>
            <label className="field" style={{ marginTop: 12 }}>
              {t.login_password}
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </label>
          </>
        ) : (
          <label className="field" style={{ marginTop: 18 }}>
            {t.login_key}
            <input value={deskKey} onChange={(e) => setDeskKey(e.target.value)} autoComplete="off" placeholder="emb_…" />
          </label>
        )}
        {error && <p className="err">{error}</p>}
        <button className="btn btn-ember" style={{ marginTop: 18, width: "100%" }} type="submit">
          {t.login_enter}
        </button>
        <p className="muted" style={{ marginTop: 16 }}>
          <Link to="/">Back to marketing</Link>
        </p>
      </form>
    </>
  );
}

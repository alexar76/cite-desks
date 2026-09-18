import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { SiteNav } from "../components/Nav";
import { api } from "../lib/api";
import type { PayRail } from "../lib/basePay";

const PLAN_COPY: Record<string, string> = {
  solo: "2 watches · 200 runs · 30-day archive",
  team: "10 watches · 1,000 runs · Slack · 90-day archive",
  desk: "50 watches · 5,000 runs · API · 365-day archive",
};

export function Pay() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [rail, setRail] = useState<PayRail | null>(null);
  const [plan, setPlan] = useState(params.get("plan") || "solo");
  const [method, setMethod] = useState("usdc_base");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.payStatus().then(setRail).catch(() => setRail(null));
  }, []);

  const selected = rail?.plans?.[plan];
  const methods = rail?.methods || [
    { id: "usdc_base", label: "USDC on Base", available: false, reason: "Loading" },
  ];
  const methodOk = methods.some((item) => item.id === method && item.available);
  const closed = rail != null && rail.enabled === false;

  async function place(event: FormEvent) {
    event.preventDefault();
    if (closed) return;
    setError("");
    setBusy(true);
    try {
      const invoice = await api.createOrder(plan, method);
      navigate(invoice.public_path || `/pay/${invoice.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the order.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <SiteNav />
      {closed ? (
        <main className="checkout">
          <div className="kicker">Order</div>
          <h2 className="serif" style={{ marginTop: 8 }}>
            Checkout is closed.
          </h2>
          <p className="muted">
            {rail?.closed_reason || "This host is a reference demo. We are not the merchant."}
          </p>
          <p className="muted" style={{ marginTop: 18 }}>
            <Link to="/sample">Sample brief</Link>
            {" · "}
            <Link to="/login">Already have a key</Link>
          </p>
        </main>
      ) : (
      <form className="checkout" onSubmit={place}>
        <div className="kicker">Order</div>
        <h2 className="serif" style={{ marginTop: 8 }}>
          Choose a desk, then a rail.
        </h2>
        <p className="muted">
          You get a numbered invoice. Crypto is open: USDC on Base. Wire and card are listed so the
          seat is reserved — they do not settle yet.
        </p>

        <div className="kicker" style={{ marginTop: 28 }}>
          1 · Plan
        </div>
        <div className="plan-pick">
          {Object.entries(PLAN_COPY).map(([code, copy]) => {
            const price = rail?.plans?.[code]?.price_usd;
            return (
              <button
                key={code}
                type="button"
                className={`method-card ${plan === code ? "on" : ""}`}
                onClick={() => setPlan(code)}
              >
                <div className="kicker">{code}</div>
                <div className="pick-price">${price ?? "—"}</div>
                <p>{copy}</p>
              </button>
            );
          })}
        </div>

        <div className="kicker" style={{ marginTop: 28 }}>
          2 · Payment method
        </div>
        <div className="method-pick">
          {methods.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`method-card ${method === item.id ? "on" : ""}`}
              disabled={!item.available}
              onClick={() => item.available && setMethod(item.id)}
            >
              <div className="kicker">{item.kind || "rail"}</div>
              <strong>{item.label}</strong>
              <p>{item.available ? "Open · exact USDC amount is the invoice" : item.reason || "Not open yet"}</p>
            </button>
          ))}
        </div>

        <div className="checkout-total">
          <div>
            <div className="kicker">Due</div>
            <div className="pick-price">${selected?.price_usd ?? "—"}</div>
            <p className="muted">
              {selected?.name || plan} · {selected?.days ?? 30} days · {methodOk ? "USDC on Base" : "no open rail"}
            </p>
          </div>
          <button className="btn btn-ember" type="submit" disabled={!methodOk || busy}>
            {busy ? "Writing invoice…" : "Place order · get invoice"}
          </button>
        </div>
        {error && <p className="err">{error}</p>}
        <p className="muted" style={{ marginTop: 18 }}>
          <Link to="/#pricing">Back to pricing</Link>
          {" · "}
          <Link to="/login">Already have a key</Link>
        </p>
      </form>
      )}
    </>
  );
}

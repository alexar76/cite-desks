import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CopyButton } from "../components/CopyButton";
import { SiteNav } from "../components/Nav";
import { api } from "../lib/api";
import { payWithWallet, type Invoice } from "../lib/basePay";
import { when } from "../lib/format";

export function InvoicePage() {
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!invoiceId) return;
    api.payInvoice(invoiceId).then(setInvoice).catch(() => setInvoice(null));
  }, [invoiceId]);

  useEffect(() => {
    if (!invoice || !invoice.claimable) return;
    const poll = window.setInterval(() => {
      void api.payInvoice(invoice.id).then(setInvoice).catch(() => undefined);
    }, 4000);
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      window.clearInterval(poll);
      window.clearInterval(clock);
    };
  }, [invoice?.id, invoice?.claimable]);

  const remaining = useMemo(() => {
    if (!invoice?.expires_at) return "";
    const ms = new Date(invoice.expires_at).getTime() - now;
    if (ms <= 0) return "expired";
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  }, [invoice?.expires_at, now]);

  const graceLeft = useMemo(() => {
    if (!invoice?.claim_deadline) return 0;
    return Math.max(0, Math.round((new Date(invoice.claim_deadline).getTime() - now) / 3600000));
  }, [invoice?.claim_deadline, now]);

  async function walletPay() {
    if (!invoice) return;
    setError("");
    setBusy(true);
    try {
      const tx = await payWithWallet(invoice);
      setInvoice(await api.confirmInvoice(invoice.id, tx).catch(async () => api.payInvoice(invoice.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Wallet send failed.");
    } finally {
      setBusy(false);
    }
  }

  async function simulatePay() {
    if (!invoice) return;
    setError("");
    setBusy(true);
    try {
      setInvoice(await api.simulateInvoice(invoice.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulate failed.");
    } finally {
      setBusy(false);
    }
  }

  async function enterDesk() {
    if (!invoice?.desk_key) return;
    setBusy(true);
    try {
      await api.redeem(invoice.desk_key);
      navigate("/desk");
    } catch {
      setError("Key is on this invoice. Redeem it at login if this session failed.");
      setBusy(false);
    }
  }

  return (
    <>
      <SiteNav />
      <section className="section" style={{ maxWidth: 820 }}>
        <div className="kicker">Invoice</div>
        <h2 className="serif">Your bill.</h2>
        {!invoice ? (
          <p className="muted">Invoice not found.</p>
        ) : (
          <article className="paper invoice-paper">
            <div className="meta">EMBERLINE · COMMERCIAL INVOICE · {invoice.number}</div>
            <h3>{invoice.plan_name} desk</h3>
            <div className="meta">
              Issued {when(invoice.created_at)} · due {when(invoice.expires_at)}
              {invoice.status === "pending" && remaining ? ` · ${remaining} left` : ""}
            </div>
            <div className="stamps">
              <span className="stamp">{invoice.status.toUpperCase()}</span>
              <span className="stamp">{invoice.payment_method_label}</span>
              <span className="stamp">NOT A SUBSCRIPTION CHARGE</span>
            </div>
            <table className="hot-table">
              <thead>
                <tr>
                  <th>line</th>
                  <th>usd</th>
                  <th>due</th>
                </tr>
              </thead>
              <tbody>
                {(invoice.line_items || []).map((row) => (
                  <tr key={row.description}>
                    <td>{row.description}</td>
                    <td>${row.amount_usd}</td>
                    <td>{row.amount_usdc} USDC</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mono" style={{ fontSize: 28, margin: "18px 0 6px" }}>
              {invoice.amount_usdc} USDC
            </p>
            <p className="meta">
              List ${invoice.amount_usd}. Send this exact amount on Base. Rounding will not match.
              {invoice.late_grace_hours > 0 &&
                ` A transfer that lands after the quote lapses still settles for ${invoice.late_grace_hours}h — you do not need a refund.`}
            </p>
            <p className="mono" style={{ fontSize: 12, wordBreak: "break-all", marginTop: 14 }}>
              {invoice.pay_to}
            </p>
            <div className="hero-actions" style={{ marginTop: 14 }}>
              <CopyButton value={invoice.pay_to} label="Copy address" />
              <CopyButton value={invoice.amount_usdc} label="Copy amount" />
              <CopyButton value={`${window.location.origin}${invoice.public_path}`} label="Copy invoice link" />
              <a className="btn" href={`/api/public/pay/invoices/${invoice.id}/pdf`}>
                Download PDF
              </a>
            </div>
            {invoice.claimable && (
              <div className="hero-actions" style={{ marginTop: 12 }}>
                <button className="btn btn-ember" type="button" onClick={() => void walletPay()} disabled={busy}>
                  Pay with wallet
                </button>
                {invoice.fixture && (
                  <button className="btn" type="button" onClick={() => void simulatePay()} disabled={busy}>
                    Simulate USDC (test rail)
                  </button>
                )}
                <a className="btn" href={invoice.eip681}>
                  Open wallet link
                </a>
                <a className="btn" href={invoice.explorer_address} target="_blank" rel="noreferrer">
                  Basescan
                </a>
              </div>
            )}
            {invoice.status === "paid" && invoice.desk_key && (
              <div className="delta-block">
                <div className="kicker" style={{ color: "#9a3412" }}>
                  Paid · desk key
                </div>
                <p className="mono" style={{ wordBreak: "break-all", margin: "8px 0 0" }}>
                  {invoice.desk_key}
                </p>
                <div className="hero-actions" style={{ marginTop: 12 }}>
                  <CopyButton value={invoice.desk_key} label="Copy key" />
                  <button className="btn btn-ember" type="button" onClick={() => void enterDesk()} disabled={busy}>
                    Enter desk
                  </button>
                </div>
              </div>
            )}
            {invoice.tx_hash && (
              <p className="meta" style={{ marginTop: 12 }}>
                Tx{" "}
                <a href={invoice.explorer_tx || "#"} target="_blank" rel="noreferrer">
                  {invoice.tx_hash}
                </a>
              </p>
            )}
            {invoice.status === "expired" && (
              <p className="meta" style={{ marginTop: 12 }}>
                {invoice.claimable ? (
                  <>
                    Quote lapsed, still watching. A transfer to this invoice settles for another{" "}
                    {graceLeft}h — send it, or <Link to="/pay">place a new order</Link>.
                  </>
                ) : (
                  <>
                    Expired. <Link to="/pay">Place a new order</Link>. If you paid anyway, mail{" "}
                    <a href="mailto:desk@emberlinedesk.com">desk@emberlinedesk.com</a> with the tx hash.
                  </>
                )}
              </p>
            )}
            {invoice.status === "paid" && invoice.late && (
              <p className="meta" style={{ marginTop: 12 }}>
                Settled after the quote lapsed, inside the grace window.
              </p>
            )}
          </article>
        )}
        {error && <p className="err">{error}</p>}
        <p className="muted" style={{ marginTop: 20 }}>
          <Link to="/pay">New order</Link>
        </p>
      </section>
    </>
  );
}

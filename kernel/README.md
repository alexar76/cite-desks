# desk_kernel

<p align="center">
  <strong>desk_kernel</strong> — shared evidence-desk rail<br/>
  Hub custody · USDC on Base · card via Stripe · cite packs · webhooks
</p>

Shared evidence-desk kernel. Desks own brand and claim class; this package owns:

- Hub custody (`HubClient`)
- `on_match` vs `always_brief`
- USDC salt invoices (unique micro-amount) **and the settlement that closes them**
- Card checkout through Stripe (`service/card.py`), settled by webhook, refresh or sweep
- Base chain layer: RPC failover, chunked `eth_getLogs`, transfer matching (`desk_kernel.chain`)
- HMAC `t=,v1=` webhooks (SSRF-safe URL)
- Cite pack ZIP (cover PDF + SHA256SUMS, byte-stable)
- Receipt Ed25519 check
- Bbox / point watches, quiet hours, cadence
- Generic FastAPI runtime used by Tideline, Solrecord, Seamark, Plinth

Emberline keeps its fire UI and calls these primitives.

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Checkout: nobody in the loop

| Step | Code | Who acts |
|---|---|---|
| `POST /api/public/pay/invoices` | `pay.create_invoice` | buyer |
| USDC transfer to the treasury | — | buyer's wallet |
| poll every `PAY_SCAN_INTERVAL_SECONDS` | `main._pay_tick` → `pay.scan_payments` | the desk, alone |
| grant + desk key on the invoice | `pay.settle` → `pay.mint_grant` | the desk, alone |
| `GET .../pay/invoices/{id}` | `pay.invoice_view` | buyer's browser polls |
| `POST /api/auth/redeem` | `api.redeem` | the web shell, automatically |

`POST .../invoices/{id}/confirm` is the impatient path: a pasted tx hash settles now
instead of at the next poll. Both paths converge on `settle()`, and `settle()` is the only
place a grant is minted, so **one transfer buys exactly one desk key**.

The buyer's browser opens `/pay/<invoice_id>`, so a reload or a return from the wallet
resumes the same quote. `GET /api/public/health` reports `checkout.open`,
`checkout.reason`, and `checkout.settlement` — read it before believing a desk sells.

### Failing closed

The rail refuses to quote rather than take money it cannot honour:

- no `PAY_BASE_ADDRESS`, an invalid address, or the `0x1111…` placeholder in live mode →
  checkout closed, `503`, and the reason is on `/api/public/pay/status`;
- production additionally refuses to **boot** in those states (`assert_runtime_safety`);
- an amount that does not match any claimable invoice is ignored, not "close enough";
- a lapsed quote keeps its amount through `PAY_LATE_GRACE_HOURS` so a slow wallet is not a
  manual refund, and a transfer after that window does not settle;
- a tx hash that already settled an invoice cannot settle another one.

`PAY_MODE=fixture` runs the same scanner against an in-process chain
(`service/payfixture.py`) — deliberately not a shortcut to `paid`, so the demo exercises
the production path. Fixture mode is unavailable when `APP_ENV=production`.

## Card checkout (Stripe)

The same desk key, paid by card through Stripe Checkout (`service/card.py`). The desk never
sees the card: it opens a Checkout Session and turns the paid session into a key.

| Step | Code | Who acts |
|---|---|---|
| `POST /api/public/pay/card {plan}` | `card.create_card_invoice` | buyer → `card.checkout_url` |
| pays on checkout.stripe.com | — | buyer |
| `POST /api/public/pay/stripe/webhook` | `card.handle_webhook` → `card.settle_card` | Stripe |
| `POST .../invoices/{id}/card/refresh` | `card.refresh_card` | the web shell, back from Stripe |
| poll every `PAY_SCAN_INTERVAL_SECONDS` | `card.sweep_card_invoices` | the desk, alone (tab closed and webhook lost) |

Settings: `STRIPE_SECRET_KEY` (a restricted key with Checkout Sessions: Write is enough) and
`STRIPE_WEBHOOK_SECRET` for an endpoint at `/api/public/pay/stripe/webhook` with the events
`checkout.session.completed`, `checkout.session.expired`, `charge.refunded`,
`charge.dispute.created`. Without both, card checkout stays closed.

Failing closed, as the USDC rail does:

- `DESK_MODE=demo` keeps card checkout closed even with keys set;
- a test key (`sk_test_`/`rk_test_`) opens only outside production and a live key only in
  production, so a test card never buys a real key and a development desk never charges a card;
- the plan, the amount (USD cents) and the session id come from the desk's own row, never
  from the event; a signed event for another session, another amount or another currency
  grants nothing;
- a full refund or a dispute ends the access it bought (the key stops redeeming, the
  workspace drops to Expired); a partial refund is noted and access stays;
- a card invoice keeps its price in cents, and the USDC matcher only reads `usdc_base` rows.

Stripe's Adaptive Pricing may show the buyer a local currency; the session still reports
the USD figure the desk opened (checked in the sandbox on 2026-10-31 with EUR), so the
amount check holds.

### Known duplication

`emberline/backend/app/basepay.py` is where this logic was proven, and it still carries its
own copy (plus the invoice PDF and `/ops` funnel). `desk_kernel.chain` is the generic
extraction. Fix chain bugs in **both** until Emberline is moved onto the kernel layer.
The same holds for card checkout: `emberline/backend/app/card.py` is a port of
`service/card.py` onto Emberline's models; a card bug fixed in one is open in the other.

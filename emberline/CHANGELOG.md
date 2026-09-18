# Changelog

All notable changes to Emberline are documented here.

## Unreleased

- Removed Google Analytics from the public web app.
- A USDC transfer that lands after the invoice quote lapses now still settles,
  for `PAY_LATE_GRACE_HOURS` (default 24). Before this a slow wallet paid real
  money into the treasury and got nothing back but a manual refund: the scan
  matched only invoices that were still `pending`, and `confirm` refused an
  expired one outright. An invoice inside its grace also keeps its amount
  reserved, so the salt is never handed to a second buyer.
- `confirm` now bounds the transfer to the invoice's own lifetime. It had no
  lower bound at all, so any old treasury transfer with a matching amount could
  be claimed by a fresh invoice through a hand-supplied tx hash.
- `/api/public/pay/status` reports `late_grace_hours`; an invoice reports
  `claimable`, `claim_deadline` and `late`. The invoice page keeps watching the
  chain while an invoice is claimable instead of declaring it dead at the quote
  deadline.

## 0.1.8 — 2026-08-19

### Added

- Public SEO surface: Open Graph image, JSON-LD, `robots.txt`, `sitemap.xml`
- `/press` kit (boilerplate, facts, do/do-not, assets)
- `/sample` as the selling artifact: how to read a brief, dashboard vs Emberline, cite-pack contents
- Outreach templates (five roles) in `docs/outreach/TEMPLATES.md`

### Changed

- Marketing primary CTA is the sample brief; hero no longer leads with Hub list price
- Shared marketing footer includes Press

### Fixed

- Marketing globe stays visible while Blue Marble loads (canvas is no longer `opacity: 0` until texture ready)

## 0.1.7 — 2026-08-19

### Added

- Desk mailbox on the Emberline VPS (`mail/`): maddy IMAP/SMTP for `desk@emberlinedesk.com`. Not an alert channel.

## 0.1.6 — 2026-08-17

### Added

- Operator desk at `/ops`: cross-tenant KPIs, pay→evidence funnel, 30-day charts, every workspace. Auth is `OPS_SECRET` or `PAY_MINT_SECRET` (cookie or `X-Emberline-Ops`)

## 0.1.5 — 2026-08-17

### Added

- Installable desk PWA (`/desk`) with Web Push for watch alerts
- `GET/POST/DELETE /api/push/*` plus VAPID keys (`VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`)

### Changed

- SMTP stays desk-only (named-seat mail later). Alerts are app UI, PWA push, Slack, or HTTPS webhook — not email

## 0.1.4 — 2026-08-17

### Added

- Canonical public origin `https://emberlinedesk.com` (desk mail `desk@emberlinedesk.com`)

- Unlisted brief share tokens: alerts link to `/b/{token}`; `GET /api/public/briefs/{token}` is `noindex`
- Watch bbox map (Carto/OSM rectangle only) plus `/sample` and `/request` marketing routes
- Fixture rails banner; sample brief watermark; status shows `hub_mode` and `pay_mode` separately

### Changed

- Email is not a delivery channel (API 400 if `email_to` is set)
- Landing CTA is “sample brief”, not “live brief”; pricing primary CTA is request a desk key
- Webhook secret stays on screen until Continue (copy button)

## 0.1.3 — 2026-08-16

### Added

- Public USDC-on-Base checkout: unique-amount invoices, log watcher, wallet send, `tx_hash` confirm, desk key on settle

## 0.1.2 — 2026-08-16

### Added

- Run-to-run delta on every brief (`emberline.run_delta@v1`): LIVE count, appeared / disappeared / brightened / dimmed
- Cite pack ZIP: cover PDF, brief, delta, receipt, raw Hub payloads, SHA256SUMS (same brief → same bytes)

## 0.1.1 — 2026-08-16

### Added

- Enterprise documentation pack (`docs/enterprise/`, served at `/docs/enterprise/`)
- Prepaid desk keys: `POST /api/pay/mint`, `POST /api/auth/redeem`
- HttpOnly session cookie, login rate limit, production boot guards
- Webhook SSRF allowlist (https + public DNS), timestamped HMAC
- Quiet hours honored for alerts; monthly run quota; scheduler locks
- Ed25519 receipt verification flag on briefs

### Changed

- Default compose no longer publishes Postgres or API ports
- `HUB_MODE=live` requires `HUB_API_KEY` or a complete Hub payment channel (no silent sandbox visitor)
- Email delivery logs failure until SMTP exists
- OpenAPI disabled when `APP_ENV=production`

## 0.1.0 — 2026-08-16

### Added

- Independent Fire Evidence Desk (watches, run engine, briefs, archive, billing meter)
- Fail-closed LIVE vs SIM brief builder
- Fixture Hub client plus live `atlas.fire.weather@v1` / `atlas.watchbox.check@v1` path
- Marketing site with 3D watch-box globe and sample brief
- Docker Compose (Postgres, API, nginx web)
- Pytest + Vitest + GitHub Actions CI

# HTTP API

Base path `/api`. Browser sessions send the `emberline_session` cookie. API clients may send `Authorization: Bearer <jwt>`.

Production hides `/docs` and `/openapi.json`.

## Public

| Method | Path | Notes |
|---|---|---|
| GET | `/public/health` | liveness; `hub_mode`, `pay_mode` |
| GET | `/public/status` | product claims; does **not** invoke Hub |
| GET | `/public/sample-brief` | marketing fixture |
| GET | `/public/briefs/{token}` | unlisted share (`noindex`); token ≠ brief id |
| GET | `/public/sample-cite-pack` | sample ZIP for intake |
| GET | `/public/pay/status` | USDC Base rail (enabled, treasury, plans) |
| POST | `/public/pay/orders` | `{plan, payment_method}` → invoice. Only `usdc_base` is open |
| POST | `/public/pay/invoices` | same as orders |
| GET | `/public/pay/invoices/{id}` | bill JSON; `desk_key` when paid |
| GET | `/public/pay/invoices/{id}/pdf` | printable invoice |
| POST | `/public/pay/invoices/{id}/confirm` | `{tx_hash}` verify on-chain now |

## Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | `{email,password}` → token + cookie. Rate-limited per IP. |
| POST | `/auth/redeem` | `{desk_key}` → token + cookie |
| POST | `/auth/logout` | clears cookie |
| GET | `/auth/me` | session |

## Desk

| Method | Path | Auth |
|---|---|---|
| GET/POST | `/watches` | list / create (owner, analyst) |
| GET/PATCH | `/watches/{id}` | workspace scoped |
| POST | `/watches/{id}/run` | 402 on monthly quota |
| GET | `/watches/{id}/runs` | last 100 |
| GET | `/archive` | |
| GET | `/briefs/{id}` | normalized brief |
| GET | `/briefs/{id}/raw` | brief + raw Hub payloads |
| GET | `/briefs/{id}/cite-pack` | ZIP: PDF cover, JSON, raw, SHA256SUMS |
| GET | `/public/sample-cite-pack` | marketing sample pack |
| GET | `/billing/usage` | meter |
| GET | `/push/status` | `{enabled, public_key, subscribed}` — VAPID public key for Web Push |
| POST | `/push/subscribe` | `{endpoint, keys:{p256dh,auth}}` |
| DELETE | `/push/subscribe` | same body; drops this device |

Create response includes `webhook_secret` once. Later GETs expose `has_webhook_secret` only. Non-empty `email_to` on create/patch returns **400** (`email delivery is not available`). Alert links use `/b/{share_token}`, not `/briefs/{id}`. Desk push opens `/briefs/{id}` for a signed-in session.

## Pay (operator)

| Method | Path | Auth |
|---|---|---|
| GET | `/pay/status` | whether mint is configured |
| POST | `/pay/mint` | header `X-Emberline-Mint` |

Mint body: `{plan, days, payment_ref}`. Returns `{desk_key, grant_id, expires_at}` once.

## Ops (operator)

Not a desk seat. Do not link this from marketing.

| Method | Path | Auth |
|---|---|---|
| POST | `/ops/login` | `{secret}` → HttpOnly `emberline_ops` cookie. Rate-limited. Secret is `OPS_SECRET` or `PAY_MINT_SECRET` |
| POST | `/ops/logout` | clears cookie |
| GET | `/ops/me` | cookie or `X-Emberline-Ops` / `X-Emberline-Mint` |
| GET | `/ops/dashboard` | KPIs, funnel, 30d series, workspaces, recent runs/invoices. Never returns desk keys |

UI: `/ops`.

# Operations runbook

## Desk mail

`desk@emberlinedesk.com` is a mailbox on Metis (`/opt/mail`, maddy). IMAP 993 / SMTP 587. Secret file `/opt/mail/CREDENTIALS`. Runbook and Timeweb DNS: `mail/README.md`. Not on Attested Memory.

This is not an alert channel.

## Health

- Local: `GET http://localhost:8080/`
- Production: `GET https://emberlinedesk.com/`
- API (from inside the api container): `GET /api/public/health`

If the API container restarts in a loop, read logs for `JWT_SECRET must be set` or `SEED_DEMO must be false`.

## Scheduler

A background job ticks every 5 minutes. A process lock plus Postgres advisory lock `87421001` prevent double Hub spend if two workers start.

Failed Hub invokes mark the run `failed` and do not write a brief.

Quota exhaustion is skipped on the scheduler and returned as HTTP 402 on manual run.

## USDC on Base

Rail is off until `PAY_BASE_ADDRESS` is set. RPC is built-in: `https://mainnet.base.org` plus public backups (publicnode, 1rpc, drpc, tenderly). The watcher fails over on timeout/HTTP/JSON-RPC error and sticks to the last healthy endpoint. Optional `PAY_BASE_RPC_URL` (comma-separated) is tried first. The API never holds a private key.

- Watcher: every 20s, advisory lock `87421002`, lookback ~2200 blocks, settle after `PAY_BASE_CONFIRMATIONS`.
- Local compose uses `PAY_MODE=fixture`: `/pay` issues a real invoice, **Simulate USDC (test rail)** injects a matching Transfer and mints a desk key. Production overlay forbids fixture and requires a live RPC + treasury.
- Unique amount collisions: 9999 pending slots per price tier. Expire after 45 minutes.
- If a buyer sent the wrong amount, do not “fix it up.” Open a new invoice or mint manually with `PAY_MINT_SECRET`.
- Treasury sweep is an operator wallet action, not a product feature.

## Spend control

Live mode costs about $0.02 per watchbox and $0.08 per fire.weather. Prefer `on_match`. Watch `GET /api/billing/usage` `cogs_usd`.

If Hub is unreachable, runs fail closed. Emberline will not fill from SIM.

## Operator dashboard

`https://emberlinedesk.com/ops` (local: `http://localhost:8080/ops`). Sign in with `OPS_SECRET`, or `PAY_MINT_SECRET` if ops secret is empty. Desk JWT is not enough.

The page shows every workspace, the pay→redeem→watch→run→alert funnel, 30-day run/invoice series, Hub COGS, and delivery logs. It does not invent perimeters and does not expose desk keys.

## Alerts failing

1. Confirm the URL is https and public (`UnsafeWebhook` in delivery log).
2. Confirm the consumer checks `t=,v1=` HMAC.
3. Email is not an alert channel. SMTP is desk-only (named-seat mail later), not marketing.
4. Desk push: install the PWA, then **Enable desk push** on `/desk`. Slack and HTTPS webhooks still work.
5. Quiet hours suppress delivery; look for channel `quiet`.

## Key rotation

- `JWT_SECRET` — all sessions die; users sign in again.
- `PAY_MINT_SECRET` — old mint header stops working; existing desk keys still redeem. `/ops` sessions that used this secret as the login also die if `OPS_SECRET` is unset.
- `OPS_SECRET` — ops login only; mint still uses `PAY_MINT_SECRET`. Empty means ops uses the mint secret.
- `VAPID_PRIVATE_KEY` — existing desk push subscriptions stop; users tap Enable desk push again.
- Watch webhook secret — create a new watch or extend the API later; MVP does not rotate in place.

## Backup

Snapshot Docker volume `emberline_pg`. The archive **is** the product. Losing it loses citeable history.

## Incidents you must not create

Do not “helpfully” draw a perimeter during an outage. Publish `no_live_evidence` or nothing.

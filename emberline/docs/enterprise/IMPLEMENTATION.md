# Implementation guide

## 1. Topology

```
Browser  →  nginx :8080  →  FastAPI (internal)  →  Postgres (internal)
                              ↓
                         AIMarket Hub (live) or fixtures
```

Do not publish Postgres or the API port on the host. The web container proxies `/api/`.

## 2. Local demo

```bash
cp .env.example .env
make up
# http://localhost:8080
```

Default compose uses `APP_ENV=development` and `SEED_DEMO=true`. Demo login exists only in that mode: `owner@emberlinedesk.com` / `emberline-demo`.

Debug ports (never production):

```bash
docker compose -f docker-compose.yml -f docker-compose.debug.yml up --build
```

## 3. Production

Required environment:

| Variable | Rule |
|---|---|
| `APP_ENV=production` | Enables runtime safety checks |
| `JWT_SECRET` | Non-default, long random |
| `POSTGRES_PASSWORD` | Not `emberline` |
| `SEED_DEMO=false` | Process refuses to boot if true |
| `HUB_MODE=live` | Requires `HUB_API_KEY` or a complete Hub payment-channel pair |
| `HUB_PAYMENT_CHANNEL` / `HUB_PAYMENT_CHANNEL_SECRET` | Preferred channel rail; both values are required together |
| `PAY_MINT_SECRET` | Mints prepaid desk keys |
| `PAY_BASE_ADDRESS` | Treasury that receives USDC (watch-only). Enables the rail. |
| `PAY_BASE_RPC_URL` | Optional extra Base RPCs, comma-separated; built-in backups always follow |
| `PUBLIC_URL` | Public origin for unlisted alert links (`/b/{token}`). Canon: `https://emberlinedesk.com` |
| `CORS_ORIGINS` | Exact browser origins. Canon: `https://emberlinedesk.com` |
| `COOKIE_SECURE=true` | HTTPS cookies |
| `OPS_SECRET` | Optional. Unlocks `/ops`. Empty = `PAY_MINT_SECRET` |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Web Push for the installed desk. Empty = install still works, push is off |

```bash
export JWT_SECRET=... POSTGRES_PASSWORD=... PAY_MINT_SECRET=...
export HUB_PAYMENT_CHANNEL=... HUB_PAYMENT_CHANNEL_SECRET=...
export PUBLIC_URL=https://emberlinedesk.com
export CORS_ORIGINS=https://emberlinedesk.com
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Production boot **fails closed** if the JWT secret is the repo default, demo seed is on, or the database URL still has `emberline:emberline`.

Put TLS in front of nginx (Caddy, Traefik, or a load balancer). Session cookie is `HttpOnly`, `SameSite=Lax`, `Secure` in production.

## 4. Hub modes

| Mode | Behavior |
|---|---|
| `fixture` | Signed snapshot fixtures. No Hub spend. Default for demo and CI. |
| `live` | POST `/ai-market/v2/invoke`. **Refuses to start invokes without Hub credit or a complete payment channel.** No silent sandbox visitor. |

## 5. Prepaid desk keys

### USDC on Base (public)

Set `PAY_BASE_ADDRESS` (treasury, watch-only). Token defaults to native USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` on chain `8453`. RPC defaults to `https://mainnet.base.org` plus public backups; the watcher fails over and sticks to the last healthy node. Optional `PAY_BASE_RPC_URL` (comma-separated) is tried first.

1. Buyer opens `/pay?plan=solo` → `POST /api/public/pay/invoices`.
2. Invoice amount is list price plus a unique 1–9999 micro-USDC salt (`49.000123`). That salt **is** the invoice. A rounded `49.00` will not settle.
3. Buyer sends USDC on Base to `PAY_BASE_ADDRESS`, or uses **Pay with wallet** (injected `window.ethereum`, switches to Base, `transfer` on the USDC contract).
4. Watcher scans `Transfer` logs every 20s and waits `PAY_BASE_CONFIRMATIONS` (default 2). Buyer may also `POST .../confirm` with `tx_hash`.
5. Invoice poll returns `desk_key`. Redeem at `/login` or the Pay page **Enter desk**.

No hot key lives in Emberline. Sweep the treasury from your own wallet. Invoices expire in 45 minutes; salts become reusable.

### Manual / wire

```http
POST /api/pay/mint
X-Emberline-Mint: $PAY_MINT_SECRET
{"plan":"solo","days":30,"payment_ref":"INV-2026-014"}
```

Duplicate `payment_ref` returns 409. Expired keys return 410. Do not log the raw key. Store only `key_hash` on the grant (the invoice row keeps the key until redeem so refresh does not lose it).

## 6. Schema

API process runs `create_all` on boot. For this MVP, treat Postgres as owned by the compose stack. Backup the volume `emberline_pg` before upgrades.

## 7. Security checklist before go-live

- [ ] `SEED_DEMO=false`
- [ ] Unique `JWT_SECRET` and `POSTGRES_PASSWORD`
- [ ] No host publish of `:5432` / `:8000`
- [ ] TLS + `COOKIE_SECURE=true`
- [ ] `HUB_MODE=live` only with a real key
- [ ] Webhook URLs https and public (enforced)
- [ ] `PAY_MINT_SECRET` rotated and not in git
- [ ] Slack/HTTPS hooks not enabled on untrusted prepaid seats until you accept that risk
- [ ] `VAPID_*` set if desk push should work; private key mode 600, not in git

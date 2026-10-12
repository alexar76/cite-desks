# Usage guide

Online user guide: [/guide](https://emberlinedesk.com/guide) (English, Spanish, French). This file is the English operator detail.

## Roles

| Role | Can |
|---|---|
| owner / analyst | Create watches, run now, set delivery |
| any signed-in member | Read watches, archive, briefs, billing meter |

There is no self-serve signup. Access is a named password or a prepaid desk key.

## Sign in

- **Password** — email + password. Session is an HttpOnly cookie (24h) plus an access token for API clients.
- **Desk key** — paste `emb_…` once. Creates a Solo (or minted plan) workspace on first redeem.
- **USDC on Base** — Pricing → Pay. Send the **exact** invoice amount. After confirmations, copy the desk key.

Sign out from the desk sidebar.

## Create a watch

1. Desk → new watch.
2. Name the box. Draw it on the map or set west/south/east/north. Max 40° × 30°.
3. Schedule: 15 / 30 / 60 minutes.
4. Policy:
   - `on_match` — cheap watchbox check; buy `fire.weather` only if LIVE hits exist.
   - `always_brief` — always buy `fire.weather`. Demo-friendly, expensive in live mode.
5. Quiet hours optional (`22-06` in the watch timezone). Runs still happen; alerts do not.
6. Delivery optional: Slack webhook, HTTPS HMAC webhook, or desk PWA push. Email delivery is not available. SMTP is desk-only (named-seat mail later), not alerts.
7. **Copy the webhook secret immediately** (copy button). It is shown once, until you continue.

HTTPS and Slack URLs must be `https` and resolve to a public address. Localhost, RFC1918, and link-local are rejected.

## Read a brief

Archive or watch runs → Open. The brief is the citeable object:

- `evidence_status`: `live_evidence` or `no_live_evidence`
- badges and legal strip
- LIVE hotspots only
- receipt panel with `emberline_verified`
- **run delta** versus the previous completed brief on this watch (appeared / disappeared / brightened / dimmed; not a spread model)
- **Download cite pack** — ZIP with cover PDF, `brief.json`, `delta.json`, receipt, raw Hub files, `SHA256SUMS`. Re-download of the same brief is byte-identical. Verify hashes; do not re-draw geometry Emberline did not store.

Do not treat a quiet run as proof of safety. Do not treat a disappeared point as containment.

## Alerts

A run alerts when LIVE count and optional brightness threshold match, and it is not quiet hours.

On-device: install the desk (browser install prompt or Add to Home Screen), then **Enable desk push** in the sidebar. Slack and HTTPS webhooks still work. Email is not a channel.

HTTPS body:

```json
{
  "event": "emberline.alert",
  "brief_id": "brf_…",
  "watch_id": "wat_…",
  "evidence_status": "live_evidence",
  "live_fire_detection_count": 2,
  "link": "https://emberlinedesk.com/b/shr_…"
}
```

Header `X-Emberline-Signature: t=<unix>,v1=<hex>` is HMAC-SHA256 of `{ts}.{body}` with the watch secret.

## Billing meter

`/billing` shows plan, watch/run counts, and Hub COGS. It does not charge a card. Caps:

| Plan | Watches | Runs / calendar month |
|---|---|---|
| Solo | 2 | 200 |
| Team | 10 | 1,000 |
| Desk | 50 | 5,000 |

Over cap, `POST /watches/{id}/run` returns 402.

## What you must not do

- Draw a perimeter from points
- Paste SIM detections into a LIVE brief
- Give every contractor the Hub API key
- Use Emberline as 911 / evacuation / insurance

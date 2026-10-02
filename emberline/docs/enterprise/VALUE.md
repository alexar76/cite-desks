# Value beyond ATLAS

ATLAS / Hub sell **one attested snapshot** (`atlas.watchbox.check@v1`, `atlas.fire.weather@v1`). Emberline is not a reskin of that JSON. It is the **desk that owns a box over time**.

## What Hub already does

- Returns LIVE thermal points and bounded weather for a bbox
- Attaches a receipt (digest + Ed25519 material)
- Distinguishes LIVE from SIM

If you only need a one-off invoke, buy the SKU. You do not need Emberline.

## What Emberline adds

1. **Watch operations.** A named geozone, a human owner, 15/30/60 cadence, quiet hours, `on_match` vs `always_brief`. The unit of work is the box you are responsible for, not a raw API call.
2. **Fail-closed brief.** Empty LIVE becomes `no_live_evidence`. SIM detections never appear on a LIVE brief. Every artifact carries **NOT A PERIMETER / NOT A FORECAST / NOT AN EVACUATION ORDER**. Emberline will not invent a polygon Hub did not give.
3. **Citeable archive.** Each run is stored: brief JSON, raw Hub payloads, COGS, delivery log. Download a **cite pack** (cover PDF + JSON + raw + SHA256SUMS) for intake. The same brief yields the same ZIP bytes.
4. **Run delta.** Versus the prior completed brief on the same watch: LIVE count, appeared / disappeared / brightened / dimmed. Explicitly not a spread model.
5. **Receipt check.** Emberline verifies the Ed25519 material against the digest when present and records `emberline_verified`. It does not pretend a failed check is signed.
6. **Delivery with constraints.** Slack / HTTPS webhooks are https-only, no private IPs, no redirects, HMAC `t=,v1=` with a timestamp. Secrets are shown once at watch create. Email is not an alert channel. Desk PWA push is the on-device channel. Unlisted brief links (`/b/{token}`) are what Slack/webhooks share.
7. **Commercial envelope.** Plans cap watches and monthly runs. Public checkout is USDC on Base (exact micro-amount invoice). Prepaid desk keys (`emb_…`) let someone pay without an email. Wire still mints the same key. Emberline holds the Hub key so every analyst does not.
8. **Independent brand + legal strip.** Powered by ATLAS/GAIA; Emberline does not operate satellites and does not sell insurance.

## Margin thesis

You charge for the desk (schedule, policy, archive, fail-closed language, delivery). You pay Hub COGS on each invoke. You do not charge for invented geometry.

`always_brief` on a 15-minute watch will burn a Team plan. `on_match` is the profitable default.

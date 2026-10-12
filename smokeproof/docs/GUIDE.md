# Smokeproof — user guide

Live: `/guide` (`en`, `es`, `fr`). Host: **USA**. [LOCALES-AND-PLACEMENT.md](../../docs/LOCALES-AND-PLACEMENT.md).

Same core as sibling desks: **point · schedule · file**. There is **no single risk number**.

## Product question

1. Was this pin inside NOAA/NESDIS **HMS smoke**? (exact containment)
2. What does **nearby air** say at the same coordinate? (separate list)

## Limits (honesty)

| Claim | Honesty |
|---|---|
| HMS geography | **North America only.** Outside the inventory the SKU refuses — not a global smoke product. |
| HMS density | Qualitative polygon. **Not** measured PM2.5. **Not** a fire perimeter. |
| Nearby air | Modeled **Open-Meteo** grid at the pin (via `atlas.smoke.operations@v1`). **Not** a regulatory station. Separate from the smoke list. |
| Empty / fail | Upstream empty, truncated HMS, or Hub failure stays **empty / offline**. Readings are **not invented**. **SIM is never LIVE**. |
| Risk | Containment + air are **never** fused into a smoke-risk score. Outside smoke is **not** all-clear. |

Cadence is 15 / 30 / 60 minutes. Watch is a **point**. SKU: `atlas.smoke.operations@v1`.

Development seed: `owner@smokeproofdesk.com` / `smokeproof-demo`.

## Buy access

Pick a plan on the desk page. Smokeproof quotes a **unique USDC amount** on Base — the cents are the invoice reference, so send the amount exactly; a rounded transfer identifies no invoice and will not settle.

Nobody approves anything. The desk watches its own treasury, and once your transfer clears the confirmation depth it mints a `smp_` desk key, shows it on the invoice page, and signs that page in. Paste the transaction hash into **Confirm now** to settle without waiting for the next poll.

The invoice lives at `/pay/<id>`, so a reload resumes the same quote. A transfer that lands after the quote lapses still settles inside the grace window printed on the invoice.

# Solrecord — user guide

Live: `/guide` (`en`, `es`, `de`). Host: **USA**. [LOCALES-AND-PLACEMENT.md](../../docs/LOCALES-AND-PLACEMENT.md).

Solrecord watches one plant pin. Cadence is daily (optional 12h). It buys `atlas.pv.irradiance.record@v1`.

The POWER grid cell is not a pyranometer on the rack. CAMS is modelled composition, not soiling on the modules. `record_kind` is `retrospective_record_of_fact`. Quiet is not a performance guarantee.

Development seed: `owner@solrecorddesk.com` / `solrecord-demo`.

## Buy access

Pick a plan on the desk page. Solrecord quotes a **unique USDC amount** on Base — the cents are the invoice reference, so send the amount exactly; a rounded transfer identifies no invoice and will not settle.

Nobody approves anything. The desk watches its own treasury, and once your transfer clears the confirmation depth it mints a `sol_` desk key, shows it on the invoice page, and signs that page in. Paste the transaction hash into **Confirm now** to settle without waiting for the next poll.

The invoice lives at `/pay/<id>`, so a reload resumes the same quote. A transfer that lands after the quote lapses still settles inside the grace window printed on the invoice.

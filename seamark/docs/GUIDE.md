# Seamark — user guide

Live: `/guide` (`en`, `fi`, `nb`). Host: **Netherlands**. [LOCALES-AND-PLACEMENT.md](../../docs/LOCALES-AND-PLACEMENT.md).

Seamark watches a named coastal box. Finnish AIS (Fintraffic, CC BY 4.0) and Norwegian AIS (Kystverket / BarentsWatch, NLOD 2.0) are **two lists**.

A bbox outside Finnish or Norwegian licensed waters is refused. Swedish UI is omitted on purpose: licensed waters are FI and NO, not Sweden.

Development seed: `owner@seamarkdesk.com` / `seamark-demo`.

## Buy access

Pick a plan on the desk page. Seamark quotes a **unique USDC amount** on Base — the cents are the invoice reference, so send the amount exactly; a rounded transfer identifies no invoice and will not settle.

Nobody approves anything. The desk watches its own treasury, and once your transfer clears the confirmation depth it mints a `smk_` desk key, shows it on the invoice page, and signs that page in. Paste the transaction hash into **Confirm now** to settle without waiting for the next poll.

The invoice lives at `/pay/<id>`, so a reload resumes the same quote. A transfer that lands after the quote lapses still settles inside the grace window printed on the invoice.

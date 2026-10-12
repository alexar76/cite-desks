# Plinth — user guide

Canonical operator guide. Other languages (`es`, `de`) are served live at `/guide?lang=es`. Policy: [LOCALES-AND-PLACEMENT.md](../../docs/LOCALES-AND-PLACEMENT.md).

## What this desk is

Plinth is a named-site nowcast. It purchases Hub SKUs (`atlas.situation.brief@v1` with preset `campus`) and archives a brief. It is not a BMS, not a First Street index, not a fire perimeter, not a flood model, and not an insurer.

Weather is a public nowcast, not a roof station. Air is a public network reading, not indoor IAQ. Flood warnings and river gauges, if present, stay in two lists. Grid is a public reading. Never a campus risk score.

## Sign in

Named seats use email and password. Prepaid access is self-serve: buy a desk key with USDC on Base (below).

Development seed (never production): `owner@plinthdesk.com` / `plinth-demo`.

## Buy access

Pick a plan on the desk page. Plinth quotes a **unique USDC amount** on Base — the cents are the invoice reference, so send the amount exactly; a rounded transfer identifies no invoice and will not settle.

Nobody approves anything. The desk watches its own treasury, and once your transfer clears the confirmation depth it mints a `pln_` desk key, shows it on the invoice page, and signs that page in. Impatient? Paste the transaction hash into **Confirm now** instead of waiting for the next poll.

The invoice lives at `/pay/<id>`, so a reload or a return from your wallet resumes the same quote. A transfer that lands after the quote lapses still settles inside the grace window printed on the invoice.

## Create a site

Name the site. Set west/south/east/north. Max span is **1° × 1°** — a campus or colo, not a state. Default cadence is 60 minutes. Default policy is `always_brief`.

The engine sends ATLAS preset `campus` and does **not** also send `layers`. A fire pin in the box is not this desk's job (that is Emberline).

## Read a brief

`evidence_status` is `live_evidence` or `no_live_evidence`. Empty LIVE is not all-clear.

The brief keeps weather, air, warnings, gauges, and grid in separate lists. Download the cite pack (PDF, JSON, SHA256). Do not merge them.

## Alerts

HTTPS webhooks must be https and public. HMAC header `X-Plinth-Signature` is `t=<unix>,v1=<hex>` of `{ts}.{body}`.

Email is not an alert channel.

## Where it runs

USA host. Colo and campus buyers are US-weighted (Ashburn, Northern Virginia, university EHS). DACH and LatAm sites still use this origin. Not a Rhine flood box.

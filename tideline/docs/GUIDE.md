# Tideline — user guide

Canonical operator guide. Other languages (nl/fr/de) are served live at `/guide?lang=nl` (and `fr`, `de`). Policy: [LOCALES-AND-PLACEMENT.md](../../docs/LOCALES-AND-PLACEMENT.md).

## What this desk is

Tideline is a named-basin monitor. It purchases Hub SKUs and archives a brief. It is not a flood model, not Floodbase, not an evacuation authority, and not an all-clear.

A CAP or agency warning is a warning product. A river gauge is an in-situ stage. They stay in two lists.

## Sign in

Named seats use email and password. Prepaid access is self-serve: buy a desk key with USDC on Base (below).

Development seed (never production): `owner@tidelinedesk.com` / `tideline-demo`.

## Buy access

Pick a plan on the desk page. Tideline quotes a **unique USDC amount** on Base — the cents are the invoice reference, so send the amount exactly; a rounded transfer identifies no invoice and will not settle.

Nobody approves anything. The desk watches its own treasury, and once your transfer clears the confirmation depth it mints a `tdl_` desk key, shows it on the invoice page, and signs that page in. Impatient? Paste the transaction hash into **Confirm now** instead of waiting for the next poll.

The invoice lives at `/pay/<id>`, so a reload or a return from your wallet resumes the same quote. A transfer that lands after the quote lapses still settles inside the grace window printed on the invoice.

## Create a watch

Name the basin. Set west/south/east/north. Schedule 15 / 30 / 60 minutes.

`on_match` buys the cheap watchbox first and the situation brief only if LIVE hits exist. `always_brief` always buys the brief — expensive in live Hub mode.

## Read a brief

`evidence_status` is `live_evidence` or `no_live_evidence`. Empty LIVE is not all-clear.

Download the cite pack (PDF, JSON, SHA256). Do not merge the warning list with the gauge list.

## Alerts

HTTPS webhooks must be https and public. HMAC header `X-Tideline-Signature` is `t=<unix>,v1=<hex>` of `{ts}.{body}`.

Email is not an alert channel.

## Where it runs

Netherlands host. Rhine/RWS, Hub'Eau, eHYD, and EA are EEA evidence. US CAP still works from Amsterdam. GDPR stays in the Union.

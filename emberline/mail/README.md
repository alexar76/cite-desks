# Desk mail (`desk@emberlinedesk.com`)

Lightweight **maddy** on the **Metis** demo host. IMAP inbox for the desk address. Not an Emberline alert channel (alerts stay in the app, PWA push, Slack, HMAC). Not on the Attested Memory box.

RAM cap 192 MB. Compose is `/opt/mail` on Metis, separate from Metis cognition so a mail restart does not bounce `metis-nginx`.

## Client (after MX is switched)

| | |
|---|---|
| Address | `desk@emberlinedesk.com` |
| IMAP | `emberlinedesk.com:993` SSL |
| SMTP | `emberlinedesk.com:587` STARTTLS (or `:465` SSL) |
| Username | `desk@emberlinedesk.com` |

Password lives only on the host: `/opt/mail/CREDENTIALS` (mode 600).

## Timeweb DNS (required)

Panel → domain `emberlinedesk.com` → DNS.

Delete:

- MX `mx1.timeweb.ru` / `mx2.timeweb.ru`
- TXT `v=spf1 include:_spf.timeweb.ru ~all`

Replace the old Attested SPF `ip4` and DKIM TXT. Paste the Metis host IPv4 into A + SPF, and the Metis DKIM public key — the attested selector will not verify mail signed here. Live A/AAAA and SPF live in DNS, not in this repo.

```
emberlinedesk.com.          A     <Metis IPv4>
emberlinedesk.com.          MX    10  emberlinedesk.com.
emberlinedesk.com.          TXT       "v=spf1 ip4:<Metis IPv4> mx -all"
_dmarc.emberlinedesk.com.   TXT       "v=DMARC1; p=quarantine; rua=mailto:desk@emberlinedesk.com"
default._domainkey.emberlinedesk.com.  TXT   <paste from /opt/mail/data/dkim_keys/emberlinedesk.com_default.dns>
```

Family landing (domain `modelmarket.dev`, same Metis A):

```
desks.modelmarket.dev.     A     <Metis IPv4>
```

TTL 300 until it works, then 3600.

## Outbound

Inbound: TCP 25/465/587/993 are open (measured from the public internet: SMTP banner `emberlinedesk.com ESMTP`). Outbound TCP 25 is blocked by the provider (`Connection refused` to Gmail MX). Inbox works. Sending to Gmail/etc. needs a smarthost or an unblock.

## Host commands

```bash
cd /opt/mail && docker compose up -d
docker exec -it emberline-mail maddy imap-acct list
docker logs --tail 80 emberline-mail
```

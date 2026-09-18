# Security policy

## Supported versions

The `main` branch is the supported surface for this MVP.

## Reporting

Please **do not** open a public issue for vulnerabilities. Email [desk@emberlinedesk.com](mailto:desk@emberlinedesk.com).

Include:

- affected endpoint or component
- reproduction without exploit payloads against third-party systems
- impact (auth bypass, receipt tampering, SIM/LIVE confusion, SSRF)

## Production requirements

The API process refuses to boot in `APP_ENV=production` when:

- `JWT_SECRET` is missing or still the repository default
- `SEED_DEMO` is true
- `DATABASE_URL` still uses `emberline:emberline`

`HUB_MODE=live` refuses invokes unless either `HUB_API_KEY` or both
`HUB_PAYMENT_CHANNEL` and `HUB_PAYMENT_CHANNEL_SECRET` are configured. A Hub
API key is sent only as `X-API-Key`; provider origins never receive it directly
when a central Hub is configured. Outbound webhooks must be https and must not
resolve to private or link-local addresses. OpenAPI is disabled in production.

## Product notes

Emberline stores raw Hub responses, briefs, and delivery logs. Prepaid desk keys are stored as SHA-256 hashes. A paid Base invoice keeps the raw desk key on that invoice row so refresh does not lose it; treat invoice ids as secrets. The treasury key never enters the API — only `PAY_BASE_ADDRESS` and an RPC URL. Webhook HMAC secrets are shown once at watch create. Rotate `JWT_SECRET`, `PAY_MINT_SECRET`, and database passwords in production.

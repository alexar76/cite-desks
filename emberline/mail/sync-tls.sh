#!/bin/sh
# Copy the live Emberline cert into maddy. Called from certbot deploy hook.
set -eu
SRC=/var/lib/metis/letsencrypt/live/emberlinedesk.com
DST=/opt/mail/data/tls
mkdir -p "$DST"
cp -L "$SRC/fullchain.pem" "$DST/fullchain.pem"
cp -L "$SRC/privkey.pem" "$DST/privkey.pem"
chmod 644 "$DST/fullchain.pem"
chmod 644 "$DST/privkey.pem"
if docker ps --format '{{.Names}}' | grep -q '^emberline-mail$'; then
  docker kill -s USR2 emberline-mail >/dev/null 2>&1 || docker restart emberline-mail >/dev/null
fi

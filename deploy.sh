#!/usr/bin/env bash
# Deploy one cite-desk from this family tree.
# Emberline keeps its own compose (fire UI). Siblings share kernel + web shell.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DESKS=(emberline tideline solrecord seamark plinth)

usage() {
  cat <<EOF
Usage: $0 <desk> [--build] [--prod]
       $0 --list
       $0 --test

Desks: ${DESKS[*]}
EOF
}

if [[ "${1:-}" == "--list" ]]; then
  printf '%s\n' "${DESKS[@]}"
  exit 0
fi

if [[ "${1:-}" == "--test" ]]; then
  cd "$ROOT/kernel"
  python -m pip install -e ".[dev]" -q
  python -m pytest
  exit 0
fi

DESK="${1:-}"
if [[ -z "$DESK" || "$DESK" == "-h" || "$DESK" == "--help" ]]; then
  usage
  exit 1
fi
shift || true

found=0
for d in "${DESKS[@]}"; do
  if [[ "$d" == "$DESK" ]]; then found=1; fi
done
if [[ "$found" -ne 1 ]]; then
  echo "unknown desk: $DESK" >&2
  usage
  exit 1
fi

BUILD=0
PROD=0
for arg in "$@"; do
  case "$arg" in
    --build) BUILD=1 ;;
    --prod) PROD=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 1 ;;
  esac
done

# A desk retired on this host leaves `<desk>.off-<stamp>` beside it. A repo sync restores
# the sources, so the folder existing is not consent to run it: a second copy of a live
# desk would serve its own database while DNS points at the real one.
retired=("$ROOT/$DESK".off-*)
if [[ -e "${retired[0]}" ]]; then
  echo "$DESK was retired on this host (${retired[0]##*/}); it runs elsewhere." >&2
  echo "Remove that marker if this host is meant to serve it." >&2
  exit 1
fi

cd "$ROOT/$DESK"
files=(-f docker-compose.yml)
if [[ "$PROD" -eq 1 && -f docker-compose.prod.yml ]]; then
  files+=(-f docker-compose.prod.yml)
fi
# A host may keep its own overlay (loopback-only ports when nginx is the public edge).
# It is deliberately not in the repo, and forgetting it here republishes the desk on
# 0.0.0.0 without TLS — so pick it up automatically wherever this runs.
if [[ -f docker-compose.host.yml ]]; then
  files+=(-f docker-compose.host.yml)
  echo "using host overlay: $DESK/docker-compose.host.yml"
fi
# Metis public-demo overlay (DESK_MODE=demo, metisnet for metis-nginx). Prefer over a
# bare compose when present and --prod was not requested.
if [[ "$PROD" -eq 0 && -f docker-compose.metis.yml ]]; then
  files+=(-f docker-compose.metis.yml)
  echo "using metis overlay: $DESK/docker-compose.metis.yml"
fi
args=(up -d)
if [[ "$BUILD" -eq 1 ]]; then
  args=(up --build -d)
fi
docker compose "${files[@]}" "${args[@]}"

# A desk that boots but cannot settle sells nothing, and the only symptom is a 503 on the
# buyer's side plus a warning nobody reads. Ask it directly.
if ! docker compose "${files[@]}" exec -T api python - <<'PY'
import json
import sys
import urllib.request

health = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/public/health"))
rail = health.get("checkout") or {}
scan = rail.get("last_scan") or {}
print("checkout: open=%s settlement=%s last_scan_age=%s %s" % (
    rail.get("open"), rail.get("settlement"), scan.get("age_seconds"), rail.get("reason") or ""))
sys.exit(0 if rail.get("open") and rail.get("settlement") == "scheduled" else 1)
PY
then
  echo "!! $DESK cannot take money unattended right now — fix the reason above" >&2
fi

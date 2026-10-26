#!/bin/sh
# On first start the data volume is empty. Seed it with the real weekly series shipped in the image so
# `python -m ml weekly --no-download` works straight away. Existing files are never overwritten.
set -e
SEED=/repo/seed/v2
DATA=/repo/data/v2
if [ -d "$SEED" ]; then
  mkdir -p "$DATA"
  cp -rn "$SEED"/. "$DATA"/ 2>/dev/null || true
fi
exec "$@"
